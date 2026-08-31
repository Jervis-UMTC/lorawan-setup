package objectstore

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

var refSegmentPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._=-]*$`)

type FilesystemStore struct {
	root string
}

func NewFilesystem(root string) (*FilesystemStore, error) {
	if strings.TrimSpace(root) == "" {
		return nil, fmt.Errorf("filesystem object-store root is required")
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return nil, fmt.Errorf("resolve filesystem object-store root: %w", err)
	}
	if err := os.MkdirAll(abs, 0o750); err != nil {
		return nil, fmt.Errorf("create filesystem object-store root: %w", err)
	}
	realRoot, err := filepath.EvalSymlinks(abs)
	if err != nil {
		return nil, fmt.Errorf("resolve filesystem object-store root symlinks: %w", err)
	}
	return &FilesystemStore{root: realRoot}, nil
}

func (s *FilesystemStore) Check(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	info, err := os.Stat(s.root)
	if err != nil {
		return fmt.Errorf("stat filesystem object-store root: %w", err)
	}
	if !info.IsDir() {
		return fmt.Errorf("filesystem object-store root is not a directory")
	}
	return nil
}

func (s *FilesystemStore) PutIfAbsent(ctx context.Context, ref string, src io.Reader) (PutResult, error) {
	target, err := s.resolve(ref)
	if err != nil {
		return PutResult{}, err
	}
	if src == nil {
		return PutResult{}, fmt.Errorf("source reader is required")
	}
	if err := ctx.Err(); err != nil {
		return PutResult{}, err
	}

	parent := filepath.Dir(target)
	if err := os.MkdirAll(parent, 0o750); err != nil {
		return PutResult{}, fmt.Errorf("create object parent: %w", err)
	}
	if err := s.ensureWithinRoot(parent); err != nil {
		return PutResult{}, err
	}

	tmp, err := os.CreateTemp(parent, ".incoming-*")
	if err != nil {
		return PutResult{}, fmt.Errorf("create temporary object: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	h := sha256.New()
	n, copyErr := copyWithContext(ctx, io.MultiWriter(tmp, h), src)
	if copyErr != nil {
		_ = tmp.Close()
		return PutResult{}, fmt.Errorf("write temporary object: %w", copyErr)
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return PutResult{}, fmt.Errorf("sync temporary object: %w", err)
	}
	if err := tmp.Chmod(0o640); err != nil {
		_ = tmp.Close()
		return PutResult{}, fmt.Errorf("protect temporary object: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return PutResult{}, fmt.Errorf("close temporary object: %w", err)
	}

	metadata := Metadata{Ref: ref, SHA256: hex.EncodeToString(h.Sum(nil)), Size: n}
	if err := os.Link(tmpName, target); err == nil {
		return PutResult{Metadata: metadata, Created: true}, nil
	} else if !errors.Is(err, fs.ErrExist) {
		return PutResult{}, fmt.Errorf("publish immutable object: %w", err)
	}

	existing, err := s.statPath(ctx, ref, target)
	if err != nil {
		return PutResult{}, err
	}
	if existing.SHA256 != metadata.SHA256 || existing.Size != metadata.Size {
		return PutResult{}, fmt.Errorf("%w: ref=%s existing_sha256=%s new_sha256=%s", ErrConflict, ref, existing.SHA256, metadata.SHA256)
	}
	return PutResult{Metadata: existing, Created: false}, nil
}

func (s *FilesystemStore) Get(ctx context.Context, ref string) (io.ReadCloser, Metadata, error) {
	target, err := s.resolve(ref)
	if err != nil {
		return nil, Metadata{}, err
	}
	metadata, err := s.statPath(ctx, ref, target)
	if err != nil {
		return nil, Metadata{}, err
	}
	f, err := os.Open(target)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, Metadata{}, fmt.Errorf("%w: %s", ErrNotFound, ref)
	}
	if err != nil {
		return nil, Metadata{}, fmt.Errorf("open object: %w", err)
	}
	return f, metadata, nil
}

func (s *FilesystemStore) Stat(ctx context.Context, ref string) (Metadata, error) {
	target, err := s.resolve(ref)
	if err != nil {
		return Metadata{}, err
	}
	return s.statPath(ctx, ref, target)
}

func (s *FilesystemStore) resolve(ref string) (string, error) {
	if ref == "" || strings.HasPrefix(ref, "/") || strings.Contains(ref, "\\") || strings.ContainsRune(ref, '\x00') {
		return "", fmt.Errorf("%w: %q", ErrInvalidRef, ref)
	}
	parts := strings.Split(ref, "/")
	for _, part := range parts {
		if !refSegmentPattern.MatchString(part) || part == "." || part == ".." {
			return "", fmt.Errorf("%w: %q", ErrInvalidRef, ref)
		}
	}
	return filepath.Join(append([]string{s.root}, parts...)...), nil
}

func (s *FilesystemStore) statPath(ctx context.Context, ref, target string) (Metadata, error) {
	info, err := os.Lstat(target)
	if errors.Is(err, fs.ErrNotExist) {
		return Metadata{}, fmt.Errorf("%w: %s", ErrNotFound, ref)
	}
	if err != nil {
		return Metadata{}, fmt.Errorf("inspect object: %w", err)
	}
	if !info.Mode().IsRegular() {
		return Metadata{}, fmt.Errorf("%w: non-regular object %s", ErrInvalidRef, ref)
	}

	f, err := os.Open(target)
	if errors.Is(err, fs.ErrNotExist) {
		return Metadata{}, fmt.Errorf("%w: %s", ErrNotFound, ref)
	}
	if err != nil {
		return Metadata{}, fmt.Errorf("open object for hash: %w", err)
	}
	defer f.Close()

	h := sha256.New()
	n, err := copyWithContext(ctx, h, f)
	if err != nil {
		return Metadata{}, fmt.Errorf("hash object: %w", err)
	}
	return Metadata{Ref: ref, SHA256: hex.EncodeToString(h.Sum(nil)), Size: n}, nil
}

func (s *FilesystemStore) ensureWithinRoot(path string) error {
	realPath, err := filepath.EvalSymlinks(path)
	if err != nil {
		return fmt.Errorf("resolve object parent symlinks: %w", err)
	}
	rel, err := filepath.Rel(s.root, realPath)
	if err != nil {
		return fmt.Errorf("compare object parent with root: %w", err)
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
		return fmt.Errorf("%w: object parent escapes root", ErrInvalidRef)
	}
	return nil
}

func copyWithContext(ctx context.Context, dst io.Writer, src io.Reader) (int64, error) {
	buf := make([]byte, 64*1024)
	var total int64
	for {
		if err := ctx.Err(); err != nil {
			return total, err
		}
		n, readErr := src.Read(buf)
		if n > 0 {
			written, writeErr := dst.Write(buf[:n])
			total += int64(written)
			if writeErr != nil {
				return total, writeErr
			}
			if written != n {
				return total, io.ErrShortWrite
			}
		}
		if errors.Is(readErr, io.EOF) {
			return total, nil
		}
		if readErr != nil {
			return total, readErr
		}
	}
}
