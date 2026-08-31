package database

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const PgxVersion = "v5.10.0"

type PoolSettings struct {
	DSN              string
	ExpectedHost     string
	ExpectedDatabase string
	ExpectedRole     string
	ApplicationName  string
	MaxConns         int32
	RequireWritable  bool
}

func OpenVerifiedPool(ctx context.Context, settings PoolSettings) (*pgxpool.Pool, error) {
	if strings.TrimSpace(settings.DSN) == "" {
		return nil, errors.New("PostgreSQL DSN is required")
	}
	if strings.TrimSpace(settings.ExpectedHost) == "" || strings.TrimSpace(settings.ExpectedDatabase) == "" {
		return nil, errors.New("expected PostgreSQL host and database are required")
	}
	if strings.TrimSpace(settings.ExpectedRole) == "" {
		return nil, errors.New("expected PostgreSQL role membership is required")
	}
	if settings.MaxConns <= 0 || settings.MaxConns > 32 {
		return nil, errors.New("PostgreSQL max connections must be from 1 through 32")
	}

	cfg, err := pgxpool.ParseConfig(settings.DSN)
	if err != nil {
		// pgx parse errors retain the supplied connection string. Do not wrap the
		// original error because the DSN may contain a password.
		return nil, errors.New("parse PostgreSQL configuration failed")
	}

	conn := cfg.ConnConfig
	if !strings.EqualFold(conn.Host, settings.ExpectedHost) {
		return nil, fmt.Errorf("PostgreSQL host does not match expected logical host %q", settings.ExpectedHost)
	}
	if conn.Database != settings.ExpectedDatabase {
		return nil, fmt.Errorf("PostgreSQL database does not match expected database %q", settings.ExpectedDatabase)
	}
	if conn.Password == "" {
		return nil, errors.New("PostgreSQL password must be supplied through protected service configuration")
	}
	if conn.TLSConfig == nil || conn.TLSConfig.InsecureSkipVerify || conn.TLSConfig.ServerName == "" {
		return nil, errors.New("PostgreSQL connection must use hostname-verified TLS")
	}
	if !strings.EqualFold(conn.TLSConfig.ServerName, settings.ExpectedHost) {
		return nil, errors.New("PostgreSQL TLS server name does not match the expected logical host")
	}
	if len(conn.Fallbacks) != 0 {
		return nil, errors.New("PostgreSQL connection fallbacks are disabled; HA belongs behind the logical PgBouncer endpoint")
	}

	// pgx v5.10.0 adds require_auth. Force SCRAM so a compromised/misrouted
	// server cannot downgrade the client to cleartext or another auth method.
	conn.RequireAuth = "scram-sha-256"
	if conn.RuntimeParams == nil {
		conn.RuntimeParams = make(map[string]string)
	}
	conn.RuntimeParams["application_name"] = settings.ApplicationName

	cfg.MinConns = 0
	cfg.MaxConns = settings.MaxConns
	cfg.MaxConnIdleTime = 5 * time.Minute
	cfg.MaxConnLifetime = 30 * time.Minute
	cfg.MaxConnLifetimeJitter = 5 * time.Minute
	cfg.HealthCheckPeriod = 30 * time.Second

	// A pgx pool can establish new physical sessions after startup. Verify every
	// session before it enters the pool instead of trusting one startup probe.
	cfg.AfterConnect = func(ctx context.Context, c *pgx.Conn) error {
		var databaseName, currentUser, transactionReadOnly string
		var roleMember, inRecovery bool
		if err := c.QueryRow(ctx, `
SELECT current_database(), current_user,
       pg_has_role(current_user, $1, 'member'),
       pg_is_in_recovery(), current_setting('transaction_read_only')`,
			settings.ExpectedRole,
		).Scan(&databaseName, &currentUser, &roleMember, &inRecovery, &transactionReadOnly); err != nil {
			return errors.New("PostgreSQL session trust validation query failed")
		}
		if databaseName != settings.ExpectedDatabase {
			return fmt.Errorf("PostgreSQL session reached unexpected database %q", databaseName)
		}
		if !roleMember {
			return fmt.Errorf("PostgreSQL user %q is not a member of expected role %s", currentUser, settings.ExpectedRole)
		}
		if settings.RequireWritable && (inRecovery || transactionReadOnly != "off") {
			return errors.New("PostgreSQL session is not writable primary routing")
		}
		return nil
	}

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, errors.New("open PostgreSQL connection pool failed")
	}
	return pool, nil
}
