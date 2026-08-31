package ingest

import (
	"crypto/tls"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"
	"os"
	"time"
)

type ServerTLSFiles struct {
	CertificateFile string
	PrivateKeyFile  string
	ClientCAFile    string
}

func LoadDirectMTLSServerConfig(files ServerTLSFiles, now time.Time) (*tls.Config, error) {
	if files.CertificateFile == "" || files.PrivateKeyFile == "" || files.ClientCAFile == "" {
		return nil, errors.New("evidence server certificate, private key, and client CA files are required")
	}

	pair, err := tls.LoadX509KeyPair(files.CertificateFile, files.PrivateKeyFile)
	if err != nil {
		return nil, errors.New("load evidence server certificate/key failed")
	}
	certPEM, err := os.ReadFile(files.CertificateFile)
	if err != nil {
		return nil, errors.New("read evidence server certificate failed")
	}
	block, _ := pem.Decode(certPEM)
	if block == nil || block.Type != "CERTIFICATE" {
		return nil, errors.New("evidence server certificate file does not begin with a certificate")
	}
	leaf, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, errors.New("parse evidence server certificate failed")
	}
	if now.Before(leaf.NotBefore) || !now.Before(leaf.NotAfter) {
		return nil, errors.New("evidence server certificate is not currently valid")
	}
	if !hasExtKeyUsage(leaf, x509.ExtKeyUsageServerAuth) {
		return nil, errors.New("evidence server certificate is not serverAuth-scoped")
	}
	pair.Leaf = leaf

	clientCAPEM, err := os.ReadFile(files.ClientCAFile)
	if err != nil {
		return nil, errors.New("read evidence client CA failed")
	}
	clientCAs := x509.NewCertPool()
	if !clientCAs.AppendCertsFromPEM(clientCAPEM) {
		return nil, errors.New("evidence client CA file contains no usable certificate")
	}

	return &tls.Config{
		MinVersion:   tls.VersionTLS13,
		Certificates: []tls.Certificate{pair},
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    clientCAs,
	}, nil
}

func hasExtKeyUsage(cert *x509.Certificate, expected x509.ExtKeyUsage) bool {
	for _, usage := range cert.ExtKeyUsage {
		if usage == expected {
			return true
		}
	}
	return false
}

func DirectTLSFileSummary(files ServerTLSFiles) map[string]string {
	return map[string]string{
		"certificate_file": files.CertificateFile,
		"private_key_file": redactPrivateKeyPath(files.PrivateKeyFile),
		"client_ca_file":   files.ClientCAFile,
	}
}

func redactPrivateKeyPath(path string) string {
	if path == "" {
		return ""
	}
	return fmt.Sprintf("configured:%d-bytes-path", len(path))
}
