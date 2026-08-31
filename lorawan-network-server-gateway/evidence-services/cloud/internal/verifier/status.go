package verifier

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"lorawan/evidence-services/cloud/internal/objectstore"
	"lorawan/evidence-services/cloud/internal/trusteddecoder"
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
func (s *Status) ready() bool { s.mu.RLock(); defer s.mu.RUnlock(); return s.lastError == "" }

type HealthHandler struct {
	repo   Repository
	store  objectstore.Store
	status *Status
}

func NewHealthHandler(repo Repository, store objectstore.Store, status *Status) (*HealthHandler, error) {
	if repo == nil || store == nil || status == nil {
		return nil, fmt.Errorf("verifier health dependencies are required")
	}
	return &HealthHandler{repo: repo, store: store, status: status}, nil
}

func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch r.URL.Path {
	case "/healthz":
		writeJSON(w, http.StatusOK, map[string]any{"status": "alive"})
	case "/readyz":
		ready := h.repo.Ping(r.Context()) == nil && h.store.Check(r.Context()) == nil && trusteddecoder.SelfTest() == nil && h.status.ready()
		statusCode := http.StatusOK
		state := "ready"
		if !ready {
			statusCode = http.StatusServiceUnavailable
			state = "not_ready"
		}
		writeJSON(w, statusCode, map[string]any{"status": state, "decoder_id": trusteddecoder.DecoderID, "decoder_version": trusteddecoder.DecoderVersion, "decoder_digest": trusteddecoder.PackageDigest})
	case "/metrics":
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		fmt.Fprintf(w, "gateway_evidence_verifier_processed_total %d\n", h.status.processed.Load())
		fmt.Fprintf(w, "gateway_evidence_verifier_errors_total %d\n", h.status.errors.Load())
	default:
		http.NotFound(w, r)
	}
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
