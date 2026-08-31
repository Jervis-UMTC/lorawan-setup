package ingest

import (
	"bytes"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"lorawan/evidence-services/cloud/internal/objectstore"
)

const testGatewayID = "0016c001f139a1cb"

type staticIdentity string

func (s staticIdentity) GatewayID(*http.Request) (string, error) { return string(s), nil }

func newTestHandler(t *testing.T) (*Handler, *MemoryRepository) {
	t.Helper()
	store, err := objectstore.NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}
	repo := NewMemoryRepository()
	h, err := NewHandler(store, repo, staticIdentity(testGatewayID), 1<<20)
	if err != nil {
		t.Fatalf("NewHandler() error = %v", err)
	}
	return h, repo
}

func TestCheckpointCreateRetryAndConflict(t *testing.T) {
	h, _ := newTestHandler(t)
	body := map[string]any{
		"checkpoint_version": CheckpointVersion,
		"gateway_id":         testGatewayID,
		"segment_id":         53,
		"last_sequence":      53000,
		"last_record_hash":   hex64("a"),
		"segment_hash":       hex64("b"),
		"created_at":         "2000-01-01T00:10:00Z",
	}

	first := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", body)
	if first.Code != http.StatusCreated {
		t.Fatalf("first checkpoint status = %d body=%s", first.Code, first.Body.String())
	}
	firstReceipt := decodeReceipt(t, first)
	if !firstReceipt.Created || firstReceipt.ArtifactType != "checkpoint" || firstReceipt.GatewayID != testGatewayID || firstReceipt.SegmentID != 53 || firstReceipt.LastSequence != 53000 || firstReceipt.CheckpointDigest == "" || firstReceipt.ReceiptID == "" || firstReceipt.ServerReceivedAt == "" {
		t.Fatalf("first checkpoint receipt = %+v", firstReceipt)
	}
	second := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", body)
	if second.Code != http.StatusOK {
		t.Fatalf("retry checkpoint status = %d body=%s", second.Code, second.Body.String())
	}
	secondReceipt := decodeReceipt(t, second)
	if secondReceipt.Created || secondReceipt.ReceiptID != firstReceipt.ReceiptID || secondReceipt.ServerReceivedAt != firstReceipt.ServerReceivedAt || secondReceipt.CheckpointDigest != firstReceipt.CheckpointDigest {
		t.Fatalf("retry checkpoint receipt changed: first=%+v second=%+v", firstReceipt, secondReceipt)
	}

	body["segment_hash"] = hex64("c")
	conflict := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", body)
	if conflict.Code != http.StatusConflict {
		t.Fatalf("conflicting checkpoint status = %d body=%s", conflict.Code, conflict.Body.String())
	}
}

func TestCheckpointRegressionRejected(t *testing.T) {
	h, _ := newTestHandler(t)
	newer := map[string]any{
		"checkpoint_version": CheckpointVersion,
		"gateway_id":         testGatewayID,
		"segment_id":         10,
		"last_sequence":      100,
		"last_record_hash":   hex64("a"),
		"segment_hash":       hex64("b"),
		"created_at":         "2000-01-01T00:10:00Z",
	}
	if resp := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", newer); resp.Code != http.StatusCreated {
		t.Fatalf("newer checkpoint status = %d body=%s", resp.Code, resp.Body.String())
	}

	older := map[string]any{
		"checkpoint_version": CheckpointVersion,
		"gateway_id":         testGatewayID,
		"segment_id":         9,
		"last_sequence":      99,
		"last_record_hash":   hex64("c"),
		"segment_hash":       hex64("d"),
		"created_at":         "2000-01-01T00:09:00Z",
	}
	resp := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", older)
	if resp.Code != http.StatusConflict || !bytes.Contains(resp.Body.Bytes(), []byte("checkpoint_regression")) {
		t.Fatalf("regression status = %d body=%s", resp.Code, resp.Body.String())
	}
}

