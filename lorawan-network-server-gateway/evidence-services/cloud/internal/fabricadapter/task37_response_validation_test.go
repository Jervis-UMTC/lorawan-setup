package fabricadapter

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
)

func TestTask37CreateResponseValidatesEveryReturnedField(t *testing.T) {
	expected := task37ExpectedAnchor()
	base := hrcCreateResponse{
		Outcome:  "CREATE",
		RecordID: "hrc-record-1",
		Anchor: hrcAnchorRecord{
			RecordID:                    "hrc-record-1",
			AuthenticatedSourceSystemID: expected.AuthenticatedSourceSystemID,
			SourceRecordID:              expected.SourceRecordID,
			DigestAlgorithm:             "sha256",
			Digest:                      expected.Digest,
			PayloadLength:               expected.PayloadLength,
			SourceType:                  expected.SourceType,
			Producer:                    expected.Producer,
			ProducedAt:                  expected.ProducedAt,
			SchemaVersion:               expected.SchemaVersion,
		},
	}

	assertCreateAccepted := func(t *testing.T, response hrcCreateResponse) {
		t.Helper()
		payload, err := json.Marshal(response)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := decodeCreateResponse(payload, expected); err != nil {
			t.Fatalf("valid CreateSourceBoundAnchor response rejected: %v", err)
		}
	}
	assertCreateAccepted(t, base)
	retry := base
	retry.Outcome = "IDEMPOTENT_RETRY"
	assertCreateAccepted(t, retry)

	tests := []struct {
		name   string
		mutate func(*hrcCreateResponse)
	}{
		{"outcome", func(v *hrcCreateResponse) { v.Outcome = "OTHER" }},
		{"outer_record_id", func(v *hrcCreateResponse) { v.RecordID = "other-record" }},
		{"anchor_record_id", func(v *hrcCreateResponse) { v.Anchor.RecordID = "other-record" }},
		{"authenticated_source_system_id", func(v *hrcCreateResponse) { v.Anchor.AuthenticatedSourceSystemID = "other-source" }},
		{"source_record_id", func(v *hrcCreateResponse) { v.Anchor.SourceRecordID = "other-source-record" }},
		{"digest_algorithm", func(v *hrcCreateResponse) { v.Anchor.DigestAlgorithm = "sha512" }},
		{"digest", func(v *hrcCreateResponse) { v.Anchor.Digest = task37OtherDigest() }},
		{"payload_length", func(v *hrcCreateResponse) { v.Anchor.PayloadLength++ }},
		{"source_type", func(v *hrcCreateResponse) { v.Anchor.SourceType = "other-type" }},
		{"producer", func(v *hrcCreateResponse) { v.Anchor.Producer = "other-producer" }},
		{"produced_at", func(v *hrcCreateResponse) { v.Anchor.ProducedAt = "2026-09-07T00:00:01Z" }},
		{"schema_version", func(v *hrcCreateResponse) { v.Anchor.SchemaVersion = SchemaVersionV1 }},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			candidate := base
			tc.mutate(&candidate)
			payload, err := json.Marshal(candidate)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := decodeCreateResponse(payload, expected); err == nil {
				t.Fatalf("CreateSourceBoundAnchor accepted mismatched %s", tc.name)
			}
		})
	}
}

func TestTask37QueryResponseValidatesEveryReturnedField(t *testing.T) {
	expected := task37ExpectedAnchor()
	base := FabricQueryResult{
		Found:                       true,
		RecordID:                    "hrc-record-1",
		AuthenticatedSourceSystemID: expected.AuthenticatedSourceSystemID,
		SourceRecordID:              expected.SourceRecordID,
		DigestAlgorithm:             "sha256",
		Digest:                      expected.Digest,
		PayloadLength:               expected.PayloadLength,
		SourceType:                  expected.SourceType,
		Producer:                    expected.Producer,
		ProducedAt:                  expected.ProducedAt,
		SchemaVersion:               expected.SchemaVersion,
	}
	if err := validateAnchorQuery(expected, "hrc-record-1", base); err != nil {
		t.Fatalf("valid QuerySourceBoundAnchor result rejected: %v", err)
	}

	tests := []struct {
		name   string
		mutate func(*FabricQueryResult)
	}{
		{"found", func(v *FabricQueryResult) { v.Found = false }},
		{"record_id", func(v *FabricQueryResult) { v.RecordID = "other-record" }},
		{"authenticated_source_system_id", func(v *FabricQueryResult) { v.AuthenticatedSourceSystemID = "other-source" }},
		{"source_record_id", func(v *FabricQueryResult) { v.SourceRecordID = "other-source-record" }},
		{"digest_algorithm", func(v *FabricQueryResult) { v.DigestAlgorithm = "sha512" }},
		{"digest", func(v *FabricQueryResult) { v.Digest = task37OtherDigest() }},
		{"payload_length", func(v *FabricQueryResult) { v.PayloadLength++ }},
		{"source_type", func(v *FabricQueryResult) { v.SourceType = "other-type" }},
		{"producer", func(v *FabricQueryResult) { v.Producer = "other-producer" }},
		{"produced_at", func(v *FabricQueryResult) { v.ProducedAt = "2026-09-07T00:00:01Z" }},
		{"schema_version", func(v *FabricQueryResult) { v.SchemaVersion = SchemaVersionV1 }},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			candidate := base
			tc.mutate(&candidate)
			if err := validateAnchorQuery(expected, "hrc-record-1", candidate); err == nil {
				t.Fatalf("QuerySourceBoundAnchor accepted mismatched %s", tc.name)
			}
		})
	}
}

