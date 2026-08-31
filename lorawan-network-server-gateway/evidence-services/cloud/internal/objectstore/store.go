package objectstore

import (
	"context"
	"errors"
	"io"
)

var (
	ErrConflict   = errors.New("object identity already exists with different content")
	ErrInvalidRef = errors.New("invalid object reference")
	ErrNotFound   = errors.New("object not found")
)

type Metadata struct {
	Ref    string
	SHA256 string
	Size   int64
}

type PutResult struct {
	Metadata Metadata
	Created  bool
}

type Store interface {
	Check(ctx context.Context) error
	PutIfAbsent(ctx context.Context, ref string, src io.Reader) (PutResult, error)
	Get(ctx context.Context, ref string) (io.ReadCloser, Metadata, error)
	Stat(ctx context.Context, ref string) (Metadata, error)
}
