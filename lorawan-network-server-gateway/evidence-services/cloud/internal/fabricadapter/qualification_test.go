package fabricadapter

import (
	"strings"
	"testing"
	"time"
)

func qualificationTestSeal() QualificationSeal {
	return QualificationSeal{
		OutboxID:                  1960,
		SourceRecordID:            "fdadcf14-741e-4293-ad38-39ba89369ea7",
		SourceType:                "lorawan_uplink_accepted",
		Producer:                  "ac1f09fffe296d29",
		ProducedAtRFC3339Nano:     "2026-09-07T08:20:49.944598Z",
		SchemaVersion:             SchemaVersionV2,
		FinalizedPayloadLength:    2828,
		FinalizedPayloadSHA256:    "827e443857118c0f922c2f03e66f950a79092c74d8d8b947d489ace43d157b51",
		GatewayVerificationStatus: "verified",
	}
}

func qualificationTestSnapshot(t *testing.T) QualificationSnapshot {
	t.Helper()
	producedAt, err := time.Parse(time.RFC3339Nano, "2026-09-07T08:20:49.944598Z")
	if err != nil {
		t.Fatal(err)
	}
	return QualificationSnapshot{
		OutboxID:                  1960,
		SourceRecordID:            "fdadcf14-741e-4293-ad38-39ba89369ea7",
		Status:                    "pending",
		Attempts:                  0,
		SourceType:                "lorawan_uplink_accepted",
		Producer:                  "ac1f09fffe296d29",
		ProducedAt:                producedAt,
		SchemaVersion:             SchemaVersionV2,
		FinalizedPayloadLength:    2828,
		FinalizedPayloadSHA256:    "827e443857118c0f922c2f03e66f950a79092c74d8d8b947d489ace43d157b51",
		GatewayVerificationStatus: "verified",
		NextAttemptDue:            true,
		LeaseExpiredOrAbsent:      true,
	}
}

func TestQualificationUntouchedCandidateIsSubmissionOnly(t *testing.T) {
	mode, err := ValidateQualificationSnapshot(qualificationTestSnapshot(t), qualificationTestSeal())
	if err != nil {
		t.Fatal(err)
	}
	if mode != QualificationModeSubmission {
		t.Fatalf("mode=%q", mode)
	}
}

func TestQualificationRejectsAnySealedFieldMismatch(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*QualificationSnapshot)
	}{
		{"source_record_id", func(s *QualificationSnapshot) { s.SourceRecordID = "wrong" }},
		{"source_type", func(s *QualificationSnapshot) { s.SourceType = "wrong" }},
		{"producer", func(s *QualificationSnapshot) { s.Producer = "wrong" }},
		{"produced_at", func(s *QualificationSnapshot) { s.ProducedAt = s.ProducedAt.Add(time.Nanosecond) }},
		{"schema", func(s *QualificationSnapshot) { s.SchemaVersion = SchemaVersionV1 }},
		{"payload_length", func(s *QualificationSnapshot) { s.FinalizedPayloadLength++ }},
		{"payload_hash", func(s *QualificationSnapshot) { s.FinalizedPayloadSHA256 = strings.Repeat("f", 64) }},
		{"verification", func(s *QualificationSnapshot) { s.GatewayVerificationStatus = "pending" }},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			snapshot := qualificationTestSnapshot(t)
			tc.mutate(&snapshot)
			if _, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal()); err == nil {
				t.Fatal("mismatch was accepted")
			}
		})
	}
}

func TestQualificationRequiresExactUntouchedInitialState(t *testing.T) {
	for _, mutate := range []func(*QualificationSnapshot){
		func(s *QualificationSnapshot) { s.Status = "failed" },
		func(s *QualificationSnapshot) { s.Attempts = 1 },
		func(s *QualificationSnapshot) { s.NextAttemptDue = false },
	} {
		snapshot := qualificationTestSnapshot(t)
		mutate(&snapshot)
		if _, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal()); err == nil {
			t.Fatal("non-untouched candidate was accepted")
		}
	}
}

func TestQualificationRejectsPartialDurableTransaction(t *testing.T) {
	snapshot := qualificationTestSnapshot(t)
	snapshot.FabricTransactionID = "tx-1"
	if _, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal()); err == nil || !strings.Contains(err.Error(), "partial durable") {
		t.Fatalf("partial durable state err=%v", err)
	}
}

