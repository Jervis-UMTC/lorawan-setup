package fabricadapter

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/gowebpki/jcs"
)

const (
	SchemaVersionV1 = "telemetry-attestation-v1"
	SchemaVersionV2 = "telemetry-attestation-v2"
	EventTypeUplink = "lorawan_uplink_accepted"
)

type SourceEvidence struct {
	NetworkServer string  `json:"network_server"`
	ApplicationID *string `json:"application_id"`
	DeviceID      *string `json:"device_id"`
	DeviceModel   *string `json:"device_model"`
	DevEUI        string  `json:"dev_eui"`
	GatewayID     *string `json:"gateway_id"`
	Region        *string `json:"region"`
}

type LoRaWANEvidence struct {
	FPort     *int64 `json:"f_port"`
	FCnt      *int64 `json:"f_cnt"`
	Confirmed *bool  `json:"confirmed"`
}

type ObservationEvidence struct {
	ObservedAt string `json:"observed_at"`
	ReceivedAt string `json:"received_at"`
}

type PayloadEvidence struct {
	RawDataBase64  *string         `json:"raw_data_base64"`
	DecodedPayload json.RawMessage `json:"decoded_payload"`
	DecoderVersion *string         `json:"decoder_version"`
}

type GatewayEvidence struct {
	Status                 string `json:"status"`
	VerificationID         int64  `json:"verification_id"`
	GatewayID              string `json:"gateway_id"`
	JournalSegmentID       int64  `json:"journal_segment_id"`
	JournalSequence        int64  `json:"journal_sequence"`
	JournalRecordHash      string `json:"journal_record_hash"`
	JournalSegmentHash     string `json:"journal_segment_hash"`
	CheckpointID           int64  `json:"checkpoint_id"`
	GatewayEventID         int64  `json:"gateway_event_id"`
	DecoderID              string `json:"decoder_id"`
	DecoderVersion         string `json:"decoder_version"`
	RawAppDataSHA256       string `json:"raw_app_data_sha256"`
	NormalizedDigestSHA256 string `json:"normalized_digest_sha256"`
}

type Evidence struct {
	SchemaVersion   string              `json:"schema_version"`
	EventKey        string              `json:"event_key"`
	SourceEventKey  string              `json:"source_event_key"`
	EventType       string              `json:"event_type"`
	Source          SourceEvidence      `json:"source"`
	LoRaWAN         LoRaWANEvidence     `json:"lorawan"`
	Observation     ObservationEvidence `json:"observation"`
	Payload         PayloadEvidence     `json:"payload"`
	GatewayEvidence *GatewayEvidence    `json:"gateway_evidence,omitempty"`
}

type CanonicalSealInput struct {
	CanonicalJSON []byte
	DigestSHA256  string
}

func CanonicalizeEvidence(evidence Evidence) (CanonicalSealInput, error) {
	if err := validateEvidenceShape(evidence); err != nil {
		return CanonicalSealInput{}, err
	}
	input, err := json.Marshal(evidence)
	if err != nil {
		return CanonicalSealInput{}, fmt.Errorf("marshal evidence input: %w", err)
	}
	canonical, err := jcs.Transform(input)
	if err != nil {
		return CanonicalSealInput{}, fmt.Errorf("RFC8785 canonicalize evidence: %w", err)
	}
	digest := sha256.Sum256(canonical)
	return CanonicalSealInput{
		CanonicalJSON: canonical,
		DigestSHA256:  hex.EncodeToString(digest[:]),
	}, nil
}

func validateEvidenceShape(evidence Evidence) error {
	if evidence.EventType != EventTypeUplink {
		return fmt.Errorf("unsupported Fabric event type %q", evidence.EventType)
	}
	if !json.Valid(evidence.Payload.DecodedPayload) {
		return errors.New("decoded payload is not valid JSON")
	}
	switch evidence.SchemaVersion {
	case SchemaVersionV1:
		if evidence.GatewayEvidence != nil {
			return errors.New("v1 evidence must not contain gateway_evidence")
		}
	case SchemaVersionV2:
		if evidence.GatewayEvidence == nil {
			return errors.New("v2 evidence requires gateway_evidence")
		}
		if evidence.GatewayEvidence.Status != "verified" {
			return fmt.Errorf("v2 gateway evidence status must be verified, got %q", evidence.GatewayEvidence.Status)
		}
		if evidence.Source.GatewayID == nil || *evidence.Source.GatewayID != evidence.GatewayEvidence.GatewayID {
			return errors.New("source gateway_id does not match verifier gateway_id")
		}
	default:
		return fmt.Errorf("unsupported Fabric schema version %q", evidence.SchemaVersion)
	}
	return nil
}
