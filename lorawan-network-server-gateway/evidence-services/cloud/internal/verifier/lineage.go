package verifier

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"math"
	"strconv"
	"strings"

	"lorawan/evidence-services/cloud/internal/mqttcapture"
	"lorawan/evidence-services/cloud/internal/objectstore"
	"lorawan/evidence-services/cloud/internal/uplinkcorrelation"
)

const (
	maxMQTTObjectBytes    int64 = 1 << 20
	maxJournalObjectBytes int64 = 16 << 20
)

var (
	ErrMQTTIntegrity         = errors.New("MQTT evidence object or projection failed integrity checks")
	ErrJournalMissing        = errors.New("journal correlation source is missing")
	ErrJournalAmbiguous      = errors.New("journal correlation source is ambiguous")
	ErrJournalLineagePending = errors.New("journal predecessor lineage is not complete yet")
	ErrJournalIntegrity      = errors.New("journal evidence failed integrity checks")
)

type VerifiedMQTT struct {
	Evidence   MQTTEvidence
	Projection uplinkcorrelation.Projection
}

type JournalMatch struct {
	Segment JournalSegmentMetadata
	Record  verifiedJournalRecord
}

func VerifyMQTTObject(ctx context.Context, store objectstore.Store, app ApplicationEvidence, evidence MQTTEvidence) (VerifiedMQTT, error) {
	if store == nil {
		return VerifiedMQTT{}, errors.New("MQTT object store is required")
	}
	reader, metadata, err := store.Get(ctx, evidence.ObjectRef)
	if err != nil {
		return VerifiedMQTT{}, fmt.Errorf("read MQTT evidence object: %w", err)
	}
	defer reader.Close()
	payload, err := readBounded(reader, maxMQTTObjectBytes)
	if err != nil {
		return VerifiedMQTT{}, fmt.Errorf("read MQTT evidence object bytes: %w", err)
	}
	digest := sha256.Sum256(payload)
	serializedSHA := hex.EncodeToString(digest[:])
	if metadata.Ref != evidence.ObjectRef || metadata.SHA256 != serializedSHA ||
		metadata.Size != int64(len(payload)) || evidence.SerializedEventSHA256 != serializedSHA {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	if !validGatewayUplinkTopic(evidence.MQTTTopic, evidence.GatewayID) {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	captureKey, err := mqttcapture.CaptureKey(evidence.MQTTTopic, payload)
	if err != nil || captureKey != evidence.CaptureKeySHA256 {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	projection, err := uplinkcorrelation.DecodeUplinkFrame(payload, evidence.GatewayID)
	if err != nil {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	correlationDigest, err := projection.CorrelationDigest()
	if err != nil {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	contextBase64 := base64.StdEncoding.EncodeToString(projection.GatewayContext)
	uplinkID := strconv.FormatUint(uint64(projection.UplinkID), 10)
	if projection.PHYPayloadSHA256() != evidence.PHYPayloadSHA256 ||
		uplinkID != evidence.UplinkID || int64(projection.FrequencyHz) != evidence.FrequencyHz ||
		projection.RSSIDbm != evidence.RSSIDbm || float64(projection.SNRDb) != evidence.SNRDb ||
		contextBase64 != evidence.GatewayContextBase64 || correlationDigest != evidence.CorrelationDigestSHA256 {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	if !app.HasGatewayProvenance() || evidence.GatewayID != *app.GatewayID ||
		int64(projection.UplinkID) != *app.GatewayUplinkID || int64(projection.FrequencyHz) != *app.GatewayFrequencyHz ||
		contextBase64 != *app.GatewayContextBase64 || projection.RSSIDbm != *app.GatewayRSSIDbm ||
		math.Abs(float64(projection.SNRDb)-*app.GatewaySNRDb) > 1e-6 {
		return VerifiedMQTT{}, ErrMQTTIntegrity
	}
	return VerifiedMQTT{Evidence: evidence, Projection: projection}, nil
}

func FindJournalRecord(ctx context.Context, store objectstore.Store, segments []JournalSegmentMetadata, mqtt VerifiedMQTT) (JournalMatch, error) {
	if store == nil {
		return JournalMatch{}, errors.New("journal object store is required")
	}
	if len(segments) == 0 {
		return JournalMatch{}, ErrJournalMissing
	}
	correlation := mqtt.Evidence.CorrelationDigestSHA256
	if !isLowerHash(correlation) {
		return JournalMatch{}, ErrJournalIntegrity
	}

	var matches []JournalMatch
	for _, segment := range segments {
		if err := ctx.Err(); err != nil {
			return JournalMatch{}, err
		}
		if segment.GatewayID != mqtt.Evidence.GatewayID || segment.SegmentID < 1 ||
			segment.FirstSequence < 1 || segment.LastSequence < segment.FirstSequence || segment.RecordCount < 1 ||
			!isHashOrGenesis(segment.PreviousSegmentHash) || !isLowerHash(segment.FinalRecordHash) ||
			!isLowerHash(segment.SegmentHash) || !isLowerHash(segment.ObjectSHA256) || segment.ObjectRef == "" {
			return JournalMatch{}, ErrJournalIntegrity
		}

		reader, metadata, err := store.Get(ctx, segment.ObjectRef)
		if err != nil {
			return JournalMatch{}, fmt.Errorf("read journal segment %d: %w", segment.SegmentID, err)
		}
		objectBytes, readErr := readBounded(reader, maxJournalObjectBytes)
		closeErr := reader.Close()
		if readErr != nil {
			return JournalMatch{}, fmt.Errorf("read journal segment %d bytes: %w", segment.SegmentID, readErr)
		}
		if closeErr != nil {
			return JournalMatch{}, fmt.Errorf("close journal segment %d: %w", segment.SegmentID, closeErr)
		}
		objectDigest := sha256.Sum256(objectBytes)
		objectSHA := hex.EncodeToString(objectDigest[:])
		if metadata.Ref != segment.ObjectRef || metadata.SHA256 != objectSHA || metadata.Size != int64(len(objectBytes)) || objectSHA != segment.ObjectSHA256 {
			return JournalMatch{}, ErrJournalIntegrity
		}
		if !bytes.Contains(objectBytes, []byte(correlation)) {
			continue
		}

		verified, err := verifyClosedJournalSegment(objectBytes)
		if err != nil {
			return JournalMatch{}, fmt.Errorf("%w: segment %d: %v", ErrJournalIntegrity, segment.SegmentID, err)
		}
		if !segmentMetadataMatchesVerified(segment, verified) {
			return JournalMatch{}, ErrJournalIntegrity
		}
		for _, record := range verified.Records {
			if record.Body.SourceEventSHA256 == nil || *record.Body.SourceEventSHA256 != correlation {
				continue
			}
			if !journalRecordMatchesMQTT(record, mqtt.Projection) {
				return JournalMatch{}, ErrJournalIntegrity
			}
			matches = append(matches, JournalMatch{Segment: segment, Record: record})
		}
	}

	if len(matches) == 0 {
		return JournalMatch{}, ErrJournalMissing
	}
	if len(matches) != 1 {
		return JournalMatch{}, ErrJournalAmbiguous
	}
	if err := validateJournalObjectLineage(ctx, store, segments, matches[0]); err != nil {
		return JournalMatch{}, err
	}
	return matches[0], nil
}

func segmentMetadataMatchesVerified(meta JournalSegmentMetadata, verified verifiedJournalSegment) bool {
	return verified.Header.GatewayID == meta.GatewayID && verified.Header.SegmentID == meta.SegmentID &&
		verified.Header.FirstSequence == meta.FirstSequence && verified.Header.PreviousSegmentHash == meta.PreviousSegmentHash &&
		verified.Footer.LastSequence == meta.LastSequence && verified.Footer.RecordCount == meta.RecordCount &&
		verified.Footer.FinalRecordHash == meta.FinalRecordHash && verified.Footer.SegmentHash == meta.SegmentHash &&
		verified.ObjectSHA256 == meta.ObjectSHA256
}

func validateJournalObjectLineage(ctx context.Context, store objectstore.Store, segments []JournalSegmentMetadata, match JournalMatch) error {
	byID := make(map[int64]JournalSegmentMetadata, len(segments))
	for _, segment := range segments {
		if _, exists := byID[segment.SegmentID]; exists {
			return ErrJournalIntegrity
		}
		byID[segment.SegmentID] = segment
	}

	var previous *verifiedJournalSegment
	for segmentID := int64(1); segmentID <= match.Segment.SegmentID; segmentID++ {
		if err := ctx.Err(); err != nil {
			return err
		}
		meta, ok := byID[segmentID]
		if !ok {
			return ErrJournalLineagePending
		}
		verified, err := loadVerifiedJournalSegment(ctx, store, meta)
		if err != nil {
			return err
		}
		if len(verified.Records) == 0 {
			return ErrJournalIntegrity
		}
		if segmentID == 1 {
			if verified.Header.FirstSequence != 1 || verified.Header.PreviousSegmentHash != journalGenesis ||
				verified.Records[0].Body.PreviousRecordHash != journalGenesis {
				return ErrJournalIntegrity
			}
		} else {
			if previous == nil || verified.Header.PreviousSegmentHash != previous.Footer.SegmentHash ||
				verified.Header.FirstSequence != previous.Footer.LastSequence+1 ||
				verified.Records[0].Body.PreviousRecordHash != previous.Footer.FinalRecordHash {
				return ErrJournalIntegrity
			}
		}
		copyVerified := verified
		previous = &copyVerified
	}
	return nil
}

func loadVerifiedJournalSegment(ctx context.Context, store objectstore.Store, segment JournalSegmentMetadata) (verifiedJournalSegment, error) {
	reader, metadata, err := store.Get(ctx, segment.ObjectRef)
	if err != nil {
		return verifiedJournalSegment{}, fmt.Errorf("read journal lineage segment %d: %w", segment.SegmentID, err)
	}
	objectBytes, readErr := readBounded(reader, maxJournalObjectBytes)
	closeErr := reader.Close()
	if readErr != nil {
		return verifiedJournalSegment{}, fmt.Errorf("read journal lineage segment %d bytes: %w", segment.SegmentID, readErr)
	}
	if closeErr != nil {
		return verifiedJournalSegment{}, fmt.Errorf("close journal lineage segment %d: %w", segment.SegmentID, closeErr)
	}
	objectDigest := sha256.Sum256(objectBytes)
	objectSHA := hex.EncodeToString(objectDigest[:])
	if metadata.Ref != segment.ObjectRef || metadata.SHA256 != objectSHA || metadata.Size != int64(len(objectBytes)) || objectSHA != segment.ObjectSHA256 {
		return verifiedJournalSegment{}, ErrJournalIntegrity
	}
	verified, err := verifyClosedJournalSegment(objectBytes)
	if err != nil {
		return verifiedJournalSegment{}, fmt.Errorf("%w: lineage segment %d: %v", ErrJournalIntegrity, segment.SegmentID, err)
	}
	if !segmentMetadataMatchesVerified(segment, verified) {
		return verifiedJournalSegment{}, ErrJournalIntegrity
	}
	return verified, nil
}

func journalRecordMatchesMQTT(record verifiedJournalRecord, projection uplinkcorrelation.Projection) bool {
	if record.Body.GatewayID != projection.GatewayID || record.Body.FrequencyHz != int64(projection.FrequencyHz) ||
		record.Body.RSSIDbm != int64(projection.RSSIDbm) || math.Abs(record.SNRDb-float64(projection.SNRDb)) > 1e-6 ||
		record.Body.GatewayContextBase64 == nil {
		return false
	}
	contextBytes, err := decodeCanonicalBase64(*record.Body.GatewayContextBase64, true)
	if err != nil || !bytes.Equal(contextBytes, projection.GatewayContext) {
		return false
	}
	phyPayload, err := decodeCanonicalBase64(record.Body.PHYPayloadBase64, false)
	return err == nil && bytes.Equal(phyPayload, projection.PHYPayload)
}

func validGatewayUplinkTopic(topic, gatewayID string) bool {
	parts := strings.Split(topic, "/")
	return len(parts) == 5 && parts[0] != "" && parts[1] == "gateway" && parts[2] == gatewayID && parts[3] == "event" && parts[4] == "up"
}

func readBounded(reader io.Reader, maxBytes int64) ([]byte, error) {
	if reader == nil || maxBytes < 1 {
		return nil, errors.New("reader and positive byte limit are required")
	}
	data, err := io.ReadAll(io.LimitReader(reader, maxBytes+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > maxBytes {
		return nil, errors.New("evidence object exceeds verifier byte limit")
	}
	return data, nil
}
