package uplinkcorrelation

import (
	"encoding/hex"
	"testing"
)

const fixtureUplinkHex = "0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef"

func TestSyntheticUplinkFixedVector(t *testing.T) {
	payload, err := hex.DecodeString(fixtureUplinkHex)
	if err != nil {
		t.Fatal(err)
	}
	projection, err := DecodeUplinkFrame(payload, "0016c001f139a1cb")
	if err != nil {
		t.Fatal(err)
	}
	if projection.GatewayID != "0016c001f139a1cb" || projection.UplinkID != 16909060 || projection.FrequencyHz != 923200000 || projection.RSSIDbm != -72 || projection.SNRDb != 8.5 {
		t.Fatalf("unexpected projection: %+v", projection)
	}
	if got := hex.EncodeToString(projection.PHYPayload); got != "01020304" {
		t.Fatalf("PHYPayload=%s", got)
	}
	if got := hex.EncodeToString(projection.GatewayContext); got != "deadbeef" {
		t.Fatalf("context=%s", got)
	}
	if got := projection.PHYPayloadSHA256(); got != "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a" {
		t.Fatalf("PHYPayload SHA=%s", got)
	}
	digest, err := projection.CorrelationDigest()
	if err != nil {
		t.Fatal(err)
	}
	if digest != "a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494" {
		t.Fatalf("correlation digest=%s", digest)
	}
}

func TestUplinkRejectsWrongGatewayAndMalformedWire(t *testing.T) {
	payload, _ := hex.DecodeString(fixtureUplinkHex)
	if _, err := DecodeUplinkFrame(payload, "0000000000000001"); err == nil {
		t.Fatal("accepted MQTT-topic / Protobuf Gateway EUI mismatch")
	}
	if _, err := DecodeUplinkFrame([]byte{0x0a, 0x05, 0x01}, "0016c001f139a1cb"); err == nil {
		t.Fatal("accepted truncated Protobuf")
	}
}
