package ingest

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestLoadDirectMTLSServerConfig(t *testing.T) {
	dir := t.TempDir()
	now := time.Date(2026, 8, 30, 0, 0, 0, 0, time.UTC)

	caKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	caTemplate := &x509.Certificate{
		SerialNumber:          big.NewInt(1),
		Subject:               pkix.Name{CommonName: "Evidence Test CA"},
		NotBefore:             now.Add(-time.Hour),
		NotAfter:              now.Add(time.Hour),
		IsCA:                  true,
		KeyUsage:              x509.KeyUsageCertSign,
		BasicConstraintsValid: true,
	}
	caDER, err := x509.CreateCertificate(rand.Reader, caTemplate, caTemplate, &caKey.PublicKey, caKey)
	if err != nil {
		t.Fatal(err)
	}

	serverKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	serverTemplate := &x509.Certificate{
		SerialNumber: big.NewInt(2),
		Subject:      pkix.Name{CommonName: "evidence.internal.test"},
		DNSNames:     []string{"evidence.internal.test"},
		NotBefore:    now.Add(-time.Hour),
		NotAfter:     now.Add(time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	serverDER, err := x509.CreateCertificate(rand.Reader, serverTemplate, caTemplate, &serverKey.PublicKey, caKey)
	if err != nil {
		t.Fatal(err)
	}

	certFile := filepath.Join(dir, "server.crt")
	keyFile := filepath.Join(dir, "server.key")
	caFile := filepath.Join(dir, "ca.crt")
	writePEM(t, certFile, "CERTIFICATE", serverDER, 0o600)
	keyDER, err := x509.MarshalPKCS8PrivateKey(serverKey)
	if err != nil {
		t.Fatal(err)
	}
	writePEM(t, keyFile, "PRIVATE KEY", keyDER, 0o600)
	writePEM(t, caFile, "CERTIFICATE", caDER, 0o600)

	cfg, err := LoadDirectMTLSServerConfig(ServerTLSFiles{
		CertificateFile: certFile,
		PrivateKeyFile:  keyFile,
		ClientCAFile:    caFile,
	}, now)
	if err != nil {
		t.Fatalf("LoadDirectMTLSServerConfig() error = %v", err)
	}
	if cfg.MinVersion != 0x0304 || cfg.ClientAuth != 4 || len(cfg.Certificates) != 1 || cfg.ClientCAs == nil {
		t.Fatalf("unexpected TLS config: min=%x clientAuth=%d certs=%d", cfg.MinVersion, cfg.ClientAuth, len(cfg.Certificates))
	}
	if got := DirectTLSFileSummary(ServerTLSFiles{PrivateKeyFile: keyFile})["private_key_file"]; got == keyFile {
		t.Fatal("DirectTLSFileSummary leaked private-key path")
	}
}

func writePEM(t *testing.T, path, blockType string, der []byte, mode os.FileMode) {
	t.Helper()
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := pem.Encode(f, &pem.Block{Type: blockType, Bytes: der}); err != nil {
		t.Fatal(err)
	}
}
