package logging

import (
	"bytes"
	"context"
	"strings"
	"testing"
)

func TestNewJSONHonorsLevel(t *testing.T) {
	var out bytes.Buffer
	log, err := NewJSON(&out, "warn")
	if err != nil {
		t.Fatalf("NewJSON() error = %v", err)
	}

	log.InfoContext(context.Background(), "hidden")
	log.WarnContext(context.Background(), "visible", "gateway_id", "0016c001f139a1cb")

	got := out.String()
	if strings.Contains(got, "hidden") {
		t.Fatalf("info message unexpectedly emitted: %s", got)
	}
	if !strings.Contains(got, "visible") || !strings.Contains(got, "gateway_id") {
		t.Fatalf("warn JSON missing expected fields: %s", got)
	}
}
