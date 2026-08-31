package main

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"lorawan/evidence-services/cloud/internal/config"
	"lorawan/evidence-services/cloud/internal/database"
	"lorawan/evidence-services/cloud/internal/ingest"
	"lorawan/evidence-services/cloud/internal/logging"
	"lorawan/evidence-services/cloud/internal/objectstore"
)

const serviceName = "gateway-evidence-ingest"

func main() {
	var err error
	if len(os.Args) == 1 {
		err = run()
	} else {
		err = runObjectStoreContractCommand(os.Args[1:])
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, serviceName+": "+err.Error())
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load(serviceName)
	if err != nil {
		return err
	}
	logger, err := logging.NewJSON(os.Stdout, cfg.LogLevel)
	if err != nil {
		return err
	}
	logger.Info("configuration accepted", "config", cfg.PublicSummary())

	pool, err := database.OpenVerifiedPool(context.Background(), database.PoolSettings{
		DSN:              cfg.DatabaseDSN,
		ExpectedHost:     cfg.DatabaseExpectedHost,
		ExpectedDatabase: cfg.DatabaseExpectedName,
		ExpectedRole:     database.RoleIngestor,
		ApplicationName:  serviceName,
		MaxConns:         cfg.DatabaseMaxConns,
		RequireWritable:  true,
	})
	if err != nil {
		return err
	}
	defer pool.Close()

	repository, err := ingest.NewPostgresRepository(pool, cfg.DatabaseExpectedName)
	if err != nil {
		return err
	}
	readyCtx, readyCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer readyCancel()
	if err := repository.Ping(readyCtx); err != nil {
		return err
	}

	store, err := buildObjectStore(cfg)
	if err != nil {
		return err
	}
	if err := store.Check(context.Background()); err != nil {
		return errors.New("object-store startup check failed")
	}

	tlsFiles := ingest.ServerTLSFiles{
		CertificateFile: strings.TrimSpace(os.Getenv("EVIDENCE_TLS_CERT_FILE")),
		PrivateKeyFile:  strings.TrimSpace(os.Getenv("EVIDENCE_TLS_KEY_FILE")),
		ClientCAFile:    strings.TrimSpace(os.Getenv("EVIDENCE_TLS_CLIENT_CA_FILE")),
	}
	tlsConfig, err := ingest.LoadDirectMTLSServerConfig(tlsFiles, time.Now().UTC())
	if err != nil {
		return err
	}
	logger.Info("direct mTLS configured", "tls_files", ingest.DirectTLSFileSummary(tlsFiles))

	handler, err := ingest.NewHandler(store, repository, ingest.TLSClientCertificateIdentity{}, cfg.MaxBodyBytes)
	if err != nil {
		return err
	}
	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           handler,
		TLSConfig:         tlsConfig,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    16 << 10,
	}

	listener, err := net.Listen("tcp", cfg.ListenAddr)
	if err != nil {
		return errors.New("open evidence-ingest listener failed")
	}
	defer listener.Close()
	tlsListener := tls.NewListener(listener, tlsConfig)

	signalCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	errCh := make(chan error, 1)
	go func() {
		logger.Info("evidence ingest listening", "addr", cfg.ListenAddr)
		errCh <- server.Serve(tlsListener)
	}()

	select {
	case serveErr := <-errCh:
		if serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
			return errors.New("evidence-ingest HTTP server failed")
		}
		return nil
	case <-signalCtx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			return errors.New("evidence-ingest graceful shutdown failed")
		}
		return nil
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