func TestCheckpointExactOldRetryAfterNewerRemainsIdempotent(t *testing.T) {
	h, _ := newTestHandler(t)
	older := map[string]any{
		"checkpoint_version": CheckpointVersion,
		"gateway_id":         testGatewayID,
		"segment_id":         1,
		"last_sequence":      10,
		"last_record_hash":   hex64("a"),
		"segment_hash":       hex64("b"),
		"created_at":         "2000-01-01T00:01:00Z",
	}
	first := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", older)
	if first.Code != http.StatusCreated {
		t.Fatalf("older checkpoint create status = %d body=%s", first.Code, first.Body.String())
	}
	firstReceipt := decodeReceipt(t, first)

	newer := map[string]any{
		"checkpoint_version": CheckpointVersion,
		"gateway_id":         testGatewayID,
		"segment_id":         2,
		"last_sequence":      20,
		"last_record_hash":   hex64("c"),
		"segment_hash":       hex64("d"),
		"created_at":         "2000-01-01T00:02:00Z",
	}
	if resp := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", newer); resp.Code != http.StatusCreated {
		t.Fatalf("newer checkpoint status = %d body=%s", resp.Code, resp.Body.String())
	}

	retry := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", older)
	if retry.Code != http.StatusOK {
		t.Fatalf("exact old retry status = %d body=%s", retry.Code, retry.Body.String())
	}
	retryReceipt := decodeReceipt(t, retry)
	if retryReceipt.Created || retryReceipt.ReceiptID != firstReceipt.ReceiptID || retryReceipt.ServerReceivedAt != firstReceipt.ServerReceivedAt {
		t.Fatalf("exact old retry receipt changed: first=%+v retry=%+v", firstReceipt, retryReceipt)
	}
}

func TestSegmentCreateRetryAndConflict(t *testing.T) {
	h, _ := newTestHandler(t)
	object := []byte("closed-segment-fixture")
	digest := sha256.Sum256(object)
	body := map[string]any{
		"segment_version":       SegmentVersion,
		"gateway_id":            testGatewayID,
		"segment_id":            53,
		"first_sequence":        52001,
		"last_sequence":         53000,
		"record_count":          1000,
		"previous_segment_hash": hex64("1"),
		"final_record_hash":     hex64("2"),
		"segment_hash":          hex64("3"),
		"object_sha256":         hex.EncodeToString(digest[:]),
		"object_base64":         base64.StdEncoding.EncodeToString(object),
	}

	first := requestJSON(t, h, http.MethodPut, "/v1/gateways/"+testGatewayID+"/segments/53", body)
	if first.Code != http.StatusCreated {
		t.Fatalf("first segment status = %d body=%s", first.Code, first.Body.String())
	}
	firstReceipt := decodeReceipt(t, first)
	if !firstReceipt.Created || firstReceipt.ArtifactType != "segment" || firstReceipt.GatewayID != testGatewayID || firstReceipt.SegmentID != 53 || firstReceipt.LastSequence != 53000 || firstReceipt.SegmentHash != hex64("3") || firstReceipt.ObjectSHA256 != hex.EncodeToString(digest[:]) || firstReceipt.ReceiptID == "" || firstReceipt.ServerReceivedAt == "" {
		t.Fatalf("first segment receipt = %+v", firstReceipt)
	}
	second := requestJSON(t, h, http.MethodPut, "/v1/gateways/"+testGatewayID+"/segments/53", body)
	if second.Code != http.StatusOK {
		t.Fatalf("retry segment status = %d body=%s", second.Code, second.Body.String())
	}
	secondReceipt := decodeReceipt(t, second)
	if secondReceipt.Created || secondReceipt.ReceiptID != firstReceipt.ReceiptID || secondReceipt.ServerReceivedAt != firstReceipt.ServerReceivedAt || secondReceipt.SegmentHash != firstReceipt.SegmentHash || secondReceipt.ObjectSHA256 != firstReceipt.ObjectSHA256 {
		t.Fatalf("retry segment receipt changed: first=%+v second=%+v", firstReceipt, secondReceipt)
	}

	body["final_record_hash"] = hex64("4")
	conflict := requestJSON(t, h, http.MethodPut, "/v1/gateways/"+testGatewayID+"/segments/53", body)
	if conflict.Code != http.StatusConflict {
		t.Fatalf("conflicting segment metadata status = %d body=%s", conflict.Code, conflict.Body.String())
	}
}

