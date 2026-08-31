package objectstore

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"testing"
)

func TestFilesystemStoreCreateIdempotentConflictAndRead(t *testing.T) {
	store, err := NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}
	ctx := context.Background()
	ref := "segments/0016c001f139a1cb/53.evidence"
	body := []byte("immutable-segment-bytes")

	first, err := store.PutIfAbsent(ctx, ref, bytes.NewReader(body))
	if err != nil {
		t.Fatalf("first PutIfAbsent() error = %v", err)
	}
	if !first.Created || len(first.Metadata.SHA256) != 64 || first.Metadata.Size != int64(len(body)) {
		t.Fatalf("unexpected first put result: %+v", first)
	}

	second, err := store.PutIfAbsent(ctx, ref, bytes.NewReader(body))
	if err != nil {
		t.Fatalf("duplicate PutIfAbsent() error = %v", err)
	}
	if second.Created {
		t.Fatal("exact duplicate created a second object")
	}
	if second.Metadata != first.Metadata {
		t.Fatalf("duplicate metadata changed: %+v != %+v", second.Metadata, first.Metadata)
	}

	_, err = store.PutIfAbsent(ctx, ref, bytes.NewReader([]byte("conflicting-bytes")))
	if !errors.Is(err, ErrConflict) {
		t.Fatalf("conflicting PutIfAbsent() error = %v, want ErrConflict", err)
	}

	r, metadata, err := store.Get(ctx, ref)
	if err != nil {
		t.Fatalf("Get() error = %v", err)
	}
	defer r.Close()
	got, err := io.ReadAll(r)
	if err != nil {
		t.Fatalf("ReadAll() error = %v", err)
	}
	if !bytes.Equal(got, body) {
		t.Fatalf("stored bytes changed: %q != %q", got, body)
	}
	if metadata != first.Metadata {
		t.Fatalf("Get metadata changed: %+v != %+v", metadata, first.Metadata)
	}
}

func TestFilesystemStoreRejectsUnsafeRefs(t *testing.T) {
	store, err := NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}

	for _, ref := range []string{"", "../escape", "/absolute", "a//b", "a\\b", "./a", "a/../b", "C:/drive"} {
		if _, err := store.Stat(context.Background(), ref); !errors.Is(err, ErrInvalidRef) {
			t.Errorf("Stat(%q) error = %v, want ErrInvalidRef", ref, err)
		}
	}
}

func TestFilesystemStoreRejectsSymlinkObject(t *testing.T) {
	root := t.TempDir()
	store, err := NewFilesystem(root)
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}

	outside := t.TempDir() + "/outside"
	if err := os.WriteFile(outside, []byte("outside"), 0o600); err != nil {
		t.Fatalf("WriteFile() error = %v", err)
	}
	link := root + "/linked"
	if err := os.Symlink(outside, link); err != nil {
		t.Skipf("symlink not available on this platform: %v", err)
	}

	if _, err := store.Stat(context.Background(), "linked"); !errors.Is(err, ErrInvalidRef) {
		t.Fatalf("Stat(symlink) error = %v, want ErrInvalidRef", err)
	}
}

func TestFilesystemStoreHonorsCancelledContext(t *testing.T) {
	store, err := NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	_, err = store.PutIfAbsent(ctx, "segments/gw/1.evidence", bytes.NewReader([]byte("x")))
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("PutIfAbsent() error = %v, want context.Canceled", err)
	}
}
