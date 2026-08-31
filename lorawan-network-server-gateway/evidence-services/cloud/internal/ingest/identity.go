package ingest

import (
	"crypto/x509"
	"fmt"
	"net/http"
)

type IdentityProvider interface {
	GatewayID(r *http.Request) (string, error)
}

type TLSClientCertificateIdentity struct{}

func (TLSClientCertificateIdentity) GatewayID(r *http.Request) (string, error) {
	if r.TLS == nil || len(r.TLS.PeerCertificates) == 0 || len(r.TLS.VerifiedChains) == 0 {
		return "", fmt.Errorf("verified client certificate is required")
	}
	cert := r.TLS.PeerCertificates[0]
	if !hasClientAuth(cert) {
		return "", fmt.Errorf("client certificate is not clientAuth-scoped")
	}
	gatewayID, err := normalizeGatewayID(cert.Subject.CommonName)
	if err != nil {
		return "", fmt.Errorf("client certificate Common Name must be one Gateway EUI: %w", err)
	}
	return gatewayID, nil
}

func hasClientAuth(cert *x509.Certificate) bool {
	for _, usage := range cert.ExtKeyUsage {
		if usage == x509.ExtKeyUsageClientAuth {
			return true
		}
	}
	return false
}
