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
	"lorawan/evidence-services/cloud/internal/mqttcollector"
	"lorawan/evidence-services/cloud/internal/objectstore"
)

const serviceName = "gateway-mqtt-evidence-collector"

func main() {
	logger, _ := logging.NewJSON(os.Stdout, "info")
	if err := run(); err != nil {
		logger.Error("service_stopped", "service", serviceName, "error", err.Error())
		os.Exit(1)
	}
}

func run() error {
	common, err := config.Load(serviceName)
	if err != nil {
		return err
	}
	logger, err := logging.NewJSON(os.Stdout, common.LogLevel)
	if err != nil {
		return err
	}
	mqttCfg, err := mqttcollector.LoadRuntimeConfig()
	if err != nil {
		return err
	}
	logger.Info("service_config_loaded", "service", serviceName, "config", common.PublicSummary(), "mqtt", mqttCfg.PublicSummary())

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	pool, err := database.OpenVerifiedPool(ctx, database.PoolSettings{
		DSN:              common.DatabaseDSN,
		ExpectedHost:     common.DatabaseExpectedHost,
		ExpectedDatabase: common.DatabaseExpectedName,
		ExpectedRole:     database.RoleCollector,
		ApplicationName:  serviceName,
		MaxConns:         common.DatabaseMaxConns,
		RequireWritable:  true,
	})
	if err != nil {
		return err
	}
	defer pool.Close()
	repo, err := mqttcollector.NewPostgresRepository(pool)
	if err != nil {
		return err
	}

	store, err := objectstore.NewRuntime(objectstore.RuntimeSettings{
		Backend:            common.ObjectStoreBackend,
		FilesystemRoot:     common.ObjectStoreRoot,
		AllowDevFilesystem: common.AllowDevFilesystem,
		S3: objectstore.S3Settings{
			Endpoint:        common.S3Endpoint,
			Region:          common.S3Region,
			Bucket:          common.S3Bucket,
			Prefix:          common.S3Prefix,
			AccessKeyID:     common.S3AccessKeyID,
			SecretAccessKey: common.S3SecretAccessKey,
			CAFile:          common.S3CAFile,
			UsePathStyle:    common.S3UsePathStyle,
			MaxObjectBytes:  common.MaxBodyBytes,
		},
	})
	if err != nil {
		return err
	}
	processor, err := mqttcollector.NewProcessor(store, repo, mqttCfg.Region)
	if err != nil {
		return err
	}

	broker1Status := mqttcollector.NewSessionStatus(mqttCfg.Broker1.Label)
	broker2Status := mqttcollector.NewSessionStatus(mqttCfg.Broker2.Label)
	health, err := mqttcollector.NewHealthHandler(broker1Status, broker2Status, repo, store)
	if err != nil {
		return err
	}
	healthServer := &http.Server{
		Addr:              common.ListenAddr,
		Handler:           health,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       30 * time.Second,
	}
	healthErr := make(chan error, 1)
	go func() {
		logger.Info("health_listener_starting", "listen_addr", common.ListenAddr)
		err := healthServer.ListenAndServe()
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			healthErr <- err
		}
		close(healthErr)
	}()

	session1, err := mqttcollector.StartSession(ctx, mqttCfg, mqttCfg.Broker1, processor, broker1Status, logger)
	if err != nil {
		return err
	}
	session2, err := mqttcollector.StartSession(ctx, mqttCfg, mqttCfg.Broker2, processor, broker2Status, logger)
	if err != nil {
		return err
	}

	select {
	case <-ctx.Done():
	case err := <-healthErr:
		if err != nil {
			return err
		}
	case <-session1.Done():
		if ctx.Err() == nil {
			return errors.New("broker-1 MQTT connection manager stopped unexpectedly")
		}
	case <-session2.Done():
		if ctx.Err() == nil {
			return errors.New("broker-2 MQTT connection manager stopped unexpectedly")
		}
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = healthServer.Shutdown(shutdownCtx)
	logger.Info("service_shutdown_complete", "service", serviceName)
	return nil
}
