package mqttcapture

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
)

const Version = "mqtt-capture-v1"

func CaptureKey(topic string, payload []byte) (string, error) {
	if topic == "" {
		return "", fmt.Errorf("MQTT topic is required")
	}
	if len(payload) == 0 {
		return "", fmt.Errorf("MQTT payload is required")
	}

	topicBytes := []byte(topic)
	if uint64(len(topicBytes)) > uint64(1<<32-1) {
		return "", fmt.Errorf("MQTT topic is too large")
	}

	h := sha256.New()
	_, _ = h.Write([]byte(Version))
	_, _ = h.Write([]byte{0})

	var topicLen [4]byte
	binary.BigEndian.PutUint32(topicLen[:], uint32(len(topicBytes)))
	_, _ = h.Write(topicLen[:])
	_, _ = h.Write(topicBytes)

	var payloadLen [8]byte
	binary.BigEndian.PutUint64(payloadLen[:], uint64(len(payload)))
	_, _ = h.Write(payloadLen[:])
	_, _ = h.Write(payload)

	return hex.EncodeToString(h.Sum(nil)), nil
}
