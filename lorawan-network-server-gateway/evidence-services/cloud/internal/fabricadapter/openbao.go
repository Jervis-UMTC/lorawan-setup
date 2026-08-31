package fabricadapter

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

var (
	versionedSignaturePattern = regexp.MustCompile(`^[^:]+:v([1-9][0-9]*):.+$`)
	ErrSignatureRejected      = errors.New("OpenBao Transit signature verification rejected")
)

type EvidenceSigner interface {
	Sign(context.Context, []byte) (signature string, signingKeyID string, err error)
	Verify(context.Context, []byte, string, string) error
}

type OpenBaoClient struct {
	baseURL      string
	mount        string
	key          string
	roleIDFile   string
	secretIDFile string
	httpClient   *http.Client
	mu           sync.Mutex
	token        string
}

func NewOpenBaoClient(cfg Config) (*OpenBaoClient, error) {
	parsed, err := url.Parse(cfg.OpenBaoAddr)
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.User != nil {
		return nil, errors.New("OPENBAO_ADDR must be an HTTPS URL without embedded credentials")
	}
	if parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, errors.New("OPENBAO_ADDR must not contain query or fragment components")
	}
	caPEM, err := os.ReadFile(cfg.OpenBaoCAFile)
	if err != nil {
		return nil, errors.New("read OpenBao CA file failed")
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(caPEM) {
		return nil, errors.New("OpenBao CA file contains no usable certificate")
	}
	transport := &http.Transport{
		TLSClientConfig:   &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: roots},
		ForceAttemptHTTP2: true,
	}
	return &OpenBaoClient{
		baseURL:      strings.TrimRight(cfg.OpenBaoAddr, "/"),
		mount:        cfg.OpenBaoTransitMount,
		key:          cfg.OpenBaoTransitKey,
		roleIDFile:   cfg.OpenBaoRoleIDFile,
		secretIDFile: cfg.OpenBaoSecretIDFile,
		httpClient:   &http.Client{Transport: transport, Timeout: 15 * time.Second},
	}, nil
}

func (c *OpenBaoClient) Sign(ctx context.Context, canonical []byte) (string, string, error) {
	body := map[string]any{
		"input":                base64.StdEncoding.EncodeToString(canonical),
		"prehashed":            false,
		"marshaling_algorithm": "asn1",
	}
	var response struct {
		Data struct {
			Signature string `json:"signature"`
		} `json:"data"`
	}
	if err := c.authedJSON(ctx, http.MethodPost, "/v1/"+url.PathEscape(c.mount)+"/sign/"+url.PathEscape(c.key)+"/sha2-256", body, &response); err != nil {
		return "", "", err
	}
	if response.Data.Signature == "" {
		return "", "", errors.New("OpenBao Transit sign returned no signature")
	}
	version, err := signatureVersion(response.Data.Signature)
	if err != nil {
		return "", "", err
	}
	return response.Data.Signature, "openbao:transit:" + c.key + ":v" + strconv.Itoa(version), nil
}

func (c *OpenBaoClient) Verify(ctx context.Context, canonical []byte, signature, signingKeyID string) error {
	version, err := signatureVersion(signature)
	if err != nil {
		return err
	}
	expectedKeyID := "openbao:transit:" + c.key + ":v" + strconv.Itoa(version)
	if signingKeyID != expectedKeyID {
		return fmt.Errorf("stored OpenBao key ID %q does not match signature version", signingKeyID)
	}
	body := map[string]any{
		"input":                base64.StdEncoding.EncodeToString(canonical),
		"signature":            signature,
		"prehashed":            false,
		"marshaling_algorithm": "asn1",
	}
	var response struct {
		Data struct {
			Valid bool `json:"valid"`
		} `json:"data"`
	}
	if err := c.authedJSON(ctx, http.MethodPost, "/v1/"+url.PathEscape(c.mount)+"/verify/"+url.PathEscape(c.key)+"/sha2-256", body, &response); err != nil {
		return err
	}
	if !response.Data.Valid {
		return ErrSignatureRejected
	}
	return nil
}

