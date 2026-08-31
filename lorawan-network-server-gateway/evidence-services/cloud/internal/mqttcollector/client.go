package mqttcollector

import (
	"context"
	"errors"
	"log/slog"
	"net/url"
	"time"

	"github.com/eclipse/paho.golang/autopaho"
	"github.com/eclipse/paho.golang/paho"
)

type Session struct {
	manager *autopaho.ConnectionManager
	status  *SessionStatus
}

func StartSession(ctx context.Context, cfg RuntimeConfig, broker BrokerConfig, processor *Processor, status *SessionStatus, logger *slog.Logger) (*Session, error) {
	if processor == nil || status == nil || logger == nil {
		return nil, errors.New("collector processor, status, and logger are required")
	}
	serverURL, err := url.Parse(broker.URL)
	if err != nil {
		return nil, errors.New("parse MQTT broker URL failed")
	}
	tlsConfig, err := LoadBrokerTLSConfig(cfg.TLSCAFile, cfg.TLSServerName, broker)
	if err != nil {
		return nil, err
	}

	clientConfig := autopaho.ClientConfig{
		ServerUrls:                    []*url.URL{serverURL},
		TlsCfg:                        tlsConfig,
		KeepAlive:                     cfg.KeepAliveSeconds,
		CleanStartOnInitialConnection: false,
		SessionExpiryInterval:         cfg.SessionExpirySeconds,
		ConnectUsername:               broker.Username,
		ConnectPassword:               []byte(broker.Password),
		OnConnectionUp: func(cm *autopaho.ConnectionManager, _ *paho.Connack) {
			status.setConnected(true)
			subCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()
			_, err := cm.Subscribe(subCtx, &paho.Subscribe{Subscriptions: []paho.SubscribeOptions{{Topic: cfg.TopicFilter, QoS: 1}}})
			if err != nil {
				status.captureError(errors.New("MQTT subscription failed"), false)
				logger.Error("mqtt_subscription_failed", "broker", broker.Label, "client_id", broker.ClientID)
				return
			}
			status.setSubscribed(true)
			logger.Info("mqtt_session_ready", "broker", broker.Label, "client_id", broker.ClientID)
		},
		OnConnectionDown: func() bool {
			status.setConnected(false)
			return true
		},
		OnConnectError: func(error) {
			status.setConnected(false)
			logger.Warn("mqtt_connect_failed", "broker", broker.Label, "client_id", broker.ClientID)
		},
		ClientConfig: paho.ClientConfig{
			ClientID:                   broker.ClientID,
			EnableManualAcknowledgment: true,
			SendAcksInterval:           100 * time.Millisecond,
			OnPublishReceived: []func(paho.PublishReceived) (bool, error){
				func(received paho.PublishReceived) (bool, error) {
					observation := Observation{
						Topic:      received.Packet.Topic,
						Payload:    append([]byte(nil), received.Packet.Payload...),
						ReceivedAt: time.Now().UTC(),
					}
					record, created, err := processor.Process(ctx, observation)
					if err != nil {
						fatal := errors.Is(err, ErrCaptureConflict)
						status.captureError(err, fatal)
						logger.Error("mqtt_capture_persist_failed", "broker", broker.Label, "gateway_id", gatewayIDForLog(observation.Topic, cfg.Region), "fatal", fatal)
						// Manual ACK is deliberately withheld. QoS1 evidence is never
						// acknowledged before immutable object + metadata persistence.
						return true, err
					}
					if received.Packet.QoS > 0 {
						if err := received.Client.Ack(received.Packet); err != nil {
							status.captureError(errors.New("MQTT manual acknowledgment failed"), false)
							return true, err
						}
					}
					status.captureOK()
					logger.Debug("mqtt_capture_persisted", "broker", broker.Label, "gateway_id", record.GatewayID, "capture_key_sha256", record.CaptureKeySHA256, "created", created)
					return true, nil
				},
			},
			OnClientError: func(error) {
				status.setConnected(false)
			},
		},
	}

	manager, err := autopaho.NewConnection(ctx, clientConfig)
	if err != nil {
		return nil, errors.New("start MQTT connection manager failed")
	}
	return &Session{manager: manager, status: status}, nil
}

func (s *Session) AwaitConnection(ctx context.Context) error { return s.manager.AwaitConnection(ctx) }
func (s *Session) Done() <-chan struct{}                     { return s.manager.Done() }

func gatewayIDForLog(topic, region string) string {
	gatewayID, err := gatewayIDFromTopic(topic, region)
	if err != nil {
		return "invalid"
	}
	return gatewayID
}
