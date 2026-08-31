package mqttcollector

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
)

const (
	DefaultBrokerTLSName        = "mqtt.internal.lorawan.com"
	DefaultBroker1URL           = "tls://10.104.0.2:8884"
	DefaultBroker2URL           = "tls://10.104.0.4:8884"
	DefaultSessionExpiry uint32 = 604800
	DefaultKeepAlive     uint16 = 30
)

type BrokerConfig struct {
	Label          string
	URL            string
	ClientID       string
	Username       string
	Password       string
	ClientCertFile string
	ClientKeyFile  string
}

type RuntimeConfig struct {
	Region               string
	TopicFilter          string
	TLSCAFile            string
	TLSServerName        string
	SessionExpirySeconds uint32
	KeepAliveSeconds     uint16
	Broker1              BrokerConfig
	Broker2              BrokerConfig
}

func LoadRuntimeConfig() (RuntimeConfig, error) {
	cfg := RuntimeConfig{
		Region:               valueOrDefault("EVIDENCE_MQTT_REGION", DefaultRegion),
		TopicFilter:          valueOrDefault("EVIDENCE_MQTT_TOPIC_FILTER", DefaultTopicFilter),
		TLSCAFile:            strings.TrimSpace(os.Getenv("EVIDENCE_MQTT_CA_FILE")),
		TLSServerName:        valueOrDefault("EVIDENCE_MQTT_TLS_SERVER_NAME", DefaultBrokerTLSName),
		SessionExpirySeconds: DefaultSessionExpiry,
		KeepAliveSeconds:     DefaultKeepAlive,
		Broker1:              loadBroker("BROKER1", "broker-1", DefaultBroker1URL),
		Broker2:              loadBroker("BROKER2", "broker-2", DefaultBroker2URL),
	}
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_MQTT_SESSION_EXPIRY_SECONDS")); raw != "" {
		v, err := strconv.ParseUint(raw, 10, 32)
		if err != nil || v == 0 || v == 0xffffffff {
			return RuntimeConfig{}, errors.New("EVIDENCE_MQTT_SESSION_EXPIRY_SECONDS must be from 1 through 4294967294")
		}
		cfg.SessionExpirySeconds = uint32(v)
	}
	if raw := strings.TrimSpace(os.Getenv("EVIDENCE_MQTT_KEEPALIVE_SECONDS")); raw != "" {
		v, err := strconv.ParseUint(raw, 10, 16)
		if err != nil || v < 10 {
			return RuntimeConfig{}, errors.New("EVIDENCE_MQTT_KEEPALIVE_SECONDS must be at least 10")
		}
		cfg.KeepAliveSeconds = uint16(v)
	}
	if err := cfg.Validate(); err != nil {
		return RuntimeConfig{}, err
	}
	return cfg, nil
}

func (c RuntimeConfig) Validate() error {
	if c.Region != DefaultRegion || c.TopicFilter != DefaultTopicFilter {
		return fmt.Errorf("collector source is frozen to region %q and filter %q", DefaultRegion, DefaultTopicFilter)
	}
	if strings.TrimSpace(c.TLSCAFile) == "" {
		return errors.New("MQTT CA file is required")
	}
	if c.TLSServerName != DefaultBrokerTLSName {
		return fmt.Errorf("collector TLS identity is frozen to %q", DefaultBrokerTLSName)
	}
	if c.SessionExpirySeconds == 0 || c.KeepAliveSeconds < 10 {
		return errors.New("persistent MQTT session expiry and keepalive are required")
	}
	if err := validateBroker(c.Broker1); err != nil {
		return fmt.Errorf("broker-1: %w", err)
	}
	if err := validateBroker(c.Broker2); err != nil {
		return fmt.Errorf("broker-2: %w", err)
	}
	if c.Broker1.URL != DefaultBroker1URL || c.Broker2.URL != DefaultBroker2URL {
		return fmt.Errorf("collector backends are frozen to %s and %s", DefaultBroker1URL, DefaultBroker2URL)
	}
	if c.Broker1.URL == c.Broker2.URL {
		return errors.New("collector must connect to two distinct broker backends")
	}
	if c.Broker1.ClientID == c.Broker2.ClientID {
		return errors.New("collector broker sessions must use distinct client IDs")
	}
	return nil
}

func (c RuntimeConfig) PublicSummary() map[string]any {
	return map[string]any{
		"region":                   c.Region,
		"topic_filter":             c.TopicFilter,
		"tls_server_name":          c.TLSServerName,
		"ca_file":                  c.TLSCAFile,
		"session_expiry_seconds":   c.SessionExpirySeconds,
		"keepalive_seconds":        c.KeepAliveSeconds,
		"broker_1_url":             c.Broker1.URL,
		"broker_1_client_id":       c.Broker1.ClientID,
		"broker_1_auth_configured": brokerAuthConfigured(c.Broker1),
		"broker_2_url":             c.Broker2.URL,
		"broker_2_client_id":       c.Broker2.ClientID,
		"broker_2_auth_configured": brokerAuthConfigured(c.Broker2),
	}
}

func loadBroker(prefix, label, defaultURL string) BrokerConfig {
	base := "EVIDENCE_MQTT_" + prefix + "_"
	return BrokerConfig{
		Label:          label,
		URL:            valueOrDefault(base+"URL", defaultURL),
		ClientID:       strings.TrimSpace(os.Getenv(base + "CLIENT_ID")),
		Username:       strings.TrimSpace(os.Getenv(base + "USERNAME")),
		Password:       os.Getenv(base + "PASSWORD"),
		ClientCertFile: strings.TrimSpace(os.Getenv(base + "CLIENT_CERT_FILE")),
		ClientKeyFile:  strings.TrimSpace(os.Getenv(base + "CLIENT_KEY_FILE")),
	}
}

func validateBroker(b BrokerConfig) error {
	u, err := url.Parse(b.URL)
	if err != nil || u.Scheme != "tls" || u.Host == "" || u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" {
		return errors.New("broker URL must be one tls://host:port endpoint without credentials/path/query")
	}
	if strings.TrimSpace(b.ClientID) == "" {
		return errors.New("client ID is required")
	}
	if (b.Username == "") != (b.Password == "") {
		return errors.New("username and password must be supplied together")
	}
	if (b.ClientCertFile == "") != (b.ClientKeyFile == "") {
		return errors.New("client certificate and key must be supplied together")
	}
	if !brokerAuthConfigured(b) {
		return errors.New("dedicated broker authentication is required")
	}
	return nil
}

func brokerAuthConfigured(b BrokerConfig) bool {
	return (b.Username != "" && b.Password != "") || (b.ClientCertFile != "" && b.ClientKeyFile != "")
}

func valueOrDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}
