package verifier

import (
	"strings"
	"testing"
	"time"
)

func TestCheckpointEvidenceDigestFixedVector(t *testing.T) {
	checkpoint := CheckpointEvidence{
		CheckpointVersion: "gateway-checkpoint-v1",
		GatewayID:         "0016c001f139a1cb",
		SegmentID:         1,
		LastSequence:      2,
		LastRecordHash:    strings.Repeat("a", 64),
		SegmentHash:       strings.Repeat("b", 64),
		GatewayCreatedAt:  time.Date(2000, 1, 1, 0, 10, 0, 0, time.UTC),
	}
	const expected = "fde615a8eb264090d324fe5642e0992748de9cc4f2d73cbd8f43459e12792903"
	if actual := checkpointEvidenceDigest(checkpoint); actual != expected {
		t.Fatalf("checkpointEvidenceDigest=%q want %q", actual, expected)
	}
}
