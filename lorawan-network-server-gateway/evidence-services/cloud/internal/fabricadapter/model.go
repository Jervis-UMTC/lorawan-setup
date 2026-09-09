package fabricadapter

import "time"

const EvidenceSignatureAlgorithm = "OPENBAO-TRANSIT-ECDSA-P256-SHA2-256"

type OutboxWork struct {
	OutboxID             int64
	EventKey             string
	SourceEventKey       string
	ObservedAt           time.Time
	EventType            string
	SchemaVersion        string
	Attempts             int
	LeaseGeneration      int64
	CanonicalJSON        *string
	DigestSHA256         *string
	EvidenceSignatureAlg *string
	EvidenceSigningKeyID *string
	EvidenceSignature    *string
	EvidenceSealedAt     *time.Time
	FinalizedPayload     []byte
	FabricTxID           *string
	FabricRecordID       *string
	FabricPreparedTx     []byte
	FabricCommitRequest  []byte
}

type SourceRow struct {
	ReceivedAt     time.Time
	ApplicationID  *string
	DeviceID       *string
	DeviceModel    *string
	DecoderVersion *string
	DevEUI         string
	GatewayID      *string
	Region         *string
	FPort          *int64
	FCnt           *int64
	Confirmed      *bool
	RawDataBase64  *string
	PayloadJSON    []byte
}

type VerificationRow struct {
	VerificationID         int64
	Status                 string
	GatewayID              string
	JournalSegmentID       int64
	JournalSequence        int64
	JournalRecordHash      string
	JournalSegmentHash     string
	CheckpointID           int64
	GatewayEventID         int64
	DecoderID              string
	DecoderVersion         string
	RawAppDataSHA256       string
	NormalizedDigestSHA256 string
}

type Seal struct {
	CanonicalJSON string
	DigestSHA256  string
	Algorithm     string
	SigningKeyID  string
	Signature     string
	SealedAt      time.Time
}

type FabricAnchor struct {
	AuthenticatedSourceSystemID string
	SourceRecordID              string
	Digest                      string
	PayloadLength               int
	ExactPayload                []byte
	SourceType                  string
	Producer                    string
	ProducedAt                  string
	SchemaVersion               string
}

type FabricPreparedSubmission struct {
	TransactionID       string
	PreparedTransaction []byte
	CommitStatusRequest []byte
	CreateOutcome       string
	RecordID            string
}

type FabricQueryResult struct {
	Found                       bool
	RecordID                    string
	AuthenticatedSourceSystemID string
	SourceRecordID              string
	DigestAlgorithm             string
	Digest                      string
	PayloadLength               int
	SourceType                  string
	Producer                    string
	ProducedAt                  string
	SchemaVersion               string
}

type FabricVerifyResult struct {
	Outcome        string
	RecordID       string
	ExpectedDigest string
	ObservedDigest string
}
