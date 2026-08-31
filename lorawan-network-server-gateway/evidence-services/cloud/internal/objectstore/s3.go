package objectstore

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

const (
	S3SDKVersion          = "v1.107.0"
	defaultS3ObjectLimit  = int64(8 << 20)
	maxS3ConditionalTries = 3
)

var (
	s3BucketPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$`)
	s3RefPattern    = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._=-]*$`)
)

type S3Settings struct {
	Endpoint        string
	Region          string
	Bucket          string
	Prefix          string
	AccessKeyID     string
	SecretAccessKey string
	CAFile          string
	UsePathStyle    bool
	MaxObjectBytes  int64
}

type s3API interface {
	PutObject(context.Context, *s3.PutObjectInput, ...func(*s3.Options)) (*s3.PutObjectOutput, error)
	GetObject(context.Context, *s3.GetObjectInput, ...func(*s3.Options)) (*s3.GetObjectOutput, error)
	HeadBucket(context.Context, *s3.HeadBucketInput, ...func(*s3.Options)) (*s3.HeadBucketOutput, error)
}

type S3Store struct {
	client         s3API
	bucket         string
	prefix         string
	maxObjectBytes int64
}

type staticS3Credentials struct {
	accessKeyID     string
	secretAccessKey string
}

func (p staticS3Credentials) Retrieve(context.Context) (aws.Credentials, error) {
	if p.accessKeyID == "" || p.secretAccessKey == "" {
		return aws.Credentials{}, errors.New("S3 credentials are unavailable")
	}
	return aws.Credentials{
		AccessKeyID:     p.accessKeyID,
		SecretAccessKey: p.secretAccessKey,
		Source:          "lorawan-evidence-static",
	}, nil
}

func NewS3(settings S3Settings) (*S3Store, error) {
	endpoint, prefix, maxBytes, err := validateS3Settings(settings)
	if err != nil {
		return nil, err
	}

	caPEM, err := os.ReadFile(settings.CAFile)
	if err != nil {
		return nil, errors.New("read S3 CA file failed")
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(caPEM) {
		return nil, errors.New("S3 CA file contains no usable certificate")
	}

	transport := &http.Transport{
		Proxy:                 nil,
		DialContext:           (&net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          20,
		MaxIdleConnsPerHost:   10,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ResponseHeaderTimeout: 30 * time.Second,
		TLSClientConfig: &tls.Config{
			MinVersion: tls.VersionTLS12,
			RootCAs:    roots,
		},
	}
	httpClient := &http.Client{
		Transport: transport,
		Timeout:   60 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return errors.New("S3 HTTP redirects are disabled")
		},
	}

	client := s3.New(s3.Options{
		BaseEndpoint:               aws.String(endpoint.String()),
		Region:                     settings.Region,
		Credentials:                aws.NewCredentialsCache(staticS3Credentials{accessKeyID: settings.AccessKeyID, secretAccessKey: settings.SecretAccessKey}),
		HTTPClient:                 httpClient,
		UsePathStyle:               settings.UsePathStyle,
		RetryMaxAttempts:           3,
		RequestChecksumCalculation: aws.RequestChecksumCalculationWhenRequired,
		ResponseChecksumValidation: aws.ResponseChecksumValidationWhenRequired,
	})
	return &S3Store{client: client, bucket: settings.Bucket, prefix: prefix, maxObjectBytes: maxBytes}, nil
}

func (s *S3Store) Check(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	_, err := s.client.HeadBucket(ctx, &s3.HeadBucketInput{Bucket: aws.String(s.bucket)})
	if err != nil {
		return fmt.Errorf("S3 readiness check failed: code=%s", safeS3ErrorCode(err))
	}
	return nil
}

func (s *S3Store) PutIfAbsent(ctx context.Context, ref string, src io.Reader) (PutResult, error) {
	if err := validateS3Ref(ref); err != nil {
		return PutResult{}, err
	}
	if src == nil {
		return PutResult{}, errors.New("source reader is required")
	}
	body, err := readBounded(ctx, src, s.maxObjectBytes)
	if err != nil {
		return PutResult{}, err
	}
	metadata := metadataForBytes(ref, body)
	key := s.key(ref)

	for attempt := 1; attempt <= maxS3ConditionalTries; attempt++ {
		_, err = s.client.PutObject(ctx, &s3.PutObjectInput{
			Bucket:      aws.String(s.bucket),
			Key:         aws.String(key),
			Body:        bytes.NewReader(body),
			IfNoneMatch: aws.String("*"),
			ContentType: aws.String("application/octet-stream"),
			Metadata: map[string]string{
				"sha256": metadata.SHA256,
				"size":   strconv.FormatInt(metadata.Size, 10),
			},
		})
		if err == nil {
			return PutResult{Metadata: metadata, Created: true}, nil
		}

		code := safeS3ErrorCode(err)
		switch code {
		case "PreconditionFailed":
			return s.compareExisting(ctx, ref, metadata)
		case "ConditionalRequestConflict":
			result, compareErr := s.compareExisting(ctx, ref, metadata)
			if compareErr == nil || errors.Is(compareErr, ErrConflict) {
				return result, compareErr
			}
			if !errors.Is(compareErr, ErrNotFound) || attempt == maxS3ConditionalTries {
				return PutResult{}, compareErr
			}
			if err := sleepContext(ctx, time.Duration(attempt)*50*time.Millisecond); err != nil {
				return PutResult{}, err
			}
		default:
			return PutResult{}, fmt.Errorf("S3 conditional PutObject failed: code=%s", code)
		}
	}
	return PutResult{}, errors.New("S3 conditional PutObject retry budget exhausted")
}

func (s *S3Store) Get(ctx context.Context, ref string) (io.ReadCloser, Metadata, error) {
	body, metadata, err := s.readObject(ctx, ref)
	if err != nil {
		return nil, Metadata{}, err
	}
	return io.NopCloser(bytes.NewReader(body)), metadata, nil
}

func (s *S3Store) Stat(ctx context.Context, ref string) (Metadata, error) {
	_, metadata, err := s.readObject(ctx, ref)
	return metadata, err
}

func (s *S3Store) compareExisting(ctx context.Context, ref string, expected Metadata) (PutResult, error) {
	_, existing, err := s.readObject(ctx, ref)
	if err != nil {
		return PutResult{}, err
	}
	if existing.SHA256 != expected.SHA256 || existing.Size != expected.Size {
		return PutResult{}, fmt.Errorf("%w: ref=%s existing_sha256=%s new_sha256=%s", ErrConflict, ref, existing.SHA256, expected.SHA256)
	}
	return PutResult{Metadata: existing, Created: false}, nil
}

func (s *S3Store) readObject(ctx context.Context, ref string) ([]byte, Metadata, error) {
	if err := validateS3Ref(ref); err != nil {
		return nil, Metadata{}, err
	}
	out, err := s.client.GetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(s.key(ref))})
	if err != nil {
		if isS3NotFound(err) {
			return nil, Metadata{}, fmt.Errorf("%w: %s", ErrNotFound, ref)
		}
		return nil, Metadata{}, fmt.Errorf("S3 GetObject failed: code=%s", safeS3ErrorCode(err))
	}
	if out.Body == nil {
		return nil, Metadata{}, errors.New("S3 GetObject returned an empty response body")
	}
	defer out.Body.Close()
	body, err := readBounded(ctx, out.Body, s.maxObjectBytes)
	if err != nil {
		return nil, Metadata{}, err
	}
	return body, metadataForBytes(ref, body), nil
}

