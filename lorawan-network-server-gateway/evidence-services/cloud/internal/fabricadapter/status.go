package fabricadapter

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

type Status struct {
	processed   atomic.Uint64
	errors      atomic.Uint64
	mu          sync.RWMutex
	lastError   string
	lastSuccess time.Time
}

func (s *Status) IterationOK(processed bool) {
	if processed {
		s.processed.Add(1)
	}
	s.mu.Lock()
	s.lastError = ""
	s.lastSuccess = time.Now().UTC()
	s.mu.Unlock()
}

func (s *Status) Error(err error) {
	s.errors.Add(1)
	s.mu.Lock()
	s.lastError = err.Error()
	s.mu.Unlock()
}

func (s *Status) ready() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastError == ""
}

type HealthHandler struct {
	enabled bool
	repo    Repository
	status  *Status
}

func NewHealthHandler(enabled bool, repo Repository, status *Status) (*HealthHandler, error) {
	if status == nil {
		return nil, fmt.Errorf("Fabric adapter health status is required")
	}
	if enabled && repo == nil {
		return nil, fmt.Errorf("enabled Fabric adapter health requires repository")
	}
	return &HealthHandler{enabled: enabled, repo: repo, status: status}, nil
}

func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch r.URL.Path {
	case "/healthz":
		writeStatusJSON(w, http.StatusOK, map[string]any{"status": "alive", "enabled": h.enabled})
	case "/readyz":
		if !h.enabled {
			writeStatusJSON(w, http.StatusOK, map[string]any{"status": "standby", "enabled": false, "canonical_self_test": "pass"})
			return
		}
		ready := h.repo.Ping(r.Context()) == nil && h.status.ready()
		if !ready {
			writeStatusJSON(w, http.StatusServiceUnavailable, map[string]any{"status": "not_ready", "enabled": true})
			return
		}
		writeStatusJSON(w, http.StatusOK, map[string]any{"status": "ready", "enabled": true})
	case "/metrics":
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		enabled := 0
		if h.enabled {
			enabled = 1
		}
		fmt.Fprintf(w, "gateway_fabric_adapter_enabled %d\n", enabled)
		fmt.Fprintf(w, "gateway_fabric_adapter_processed_total %d\n", h.status.processed.Load())
		fmt.Fprintf(w, "gateway_fabric_adapter_errors_total %d\n", h.status.errors.Load())
	default:
		http.NotFound(w, r)
	}
}

func writeStatusJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
