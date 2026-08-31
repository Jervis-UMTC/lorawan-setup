package mqttcapture

import "testing"

func TestCaptureKeyDeterministic(t *testing.T) {
	topic := "as923/gateway/0016c001f139a1cb/event/up"
	payload := []byte("{\"phyPayload\":\"AQI=\"}")

	first, err := CaptureKey(topic, payload)
	if err != nil {
		t.Fatalf("CaptureKey() error = %v", err)
	}
	second, err := CaptureKey(topic, payload)
	if err != nil {
		t.Fatalf("CaptureKey() second error = %v", err)
	}
	if first != second {
		t.Fatalf("capture key changed: %s != %s", first, second)
	}
	if len(first) != 64 {
		t.Fatalf("capture key length = %d, want 64", len(first))
	}
	const expected = "de1a848838d6d27e02261e0cc37d3478e70dfd5e0e1d381927349dfe803ead74"
	if first != expected {
		t.Fatalf("capture key = %s, want fixed vector %s", first, expected)
	}
}

func TestCaptureKeySeparatesTopicAndPayload(t *testing.T) {
	a, _ := CaptureKey("a/b", []byte("c"))
	b, _ := CaptureKey("a", []byte("b/c"))
	if a == b {
		t.Fatal("length-prefixed capture contract produced ambiguous identity")
	}
}

func TestCaptureKeyRejectsMissingInput(t *testing.T) {
	if _, err := CaptureKey("", []byte("x")); err == nil {
		t.Fatal("CaptureKey accepted empty topic")
	}
	if _, err := CaptureKey("topic", nil); err == nil {
		t.Fatal("CaptureKey accepted empty payload")
	}
}