func TestSegmentRejectsInvalidGenesisPlacement(t *testing.T) {
	h, _ := newTestHandler(t)
	object := []byte("closed-segment-fixture")
	digest := sha256.Sum256(object)
	body := map[string]any{
		"segment_version":       SegmentVersion,
		"gateway_id":            testGatewayID,
		"segment_id":            2,
		"first_sequence":        2,
		"last_sequence":         2,
		"record_count":          1,
		"previous_segment_hash": "GENESIS",
		"final_record_hash":     hex64("2"),
		"segment_hash":          hex64("3"),
		"object_sha256":         hex.EncodeToString(digest[:]),
		"object_base64":         base64.StdEncoding.EncodeToString(object),
	}
	resp := requestJSON(t, h, http.MethodPut, "/v1/gateways/"+testGatewayID+"/segments/2", body)
	if resp.Code != http.StatusBadRequest {
		t.Fatalf("later GENESIS segment status = %d body=%s", resp.Code, resp.Body.String())
	}
}

func TestSegmentRejectsObjectDigestMismatch(t *testing.T) {
	h, _ := newTestHandler(t)
	body := map[string]any{
		"segment_version":       SegmentVersion,
		"gateway_id":            testGatewayID,
		"segment_id":            1,
		"first_sequence":        1,
		"last_sequence":         1,
		"record_count":          1,
		"previous_segment_hash": "GENESIS",
		"final_record_hash":     hex64("2"),
		"segment_hash":          hex64("3"),
		"object_sha256":         hex64("4"),
		"object_base64":         base64.StdEncoding.EncodeToString([]byte("different")),
	}
	resp := requestJSON(t, h, http.MethodPut, "/v1/gateways/"+testGatewayID+"/segments/1", body)
	if resp.Code != http.StatusBadRequest {
		t.Fatalf("digest mismatch status = %d body=%s", resp.Code, resp.Body.String())
	}
}