func TestTask37VerifyResponseValidatesEveryReturnedField(t *testing.T) {
	digest := task37ExpectedAnchor().Digest
	base := FabricVerifyResult{
		Outcome:        "MATCH",
		RecordID:       "hrc-record-1",
		ExpectedDigest: digest,
		ObservedDigest: digest,
	}
	if err := validateDigestVerification("hrc-record-1", digest, base); err != nil {
		t.Fatalf("valid VerifySourceBoundDigest result rejected: %v", err)
	}

	tests := []struct {
		name   string
		mutate func(*FabricVerifyResult)
	}{
		{"outcome", func(v *FabricVerifyResult) { v.Outcome = "MISMATCH" }},
		{"record_id", func(v *FabricVerifyResult) { v.RecordID = "other-record" }},
		{"expected_digest", func(v *FabricVerifyResult) { v.ExpectedDigest = task37OtherDigest() }},
		{"observed_digest", func(v *FabricVerifyResult) { v.ObservedDigest = task37OtherDigest() }},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			candidate := base
			tc.mutate(&candidate)
			if err := validateDigestVerification("hrc-record-1", digest, candidate); err == nil {
				t.Fatalf("VerifySourceBoundDigest accepted mismatched %s", tc.name)
			}
		})
	}
}

func TestTask37QueryAndVerifyTransportErrorsRemainUnknown(t *testing.T) {
	t.Run("query_transport_error", func(t *testing.T) {
		repo := &fakeRepository{work: fixtureWorkV2(), source: fixtureSource(), verification: fixtureVerification()}
		ledger := &fakeLedger{
			prepare:  FabricPreparedSubmission{TransactionID: "tx-query-transport", PreparedTransaction: []byte("prepared"), CommitStatusRequest: []byte("status"), CreateOutcome: "CREATE", RecordID: "hrc-query-transport"},
			submit:   FabricSubmitResult{TransactionID: "tx-query-transport", Committed: true},
			queryErr: errors.New("injected QuerySourceBoundAnchor transport failure"),
		}
		worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)
		processed, err := worker.RunOnce(context.Background())
		if err != nil || !processed {
			t.Fatalf("RunOnce processed=%v err=%v", processed, err)
		}
		if repo.unknownTxID != "tx-query-transport" || repo.deadCategory != "" || repo.confirmedTxID != "" {
			t.Fatalf("query transport error mapped incorrectly: unknown=%q dead=%q confirmed=%q", repo.unknownTxID, repo.deadCategory, repo.confirmedTxID)
		}
	})

	t.Run("verify_transport_error", func(t *testing.T) {
		repo := &fakeRepository{work: fixtureWorkV2(), source: fixtureSource(), verification: fixtureVerification()}
		ledger := &fakeLedger{
			prepare:   FabricPreparedSubmission{TransactionID: "tx-verify-transport", PreparedTransaction: []byte("prepared"), CommitStatusRequest: []byte("status"), CreateOutcome: "CREATE", RecordID: "hrc-verify-transport"},
			submit:    FabricSubmitResult{TransactionID: "tx-verify-transport", Committed: true},
			autoQuery: true,
			verifyErr: errors.New("injected VerifySourceBoundDigest transport failure"),
		}
		worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)
		processed, err := worker.RunOnce(context.Background())
		if err != nil || !processed {
			t.Fatalf("RunOnce processed=%v err=%v", processed, err)
		}
		if repo.unknownTxID != "tx-verify-transport" || repo.deadCategory != "" || repo.confirmedTxID != "" {
			t.Fatalf("verify transport error mapped incorrectly: unknown=%q dead=%q confirmed=%q", repo.unknownTxID, repo.deadCategory, repo.confirmedTxID)
		}
	})
}

func task37ExpectedAnchor() FabricAnchor {
	return FabricAnchor{
		AuthenticatedSourceSystemID: "lorawan-test",
		SourceRecordID:              "source-1",
		Digest:                      "a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222",
		PayloadLength:               2,
		SourceType:                  EventTypeUplink,
		Producer:                    "0000000000000001",
		ProducedAt:                  "2026-09-07T00:00:00Z",
		SchemaVersion:               SchemaVersionV2,
	}
}

func task37OtherDigest() string {
	return "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
}
