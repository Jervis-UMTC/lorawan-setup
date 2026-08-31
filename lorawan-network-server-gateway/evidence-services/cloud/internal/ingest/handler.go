package ingest

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"lorawan/evidence-services/cloud/internal/objectstore"
)

const DefaultMaxBodyBytes int64 = 8 << 20

var (
	gatewayIDPattern = regexp.MustCompile(`^[0-9a-f]{16}$`)
	hashPattern      = regexp.MustCompile(`^[0-9a-f]{64}$`)
)

type Handler struct {
	store        objectstore.Store
	repository   Repository
	identity     IdentityProvider
	maxBodyBytes int64
}

func NewHandler(store objectstore.Store, repository Repository, identity IdentityProvider, maxBodyBytes int64) (*Handler, error) {
	if store == nil || repository == nil || identity == nil {
		return nil, fmt.Errorf("store, repository, and identity provider are required")
	}
	if maxBodyBytes <= 0 {
		maxBodyBytes = DefaultMaxBodyBytes
	}
	return &Handler{store: store, repository: repository, identity: identity, maxBodyBytes: maxBodyBytes}, nil
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/livez" {
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"status": "alive"})
		return
	}
	if r.URL.Path == "/readyz" {
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		if err := h.repository.Ping(r.Context()); err != nil {
			writeError(w, http.StatusServiceUnavailable, "metadata_unavailable")
			return
		}
		if err := h.store.Check(r.Context()); err != nil {
			writeError(w, http.StatusServiceUnavailable, "object_store_unavailable")
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"status": "ready"})
		return
	}

	parts := splitPath(r.URL.Path)
	if len(parts) < 4 || parts[0] != "v1" || parts[1] != "gateways" {
		writeError(w, http.StatusNotFound, "not_found")
		return
	}
	pathGatewayID, err := normalizeGatewayID(parts[2])
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_gateway_id")
		return
	}
	clientGatewayID, err := h.identity.GatewayID(r)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "verified_client_identity_required")
		return
	}
	if clientGatewayID != pathGatewayID {
		writeError(w, http.StatusForbidden, "gateway_identity_mismatch")
		return
	}

	switch {
	case len(parts) == 4 && parts[3] == "checkpoints":
		if r.Method != http.MethodPost {
			writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		h.handleCheckpoint(w, r, pathGatewayID)
	case len(parts) == 5 && parts[3] == "segments":
		if r.Method != http.MethodPut {
			writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		h.handleSegment(w, r, pathGatewayID, parts[4])
	default:
		writeError(w, http.StatusNotFound, "not_found")
	}
}

func (h *Handler) handleCheckpoint(w http.ResponseWriter, r *http.Request, gatewayID string) {
	if !isJSON(r.Header.Get("Content-Type")) {
		writeError(w, http.StatusUnsupportedMediaType, "content_type_must_be_application_json")
		return
	}
	var req CheckpointRequest
	if err := decodeJSONBody(w, r, h.maxBodyBytes, &req); err != nil {
		writeDecodeError(w, err)
		return
	}

	record, err := validateCheckpoint(req, gatewayID, requestID(r))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_checkpoint")
		return
	}
	record.ClientIdentity = gatewayID

	acceptance, err := h.repository.PutCheckpoint(r.Context(), record)
	if errors.Is(err, ErrConflict) {
		writeError(w, http.StatusConflict, "checkpoint_conflict")
		return
	}
	if errors.Is(err, ErrRegression) {
		writeError(w, http.StatusConflict, "checkpoint_regression")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "checkpoint_persistence_failed")
		return
	}
	status := http.StatusOK
	if acceptance.Created {
		status = http.StatusCreated
	}
	writeJSON(w, status, checkpointReceipt(record, acceptance))
}

func (h *Handler) handleSegment(w http.ResponseWriter, r *http.Request, gatewayID, segmentIDText string) {
	if !isJSON(r.Header.Get("Content-Type")) {
		writeError(w, http.StatusUnsupportedMediaType, "content_type_must_be_application_json")
		return
	}
	pathSegmentID, err := strconv.ParseInt(segmentIDText, 10, 64)
	if err != nil || pathSegmentID < 1 {
		writeError(w, http.StatusBadRequest, "invalid_segment_id")
		return
	}

	var req SegmentRequest
	if err := decodeJSONBody(w, r, h.maxBodyBytes, &req); err != nil {
		writeDecodeError(w, err)
		return
	}
	record, objectBytes, err := validateSegment(req, gatewayID, pathSegmentID)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_segment")
		return
	}

	putResult, err := h.store.PutIfAbsent(r.Context(), record.ObjectRef, bytes.NewReader(objectBytes))
	if errors.Is(err, objectstore.ErrConflict) {
		writeError(w, http.StatusConflict, "segment_object_conflict")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "segment_object_persistence_failed")
		return
	}
	if putResult.Metadata.SHA256 != record.ObjectSHA256 {
		writeError(w, http.StatusInternalServerError, "segment_object_hash_mismatch_after_write")
		return
	}

	metadataAcceptance, err := h.repository.PutSegment(r.Context(), record)
	if errors.Is(err, ErrConflict) {
		writeError(w, http.StatusConflict, "segment_metadata_conflict")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "segment_metadata_persistence_failed")
		return
	}

	created := putResult.Created || metadataAcceptance.Created
	metadataAcceptance.Created = created
	status := http.StatusOK
	if created {
		status = http.StatusCreated
	}
	writeJSON(w, status, segmentReceipt(record, metadataAcceptance))
}

