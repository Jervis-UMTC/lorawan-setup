package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"lorawan/evidence-services/cloud/internal/database"
	"lorawan/evidence-services/cloud/internal/fabricadapter"
)

const (
	qualificationServiceName = "task37-fabric-qualification"
	qualificationWorkerID    = "task37-qualification-ulc01-1960"
)

var qualificationSeal = fabricadapter.QualificationSeal{
	OutboxID:                  1960,
	SourceRecordID:            "fdadcf14-741e-4293-ad38-39ba89369ea7",
	SourceType:                "lorawan_uplink_accepted",
	Producer:                  "ac1f09fffe296d29",
	ProducedAtRFC3339Nano:     "2026-09-07T08:20:49.944598Z",
	SchemaVersion:             "telemetry-attestation-v2",
	FinalizedPayloadLength:    2828,
	FinalizedPayloadSHA256:    "827e443857118c0f922c2f03e66f950a79092c74d8d8b947d489ace43d157b51",
	GatewayVerificationStatus: "verified",
}

var qualificationRuntimeContract = fabricadapter.QualificationRuntimeContract{
	WorkerID:             qualificationWorkerID,
	DatabaseExpectedHost: "pgbouncer.internal.lorawan.com",
	DatabaseExpectedName: "lorawan_telemetry",
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
	FabricContract:       "",
	FabricSourceSystemID: "lorawan-gateway-evidence",
	FabricSubmitFunction: "CreateSourceBoundAnchor",
	FabricQueryFunction:  "QuerySourceBoundAnchor",
	FabricVerifyFunction: "VerifySourceBoundDigest",
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintf(os.Stderr, "TASK37_QUALIFICATION_ERROR=%s\n", strings.ReplaceAll(err.Error(), "\n", " "))
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) != 1 || args[0] != "execute" {
		return errors.New("usage: task37-fabric-qualification execute")
	}
	if err := fabricadapter.SelfTest(); err != nil {
		return err
	}
	cfg, err := fabricadapter.LoadConfig()
	if err != nil {
		return err
	}
	if err := fabricadapter.ValidateQualificationConfig(cfg, qualificationRuntimeContract); err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	pool, err := database.OpenVerifiedPool(ctx, database.PoolSettings{
		DSN:              cfg.DatabaseDSN,
		ExpectedHost:     cfg.DatabaseExpectedHost,
		ExpectedDatabase: cfg.DatabaseExpectedName,
		ExpectedRole:     database.RoleFabricAdapter,
		ApplicationName:  qualificationServiceName,
		MaxConns:         1,
		RequireWritable:  true,
	})
	if err != nil {
		return err
	}
	defer pool.Close()
	repo, err := fabricadapter.NewPostgresRepository(pool)
	if err != nil {
		return err
	}

	before, err := repo.LoadQualificationSnapshot(ctx, qualificationSeal.OutboxID, qualificationSeal.SourceRecordID)
	if err != nil {
		return err
	}
	mode, err := fabricadapter.ValidateQualificationSnapshot(before, qualificationSeal)
	if err != nil {
		return err
	}
	fmt.Printf("TASK37_QUALIFICATION_PRECLAIM=PASS\nOUTBOX_ID=%d\nSOURCE_RECORD_ID=%s\nMODE=%s\nSOURCE_TYPE=%s\nPRODUCER=%s\nPRODUCED_AT_UTC_RFC3339NANO=%s\nSCHEMA_VERSION=%s\nFINALIZED_PAYLOAD_LENGTH=%d\nFINALIZED_PAYLOAD_SHA256=%s\nGATEWAY_VERIFICATION_STATUS=%s\nNORMAL_ADAPTER_REQUIRED_STATE=false\nULC02_TOUCHED=NO\n",
		qualificationSeal.OutboxID,
		qualificationSeal.SourceRecordID,
		mode,
		qualificationSeal.SourceType,
		qualificationSeal.Producer,
		qualificationSeal.ProducedAtRFC3339Nano,
		qualificationSeal.SchemaVersion,
		qualificationSeal.FinalizedPayloadLength,
		qualificationSeal.FinalizedPayloadSHA256,
		qualificationSeal.GatewayVerificationStatus,
	)

	signer, err := fabricadapter.NewOpenBaoClient(cfg)
	if err != nil {
		return err
	}
	ledger, err := fabricadapter.NewGatewayClient(cfg)
	if err != nil {
		return err
	}
	defer ledger.Close()
	worker, err := fabricadapter.NewWorker(repo, signer, ledger, cfg)
	if err != nil {
		return err
	}

	work, claimedMode, err := repo.ClaimQualification(ctx, qualificationSeal, qualificationWorkerID, cfg.ProcessingLease)
	if err != nil {
		return err
	}
	if work == nil || claimedMode != mode {
		return errors.New("atomic qualification claim did not return the sealed candidate in the expected mode")
	}
	if err := worker.ProcessQualification(ctx, *work, claimedMode); err != nil {
		return err
	}

	after, err := repo.LoadQualificationSnapshot(ctx, qualificationSeal.OutboxID, qualificationSeal.SourceRecordID)
	if err != nil {
		return err
	}
	if after.Status != "confirmed" || strings.TrimSpace(after.FabricTransactionID) == "" {
		return fmt.Errorf("qualification did not reach confirmed state; status=%s durable transaction state is preserved for governed same-transaction recovery", after.Status)
	}
	if !after.PreparedTransactionPresent || after.PreparedTransactionLength == 0 || !after.CommitStatusRequestPresent || after.CommitStatusRequestLength == 0 {
		return errors.New("confirmed qualification is missing durable same-transaction recovery material")
	}
	fmt.Printf("TASK37_QUALIFICATION=PASS\nFABRIC_TRANSACTION_ID=%s\nSTATUS=confirmed\nNORMAL_ADAPTER_REQUIRED_STATE=false\nULC02_TOUCHED=NO\n", after.FabricTransactionID)
	return nil
}