func signatureVersion(signature string) (int, error) {
	matches := versionedSignaturePattern.FindStringSubmatch(signature)
	if len(matches) != 2 {
		return 0, errors.New("OpenBao Transit returned malformed versioned signature")
	}
	version, err := strconv.Atoi(matches[1])
	if err != nil || version < 1 {
		return 0, errors.New("OpenBao Transit signature contains invalid key version")
	}
	return version, nil
}

func (c *OpenBaoClient) authedJSON(ctx context.Context, method, path string, input, output any) error {
	for attempt := 0; attempt < 2; attempt++ {
		token, err := c.currentToken(ctx)
		if err != nil {
			return err
		}
		status, err := c.doJSON(ctx, method, path, token, input, output)
		if err != nil {
			return err
		}
		if status >= 200 && status < 300 {
			return nil
		}
		if status == http.StatusForbidden && attempt == 0 {
			c.mu.Lock()
			if c.token == token {
				c.token = ""
			}
			c.mu.Unlock()
			continue
		}
		return &OpenBaoHTTPError{StatusCode: status}
	}
	return errors.New("OpenBao authentication retry exhausted")
}

func (c *OpenBaoClient) currentToken(ctx context.Context) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.token != "" {
		return c.token, nil
	}
	roleID, err := readCredentialFile(c.roleIDFile)
	if err != nil {
		return "", fmt.Errorf("read OpenBao RoleID: %w", err)
	}
	secretID, err := readCredentialFile(c.secretIDFile)
	if err != nil {
		return "", fmt.Errorf("read OpenBao SecretID: %w", err)
	}
	var response struct {
		Auth struct {
			ClientToken string `json:"client_token"`
		} `json:"auth"`
	}
	status, err := c.doJSON(ctx, http.MethodPost, "/v1/auth/approle/login", "", map[string]string{
		"role_id": roleID, "secret_id": secretID,
	}, &response)
	if err != nil {
		return "", err
	}
	if status < 200 || status >= 300 || response.Auth.ClientToken == "" {
		return "", &OpenBaoHTTPError{StatusCode: status}
	}
	c.token = response.Auth.ClientToken
	return c.token, nil
}

func (c *OpenBaoClient) doJSON(ctx context.Context, method, path, token string, input, output any) (int, error) {
	payload, err := json.Marshal(input)
	if err != nil {
		return 0, errors.New("encode OpenBao request failed")
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bytes.NewReader(payload))
	if err != nil {
		return 0, errors.New("create OpenBao request failed")
	}
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("X-Vault-Token", token)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("OpenBao request failed: %w", err)
	}
	defer resp.Body.Close()
	limited := io.LimitReader(resp.Body, 1<<20)
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		if err := json.NewDecoder(limited).Decode(output); err != nil {
			return resp.StatusCode, errors.New("decode OpenBao response failed")
		}
	} else {
		_, _ = io.Copy(io.Discard, limited)
	}
	return resp.StatusCode, nil
}

type OpenBaoHTTPError struct {
	StatusCode int
}

func (e *OpenBaoHTTPError) Error() string {
	return fmt.Sprintf("OpenBao API returned HTTP %d", e.StatusCode)
}

func IsTransientOpenBaoError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	var httpErr *OpenBaoHTTPError
	if errors.As(err, &httpErr) {
		return httpErr.StatusCode == http.StatusRequestTimeout || httpErr.StatusCode == http.StatusTooManyRequests || httpErr.StatusCode >= 500
	}
	var netErr interface{ Timeout() bool }
	return errors.As(err, &netErr) && netErr.Timeout()
}

func readCredentialFile(path string) (string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return "", err
	}
	if info.Size() <= 0 || info.Size() > 64<<10 {
		return "", errors.New("credential file size is invalid")
	}
	contents, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	value := strings.TrimSpace(string(contents))
	if value == "" || strings.ContainsAny(value, "\r\n") {
		return "", errors.New("credential file must contain exactly one non-empty value")
	}
	return value, nil
}
