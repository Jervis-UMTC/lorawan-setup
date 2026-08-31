package fabricadapter

import (
	"errors"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Enabled              bool
	ListenAddr           string
	LogLevel             string
	DatabaseDSN          string
	DatabaseExpectedHost string
	DatabaseExpectedName string
	DatabaseMaxConns     int32
	WorkerID             string
	ProcessingLease      time.Duration
	PollInterval         time.Duration
	MaxAttempts          int
	RetryBase            time.Duration
	RetryMax             time.Duration
	RetryJitter          time.Duration
	CommitTimeout        time.Duration
	OpenBaoAddr          string
	OpenBaoCAFile        string
	OpenBaoTransitMount  string
	OpenBaoTransitKey    string
	OpenBaoRoleIDFile    string
	OpenBaoSecretIDFile  string
	FabricEndpoint       string
	FabricTLSServerName  string
	FabricTLSRootCert    string
	FabricMSPID          string
	FabricCertPath       string
	FabricKeyPath        string
	FabricChannel        string
	FabricChaincode      string
	FabricContract       string
	FabricSubmitFunction string
	FabricQueryFunction  string
}

func LoadConfig() (Config, error) {
	cfg := Config{
		ListenAddr:           envDefault("FABRIC_ADAPTER_LISTEN_ADDR", "127.0.0.1:8080"),
		LogLevel:             strings.ToLower(envDefault("FABRIC_ADAPTER_LOG_LEVEL", "info")),
		DatabaseExpectedHost: strings.ToLower(envDefault("FABRIC_ADAPTER_DATABASE_EXPECTED_HOST", "pgbouncer.internal.lorawan.com")),
		DatabaseExpectedName: envDefault("FABRIC_ADAPTER_DATABASE_EXPECTED_NAME", "lorawan_telemetry"),
		DatabaseMaxConns:     4,
		ProcessingLease:      90 * time.Second,
		PollInterval:         2 * time.Second,
		MaxAttempts:          10,
		RetryBase:            5 * time.Second,
		RetryMax:             5 * time.Minute,
		RetryJitter:          2 * time.Second,
		CommitTimeout:        30 * time.Second,
		OpenBaoTransitMount:  "transit",
		OpenBaoTransitKey:    "lorawan-evidence",
	}
	var err error
	if cfg.Enabled, err = envBool("FABRIC_ADAPTER_ENABLED", false); err != nil {
		return Config{}, err
	}
	cfg.DatabaseDSN = strings.TrimSpace(os.Getenv("FABRIC_ADAPTER_DATABASE_URL"))
	cfg.WorkerID = strings.TrimSpace(os.Getenv("FABRIC_ADAPTER_WORKER_ID"))
	cfg.OpenBaoAddr = strings.TrimRight(strings.TrimSpace(os.Getenv("OPENBAO_ADDR")), "/")
	cfg.OpenBaoCAFile = strings.TrimSpace(os.Getenv("OPENBAO_CA_FILE"))
	cfg.OpenBaoTransitMount = envDefault("OPENBAO_TRANSIT_MOUNT", cfg.OpenBaoTransitMount)
	cfg.OpenBaoTransitKey = envDefault("OPENBAO_TRANSIT_KEY", cfg.OpenBaoTransitKey)
	cfg.OpenBaoRoleIDFile = strings.TrimSpace(os.Getenv("OPENBAO_APPROLE_ROLE_ID_FILE"))
	cfg.OpenBaoSecretIDFile = strings.TrimSpace(os.Getenv("OPENBAO_APPROLE_SECRET_ID_FILE"))
	cfg.FabricEndpoint = strings.TrimSpace(os.Getenv("FABRIC_GATEWAY_ENDPOINT"))
	cfg.FabricTLSServerName = strings.TrimSpace(os.Getenv("FABRIC_TLS_SERVER_NAME"))
	cfg.FabricTLSRootCert = strings.TrimSpace(os.Getenv("FABRIC_TLS_ROOT_CERT"))
	cfg.FabricMSPID = strings.TrimSpace(os.Getenv("FABRIC_MSP_ID"))
	cfg.FabricCertPath = strings.TrimSpace(os.Getenv("FABRIC_CERT_PATH"))
	cfg.FabricKeyPath = strings.TrimSpace(os.Getenv("FABRIC_KEY_PATH"))
	cfg.FabricChannel = strings.TrimSpace(os.Getenv("FABRIC_CHANNEL"))
	cfg.FabricChaincode = strings.TrimSpace(os.Getenv("FABRIC_CHAINCODE"))
	cfg.FabricContract = strings.TrimSpace(os.Getenv("FABRIC_CONTRACT"))
	cfg.FabricSubmitFunction = strings.TrimSpace(os.Getenv("FABRIC_SUBMIT_FUNCTION"))
	cfg.FabricQueryFunction = strings.TrimSpace(os.Getenv("FABRIC_QUERY_FUNCTION"))

	if cfg.DatabaseMaxConns, err = envInt32("FABRIC_ADAPTER_DB_MAX_CONNS", cfg.DatabaseMaxConns, 1, 32); err != nil {
		return Config{}, err
	}
	if cfg.ProcessingLease, err = envDuration("FABRIC_ADAPTER_PROCESSING_LEASE_SECONDS", cfg.ProcessingLease, 10, 3600); err != nil {
		return Config{}, err
	}
	if cfg.PollInterval, err = envDuration("FABRIC_ADAPTER_POLL_SECONDS", cfg.PollInterval, 1, 60); err != nil {
		return Config{}, err
	}
	if cfg.RetryBase, err = envDuration("FABRIC_RETRY_BASE_DELAY_SECONDS", cfg.RetryBase, 1, 3600); err != nil {
		return Config{}, err
	}
	if cfg.RetryMax, err = envDuration("FABRIC_RETRY_MAX_DELAY_SECONDS", cfg.RetryMax, 1, 86400); err != nil {
		return Config{}, err
	}
	if cfg.RetryJitter, err = envDuration("FABRIC_RETRY_JITTER_SECONDS", cfg.RetryJitter, 0, 3600); err != nil {
		return Config{}, err
	}
	if cfg.CommitTimeout, err = envDuration("FABRIC_COMMIT_TIMEOUT_SECONDS", cfg.CommitTimeout, 1, 3600); err != nil {
		return Config{}, err
	}
	if cfg.MaxAttempts, err = envInt("FABRIC_MAX_ATTEMPTS", cfg.MaxAttempts, 1, 1000); err != nil {
		return Config{}, err
	}
	if cfg.RetryMax < cfg.RetryBase {
		return Config{}, errors.New("FABRIC_RETRY_MAX_DELAY_SECONDS must be greater than or equal to the base delay")
	}
	if cfg.ListenAddr == "" {
		return Config{}, errors.New("FABRIC_ADAPTER_LISTEN_ADDR is required")
	}
	switch cfg.LogLevel {
	case "debug", "info", "warn", "error":
	default:
		return Config{}, errors.New("FABRIC_ADAPTER_LOG_LEVEL must be debug, info, warn, or error")
	}
	if !cfg.Enabled {
		return cfg, nil
	}
	if cfg.WorkerID == "" || len(cfg.WorkerID) > 128 {
		return Config{}, errors.New("FABRIC_ADAPTER_WORKER_ID must be 1 through 128 characters when enabled")
	}
	required := map[string]string{
		"FABRIC_ADAPTER_DATABASE_URL":    cfg.DatabaseDSN,
		"OPENBAO_ADDR":                   cfg.OpenBaoAddr,
		"OPENBAO_CA_FILE":                cfg.OpenBaoCAFile,
		"OPENBAO_APPROLE_ROLE_ID_FILE":   cfg.OpenBaoRoleIDFile,
		"OPENBAO_APPROLE_SECRET_ID_FILE": cfg.OpenBaoSecretIDFile,
		"FABRIC_GATEWAY_ENDPOINT":        cfg.FabricEndpoint,
		"FABRIC_TLS_SERVER_NAME":         cfg.FabricTLSServerName,
		"FABRIC_TLS_ROOT_CERT":           cfg.FabricTLSRootCert,
		"FABRIC_MSP_ID":                  cfg.FabricMSPID,
		"FABRIC_CERT_PATH":               cfg.FabricCertPath,
		"FABRIC_KEY_PATH":                cfg.FabricKeyPath,
		"FABRIC_CHANNEL":                 cfg.FabricChannel,
		"FABRIC_CHAINCODE":               cfg.FabricChaincode,
		"FABRIC_SUBMIT_FUNCTION":         cfg.FabricSubmitFunction,
		"FABRIC_QUERY_FUNCTION":          cfg.FabricQueryFunction,
	}
	for name, value := range required {
		if strings.TrimSpace(value) == "" {
			return Config{}, errors.New(name + " is required when FABRIC_ADAPTER_ENABLED=true")
		}
	}
	return cfg, nil
}

func envDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func envBool(name string, fallback bool) (bool, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		return false, errors.New(name + " must be true or false")
	}
	return value, nil
}

func envDuration(name string, fallback time.Duration, min, max int) (time.Duration, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value < min || value > max {
		return 0, errors.New(name + " is outside its permitted range")
	}
	return time.Duration(value) * time.Second, nil
}

func envInt(name string, fallback, min, max int) (int, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value < min || value > max {
		return 0, errors.New(name + " is outside its permitted range")
	}
	return value, nil
}

func envInt32(name string, fallback int32, min, max int) (int32, error) {
	value, err := envInt(name, int(fallback), min, max)
	return int32(value), err
}
