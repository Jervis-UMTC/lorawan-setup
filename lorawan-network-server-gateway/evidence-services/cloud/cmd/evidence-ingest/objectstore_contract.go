package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
	"time"

	"lorawan/evidence-services/cloud/internal/config"
	"lorawan/evidence-services/cloud/internal/objectstore"
)

const objectStoreContractVersion = "objectstore-contract-v1"

type objectStoreContractResult struct {
	Ref      string
	SHA256   string
	Size     int64
	RaceRef  string
	RaceSHA  string
	RaceSize int64
}

func runObjectStoreContractCommand(args []string) error {
	if len(args) == 0 {
		return errors.New("missing command")
	}
	store, err := loadObjectStoreContractStore()
	if err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	switch args[0] {
	case "objectstore-contract-write":
		if len(args) != 1 {
			return errors.New("usage: gateway-evidence-ingest objectstore-contract-write")
		}
		ref, err := newObjectStoreContractRef()
		if err != nil {
			return err
		}
		result, err := exerciseObjectStoreWriteContract(ctx, store, ref)
		if err != nil {
			return err
		}
		fmt.Println("OBJECTSTORE_CONTRACT=PASS")
		fmt.Printf("OBJECTSTORE_ACCEPTANCE_REF=%s\n", result.Ref)
		fmt.Printf("OBJECTSTORE_ACCEPTANCE_SHA256=%s\n", result.SHA256)
		fmt.Printf("OBJECTSTORE_ACCEPTANCE_SIZE=%d\n", result.Size)
		fmt.Printf("OBJECTSTORE_CONCURRENT_REF=%s\n", result.RaceRef)
		fmt.Printf("OBJECTSTORE_CONCURRENT_SHA256=%s\n", result.RaceSHA)
		fmt.Printf("OBJECTSTORE_CONCURRENT_SIZE=%d\n", result.RaceSize)
		fmt.Println("OBJECTSTORE_FIXTURE_RETENTION=KEEP")
		return nil

	case "objectstore-contract-verify":
		if len(args) != 4 {
			return errors.New("usage: gateway-evidence-ingest objectstore-contract-verify <ref> <sha256> <size>")
		}
		size, err := strconv.ParseInt(args[3], 10, 64)
		if err != nil || size < 0 {
			return errors.New("expected object size must be a non-negative integer")
		}
		if err := verifyObjectStoreReference(ctx, store, args[1], strings.ToLower(args[2]), size); err != nil {
			return err
		}
		fmt.Println("OBJECTSTORE_READ_VERIFY=PASS")
		fmt.Printf("OBJECTSTORE_ACCEPTANCE_REF=%s\n", args[1])
		fmt.Printf("OBJECTSTORE_ACCEPTANCE_SHA256=%s\n", strings.ToLower(args[2]))
		fmt.Printf("OBJECTSTORE_ACCEPTANCE_SIZE=%d\n", size)
		return nil

	default:
		return fmt.Errorf("unsupported command %q", args[0])
	}
}

func loadObjectStoreContractStore() (objectstore.Store, error) {
	if strings.ToLower(strings.TrimSpace(os.Getenv("EVIDENCE_OBJECTSTORE_BACKEND"))) != "s3" {
		return nil, errors.New("object-store contract command requires EVIDENCE_OBJECTSTORE_BACKEND=s3")
	}

	maxBytes := config.DefaultMaxBodyBytes
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_MAX_BODY_BYTES")); raw != "" {
		v, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || v <= 0 || v > 64<<20 {
			return nil, errors.New("EVIDENCE_MAX_BODY_BYTES must be a positive integer not greater than 67108864")
		}
		maxBytes = v
	}
	usePathStyle := false
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_S3_USE_PATH_STYLE")); raw != "" {
		v, err := strconv.ParseBool(raw)
		if err != nil {
			return nil, errors.New("EVIDENCE_S3_USE_PATH_STYLE must be true or false")
		}
		usePathStyle = v
	}

	return objectstore.NewS3(objectstore.S3Settings{
		Endpoint:        strings.TrimSpace(os.Getenv("EVIDENCE_S3_ENDPOINT")),
		Region:          strings.TrimSpace(os.Getenv("EVIDENCE_S3_REGION")),
		Bucket:          strings.TrimSpace(os.Getenv("EVIDENCE_S3_BUCKET")),
		Prefix:          strings.TrimSpace(os.Getenv("EVIDENCE_S3_PREFIX")),
		AccessKeyID:     strings.TrimSpace(os.Getenv("EVIDENCE_S3_ACCESS_KEY_ID")),
		SecretAccessKey: strings.TrimSpace(os.Getenv("EVIDENCE_S3_SECRET_ACCESS_KEY")),
		CAFile:          strings.TrimSpace(os.Getenv("EVIDENCE_S3_CA_FILE")),
		UsePathStyle:    usePathStyle,
		MaxObjectBytes:  maxBytes,
	})
}

func newObjectStoreContractRef() (string, error) {
	entropy := make([]byte, 8)
	if _, err := rand.Read(entropy); err != nil {
		return "", errors.New("generate object-store acceptance identity failed")
	}
	return fmt.Sprintf(
		"commissioning/%s/%s-%s",
		objectStoreContractVersion,
		time.Now().UTC().Format("20060102T150405Z"),
		hex.EncodeToString(entropy),
	), nil
}

