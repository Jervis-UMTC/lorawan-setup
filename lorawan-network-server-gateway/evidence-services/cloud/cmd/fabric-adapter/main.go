package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"lorawan/evidence-services/cloud/internal/database"
	"lorawan/evidence-services/cloud/internal/fabricadapter"
	"lorawan/evidence-services/cloud/internal/logging"
)

const serviceName = "gateway-fabric-adapter"

func main() {
	logger, _ := logging.NewJSON(os.Stdout, "info")
	if err := run(os.Args[1:]); err != nil {
		logger.Error("service_stopped", "service", serviceName, "error", err.Error())
		os.Exit(1)
	}
}

func run(args []string) error {
	if err := fabricadapter.SelfTest(); err != nil {
		return err
	}
	cfg, err := fabricadapter.LoadConfig()
	if err != nil {
		return err
	}
	logger, err := logging.NewJSON(os.Stdout, cfg.LogLevel)
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if len(args) > 0 {
		if args[0] != "reconstruct" || len(args) != 2 {
			return errors.New("usage: gateway-fabric-adapter reconstruct <outbox_id>")
		}
		outboxID, err := strconv.ParseInt(args[1], 10, 64)
		if err != nil || outboxID <= 0 {
			return errors.New("reconstruct outbox_id must be a positive integer")
		}
		return reconstruct(ctx, cfg, outboxID)
	}

	status := &fabricadapter.Status{}
	if !cfg.Enabled {
		health, err := fabricadapter.NewHealthHandler(false, nil, status)
		if err != nil {
			return err
		}
		logger.Info("fabric_adapter_standby", "service", serviceName, "enabled", false, "canonical_self_test", "pass")
		return serveStandby(ctx, cfg.ListenAddr, health)
	}

	pool, err := database.OpenVerifiedPool(ctx, database.PoolSettings{
		DSN: cfg.DatabaseDSN, ExpectedHost: cfg.DatabaseExpectedHost,
		ExpectedDatabase: cfg.DatabaseExpectedName, ExpectedRole: database.RoleFabricAdapter,
		ApplicationName: serviceName, MaxConns: cfg.DatabaseMaxConns, RequireWritable: true,
	})
	if err != nil {
		return err
	}
	defer pool.Close()
	repo, err := fabricadapter.NewPostgresRepository(pool)
	if err != nil {
		return err
	}
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
	health, err := fabricadapter.NewHealthHandler(true, repo, status)
	if err != nil {
		return err
	}
	logger.Info("fabric_adapter_ready", "worker_id", cfg.WorkerID, "canonical_self_test", "pass")
	return runWorker(ctx, cfg, logger, worker, health, status)
}

func reconstruct(ctx context.Context, cfg fabricadapter.Config, outboxID int64) error {
	if cfg.DatabaseDSN == "" {
		return errors.New("FABRIC_ADAPTER_DATABASE_URL is required for reconstruct mode")
	}
	pool, err := database.OpenVerifiedPool(ctx, database.PoolSettings{
		DSN: cfg.DatabaseDSN, ExpectedHost: cfg.DatabaseExpectedHost,
		ExpectedDatabase: cfg.DatabaseExpectedName, ExpectedRole: database.RoleFabricAdapter,
		ApplicationName: serviceName + "-reconstruct", MaxConns: 1, RequireWritable: false,
	})
	if err != nil {
		return err
	}
	defer pool.Close()
	repo, err := fabricadapter.NewPostgresRepository(pool)
	if err != nil {
		return err
	}
	work, err := repo.LoadOutboxReadOnly(ctx, outboxID)
	if err != nil {
		return err
	}
	source, err := repo.LoadSource(ctx, *work)
	if err != nil {
		return err
	}
	var verification *fabricadapter.VerificationRow
	if work.SchemaVersion == fabricadapter.SchemaVersionV2 {
		row, err := repo.LoadVerification(ctx, *work)
		if err != nil {
			return err
		}
		verification = &row
	}
	evidence, err := fabricadapter.BuildEvidence(*work, source, verification)
	if err != nil {
		return err
	}
	canonical, err := fabricadapter.CanonicalizeEvidence(evidence)
	if err != nil {
		return err
	}
	fmt.Printf("digest_sha256=%s\n", canonical.DigestSHA256)
	return nil
}

func serveStandby(ctx context.Context, addr string, handler http.Handler) error {
	server := &http.Server{Addr: addr, Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second}
	errCh := make(chan error, 1)
	go func() {
		err := server.ListenAndServe()
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()
	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
		return nil
	case err := <-errCh:
		return err
	}
}

func runWorker(ctx context.Context, cfg fabricadapter.Config, logger interface {
	Error(string, ...any)
}, worker *fabricadapter.Worker, health http.Handler, status *fabricadapter.Status) error {
	server := &http.Server{Addr: cfg.ListenAddr, Handler: health, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second}
	healthErr := make(chan error, 1)
	go func() {
		err := server.ListenAndServe()
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			healthErr <- err
		}
	}()
	ticker := time.NewTicker(cfg.PollInterval)
	defer ticker.Stop()
	for {
		processed, workErr := worker.RunOnce(ctx)
		if workErr != nil {
			status.Error(workErr)
			logger.Error("fabric_adapter_iteration_failed", "worker_id", cfg.WorkerID, "error", workErr.Error())
		} else {
			status.IterationOK(processed)
		}
		select {
		case <-ctx.Done():
			shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			_ = server.Shutdown(shutdownCtx)
			return nil
		case err := <-healthErr:
			if err != nil {
				return err
			}
			return errors.New("Fabric adapter health server stopped unexpectedly")
		case <-ticker.C:
		}
	}
}
