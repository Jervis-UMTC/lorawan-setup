package fabricadapter

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"time"
)

var euiPattern = regexp.MustCompile(`^[0-9a-f]{16}$`)

func BuildEvidence(work OutboxWork, source SourceRow, verification *VerificationRow) (Evidence, error) {
	if work.EventKey == "" || work.SourceEventKey == "" || work.EventType == "" {
		return Evidence{}, errors.New("Fabric outbox source identity is incomplete")
	}
	if work.EventType != EventTypeUplink {
		return Evidence{}, fmt.Errorf("unsupported Fabric event type %q", work.EventType)
	}
	if !euiPattern.MatchString(source.DevEUI) {
		return Evidence{}, errors.New("source DevEUI is not canonical lowercase 16-hex")
	}
	if source.RawDataBase64 != nil {
		decoded, err := base64.StdEncoding.Strict().DecodeString(*source.RawDataBase64)
		if err != nil || base64.StdEncoding.EncodeToString(decoded) != *source.RawDataBase64 {
			return Evidence{}, errors.New("stored application raw_data is not canonical Base64")
		}
	}
	if !json.Valid(source.PayloadJSON) {
		return Evidence{}, errors.New("stored payload_json is invalid JSON")
	}

	evidence := Evidence{
		SchemaVersion:  work.SchemaVersion,
		EventKey:       work.EventKey,
		SourceEventKey: work.SourceEventKey,
		EventType:      work.EventType,
		Source: SourceEvidence{
			NetworkServer: "chirpstack",
			ApplicationID: source.ApplicationID,
			DeviceID:      source.DeviceID,
			DeviceModel:   source.DeviceModel,
			DevEUI:        source.DevEUI,
			GatewayID:     source.GatewayID,
			Region:        source.Region,
		},
		LoRaWAN: LoRaWANEvidence{
			FPort:     source.FPort,
			FCnt:      source.FCnt,
			Confirmed: source.Confirmed,
		},
		Observation: ObservationEvidence{
			ObservedAt: formatEvidenceTime(work.ObservedAt),
			ReceivedAt: formatEvidenceTime(source.ReceivedAt),
		},
		Payload: PayloadEvidence{
			RawDataBase64:  source.RawDataBase64,
			DecodedPayload: json.RawMessage(append([]byte(nil), source.PayloadJSON...)),
			DecoderVersion: source.DecoderVersion,
		},
	}

	switch work.SchemaVersion {
	case SchemaVersionV1:
		if verification != nil {
			return Evidence{}, errors.New("v1 evidence must not be supplied gateway verification")
		}
	case SchemaVersionV2:
		if verification == nil {
			return Evidence{}, ErrVerificationMissing
		}
		if verification.Status != "verified" {
			return Evidence{}, fmt.Errorf("gateway verification status is %q, not verified", verification.Status)
		}
		if source.GatewayID == nil || *source.GatewayID != verification.GatewayID {
			return Evidence{}, errors.New("source gateway_id does not match verified gateway lineage")
		}
		evidence.GatewayEvidence = &GatewayEvidence{
			Status:                 verification.Status,
			VerificationID:         verification.VerificationID,
			GatewayID:              verification.GatewayID,
			JournalSegmentID:       verification.JournalSegmentID,
			JournalSequence:        verification.JournalSequence,
			JournalRecordHash:      verification.JournalRecordHash,
			JournalSegmentHash:     verification.JournalSegmentHash,
			CheckpointID:           verification.CheckpointID,
			GatewayEventID:         verification.GatewayEventID,
			DecoderID:              verification.DecoderID,
			DecoderVersion:         verification.DecoderVersion,
			RawAppDataSHA256:       verification.RawAppDataSHA256,
			NormalizedDigestSHA256: verification.NormalizedDigestSHA256,
		}
	default:
		return Evidence{}, fmt.Errorf("unsupported Fabric schema version %q", work.SchemaVersion)
	}
	return evidence, nil
}

func formatEvidenceTime(value time.Time) string {
	return value.UTC().Truncate(time.Millisecond).Format("2006-01-02T15:04:05.000Z")
}
