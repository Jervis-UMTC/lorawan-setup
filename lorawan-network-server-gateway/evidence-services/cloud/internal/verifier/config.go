package verifier

import (
	"errors"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	WorkerID       string
	Lease          time.Duration
	RetryAfter     time.Duration
	PollInterval   time.Duration
	DiscoveryLimit int
}

func LoadConfig() (Config, error) {
	cfg := Config{
		WorkerID:       strings.TrimSpace(os.Getenv("EVIDENCE_VERIFIER_WORKER_ID")),
		Lease:          60 * time.Second,
		RetryAfter:     30 * time.Second,
		PollInterval:   2 * time.Second,
		DiscoveryLimit: 100,
	}
	var err error
	if cfg.Lease, err = durationSeconds("EVIDENCE_VERIFIER_LEASE_SECONDS", cfg.Lease, 5, 3600); err != nil {
		return Config{}, err
	}
	if cfg.RetryAfter, err = durationSeconds("EVIDENCE_VERIFIER_RETRY_SECONDS", cfg.RetryAfter, 1, 86400); err != nil {
		return Config{}, err
	}
	if cfg.PollInterval, err = durationSeconds("EVIDENCE_VERIFIER_POLL_SECONDS", cfg.PollInterval, 1, 60); err != nil {
		return Config{}, err
	}
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_VERIFIER_DISCOVERY_LIMIT")); raw != "" {
		value, parseErr := strconv.Atoi(raw)
		if parseErr != nil || value < 1 || value > 1000 {
			return Config{}, errors.New("EVIDENCE_VERIFIER_DISCOVERY_LIMIT must be 1 through 1000")
		}
		cfg.DiscoveryLimit = value
	}
	if cfg.WorkerID == "" || len(cfg.WorkerID) > 128 {
		return Config{}, errors.New("EVIDENCE_VERIFIER_WORKER_ID must be 1 through 128 characters")
	}
	return cfg, nil
}

func durationSeconds(name string, fallback time.Duration, min, max int) (time.Duration, error) {
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