func TestQualificationAcceptsOnlyCompleteSameTransactionRecovery(t *testing.T) {
	snapshot := qualificationTestSnapshot(t)
	snapshot.Status = "reconciling"
	snapshot.Attempts = 1
	snapshot.FabricTransactionID = "tx-1"
	snapshot.FabricRecordID = "record-1"
	snapshot.PreparedTransactionPresent = true
	snapshot.PreparedTransactionLength = 100
	snapshot.CommitStatusRequestPresent = true
	snapshot.CommitStatusRequestLength = 50
	mode, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal())
	if err != nil {
		t.Fatal(err)
	}
	if mode != QualificationModeRecovery {
		t.Fatalf("mode=%q", mode)
	}

	snapshot.NextAttemptDue = false
	if _, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal()); err == nil {
		t.Fatal("not-due durable recovery was accepted")
	}
}

func TestQualificationExpiredProcessingRecoveryUsesSameDurableTransaction(t *testing.T) {
	snapshot := qualificationTestSnapshot(t)
	snapshot.Status = "processing"
	snapshot.Attempts = 1
	snapshot.FabricTransactionID = "tx-1"
	snapshot.FabricRecordID = "record-1"
	snapshot.PreparedTransactionPresent = true
	snapshot.PreparedTransactionLength = 100
	snapshot.CommitStatusRequestPresent = true
	snapshot.CommitStatusRequestLength = 50
	snapshot.LeaseExpiredOrAbsent = true
	mode, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal())
	if err != nil {
		t.Fatal(err)
	}
	if mode != QualificationModeRecovery {
		t.Fatalf("mode=%q", mode)
	}

	snapshot.LeaseExpiredOrAbsent = false
	if _, err := ValidateQualificationSnapshot(snapshot, qualificationTestSeal()); err == nil {
		t.Fatal("active processing lease was accepted")
	}
}

func TestQualificationConfigRequiresNormalAdapterDisabled(t *testing.T) {
	cfg := Config{
		Enabled:              false,
		DatabaseDSN:          "postgres://example.invalid/db",
		DatabaseExpectedHost: "pgbouncer.internal.lorawan.com",
		DatabaseExpectedName: "lorawan_telemetry",
		WorkerID:             "task37-qualification-ulc01-1960",
		OpenBaoAddr:          "https://openbao-kms.internal.lorawan.com:18200",
		OpenBaoCAFile:        "/run/openbao/ca.crt",
		OpenBaoRoleIDFile:    "/run/openbao-approle/role_id",
		OpenBaoSecretIDFile:  "/run/openbao-approle/secret_id",
		FabricEndpoint:       "10.104.0.7:7051",
		FabricTLSServerName:  "peer1.hrc.local",
		FabricTLSRootCert:    "/run/fabric/tls/ca.crt",
		FabricMSPID:          "HrcMSP",
		FabricCertPath:       "/run/fabric/identity/client.crt",
		FabricKeyPath:        "/run/fabric/identity/client.key",
		FabricChannel:        "hrc-channel",
		FabricChaincode:      "hrc-evidence",
		FabricSourceSystemID: "lorawan-gateway-evidence",
		FabricSubmitFunction: "CreateSourceBoundAnchor",
		FabricQueryFunction:  "QuerySourceBoundAnchor",
		FabricVerifyFunction: "VerifySourceBoundDigest",
	}
	contract := QualificationRuntimeContract{
		WorkerID:             cfg.WorkerID,
		DatabaseExpectedHost: cfg.DatabaseExpectedHost,
		DatabaseExpectedName: cfg.DatabaseExpectedName,
		OpenBaoAddr:          cfg.OpenBaoAddr,
		OpenBaoCAFile:        cfg.OpenBaoCAFile,
		OpenBaoRoleIDFile:    cfg.OpenBaoRoleIDFile,
		OpenBaoSecretIDFile:  cfg.OpenBaoSecretIDFile,
		FabricEndpoint:       cfg.FabricEndpoint,
		FabricTLSServerName:  cfg.FabricTLSServerName,
		FabricTLSRootCert:    cfg.FabricTLSRootCert,
		FabricMSPID:          cfg.FabricMSPID,
		FabricCertPath:       cfg.FabricCertPath,
		FabricKeyPath:        cfg.FabricKeyPath,
		FabricChannel:        cfg.FabricChannel,
		FabricChaincode:      cfg.FabricChaincode,
		FabricContract:       "",
		FabricSourceSystemID: cfg.FabricSourceSystemID,
		FabricSubmitFunction: cfg.FabricSubmitFunction,
		FabricQueryFunction:  cfg.FabricQueryFunction,
		FabricVerifyFunction: cfg.FabricVerifyFunction,
	}
	if err := ValidateQualificationConfig(cfg, contract); err != nil {
		t.Fatal(err)
	}
	cfg.Enabled = true
	if err := ValidateQualificationConfig(cfg, contract); err == nil {
		t.Fatal("qualification accepted FABRIC_ADAPTER_ENABLED=true")
	}
}
