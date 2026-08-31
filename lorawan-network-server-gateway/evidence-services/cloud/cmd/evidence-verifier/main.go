package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"lorawan/evidence-services/cloud/internal/config"
	"lorawan/evidence-services/cloud/internal/database"
	"lorawan/evidence-services/cloud/internal/logging"
	"lorawan/evidence-services/cloud/internal/objectstore"
	"lorawan/evidence-services/cloud/internal/trusteddecoder"
	"lorawan/evidence-services/cloud/internal/verifier"
)

const serviceName = "gateway-evidence-verifier"

func main() {
	logger, _ := logging.NewJSON(os.Stdout, "info")
	if err := run(); err != nil {
		logger.Error("service_stopped", "service", serviceName, "error", err.Error())
		os.Exit(1)
	}
}

func buildObjectStore(cfg config.Config) (objectstore.Store, error) {
	return objectstore.NewRuntime(objectstore.RuntimeSettings{
		Backend:            cfg.ObjectStoreBackend,
		FilesystemRoot:     cfg.ObjectStoreRoot,
		AllowDevFilesystem: cfg.AllowDevFilesystem,
		S3: objectstore.S3Settings{
			Endpoint:        cfg.S3Endpoint,
			Region:          cfg.S3Region,
			Bucket:          cfg.S3Bucket,
			Prefix:          cfg.S3Prefix,
			AccessKeyID:     cfg.S3AccessKeyID,
			SecretAccessKey: cfg.S3SecretAccessKey,
			CAFile:          cfg.S3CAFile,
			UsePathStyle:    cfg.S3UsePathStyle,
			MaxObjectBytes:  cfg.MaxBodyBytes,
		},
	})
}

func run() error {
	common, err := config.Load(serviceName)
	if err != nil {
		return err
	}
	cfg, err := verifier.LoadConfig()
	if err != nil {
		return err
	}
	logger, err := logging.NewJSON(os.Stdout, common.LogLevel)
	if err != nil {
		return err
	}
	if err := trusteddecoder.ValidatePackageDigest(); err != nil {
		return err
	}
	if err := trusteddecoder.SelfTest(); err != nil {
		return err
	}
	logger.Info("trusted_decoder_ready", "decoder_id", trusteddecoder.DecoderID, "decoder_version", trusteddecoder.DecoderVersion, "decoder_digest", trusteddecoder.PackageDigest, "fixture_result", "pass")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	pool, err := database.OpenVerifiedPool(ctx, database.PoolSettings{
		DSN:              common.DatabaseDSN,
		ExpectedHost:     common.DatabaseExpectedHost,
		ExpectedDatabase: common.DatabaseExpectedName,
		ExpectedRole:     database.RoleVerifier,
		ApplicationName:  serviceName,
		MaxConns:         common.DatabaseMaxConns,
		RequireWritable:  true,
	})
	if err != nil {
		return err
	}
	defer pool.Close()
	repo, err := verifier.NewPostgresRepository(pool)
	if err != nil {
		return err
	}
	store, err := buildObjectStore(common)
	if err != nil {
		return err
	}
	if err := store.Check(ctx); err != nil {
		return errors.New("verifier object-store startup check failed")
	}
	worker, err := verifier.NewWorker(repo, store, cfg.WorkerID, cfg.Lease, cfg.RetryAfter, cfg.DiscoveryLimit)
	if err != nil {
		return err
	}
	status := &verifier.Status{}
	health, err := verifier.NewHealthHandler(repo, store, status)
	if err != nil {
		return err
	}
	healthServer := &http.Server{Addr: common.ListenAddr, Handler: health, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second}
	healthErr := make(chan error, 1)
	go func() {
		err := healthServer.ListenAndServe()
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
			logger.Error("verifier_iteration_failed", "worker_id", cfg.WorkerID, "error", workErr.Error())
		} else {
			status.IterationOK(processed)
		}

		select {
		case <-ctx.Done():
			shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			_ = healthServer.Shutdown(shutdownCtx)
			return nil
		case err := <-healthErr:
			if err != nil {
				return err
			}
			return errors.New("verifier health server stopped unexpectedly")
		case <-ticker.C:
		}
	}
}
