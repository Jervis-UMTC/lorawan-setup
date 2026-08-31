package ingest

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

var (
	ErrConflict   = errors.New("durable identity conflicts with accepted content")
	ErrRegression = errors.New("checkpoint regresses accepted gateway history")
)

type Repository interface {
	Ping(ctx context.Context) error
	PutCheckpoint(ctx context.Context, record CheckpointRecord) (Acceptance, error)
	PutSegment(ctx context.Context, record SegmentRecord) (Acceptance, error)
}

type acceptedCheckpoint struct {
	Record           CheckpointRecord
	ServerReceivedAt time.Time
}

type acceptedSegment struct {
	Record           SegmentRecord
	ServerReceivedAt time.Time
}

// MemoryRepository is for unit tests and local smoke only. It is not a substitute
// for the PostgreSQL gateway_evidence metadata layer in cloud deployment.
type MemoryRepository struct {
	mu          sync.Mutex
	checkpoints map[string]acceptedCheckpoint
	segments    map[string]acceptedSegment
}

func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{
		checkpoints: make(map[string]acceptedCheckpoint),
		segments:    make(map[string]acceptedSegment),
	}
}

func (r *MemoryRepository) Ping(ctx context.Context) error { return ctx.Err() }

func (r *MemoryRepository) PutCheckpoint(ctx context.Context, record CheckpointRecord) (Acceptance, error) {
	if err := ctx.Err(); err != nil {
		return Acceptance{}, err
	}
	key := fmt.Sprintf("%s/%d", record.GatewayID, record.LastSequence)
	r.mu.Lock()
	defer r.mu.Unlock()

	if existing, ok := r.checkpoints[key]; ok {
		if existing.Record.CheckpointDigest != record.CheckpointDigest {
			return Acceptance{}, ErrConflict
		}
		return Acceptance{ServerReceivedAt: existing.ServerReceivedAt}, nil
	}
	for _, existing := range r.checkpoints {
		if existing.Record.GatewayID == record.GatewayID && existing.Record.LastSequence > record.LastSequence {
			return Acceptance{}, ErrRegression
		}
	}
	serverReceivedAt := time.Now().UTC()
	r.checkpoints[key] = acceptedCheckpoint{Record: record, ServerReceivedAt: serverReceivedAt}
	return Acceptance{Created: true, ServerReceivedAt: serverReceivedAt}, nil
}

func (r *MemoryRepository) PutSegment(ctx context.Context, record SegmentRecord) (Acceptance, error) {
	if err := ctx.Err(); err != nil {
		return Acceptance{}, err
	}
	key := fmt.Sprintf("%s/%d", record.GatewayID, record.SegmentID)
	r.mu.Lock()
	defer r.mu.Unlock()

	if existing, ok := r.segments[key]; ok {
		if existing.Record != record {
			return Acceptance{}, ErrConflict
		}
		return Acceptance{ServerReceivedAt: existing.ServerReceivedAt}, nil
	}
	serverReceivedAt := time.Now().UTC()
	r.segments[key] = acceptedSegment{Record: record, ServerReceivedAt: serverReceivedAt}
	return Acceptance{Created: true, ServerReceivedAt: serverReceivedAt}, nil
}