func validateCheckpoint(req CheckpointRequest, pathGatewayID, reqID string) (CheckpointRecord, error) {
	gatewayID, err := normalizeGatewayID(req.GatewayID)
	if err != nil || gatewayID != pathGatewayID {
		return CheckpointRecord{}, fmt.Errorf("gateway mismatch")
	}
	if req.CheckpointVersion != CheckpointVersion || req.SegmentID < 1 || req.LastSequence < 1 {
		return CheckpointRecord{}, fmt.Errorf("invalid checkpoint version or sequence")
	}
	lastRecordHash, err := normalizeHash(req.LastRecordHash)
	if err != nil {
		return CheckpointRecord{}, err
	}
	segmentHash, err := normalizeHash(req.SegmentHash)
	if err != nil {
		return CheckpointRecord{}, err
	}
	createdAt, err := time.Parse(time.RFC3339Nano, req.CreatedAt)
	if err != nil {
		return CheckpointRecord{}, fmt.Errorf("invalid created_at: %w", err)
	}
	createdAt = createdAt.UTC()

	digest := checkpointDigest(gatewayID, req.SegmentID, req.LastSequence, lastRecordHash, segmentHash, createdAt)
	return CheckpointRecord{
		GatewayID: gatewayID, SegmentID: req.SegmentID, LastSequence: req.LastSequence,
		LastRecordHash: lastRecordHash, SegmentHash: segmentHash, GatewayCreatedAt: createdAt,
		RequestID: reqID, CheckpointDigest: digest,
	}, nil
}

func validateSegment(req SegmentRequest, pathGatewayID string, pathSegmentID int64) (SegmentRecord, []byte, error) {
	gatewayID, err := normalizeGatewayID(req.GatewayID)
	if err != nil || gatewayID != pathGatewayID || req.SegmentID != pathSegmentID {
		return SegmentRecord{}, nil, fmt.Errorf("gateway or segment identity mismatch")
	}
	if req.SegmentVersion != SegmentVersion || req.SegmentID < 1 || req.FirstSequence < 1 || req.LastSequence < req.FirstSequence || req.RecordCount <= 0 {
		return SegmentRecord{}, nil, fmt.Errorf("invalid segment metadata")
	}
	previousSegmentHash, err := normalizePreviousSegmentHash(req.PreviousSegmentHash, req.SegmentID)
	if err != nil {
		return SegmentRecord{}, nil, err
	}
	finalRecordHash, err := normalizeHash(req.FinalRecordHash)
	if err != nil {
		return SegmentRecord{}, nil, err
	}
	segmentHash, err := normalizeHash(req.SegmentHash)
	if err != nil {
		return SegmentRecord{}, nil, err
	}
	objectSHA, err := normalizeHash(req.ObjectSHA256)
	if err != nil {
		return SegmentRecord{}, nil, err
	}
	objectBytes, err := base64.StdEncoding.Strict().DecodeString(req.ObjectBase64)
	if err != nil || len(objectBytes) == 0 {
		return SegmentRecord{}, nil, fmt.Errorf("invalid object_base64")
	}
	actual := sha256.Sum256(objectBytes)
	if hex.EncodeToString(actual[:]) != objectSHA {
		return SegmentRecord{}, nil, fmt.Errorf("object SHA-256 mismatch")
	}

	ref := fmt.Sprintf("segments/%s/%d.segment", gatewayID, req.SegmentID)
	return SegmentRecord{
		GatewayID: gatewayID, SegmentID: req.SegmentID, FirstSequence: req.FirstSequence,
		LastSequence: req.LastSequence, RecordCount: req.RecordCount,
		PreviousSegmentHash: previousSegmentHash, FinalRecordHash: finalRecordHash,
		SegmentHash: segmentHash, ObjectRef: ref, ObjectSHA256: objectSHA,
	}, objectBytes, nil
}