func exerciseObjectStoreWriteContract(ctx context.Context, store objectstore.Store, ref string) (objectStoreContractResult, error) {
	if store == nil {
		return objectStoreContractResult{}, errors.New("object store is required")
	}
	if err := store.Check(ctx); err != nil {
		return objectStoreContractResult{}, fmt.Errorf("object-store readiness failed: %w", err)
	}

	body := []byte("lorawan-evidence-objectstore-contract-v1\nref=" + ref + "\n")
	first, err := store.PutIfAbsent(ctx, ref, bytes.NewReader(body))
	if err != nil {
		return objectStoreContractResult{}, fmt.Errorf("first create-only write failed: %w", err)
	}
	if !first.Created {
		return objectStoreContractResult{}, errors.New("first create-only write did not create a new object")
	}

	second, err := store.PutIfAbsent(ctx, ref, bytes.NewReader(body))
	if err != nil {
		return objectStoreContractResult{}, fmt.Errorf("identical retry failed: %w", err)
	}
	if second.Created || second.Metadata != first.Metadata {
		return objectStoreContractResult{}, errors.New("identical retry was not idempotent")
	}

	if _, err := store.PutIfAbsent(ctx, ref, strings.NewReader("conflicting-body")); !errors.Is(err, objectstore.ErrConflict) {
		return objectStoreContractResult{}, fmt.Errorf("conflicting retry did not return ErrConflict: %w", err)
	}
	if err := verifyObjectStoreReference(ctx, store, ref, first.Metadata.SHA256, first.Metadata.Size); err != nil {
		return objectStoreContractResult{}, fmt.Errorf("read-back verification failed: %w", err)
	}

	raceRef := ref + "-race"
	raceBodies := [][]byte{
		[]byte("race-a:" + raceRef),
		[]byte("race-b:" + raceRef),
	}
	type raceOutcome struct {
		result objectstore.PutResult
		err    error
	}
	outcomes := make(chan raceOutcome, len(raceBodies))
	for _, raceBody := range raceBodies {
		raceBody := append([]byte(nil), raceBody...)
		go func() {
			result, putErr := store.PutIfAbsent(ctx, raceRef, bytes.NewReader(raceBody))
			outcomes <- raceOutcome{result: result, err: putErr}
		}()
	}

	created := 0
	conflicts := 0
	for range raceBodies {
		outcome := <-outcomes
		switch {
		case outcome.err == nil && outcome.result.Created:
			created++
		case errors.Is(outcome.err, objectstore.ErrConflict):
			conflicts++
		default:
			return objectStoreContractResult{}, fmt.Errorf("unexpected concurrent conditional-write result: %w", outcome.err)
		}
	}
	if created != 1 || conflicts != 1 {
		return objectStoreContractResult{}, fmt.Errorf("concurrent conditional write expected one create and one conflict, got creates=%d conflicts=%d", created, conflicts)
	}

	r, raceMetadata, err := store.Get(ctx, raceRef)
	if err != nil {
		return objectStoreContractResult{}, fmt.Errorf("read concurrent fixture failed: %w", err)
	}
	raceBytes, readErr := io.ReadAll(r)
	closeErr := r.Close()
	if readErr != nil {
		return objectStoreContractResult{}, fmt.Errorf("read concurrent fixture body failed: %w", readErr)
	}
	if closeErr != nil {
		return objectStoreContractResult{}, errors.New("close concurrent fixture body failed")
	}
	if !bytes.Equal(raceBytes, raceBodies[0]) && !bytes.Equal(raceBytes, raceBodies[1]) {
		return objectStoreContractResult{}, errors.New("concurrent fixture contains bytes from neither submitted object")
	}
	if err := verifyObjectStoreReference(ctx, store, raceRef, raceMetadata.SHA256, raceMetadata.Size); err != nil {
		return objectStoreContractResult{}, fmt.Errorf("concurrent fixture verification failed: %w", err)
	}

	return objectStoreContractResult{
		Ref:      ref,
		SHA256:   first.Metadata.SHA256,
		Size:     first.Metadata.Size,
		RaceRef:  raceRef,
		RaceSHA:  raceMetadata.SHA256,
		RaceSize: raceMetadata.Size,
	}, nil
}

func verifyObjectStoreReference(ctx context.Context, store objectstore.Store, ref, expectedSHA256 string, expectedSize int64) error {
	if store == nil {
		return errors.New("object store is required")
	}
	if len(expectedSHA256) != 64 {
		return errors.New("expected SHA-256 must contain exactly 64 hexadecimal characters")
	}
	if _, err := hex.DecodeString(expectedSHA256); err != nil {
		return errors.New("expected SHA-256 must be lowercase/uppercase hexadecimal")
	}
	if expectedSize < 0 {
		return errors.New("expected size must not be negative")
	}
	if err := store.Check(ctx); err != nil {
		return fmt.Errorf("object-store readiness failed: %w", err)
	}

	stat, err := store.Stat(ctx, ref)
	if err != nil {
		return fmt.Errorf("stat acceptance object failed: %w", err)
	}
	if stat.SHA256 != expectedSHA256 || stat.Size != expectedSize {
		return fmt.Errorf("acceptance object stat mismatch: ref=%s", ref)
	}

	r, metadata, err := store.Get(ctx, ref)
	if err != nil {
		return fmt.Errorf("get acceptance object failed: %w", err)
	}
	body, readErr := io.ReadAll(r)
	closeErr := r.Close()
	if readErr != nil {
		return fmt.Errorf("read acceptance object failed: %w", readErr)
	}
	if closeErr != nil {
		return errors.New("close acceptance object failed")
	}
	digest := sha256.Sum256(body)
	actualSHA := hex.EncodeToString(digest[:])
	if metadata.SHA256 != expectedSHA256 || metadata.Size != expectedSize || actualSHA != expectedSHA256 || int64(len(body)) != expectedSize {
		return fmt.Errorf("acceptance object read-back mismatch: ref=%s", ref)
	}
	return nil
}
