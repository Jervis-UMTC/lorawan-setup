package verifier

import "time"

const (
	SchemaVersionV2           = "telemetry-attestation-v2"
	ExpectedEventType         = "lorawan_uplink_accepted"
	OperationalDecoderVersion = "agriculture-kit-payload-v2-node-red-v1"

	ReasonApplicationSourceMissing    = "application_source_missing"
	ReasonApplicationSourceAmbiguous  = "application_source_ambiguous"
	ReasonUnsupportedSchemaVersion    = "unsupported_schema_version"
	ReasonUnsupportedEventType        = "unsupported_event_type"
	ReasonUnsupportedApplicationCodec = "unsupported_application_decoder"
	ReasonApplicationPayloadInvalid   = "application_payload_invalid"
	ReasonApplicationGatewayInvalid   = "application_gateway_invalid"
	ReasonApplicationGatewayMissing   = "application_gateway_provenance_missing"
	ReasonStoredTelemetryMismatch     = "stored_telemetry_mismatch"
	ReasonMQTTSourceMissing           = "mqtt_source_missing"
	ReasonMQTTSourceAmbiguous         = "mqtt_source_ambiguous"
	ReasonMQTTIntegrityMismatch       = "mqtt_integrity_mismatch"
	ReasonJournalSourceMissing        = "journal_source_missing"
	ReasonJournalSourceAmbiguous      = "journal_source_ambiguous"
	ReasonJournalLineagePending       = "journal_lineage_pending"
	ReasonJournalIntegrityMismatch    = "journal_integrity_mismatch"
	ReasonCheckpointMissing           = "checkpoint_missing"
	ReasonCheckpointMismatch          = "checkpoint_mismatch"
)

type Work struct {
	VerificationID int64
	SourceEventKey string
	ObservedAt     time.Time
	WorkerID       string
	Attempts       int
}

type StoredMetric struct {
	DevEUI      string
	MetricName  string
	ValueNumber *float64
	ValueText   *string
	ValueBool   *bool
	Unit        string
	Quality     string
	SourceField string
}

type ApplicationEvidence struct {
	EventType                 string
	SchemaVersion             string
	EventKey                  string
	ObservedAt                time.Time
	DevEUI                    string
	GatewayID                 *string
	GatewayUplinkID           *int64
	GatewayFrequencyHz        *int64
	GatewayContextBase64      *string
	GatewayRSSIDbm            *int32
	GatewaySNRDb              *float64
	OperationalDecoderVersion *string
	RawDataBase64             *string
	Measurements              []StoredMetric
}

func (a ApplicationEvidence) HasGatewayProvenance() bool {
	return a.GatewayID != nil && a.GatewayUplinkID != nil && a.GatewayFrequencyHz != nil &&
		a.GatewayContextBase64 != nil && a.GatewayRSSIDbm != nil && a.GatewaySNRDb != nil
}

type DecoderEvidence struct {
	GatewayID              *string
	DecoderID              string
	DecoderVersion         string
	RawAppDataSHA256       string
	NormalizedDigestSHA256 string
}

type MQTTEvidence struct {
	GatewayEventID          int64
	GatewayID               string
	MQTTTopic               string
	CaptureKeySHA256        string
	SerializedEventSHA256   string
	PHYPayloadSHA256        string
	UplinkID                string
	FrequencyHz             int64
	RSSIDbm                 int32
	SNRDb                   float64
	GatewayContextBase64    string
	CorrelationDigestSHA256 string
	ObjectRef               string
}

type JournalSegmentMetadata struct {
	GatewayID           string
	SegmentID           int64
	FirstSequence       int64
	LastSequence        int64
	RecordCount         int64
	PreviousSegmentHash string
	FinalRecordHash     string
	SegmentHash         string
	ObjectRef           string
	ObjectSHA256        string
}

type CheckpointEvidence struct {
	CheckpointID      int64
	CheckpointVersion string
	GatewayID         string
	SegmentID         int64
	LastSequence      int64
	LastRecordHash    string
	SegmentHash       string
	GatewayCreatedAt  time.Time
	CheckpointDigest  string
}

type LineageEvidence struct {
	GatewayID          string
	JournalSegmentID   int64
	JournalSequence    int64
	JournalRecordHash  string
	JournalSegmentHash string
	CheckpointID       int64
	GatewayEventID     int64
	Decoder            DecoderEvidence
}
