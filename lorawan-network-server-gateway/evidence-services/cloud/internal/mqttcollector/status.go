package mqttcollector

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"

	"lorawan/evidence-services/cloud/internal/objectstore"
)

type SessionStatus struct {
	label      string
	connected  atomic.Bool
	subscribed atomic.Bool
	captures   atomic.Uint64
	errors     atomic.Uint64
	fatal      atomic.Bool
	mu         sync.RWMutex
	lastError  string
}

func NewSessionStatus(label string) *SessionStatus { return &SessionStatus{label: label} }
func (s *SessionStatus) setConnected(v bool) {
	s.connected.Store(v)
	if !v {
		s.subscribed.Store(false)
	}
}
func (s *SessionStatus) setSubscribed(v bool) {
	s.subscribed.Store(v)
	if v {
		s.mu.Lock()
		s.lastError = ""
		s.mu.Unlock()
	}
}
func (s *SessionStatus) captureOK() { s.captures.Add(1); s.mu.Lock(); s.lastError = ""; s.mu.Unlock() }
func (s *SessionStatus) captureError(err error, fatal bool) {
	s.errors.Add(1)
	if fatal {
		s.fatal.Store(true)
	}
	s.mu.Lock()
	s.lastError = err.Error()
	s.mu.Unlock()
}
func (s *SessionStatus) ready() bool {
	s.mu.RLock()
	hasError := s.lastError != ""
	s.mu.RUnlock()
	return s.connected.Load() && s.subscribed.Load() && !s.fatal.Load() && !hasError
}
func (s *SessionStatus) snapshot() map[string]any {
	s.mu.RLock()
	lastError := s.lastError
	s.mu.RUnlock()
	return map[string]any{"label": s.label, "connected": s.connected.Load(), "subscribed": s.subscribed.Load(), "captures": s.captures.Load(), "errors": s.errors.Load(), "fatal": s.fatal.Load(), "last_error": lastError}
}

type HealthHandler struct {
	broker1 *SessionStatus
	broker2 *SessionStatus
	repo    Repository
	store   objectstore.Store
}

func NewHealthHandler(broker1, broker2 *SessionStatus, repo Repository, store objectstore.Store) (*HealthHandler, error) {
	if broker1 == nil || broker2 == nil || repo == nil || store == nil {
		return nil, fmt.Errorf("collector health dependencies are required")
	}
	return &HealthHandler{broker1: broker1, broker2: broker2, repo: repo, store: store}, nil
}

func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch r.URL.Path {
	case "/healthz":
		writeHealthJSON(w, http.StatusOK, map[string]any{"status": "alive"})
	case "/readyz":
		ready := h.broker1.ready() && h.broker2.ready()
		if ready {
			ready = h.repo.Ping(r.Context()) == nil && h.store.Check(r.Context()) == nil
		}
		status := http.StatusOK
		state := "ready"
		if !ready {
			status = http.StatusServiceUnavailable
			state = "not_ready"
		}
		writeHealthJSON(w, status, map[string]any{"status": state, "broker_1": h.broker1.snapshot(), "broker_2": h.broker2.snapshot()})
	case "/metrics":
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		for i, s := range []*SessionStatus{h.broker1, h.broker2} {
			connected := 0
			if s.connected.Load() {
				connected = 1
			}
			subscribed := 0
			if s.subscribed.Load() {
				subscribed = 1
			}
			fmt.Fprintf(w, "gateway_evidence_mqtt_broker_connected{broker=\"%d\"} %d\n", i+1, connected)
			fmt.Fprintf(w, "gateway_evidence_mqtt_broker_subscribed{broker=\"%d\"} %d\n", i+1, subscribed)
			fmt.Fprintf(w, "gateway_evidence_mqtt_captures_total{broker=\"%d\"} %d\n", i+1, s.captures.Load())
			fmt.Fprintf(w, "gateway_evidence_mqtt_capture_errors_total{broker=\"%d\"} %d\n", i+1, s.errors.Load())
		}
	default:
		http.NotFound(w, r)
	}
}

func writeHealthJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