func checkpointReceipt(record CheckpointRecord, acceptance Acceptance) Receipt {
	serverTime := formatReceiptTime(acceptance.ServerReceivedAt)
	return Receipt{
		Status: "accepted", Created: acceptance.Created, ReceiptVersion: ReceiptVersion,
		ArtifactType: "checkpoint", GatewayID: record.GatewayID, SegmentID: record.SegmentID,
		LastSequence: record.LastSequence, CheckpointDigest: record.CheckpointDigest,
		ReceiptID:        receiptID("checkpoint", record.GatewayID, record.SegmentID, record.LastSequence, record.CheckpointDigest, "", serverTime),
		ServerReceivedAt: serverTime,
	}
}

func segmentReceipt(record SegmentRecord, acceptance Acceptance) Receipt {
	serverTime := formatReceiptTime(acceptance.ServerReceivedAt)
	return Receipt{
		Status: "accepted", Created: acceptance.Created, ReceiptVersion: ReceiptVersion,
		ArtifactType: "segment", GatewayID: record.GatewayID, SegmentID: record.SegmentID,
		LastSequence: record.LastSequence, SegmentHash: record.SegmentHash, ObjectSHA256: record.ObjectSHA256,
		ReceiptID:        receiptID("segment", record.GatewayID, record.SegmentID, record.LastSequence, record.SegmentHash, record.ObjectSHA256, serverTime),
		ServerReceivedAt: serverTime,
	}
}

func receiptID(artifactType, gatewayID string, segmentID, lastSequence int64, primaryDigest, objectSHA, serverTime string) string {
	parts := []string{
		ReceiptVersion,
		artifactType,
		gatewayID,
		strconv.FormatInt(segmentID, 10),
		strconv.FormatInt(lastSequence, 10),
		primaryDigest,
		objectSHA,
		serverTime,
	}
	digest := sha256.Sum256([]byte(strings.Join(parts, "\x00")))
	return hex.EncodeToString(digest[:])
}

func formatReceiptTime(value time.Time) string {
	return value.UTC().Format("2006-01-02T15:04:05.000Z")
}

func checkpointDigest(gatewayID string, segmentID, lastSequence int64, lastRecordHash, segmentHash string, createdAt time.Time) string {
	parts := []string{
		CheckpointVersion,
		gatewayID,
		strconv.FormatInt(segmentID, 10),
		strconv.FormatInt(lastSequence, 10),
		lastRecordHash,
		segmentHash,
		createdAt.UTC().Format(time.RFC3339Nano),
	}
	digest := sha256.Sum256([]byte(strings.Join(parts, "\x00")))
	return hex.EncodeToString(digest[:])
}

func normalizeGatewayID(value string) (string, error) {
	value = strings.ToLower(strings.TrimSpace(value))
	if !gatewayIDPattern.MatchString(value) {
		return "", fmt.Errorf("invalid Gateway EUI")
	}
	return value, nil
}

func normalizeHash(value string) (string, error) {
	value = strings.ToLower(strings.TrimSpace(value))
	if !hashPattern.MatchString(value) {
		return "", fmt.Errorf("invalid SHA-256")
	}
	return value, nil
}

func normalizePreviousSegmentHash(value string, segmentID int64) (string, error) {
	value = strings.TrimSpace(value)
	if segmentID == 1 {
		if value != "GENESIS" {
			return "", fmt.Errorf("segment 1 previous_segment_hash must be GENESIS")
		}
		return value, nil
	}
	if value == "GENESIS" {
		return "", fmt.Errorf("GENESIS previous_segment_hash is only valid for segment 1")
	}
	return normalizeHash(value)
}

func splitPath(path string) []string {
	trimmed := strings.Trim(path, "/")
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, "/")
}

func isJSON(contentType string) bool {
	mediaType, _, err := mime.ParseMediaType(contentType)
	return err == nil && mediaType == "application/json"
}

var errBodyTooLarge = errors.New("request body too large")

func decodeJSONBody(w http.ResponseWriter, r *http.Request, maxBytes int64, dst any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBytes)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dst); err != nil {
		var maxErr *http.MaxBytesError
		if errors.As(err, &maxErr) {
			return errBodyTooLarge
		}
		return err
	}

	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return fmt.Errorf("multiple JSON values are not allowed")
		}
		var maxErr *http.MaxBytesError
		if errors.As(err, &maxErr) {
			return errBodyTooLarge
		}
		return err
	}
	return nil
}

func writeDecodeError(w http.ResponseWriter, err error) {
	if errors.Is(err, errBodyTooLarge) {
		writeError(w, http.StatusRequestEntityTooLarge, "request_body_too_large")
		return
	}
	writeError(w, http.StatusBadRequest, "invalid_json")
}

func requestID(r *http.Request) string {
	value := strings.TrimSpace(r.Header.Get("X-Request-ID"))
	if len(value) > 128 {
		return value[:128]
	}
	return value
}

func writeError(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]any{"status": "error", "error": code})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
