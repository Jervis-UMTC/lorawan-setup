package ingest

import "time"

const (
	CheckpointVersion = "gateway-checkpoint-v1"
	SegmentVersion    = "gateway-journal-segment-v1"
	ReceiptVersion    = "evidence-ingest-receipt-v1"
)

type CheckpointRequest struct {
	CheckpointVersion string `json:"checkpoint_version"`
	GatewayID         string `json:"gateway_id"`
	SegmentID         int64  `json:"segment_id"`
	LastSequence      int64  `json:"last_sequence"`
	LastRecordHash    string `json:"last_record_hash"`
	SegmentHash       string `json:"segment_hash"`
	CreatedAt         string `json:"created_at"`
}

type SegmentRequest struct {
	SegmentVersion      string `json:"segment_version"`
	GatewayID           string `json:"gateway_id"`
	SegmentID           int64  `json:"segment_id"`
	FirstSequence       int64  `json:"first_sequence"`
	LastSequence        int64  `json:"last_sequence"`
	RecordCount         int64  `json:"record_count"`
	PreviousSegmentHash string `json:"previous_segment_hash"`
	FinalRecordHash     string `json:"final_record_hash"`
	SegmentHash         string `json:"segment_hash"`
	ObjectSHA256        string `json:"object_sha256"`
	ObjectBase64        string `json:"object_base64"`
}

type CheckpointRecord struct {
	GatewayID        string
	SegmentID        int64
	LastSequence     int64
	LastRecordHash   string
	SegmentHash      string
	GatewayCreatedAt time.Time
	ClientIdentity   string
	RequestID        string
	CheckpointDigest string
}

type SegmentRecord struct {
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

type Acceptance struct {
	Created          bool
	ServerReceivedAt time.Time
}

type Receipt struct {
	Status           string `json:"status"`
	Created          bool   `json:"created"`
	ReceiptVersion   string `json:"receipt_version"`
	ArtifactType     string `json:"artifact_type"`
	GatewayID        string `json:"gateway_id"`
	SegmentID        int64  `json:"segment_id"`
	LastSequence     int64  `json:"last_sequence"`
	CheckpointDigest string `json:"checkpoint_digest,omitempty"`
	SegmentHash      string `json:"segment_hash,omitempty"`
	ObjectSHA256     string `json:"object_sha256,omitempty"`
	ReceiptID        string `json:"receipt_id"`
	ServerReceivedAt string `json:"server_received_at"`
}
