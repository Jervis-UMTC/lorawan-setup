package mqttcollector

import (
	"context"
	"errors"
	"sync"
)

var ErrCaptureConflict = errors.New("capture identity conflicts with accepted MQTT witness")

type Repository interface {
	Ping(ctx context.Context) error
	PutCapture(ctx context.Context, record CaptureRecord) (created bool, err error)
}

// MemoryRepository is only for unit/local smoke tests.
type MemoryRepository struct {
	mu       sync.Mutex
	captures map[string]CaptureRecord
}

func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{captures: make(map[string]CaptureRecord)}
}

func (r *MemoryRepository) Ping(ctx context.Context) error { return ctx.Err() }

func (r *MemoryRepository) PutCapture(ctx context.Context, record CaptureRecord) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}
	r.mu.Lock()
	defer r.mu.Unlock()

	if existing, ok := r.captures[record.CaptureKeySHA256]; ok {
		if !sameAuthoritativeCapture(existing, record) {
			return false, ErrCaptureConflict
		}
		return false, nil
	}
	r.captures[record.CaptureKeySHA256] = record
	return true, nil
}

func sameAuthoritativeCapture(a, b CaptureRecord) bool {
	return a.GatewayID == b.GatewayID &&
		a.MQTTTopic == b.MQTTTopic &&
		a.SerializedEventSHA256 == b.SerializedEventSHA256 &&
		a.HasUplinkProjection == b.HasUplinkProjection &&
		a.PHYPayloadSHA256 == b.PHYPayloadSHA256 &&
		a.UplinkID == b.UplinkID &&
		a.FrequencyHz == b.FrequencyHz &&
		a.RSSIDbm == b.RSSIDbm &&
		a.SNRDb == b.SNRDb &&
		a.GatewayContextBase64 == b.GatewayContextBase64 &&
		a.CorrelationDigestSHA256 == b.CorrelationDigestSHA256 &&
		a.ObjectRef == b.ObjectRef
}
