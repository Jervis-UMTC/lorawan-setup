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
	CanonicalJSON        *string
	DigestSHA256         *string
	EvidenceSignatureAlg *string
	EvidenceSigningKeyID *string
	EvidenceSignature    *string
	EvidenceSealedAt     *time.Time
	FabricTxID           *string
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

type FabricAttestation struct {
	SchemaVersion string
	EventKey      string
	EventType     string
	Digest        string
	SealAlgorithm string
	SealKeyID     string
	SealSignature string
}

type FabricQueryResult struct {
	Found     bool
	EventKey  string
	Digest    string
	TxID      string
	Committed bool
}
