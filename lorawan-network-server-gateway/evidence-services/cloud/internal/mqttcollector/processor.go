package mqttcollector

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"lorawan/evidence-services/cloud/internal/mqttcapture"
	"lorawan/evidence-services/cloud/internal/objectstore"
	"lorawan/evidence-services/cloud/internal/uplinkcorrelation"
)

var gatewayIDPattern = regexp.MustCompile(`^[0-9a-f]{16}$`)

type Processor struct {
	store      objectstore.Store
	repository Repository
	region     string
}

func NewProcessor(store objectstore.Store, repository Repository, region string) (*Processor, error) {
	if store == nil || repository == nil {
		return nil, errors.New("object store and capture repository are required")
	}
	region = strings.TrimSpace(region)
	if region == "" || strings.Contains(region, "/") {
		return nil, errors.New("MQTT region prefix must be one topic segment")
	}
	return &Processor{store: store, repository: repository, region: region}, nil
}

func (p *Processor) Process(ctx context.Context, observation Observation) (CaptureRecord, bool, error) {
	if err := ctx.Err(); err != nil {
		return CaptureRecord{}, false, err
	}
	if observation.ReceivedAt.IsZero() {
		return CaptureRecord{}, false, errors.New("collector receipt timestamp is required")
	}
	if len(observation.Payload) == 0 {
		return CaptureRecord{}, false, errors.New("MQTT payload is empty")
	}

	gatewayID, eventType, err := gatewayEventFromTopic(observation.Topic, p.region)
	if err != nil {
		return CaptureRecord{}, false, err
	}
	captureKey, err := mqttcapture.CaptureKey(observation.Topic, observation.Payload)
	if err != nil {
		return CaptureRecord{}, false, err
	}
	payloadDigest := sha256.Sum256(observation.Payload)
	serializedSHA := hex.EncodeToString(payloadDigest[:])
	objectRef := fmt.Sprintf("mqtt/%s.event", captureKey)

	putResult, err := p.store.PutIfAbsent(ctx, objectRef, bytes.NewReader(observation.Payload))
	if errors.Is(err, objectstore.ErrConflict) {
		return CaptureRecord{}, false, ErrCaptureConflict
	}
	if err != nil {
		return CaptureRecord{}, false, fmt.Errorf("persist MQTT evidence object: %w", err)
	}
	if putResult.Metadata.SHA256 != serializedSHA || putResult.Metadata.Ref != objectRef {
		return CaptureRecord{}, false, errors.New("persisted MQTT evidence object metadata mismatch")
	}

	record := CaptureRecord{
		GatewayID:             gatewayID,
		MQTTTopic:             observation.Topic,
		BrokerReceivedAt:      observation.ReceivedAt.UTC(),
		CaptureKeySHA256:      captureKey,
		SerializedEventSHA256: serializedSHA,
		CollectorVersion:      CollectorVersion,
		ObjectRef:             objectRef,
	}
	if eventType == "up" {
		projection, err := uplinkcorrelation.DecodeUplinkFrame(observation.Payload, gatewayID)
		if err != nil {
			return CaptureRecord{}, false, fmt.Errorf("decode persisted MQTT uplink evidence %s: %w", objectRef, err)
		}
		correlationDigest, err := projection.CorrelationDigest()
		if err != nil {
			return CaptureRecord{}, false, fmt.Errorf("correlate persisted MQTT uplink evidence %s: %w", objectRef, err)
		}
		record.HasUplinkProjection = true
		record.PHYPayloadSHA256 = projection.PHYPayloadSHA256()
		record.UplinkID = strconv.FormatUint(uint64(projection.UplinkID), 10)
		record.FrequencyHz = int64(projection.FrequencyHz)
		record.RSSIDbm = projection.RSSIDbm
		record.SNRDb = float64(projection.SNRDb)
		record.GatewayContextBase64 = base64.StdEncoding.EncodeToString(projection.GatewayContext)
		record.CorrelationDigestSHA256 = correlationDigest
	}

	created, err := p.repository.PutCapture(ctx, record)
	if errors.Is(err, ErrCaptureConflict) {
		return CaptureRecord{}, false, ErrCaptureConflict
	}
	if err != nil {
		// The immutable object intentionally remains. A later retry converges on it.
		return CaptureRecord{}, false, fmt.Errorf("persist MQTT evidence metadata: %w", err)
	}
	return record, created, nil
}

func gatewayIDFromTopic(topic, region string) (string, error) {
	gatewayID, _, err := gatewayEventFromTopic(topic, region)
	return gatewayID, err
}

func gatewayEventFromTopic(topic, region string) (string, string, error) {
	parts := strings.Split(topic, "/")
	if len(parts) != 5 || parts[0] != region || parts[1] != "gateway" || parts[3] != "event" {
		return "", "", fmt.Errorf("MQTT topic is outside approved gateway event namespace")
	}
	if parts[4] == "" {
		return "", "", fmt.Errorf("MQTT gateway event suffix is empty")
	}
	gatewayID := parts[2]
	if !gatewayIDPattern.MatchString(gatewayID) {
		return "", "", fmt.Errorf("MQTT topic Gateway EUI must be canonical lowercase 16-hex")
	}
	return gatewayID, parts[4], nil
}