func TestGatewayIdentityMismatchRejected(t *testing.T) {
	store, _ := objectstore.NewFilesystem(t.TempDir())
	h, _ := NewHandler(store, NewMemoryRepository(), staticIdentity("0000000000000001"), 1<<20)
	resp := requestJSON(t, h, http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", map[string]any{})
	if resp.Code != http.StatusForbidden {
		t.Fatalf("identity mismatch status = %d", resp.Code)
	}
}

func TestRejectsUnexpectedContentTypeTrailingJSONAndOversizedBody(t *testing.T) {
	h, _ := newTestHandler(t)
	validBody, err := json.Marshal(CheckpointRequest{
		CheckpointVersion: CheckpointVersion,
		GatewayID:         testGatewayID,
		SegmentID:         1,
		LastSequence:      1,
		LastRecordHash:    hex64("a"),
		SegmentHash:       hex64("b"),
		CreatedAt:         "2000-01-01T00:10:00Z",
	})
	if err != nil {
		t.Fatal(err)
	}

	req := httptest.NewRequest(http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", bytes.NewReader(validBody))
	req.Header.Set("Content-Type", "text/plain")
	resp := httptest.NewRecorder()
	h.ServeHTTP(resp, req)
	if resp.Code != http.StatusUnsupportedMediaType {
		t.Fatalf("content-type status = %d", resp.Code)
	}

	trailingBody := append(append([]byte(nil), validBody...), []byte(" {}")...)
	req = httptest.NewRequest(http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", bytes.NewReader(trailingBody))
	req.Header.Set("Content-Type", "application/json")
	resp = httptest.NewRecorder()
	h.ServeHTTP(resp, req)
	if resp.Code != http.StatusBadRequest {
		t.Fatalf("trailing JSON status = %d body=%s", resp.Code, resp.Body.String())
	}

	store, _ := objectstore.NewFilesystem(t.TempDir())
	small, _ := NewHandler(store, NewMemoryRepository(), staticIdentity(testGatewayID), 32)
	req = httptest.NewRequest(http.MethodPost, "/v1/gateways/"+testGatewayID+"/checkpoints", bytes.NewReader(validBody))
	req.Header.Set("Content-Type", "application/json")
	resp = httptest.NewRecorder()
	small.ServeHTTP(resp, req)
	if resp.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("oversized body status = %d body=%s", resp.Code, resp.Body.String())
	}
}

func TestReadiness(t *testing.T) {
	h, _ := newTestHandler(t)
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	resp := httptest.NewRecorder()
	h.ServeHTTP(resp, req)
	if resp.Code != http.StatusOK {
		t.Fatalf("ready status = %d body=%s", resp.Code, resp.Body.String())
	}
}

func TestTLSClientCertificateIdentity(t *testing.T) {
	cert := &x509.Certificate{
		Subject:     pkix.Name{CommonName: testGatewayID},
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.TLS = &tls.ConnectionState{
		PeerCertificates: []*x509.Certificate{cert},
		VerifiedChains:   [][]*x509.Certificate{{cert}},
	}
	got, err := (TLSClientCertificateIdentity{}).GatewayID(req)
	if err != nil || got != testGatewayID {
		t.Fatalf("GatewayID() = %q, %v", got, err)
	}

	cert.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}
	if _, err := (TLSClientCertificateIdentity{}).GatewayID(req); err == nil {
		t.Fatal("GatewayID accepted non-clientAuth certificate")
	}
}

func TestReceiptFixedVectors(t *testing.T) {
	serverTime := time.Date(2000, 1, 1, 0, 0, 5, 0, time.UTC)
	checkpoint := CheckpointRecord{
		GatewayID:        testGatewayID,
		SegmentID:        1,
		LastSequence:     2,
		CheckpointDigest: "3f7cc53ee0161e73389a8db5764082aa2b293b53f2187023c2107fa1ba935d36",
	}
	checkpointReceipt := checkpointReceipt(checkpoint, Acceptance{Created: true, ServerReceivedAt: serverTime})
	if checkpointReceipt.ReceiptID != "99e21a0f3fb156e5b9b0b553235698852eb624deb138b74da64e54615ea1333c" || checkpointReceipt.ServerReceivedAt != "2000-01-01T00:00:05.000Z" {
		t.Fatalf("checkpoint receipt vector = %+v", checkpointReceipt)
	}
	segment := SegmentRecord{
		GatewayID:    testGatewayID,
		SegmentID:    1,
		LastSequence: 2,
		SegmentHash:  "722638f91ff762185aff7c002044911226661c0efc8b70ce71b22a7f168bae90",
		ObjectSHA256: "9f34ad301bc0b1b806e2cb0c39a4baaa7509e79b8822f7f367a08720835403f1",
	}
	segmentReceipt := segmentReceipt(segment, Acceptance{Created: true, ServerReceivedAt: serverTime})
	if segmentReceipt.ReceiptID != "a5a6378baffe6a4b58aa82bc3875e5534c7964669c2a213e37e47768720930fb" || segmentReceipt.ServerReceivedAt != "2000-01-01T00:00:05.000Z" {
		t.Fatalf("segment receipt vector = %+v", segmentReceipt)
	}
}

func TestCheckpointDigestIgnoresJSONFormatting(t *testing.T) {
	requestA := CheckpointRequest{
		CheckpointVersion: CheckpointVersion, GatewayID: testGatewayID, SegmentID: 1, LastSequence: 2,
		LastRecordHash: hex64("a"), SegmentHash: hex64("b"), CreatedAt: "2000-01-01T00:10:00Z",
	}
	requestB := requestA
	requestB.CreatedAt = "2000-01-01T08:10:00+08:00"
	a, err := validateCheckpoint(requestA, testGatewayID, "a")
	if err != nil {
		t.Fatal(err)
	}
	b, err := validateCheckpoint(requestB, testGatewayID, "b")
	if err != nil {
		t.Fatal(err)
	}
	if a.CheckpointDigest != b.CheckpointDigest {
		t.Fatalf("semantic checkpoint digest changed: %s != %s", a.CheckpointDigest, b.CheckpointDigest)
	}
	const expected = "fde615a8eb264090d324fe5642e0992748de9cc4f2d73cbd8f43459e12792903"
	if a.CheckpointDigest != expected {
		t.Fatalf("checkpoint digest = %s, want fixed vector %s", a.CheckpointDigest, expected)
	}
}

func decodeReceipt(t *testing.T, response *httptest.ResponseRecorder) Receipt {
	t.Helper()
	var receipt Receipt
	if err := json.Unmarshal(response.Body.Bytes(), &receipt); err != nil {
		t.Fatalf("decode receipt: %v body=%s", err, response.Body.String())
	}
	return receipt
}

func requestJSON(t *testing.T, h http.Handler, method, path string, value any) *httptest.ResponseRecorder {
	t.Helper()
	body, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(method, path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp := httptest.NewRecorder()
	h.ServeHTTP(resp, req)
	return resp
}

func hex64(char string) string {
	return string(bytes.Repeat([]byte(char), 64))
}
