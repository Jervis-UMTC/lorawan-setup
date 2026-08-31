package objectstore

import (
	"bytes"
	"context"
	"errors"
	"io"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

type fakeS3Error struct{ code string }

func (e fakeS3Error) Error() string     { return e.code }
func (e fakeS3Error) ErrorCode() string { return e.code }

type fakeS3 struct {
	objects      map[string][]byte
	putConflicts int
	putCalls     int
	headErr      error
}

func newFakeS3() *fakeS3 { return &fakeS3{objects: make(map[string][]byte)} }

func (f *fakeS3) PutObject(_ context.Context, in *s3.PutObjectInput, _ ...func(*s3.Options)) (*s3.PutObjectOutput, error) {
	f.putCalls++
	if f.putConflicts > 0 {
		f.putConflicts--
		return nil, fakeS3Error{code: "ConditionalRequestConflict"}
	}
	body, err := io.ReadAll(in.Body)
	if err != nil {
		return nil, err
	}
	key := aws.ToString(in.Key)
	if _, exists := f.objects[key]; exists {
		return nil, fakeS3Error{code: "PreconditionFailed"}
	}
	if aws.ToString(in.IfNoneMatch) != "*" {
		return nil, errors.New("missing If-None-Match create-only precondition")
	}
	f.objects[key] = append([]byte(nil), body...)
	return &s3.PutObjectOutput{}, nil
}

func (f *fakeS3) GetObject(_ context.Context, in *s3.GetObjectInput, _ ...func(*s3.Options)) (*s3.GetObjectOutput, error) {
	body, ok := f.objects[aws.ToString(in.Key)]
	if !ok {
		return nil, fakeS3Error{code: "NoSuchKey"}
	}
	return &s3.GetObjectOutput{Body: io.NopCloser(bytes.NewReader(body))}, nil
}

func (f *fakeS3) HeadBucket(context.Context, *s3.HeadBucketInput, ...func(*s3.Options)) (*s3.HeadBucketOutput, error) {
	if f.headErr != nil {
		return nil, f.headErr
	}
	return &s3.HeadBucketOutput{}, nil
}

func newTestS3Store(client s3API) *S3Store {
	return &S3Store{client: client, bucket: "evidence-test", prefix: "raw/v1", maxObjectBytes: 1024}
}

func TestS3StoreCreateDuplicateConflictAndRead(t *testing.T) {
	fake := newFakeS3()
	store := newTestS3Store(fake)
	ctx := context.Background()
	ref := "segments/0016c001f139a1cb/1.evidence"
	body := []byte("immutable-evidence")

	first, err := store.PutIfAbsent(ctx, ref, bytes.NewReader(body))
	if err != nil {
		t.Fatalf("first PutIfAbsent() error = %v", err)
	}
	if !first.Created || first.Metadata.Size != int64(len(body)) || len(first.Metadata.SHA256) != 64 {
		t.Fatalf("unexpected first result: %+v", first)
	}

	second, err := store.PutIfAbsent(ctx, ref, bytes.NewReader(body))
	if err != nil {
		t.Fatalf("duplicate PutIfAbsent() error = %v", err)
	}
	if second.Created || second.Metadata != first.Metadata {
		t.Fatalf("duplicate result changed: first=%+v second=%+v", first, second)
	}

	_, err = store.PutIfAbsent(ctx, ref, strings.NewReader("different"))
	if !errors.Is(err, ErrConflict) {
		t.Fatalf("conflicting PutIfAbsent() error = %v, want ErrConflict", err)
	}

	r, metadata, err := store.Get(ctx, ref)
	if err != nil {
		t.Fatalf("Get() error = %v", err)
	}
	got, err := io.ReadAll(r)
	_ = r.Close()
	if err != nil {
		t.Fatalf("read object error = %v", err)
	}
	if !bytes.Equal(got, body) || metadata != first.Metadata {
		t.Fatalf("Get() mismatch: body=%q metadata=%+v", got, metadata)
	}
}

func TestS3StoreRetriesConditionalConflict(t *testing.T) {
	fake := newFakeS3()
	fake.putConflicts = 1
	store := newTestS3Store(fake)

	result, err := store.PutIfAbsent(context.Background(), "mqtt/gw/event", strings.NewReader("payload"))
	if err != nil {
		t.Fatalf("PutIfAbsent() error = %v", err)
	}
	if !result.Created || fake.putCalls != 2 {
		t.Fatalf("unexpected retry result=%+v putCalls=%d", result, fake.putCalls)
	}
}

func TestS3StoreReadHashesActualBytes(t *testing.T) {
	fake := newFakeS3()
	fake.objects["raw/v1/object"] = []byte("actual-bytes")
	store := newTestS3Store(fake)

	metadata, err := store.Stat(context.Background(), "object")
	if err != nil {
		t.Fatalf("Stat() error = %v", err)
	}
	want := metadataForBytes("object", []byte("actual-bytes"))
	if metadata != want {
		t.Fatalf("metadata = %+v, want %+v", metadata, want)
	}
}

func TestS3StoreBoundsAndNotFound(t *testing.T) {
	store := newTestS3Store(newFakeS3())
	store.maxObjectBytes = 4
	if _, err := store.PutIfAbsent(context.Background(), "too-large", strings.NewReader("12345")); err == nil {
		t.Fatal("PutIfAbsent() accepted object larger than configured maximum")
	}
	if _, err := store.Stat(context.Background(), "missing"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("Stat(missing) error = %v, want ErrNotFound", err)
	}
}

func TestS3SettingsRejectUnsafeConfiguration(t *testing.T) {
	valid := S3Settings{
		Endpoint:        "https://objects.example.test",
		Region:          "test-1",
		Bucket:          "lorawan-evidence",
		Prefix:          "raw/v1",
		AccessKeyID:     "access",
		SecretAccessKey: "secret",
		CAFile:          "ca.pem",
		MaxObjectBytes:  1024,
	}
	if _, _, _, err := validateS3Settings(valid); err != nil {
		t.Fatalf("valid settings rejected: %v", err)
	}

	cases := []S3Settings{
		func() S3Settings { c := valid; c.Endpoint = "http://objects.example.test"; return c }(),
		func() S3Settings { c := valid; c.Endpoint = "https://user:pass@objects.example.test"; return c }(),
		func() S3Settings { c := valid; c.Endpoint = "https://objects.example.test/path"; return c }(),
		func() S3Settings { c := valid; c.Bucket = "Bad_Bucket"; return c }(),
		func() S3Settings { c := valid; c.Prefix = "../escape"; return c }(),
		func() S3Settings { c := valid; c.SecretAccessKey = ""; return c }(),
		func() S3Settings { c := valid; c.CAFile = ""; return c }(),
	}
	for i, c := range cases {
		if _, _, _, err := validateS3Settings(c); err == nil {
			t.Errorf("unsafe settings case %d accepted: %+v", i, c)
		}
	}
}
