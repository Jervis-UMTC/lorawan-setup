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
	const expected = "abbc19ec4fb939048f33b211a318526be711106e60fee88a3dae2f82b2d266ac"
	if actual := checkpointEvidenceDigest(checkpoint); actual != expected {
		t.Fatalf("checkpointEvidenceDigest=%q want %q", actual, expected)
	}
}

func TestCheckpointEvidenceDigestPreservesFixedMillisecondZeros(t *testing.T) {
	checkpoint := CheckpointEvidence{
		CheckpointVersion: "gateway-checkpoint-v1",
		GatewayID:         "0016c001f139a1cb",
		SegmentID:         2,
		LastSequence:      42,
		LastRecordHash:    "df04228d3c8695564281f1b64c6072a30dce5027b02123e4dac090eeff858403",
		SegmentHash:       "f8ac36ebb397eda3033f4465d04a16c264273ffa9ca2b8ff6157ba7edc8496f2",
		GatewayCreatedAt:  time.Date(2026, 9, 2, 3, 19, 16, 450000000, time.UTC),
	}
	const expected = "86046df140df61b467f3b60331d3d1b4b1767fb30e57609ae060e9ce4746ad1b"
	if actual := checkpointEvidenceDigest(checkpoint); actual != expected {
		t.Fatalf("checkpointEvidenceDigest=%q want %q", actual, expected)
	}
}
