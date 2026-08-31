package config

import "testing"

func TestLoadFilesystemConfig(t *testing.T) {
	t.Setenv("EVIDENCE_DATABASE_DSN", "postgres://secret@example.invalid/db")
	t.Setenv("EVIDENCE_OBJECTSTORE_BACKEND", "filesystem")
	t.Setenv("EVIDENCE_OBJECTSTORE_ROOT", t.TempDir())
	t.Setenv("EVIDENCE_MAX_BODY_BYTES", "4096")
	t.Setenv("EVIDENCE_DB_MAX_CONNS", "3")
	t.Setenv("EVIDENCE_ALLOW_DEV_FILESYSTEM", "true")

	cfg, err := Load("evidence-ingest")
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if cfg.MaxBodyBytes != 4096 || cfg.DatabaseMaxConns != 3 || !cfg.AllowDevFilesystem {
		t.Fatalf("unexpected limits/dev gate: %+v", cfg)
	}
	if cfg.DatabaseExpectedHost != DefaultDatabaseHost || cfg.DatabaseExpectedName != DefaultDatabaseName {
		t.Fatalf("unexpected database identity defaults: %+v", cfg)
	}
	if got := cfg.PublicSummary()["database_dsn_present"]; got != true {
		t.Fatalf("database_dsn_present = %v, want true", got)
	}
	for _, v := range cfg.PublicSummary() {
		if s, ok := v.(string); ok && s == cfg.DatabaseDSN {
			t.Fatal("PublicSummary leaked database DSN")
		}
	}
}

func TestLoadS3ConfigDoesNotExposeCredentials(t *testing.T) {
	t.Setenv("EVIDENCE_DATABASE_DSN", "postgres://secret@example.invalid/db")
	t.Setenv("EVIDENCE_OBJECTSTORE_BACKEND", "s3")
	t.Setenv("EVIDENCE_S3_ENDPOINT", "https://objects.example.test")
	t.Setenv("EVIDENCE_S3_REGION", "test-1")
	t.Setenv("EVIDENCE_S3_BUCKET", "lorawan-evidence")
	t.Setenv("EVIDENCE_S3_PREFIX", "raw/v1")
	t.Setenv("EVIDENCE_S3_ACCESS_KEY_ID", "access-secret")
	t.Setenv("EVIDENCE_S3_SECRET_ACCESS_KEY", "key-secret")
	t.Setenv("EVIDENCE_S3_CA_FILE", "/run/evidence/s3-ca.crt")
	t.Setenv("EVIDENCE_S3_USE_PATH_STYLE", "true")

	cfg, err := Load("gateway-evidence-verifier")
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if !cfg.S3UsePathStyle || cfg.S3Bucket != "lorawan-evidence" {
		t.Fatalf("unexpected S3 config: %+v", cfg)
	}
	for _, v := range cfg.PublicSummary() {
		if s, ok := v.(string); ok && (s == cfg.S3AccessKeyID || s == cfg.S3SecretAccessKey || s == cfg.DatabaseDSN) {
			t.Fatal("PublicSummary leaked a credential")
		}
	}
}

func TestLoadRejectsImplicitObjectStore(t *testing.T) {
	t.Setenv("EVIDENCE_DATABASE_DSN", "postgres://example.invalid/db")
	t.Setenv("EVIDENCE_OBJECTSTORE_BACKEND", "")

	if _, err := Load("evidence-ingest"); err == nil {
		t.Fatal("Load() accepted missing object-store backend")
	}
}

func TestLoadRejectsUnknownBackend(t *testing.T) {
	t.Setenv("EVIDENCE_DATABASE_DSN", "postgres://example.invalid/db")
	t.Setenv("EVIDENCE_OBJECTSTORE_BACKEND", "pretend-ha")

	if _, err := Load("evidence-ingest"); err == nil {
		t.Fatal("Load() accepted unsupported object-store backend")
	}
}

func TestLoadRejectsIncompleteS3(t *testing.T) {
	t.Setenv("EVIDENCE_DATABASE_DSN", "postgres://example.invalid/db")
	t.Setenv("EVIDENCE_OBJECTSTORE_BACKEND", "s3")
	t.Setenv("EVIDENCE_S3_ENDPOINT", "https://objects.example.test")
	if _, err := Load("evidence-ingest"); err == nil {
		t.Fatal("Load() accepted incomplete S3 configuration")
	}
}

func TestLoadRejectsUnsafeDatabaseIdentityAndPoolSize(t *testing.T) {
	t.Setenv("EVIDENCE_DATABASE_DSN", "postgres://example.invalid/db")
	t.Setenv("EVIDENCE_OBJECTSTORE_BACKEND", "filesystem")
	t.Setenv("EVIDENCE_OBJECTSTORE_ROOT", t.TempDir())
	t.Setenv("EVIDENCE_DATABASE_EXPECTED_HOST", "one.example,two.example")
	if _, err := Load("evidence-ingest"); err == nil {
		t.Fatal("Load() accepted multiple expected database hosts")
	}

	t.Setenv("EVIDENCE_DATABASE_EXPECTED_HOST", DefaultDatabaseHost)
	t.Setenv("EVIDENCE_DB_MAX_CONNS", "33")
	if _, err := Load("evidence-ingest"); err == nil {
		t.Fatal("Load() accepted excessive database pool size")
	}
}
