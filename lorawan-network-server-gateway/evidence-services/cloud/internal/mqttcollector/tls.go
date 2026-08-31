package mqttcollector

import (
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"os"
	"time"
)

func LoadBrokerTLSConfig(caFile, serverName string, broker BrokerConfig) (*tls.Config, error) {
	caPEM, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("read MQTT CA: %w", err)
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(caPEM) {
		return nil, errors.New("MQTT CA file contains no usable certificate")
	}

	cfg := &tls.Config{
		MinVersion: tls.VersionTLS13,
		ServerName: serverName,
		RootCAs:    roots,
	}
	if broker.ClientCertFile != "" {
		cert, err := tls.LoadX509KeyPair(broker.ClientCertFile, broker.ClientKeyFile)
		if err != nil {
			return nil, errors.New("load MQTT collector client certificate/key failed")
		}
		if len(cert.Certificate) == 0 {
			return nil, errors.New("MQTT collector client certificate chain is empty")
		}
		leaf, err := x509.ParseCertificate(cert.Certificate[0])
		if err != nil {
			return nil, errors.New("parse MQTT collector client certificate failed")
		}
		now := time.Now()
		if now.Before(leaf.NotBefore) || now.After(leaf.NotAfter) {
			return nil, errors.New("MQTT collector client certificate is outside its validity window")
		}
		clientAuth := false
		for _, usage := range leaf.ExtKeyUsage {
			if usage == x509.ExtKeyUsageClientAuth || usage == x509.ExtKeyUsageAny {
				clientAuth = true
				break
			}
		}
		if !clientAuth {
			return nil, errors.New("MQTT collector certificate is not valid for clientAuth")
		}
		cfg.Certificates = []tls.Certificate{cert}
	}
	return cfg, nil
}
