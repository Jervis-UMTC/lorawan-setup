package mqttcollector

import "time"

const (
	CollectorVersion   = "gateway-mqtt-evidence-collector-go-v1"
	DefaultTopicFilter = "as923/gateway/+/event/#"
	DefaultRegion      = "as923"
)

type Observation struct {
	Topic      string
	Payload    []byte
	ReceivedAt time.Time
}

type CaptureRecord struct {
	GatewayID               string
	MQTTTopic               string
	BrokerReceivedAt        time.Time
	CaptureKeySHA256        string
	SerializedEventSHA256   string
	HasUplinkProjection     bool
	PHYPayloadSHA256        string
	UplinkID                string
	FrequencyHz             int64
	RSSIDbm                 int32
	SNRDb                   float64
	GatewayContextBase64    string
	CorrelationDigestSHA256 string
	CollectorVersion        string
	ObjectRef               string
}