func (s *S3Store) key(ref string) string {
	if s.prefix == "" {
		return ref
	}
	return s.prefix + "/" + ref
}

func validateS3Settings(settings S3Settings) (*url.URL, string, int64, error) {
	endpointText := strings.TrimSpace(settings.Endpoint)
	endpoint, err := url.Parse(endpointText)
	if err != nil || endpoint.Scheme != "https" || endpoint.Hostname() == "" || endpoint.User != nil || endpoint.RawQuery != "" || endpoint.Fragment != "" {
		return nil, "", 0, errors.New("S3 endpoint must be one credential-free HTTPS origin")
	}
	if endpoint.Path != "" && endpoint.Path != "/" {
		return nil, "", 0, errors.New("S3 endpoint must not contain a path")
	}
	endpoint.Path = ""
	if strings.TrimSpace(settings.Region) == "" {
		return nil, "", 0, errors.New("S3 region is required")
	}
	bucket := strings.TrimSpace(settings.Bucket)
	if !s3BucketPattern.MatchString(bucket) || strings.Contains(bucket, "..") {
		return nil, "", 0, errors.New("S3 bucket must be a DNS-compatible bucket name")
	}
	prefix := strings.Trim(strings.TrimSpace(settings.Prefix), "/")
	if prefix != "" {
		if err := validateS3Ref(prefix); err != nil {
			return nil, "", 0, errors.New("S3 prefix must use the evidence object-reference grammar")
		}
	}
	if strings.TrimSpace(settings.AccessKeyID) == "" || strings.TrimSpace(settings.SecretAccessKey) == "" {
		return nil, "", 0, errors.New("explicit S3 access key and secret key are required")
	}
	if strings.TrimSpace(settings.CAFile) == "" {
		return nil, "", 0, errors.New("explicit S3 CA file is required for the scratch runtime image")
	}
	maxBytes := settings.MaxObjectBytes
	if maxBytes <= 0 {
		maxBytes = defaultS3ObjectLimit
	}
	if maxBytes > 64<<20 {
		return nil, "", 0, errors.New("S3 max object bytes must not exceed 64 MiB")
	}
	return endpoint, prefix, maxBytes, nil
}

func validateS3Ref(ref string) error {
	if ref == "" || strings.HasPrefix(ref, "/") || strings.Contains(ref, "\\") || strings.ContainsRune(ref, '\x00') {
		return fmt.Errorf("%w: %q", ErrInvalidRef, ref)
	}
	for _, part := range strings.Split(ref, "/") {
		if !s3RefPattern.MatchString(part) || part == "." || part == ".." {
			return fmt.Errorf("%w: %q", ErrInvalidRef, ref)
		}
	}
	return nil
}

func metadataForBytes(ref string, body []byte) Metadata {
	digest := sha256.Sum256(body)
	return Metadata{Ref: ref, SHA256: hex.EncodeToString(digest[:]), Size: int64(len(body))}
}

func readBounded(ctx context.Context, src io.Reader, maxBytes int64) ([]byte, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	n, err := copyWithContext(ctx, &buf, io.LimitReader(src, maxBytes+1))
	if err != nil {
		return nil, err
	}
	if n > maxBytes {
		return nil, fmt.Errorf("object exceeds maximum size of %d bytes", maxBytes)
	}
	return buf.Bytes(), nil
}

func safeS3ErrorCode(err error) string {
	var coded interface{ ErrorCode() string }
	if errors.As(err, &coded) {
		if code := strings.TrimSpace(coded.ErrorCode()); code != "" {
			return code
		}
	}
	return "unknown"
}

func isS3NotFound(err error) bool {
	switch safeS3ErrorCode(err) {
	case "NoSuchKey", "NotFound", "NoSuchObject":
		return true
	default:
		return false
	}
}

func sleepContext(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}
