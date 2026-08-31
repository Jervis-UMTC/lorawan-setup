package mqttcollector

import (
	"context"
	"encoding/hex"
	"testing"
	"time"

	"lorawan/evidence-services/cloud/internal/objectstore"
)

const syntheticUplinkHex = "0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef"

func TestProcessorUplinkProjectionAndDuplicateConvergence(t *testing.T) {
	store, err := objectstore.NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	repo := NewMemoryRepository()
	processor, err := NewProcessor(store, repo, DefaultRegion)
	if err != nil {
		t.Fatal(err)
	}
	payload, _ := hex.DecodeString(syntheticUplinkHex)
	observation := Observation{
		Topic:      "as923/gateway/0016c001f139a1cb/event/up",
		Payload:    payload,
		ReceivedAt: time.Date(2026, 8, 30, 1, 2, 3, 0, time.UTC),
	}
	first, created, err := processor.Process(context.Background(), observation)
	if err != nil || !created {
		t.Fatalf("first Process() created=%v err=%v", created, err)
	}
	const expectedKey = "1b6f3fa713301f56dff9682baddf6ff396e6c52c5ed9a5daceb31d0b2764521b"
	if first.CaptureKeySHA256 != expectedKey || first.ObjectRef != "mqtt/"+expectedKey+".event" {
		t.Fatalf("unexpected capture identity: %+v", first)
	}
	if !first.HasUplinkProjection || first.PHYPayloadSHA256 != "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a" || first.UplinkID != "16909060" || first.FrequencyHz != 923200000 || first.RSSIDbm != -72 || first.SNRDb != 8.5 || first.GatewayContextBase64 != "3q2+7w==" || first.CorrelationDigestSHA256 != "a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494" {
		t.Fatalf("unexpected uplink projection: %+v", first)
	}

	observation.ReceivedAt = observation.ReceivedAt.Add(250 * time.Millisecond)
	second, created, err := processor.Process(context.Background(), observation)
	if err != nil || created {
		t.Fatalf("duplicate Process() created=%v err=%v", created, err)
	}
	if second.CorrelationDigestSHA256 != first.CorrelationDigestSHA256 {
		t.Fatal("duplicate observation changed semantic correlation identity")
	}
}

func TestProcessorPersistsRawObjectBeforeRejectingInvalidUplink(t *testing.T) {
	store, _ := objectstore.NewFilesystem(t.TempDir())
	processor, _ := NewProcessor(store, NewMemoryRepository(), DefaultRegion)
	observation := Observation{
		Topic:      "as923/gateway/0016c001f139a1cb/event/up",
		Payload:    []byte{0x0a, 0x05, 0x01},
		ReceivedAt: time.Date(2026, 8, 30, 1, 2, 3, 0, time.UTC),
	}
	if _, _, err := processor.Process(context.Background(), observation); err == nil {
		t.Fatal("accepted malformed uplink Protobuf")
	}
}

func TestGatewayTopicValidation(t *testing.T) {
	valid := "as923/gateway/0016c001f139a1cb/event/up"
	if got, err := gatewayIDFromTopic(valid, DefaultRegion); err != nil || got != "0016c001f139a1cb" {
		t.Fatalf("valid topic gateway=%q err=%v", got, err)
	}
	for _, topic := range []string{
		"eu868/gateway/0016c001f139a1cb/event/up",
		"as923/gateway/0016C001F139A1CB/event/up",
		"as923/gateway/0016c001f139a1cb/command/down",
		"as923/gateway/0016c001f139a1cb/event/",
		"as923/gateway/0016c001f139a1cb/event/up/extra",
	} {
		if _, err := gatewayIDFromTopic(topic, DefaultRegion); err == nil {
			t.Fatalf("accepted invalid topic %q", topic)
		}
	}
}
