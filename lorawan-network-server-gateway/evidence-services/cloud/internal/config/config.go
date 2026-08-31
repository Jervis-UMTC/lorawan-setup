package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const (
	DefaultMaxBodyBytes     int64 = 8 << 20
	DefaultDatabaseMaxConns int32 = 4
	DefaultDatabaseHost           = "pgbouncer.internal.lorawan.com"
	DefaultDatabaseName           = "lorawan_telemetry"
)

type Config struct {
	ServiceName          string
	ListenAddr           string
	LogLevel             string
	DatabaseDSN          string
	DatabaseExpectedHost string
	DatabaseExpectedName string
	DatabaseMaxConns     int32
	ObjectStoreBackend   string
	ObjectStoreRoot      string
	AllowDevFilesystem   bool
	S3Endpoint           string
	S3Region             string
	S3Bucket             string
	S3Prefix             string
	S3AccessKeyID        string
	S3SecretAccessKey    string
	S3CAFile             string
	S3UsePathStyle       bool
	MaxBodyBytes         int64
}

func Load(serviceName string) (Config, error) {
	serviceName = strings.TrimSpace(serviceName)
	if serviceName == "" {
		return Config{}, fmt.Errorf("service name is required")
	}

	cfg := Config{
		ServiceName:          serviceName,
		ListenAddr:           valueOrDefault("EVIDENCE_LISTEN_ADDR", "127.0.0.1:8080"),
		LogLevel:             strings.ToLower(valueOrDefault("EVIDENCE_LOG_LEVEL", "info")),
		DatabaseDSN:          strings.TrimSpace(os.Getenv("EVIDENCE_DATABASE_DSN")),
		DatabaseExpectedHost: strings.ToLower(valueOrDefault("EVIDENCE_DATABASE_EXPECTED_HOST", DefaultDatabaseHost)),
		DatabaseExpectedName: valueOrDefault("EVIDENCE_DATABASE_EXPECTED_NAME", DefaultDatabaseName),
		DatabaseMaxConns:     DefaultDatabaseMaxConns,
		ObjectStoreBackend:   strings.ToLower(strings.TrimSpace(os.Getenv("EVIDENCE_OBJECTSTORE_BACKEND"))),
		ObjectStoreRoot:      strings.TrimSpace(os.Getenv("EVIDENCE_OBJECTSTORE_ROOT")),
		S3Endpoint:           strings.TrimSpace(os.Getenv("EVIDENCE_S3_ENDPOINT")),
		S3Region:             strings.TrimSpace(os.Getenv("EVIDENCE_S3_REGION")),
		S3Bucket:             strings.TrimSpace(os.Getenv("EVIDENCE_S3_BUCKET")),
		S3Prefix:             strings.TrimSpace(os.Getenv("EVIDENCE_S3_PREFIX")),
		S3AccessKeyID:        strings.TrimSpace(os.Getenv("EVIDENCE_S3_ACCESS_KEY_ID")),
		S3SecretAccessKey:    strings.TrimSpace(os.Getenv("EVIDENCE_S3_SECRET_ACCESS_KEY")),
		S3CAFile:             strings.TrimSpace(os.Getenv("EVIDENCE_S3_CA_FILE")),
		MaxBodyBytes:         DefaultMaxBodyBytes,
	}

	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_MAX_BODY_BYTES")); raw != "" {
		v, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || v <= 0 || v > 64<<20 {
			return Config{}, fmt.Errorf("EVIDENCE_MAX_BODY_BYTES must be a positive integer not greater than 67108864")
		}
		cfg.MaxBodyBytes = v
	}
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_DB_MAX_CONNS")); raw != "" {
		v, err := strconv.ParseInt(raw, 10, 32)
		if err != nil || v <= 0 || v > 32 {
			return Config{}, fmt.Errorf("EVIDENCE_DB_MAX_CONNS must be an integer from 1 through 32")
		}
		cfg.DatabaseMaxConns = int32(v)
	}
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_ALLOW_DEV_FILESYSTEM")); raw != "" {
		v, err := strconv.ParseBool(raw)
		if err != nil {
			return Config{}, fmt.Errorf("EVIDENCE_ALLOW_DEV_FILESYSTEM must be true or false")
		}
		cfg.AllowDevFilesystem = v
	}
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_S3_USE_PATH_STYLE")); raw != "" {
		v, err := strconv.ParseBool(raw)
		if err != nil {
			return Config{}, fmt.Errorf("EVIDENCE_S3_USE_PATH_STYLE must be true or false")
		}
		cfg.S3UsePathStyle = v
	}

	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func (c Config) Validate() error {
	if strings.TrimSpace(c.ServiceName) == "" {
		return fmt.Errorf("service name is required")
	}
	if strings.TrimSpace(c.ListenAddr) == "" {
		return fmt.Errorf("listen address is required")
	}
	if c.DatabaseDSN == "" {
		return fmt.Errorf("EVIDENCE_DATABASE_DSN is required")
	}
	if c.DatabaseExpectedHost == "" || strings.ContainsAny(c.DatabaseExpectedHost, ",/\\") {
		return fmt.Errorf("EVIDENCE_DATABASE_EXPECTED_HOST must be one logical DNS host")
	}
	if strings.TrimSpace(c.DatabaseExpectedName) == "" {
		return fmt.Errorf("EVIDENCE_DATABASE_EXPECTED_NAME is required")
	}
	if c.DatabaseMaxConns <= 0 || c.DatabaseMaxConns > 32 {
		return fmt.Errorf("database max connections must be from 1 through 32")
	}
	if c.MaxBodyBytes <= 0 || c.MaxBodyBytes > 64<<20 {
		return fmt.Errorf("max body bytes must be positive and no greater than 64 MiB")
	}

	switch c.LogLevel {
	case "debug", "info", "warn", "error":
	default:
		return fmt.Errorf("unsupported log level %q", c.LogLevel)
	}

	switch c.ObjectStoreBackend {
	case "filesystem":
		if c.ObjectStoreRoot == "" {
			return fmt.Errorf("EVIDENCE_OBJECTSTORE_ROOT is required for filesystem backend")
		}
	case "s3":
		if c.S3Endpoint == "" || c.S3Region == "" || c.S3Bucket == "" || c.S3AccessKeyID == "" || c.S3SecretAccessKey == "" || c.S3CAFile == "" {
			return fmt.Errorf("S3 backend requires EVIDENCE_S3_ENDPOINT, EVIDENCE_S3_REGION, EVIDENCE_S3_BUCKET, EVIDENCE_S3_ACCESS_KEY_ID, EVIDENCE_S3_SECRET_ACCESS_KEY, and EVIDENCE_S3_CA_FILE")
		}
	case "":
		return fmt.Errorf("EVIDENCE_OBJECTSTORE_BACKEND is required")
	default:
		return fmt.Errorf("unsupported object-store backend %q", c.ObjectStoreBackend)
	}

	return nil
}

func (c Config) PublicSummary() map[string]any {
	return map[string]any{
		"service":                  c.ServiceName,
		"listen_addr":              c.ListenAddr,
		"log_level":                c.LogLevel,
		"database_dsn_present":     c.DatabaseDSN != "",
		"database_expected_host":   c.DatabaseExpectedHost,
		"database_expected_name":   c.DatabaseExpectedName,
		"database_max_connections": c.DatabaseMaxConns,
		"object_store_backend":     c.ObjectStoreBackend,
		"object_store_root":        c.ObjectStoreRoot,
		"dev_filesystem_enabled":   c.AllowDevFilesystem,
		"s3_endpoint":              c.S3Endpoint,
		"s3_region":                c.S3Region,
		"s3_bucket":                c.S3Bucket,
		"s3_prefix":                c.S3Prefix,
		"s3_credentials_present":   c.S3AccessKeyID != "" && c.S3SecretAccessKey != "",
		"s3_ca_file_present":       c.S3CAFile != "",
		"s3_use_path_style":        c.S3UsePathStyle,
		"max_body_bytes":           c.MaxBodyBytes,
	}
}

func valueOrDefault(name, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(name)); v != "" {
		return v
	}
	return fallback
}
