package verifier

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"strconv"
	"strings"
	"time"
)

const (
	journalVersion = "gateway-journal-v1"
	segmentVersion = "gateway-journal-segment-v1"
	journalSource  = "concentratord"
	journalGenesis = "GENESIS"
)

type journalHeaderLine struct {
	CreatedAt           string `json:"created_at"`
	FirstSequence       int64  `json:"first_sequence"`
	GatewayID           string `json:"gateway_id"`
	JournalVersion      string `json:"journal_version"`
	Kind                string `json:"kind"`
	PreviousSegmentHash string `json:"previous_segment_hash"`
	SegmentID           int64  `json:"segment_id"`
	SegmentVersion      string `json:"segment_version"`
}

type journalRecordBody struct {
	BootID               string      `json:"boot_id"`
	CapturedAt           string      `json:"captured_at"`
	FrequencyHz          int64       `json:"frequency_hz"`
	GatewayContextBase64 *string     `json:"gateway_context_base64"`
	GatewayID            string      `json:"gateway_id"`
	JournalVersion       string      `json:"journal_version"`
	PHYPayloadBase64     string      `json:"phy_payload_base64"`
	PreviousRecordHash   string      `json:"previous_record_hash"`
	RSSIDbm              int64       `json:"rssi_dbm"`
	Sequence             int64       `json:"sequence"`
	SNRDb                json.Number `json:"snr_db"`
	Source               string      `json:"source"`
	SourceEventSHA256    *string     `json:"source_event_sha256"`
}

type journalRecordLine struct {
	Kind       string            `json:"kind"`
	RecordBody journalRecordBody `json:"record_body"`
	RecordHash string            `json:"record_hash"`
}

type journalFooterLine struct {
	ClosedAt        string `json:"closed_at"`
	ContentSHA256   string `json:"content_sha256"`
	FinalRecordHash string `json:"final_record_hash"`
	Kind            string `json:"kind"`
	LastSequence    int64  `json:"last_sequence"`
	RecordCount     int64  `json:"record_count"`
	SegmentHash     string `json:"segment_hash"`
}

type verifiedJournalRecord struct {
	Body       journalRecordBody
	RecordHash string
	SNRDb      float64
}

type verifiedJournalSegment struct {
	Header       journalHeaderLine
	Records      []verifiedJournalRecord
	Footer       journalFooterLine
	ObjectSHA256 string
}

func verifyClosedJournalSegment(data []byte) (verifiedJournalSegment, error) {
	if len(data) == 0 || data[len(data)-1] != '\n' {
		return verifiedJournalSegment{}, errors.New("closed journal segment must end with LF")
	}

	var result verifiedJournalSegment
	var haveHeader, haveFooter bool
	var footerOffset int
	var expectedSequence int64
	var expectedPreviousRecordHash string

	for offset := 0; offset < len(data); {
		newline := bytes.IndexByte(data[offset:], '\n')
		if newline < 0 {
			return verifiedJournalSegment{}, errors.New("closed journal segment contains torn final line")
		}
		end := offset + newline + 1
		rawLine := data[offset : end-1]
		if len(rawLine) == 0 {
			return verifiedJournalSegment{}, errors.New("closed journal segment contains empty JSONL line")
		}

		var probe struct {
			Kind string `json:"kind"`
		}
		if err := json.Unmarshal(rawLine, &probe); err != nil {
			return verifiedJournalSegment{}, fmt.Errorf("decode journal line kind: %w", err)
		}
		switch probe.Kind {
		case "header":
			if haveHeader || haveFooter || len(result.Records) != 0 || offset != 0 {
				return verifiedJournalSegment{}, errors.New("journal header is not first and unique")
			}
			var line journalHeaderLine
			if err := decodeStrictJSON(rawLine, &line); err != nil {
				return verifiedJournalSegment{}, fmt.Errorf("decode journal header: %w", err)
			}
			if err := validateJournalHeader(line); err != nil {
				return verifiedJournalSegment{}, err
			}
			canonical, err := canonicalJournalHeader(line)
			if err != nil {
				return verifiedJournalSegment{}, err
			}
			if !bytes.Equal(rawLine, canonical) {
				return verifiedJournalSegment{}, errors.New("journal header is not exact RFC8785/JCS contract bytes")
			}
			result.Header = line
			haveHeader = true
			expectedSequence = line.FirstSequence
		case "record":
			if !haveHeader || haveFooter {
				return verifiedJournalSegment{}, errors.New("journal record placement is invalid")
			}
			var line journalRecordLine
			if err := decodeStrictJSON(rawLine, &line); err != nil {
				return verifiedJournalSegment{}, fmt.Errorf("decode journal record: %w", err)
			}
			snr, err := validateJournalRecordBody(line.RecordBody)
			if err != nil {
				return verifiedJournalSegment{}, err
			}
			canonicalBody, err := canonicalJournalRecordBody(line.RecordBody)
			if err != nil {
				return verifiedJournalSegment{}, err
			}
			recordDigest := sha256.Sum256(canonicalBody)
			expectedRecordHash := hex.EncodeToString(recordDigest[:])
			if !isLowerHash(line.RecordHash) || line.RecordHash != expectedRecordHash {
				return verifiedJournalSegment{}, errors.New("journal record_hash mismatch")
			}
			canonicalLine := canonicalJournalRecordLine(canonicalBody, line.RecordHash)
			if !bytes.Equal(rawLine, canonicalLine) {
				return verifiedJournalSegment{}, errors.New("journal record line is not exact RFC8785/JCS contract bytes")
			}
			if line.RecordBody.GatewayID != result.Header.GatewayID {
				return verifiedJournalSegment{}, errors.New("journal record Gateway EUI differs from segment")
			}
			if line.RecordBody.Sequence != expectedSequence {
				return verifiedJournalSegment{}, errors.New("journal sequence gap or reorder")
			}
			if len(result.Records) == 0 {
				if !isHashOrGenesis(line.RecordBody.PreviousRecordHash) {
					return verifiedJournalSegment{}, errors.New("first record previous_record_hash is invalid")
				}
				expectedPreviousRecordHash = line.RecordHash
			} else {
				if line.RecordBody.PreviousRecordHash != expectedPreviousRecordHash {
					return verifiedJournalSegment{}, errors.New("journal previous_record_hash chain mismatch")
				}
				expectedPreviousRecordHash = line.RecordHash
			}
			result.Records = append(result.Records, verifiedJournalRecord{Body: line.RecordBody, RecordHash: line.RecordHash, SNRDb: snr})
			expectedSequence++
		case "footer":
			if !haveHeader || haveFooter || len(result.Records) == 0 {
				return verifiedJournalSegment{}, errors.New("journal footer placement is invalid")
			}
			var line journalFooterLine
			if err := decodeStrictJSON(rawLine, &line); err != nil {
				return verifiedJournalSegment{}, fmt.Errorf("decode journal footer: %w", err)
			}
			if err := validateJournalFooter(line); err != nil {
				return verifiedJournalSegment{}, err
			}
			canonical := canonicalJournalFooter(line)
			if !bytes.Equal(rawLine, canonical) {
				return verifiedJournalSegment{}, errors.New("journal footer is not exact RFC8785/JCS contract bytes")
			}
			footerOffset = offset
			result.Footer = line
			haveFooter = true
		default:
			return verifiedJournalSegment{}, errors.New("unsupported journal JSONL kind")
		}
		offset = end
	}

	if !haveHeader || !haveFooter || len(result.Records) == 0 {
		return verifiedJournalSegment{}, errors.New("closed journal segment is incomplete")
	}
	lastRecord := result.Records[len(result.Records)-1]
	if result.Footer.RecordCount != int64(len(result.Records)) ||
		result.Footer.LastSequence != lastRecord.Body.Sequence ||
		result.Footer.FinalRecordHash != lastRecord.RecordHash {
		return verifiedJournalSegment{}, errors.New("journal footer does not match record set")
	}
	contentDigest := sha256.Sum256(data[:footerOffset])
	if result.Footer.ContentSHA256 != hex.EncodeToString(contentDigest[:]) {
		return verifiedJournalSegment{}, errors.New("journal content_sha256 mismatch")
	}
	segmentDigest, err := journalSegmentHash(result.Header, result.Footer)
	if err != nil {
		return verifiedJournalSegment{}, err
	}
	if result.Footer.SegmentHash != segmentDigest {
		return verifiedJournalSegment{}, errors.New("journal segment_hash mismatch")
	}
	objectDigest := sha256.Sum256(data)
	result.ObjectSHA256 = hex.EncodeToString(objectDigest[:])
	return result, nil
}

func validateJournalHeader(line journalHeaderLine) error {
	if line.Kind != "header" || line.SegmentVersion != segmentVersion || line.JournalVersion != journalVersion {
		return errors.New("unsupported journal segment header version")
	}
	if !isCanonicalEUI(line.GatewayID) || line.SegmentID < 1 || line.FirstSequence < 1 {
		return errors.New("invalid journal segment header identity")
	}
	if line.SegmentID == 1 {
		if line.PreviousSegmentHash != journalGenesis {
			return errors.New("journal segment 1 must use GENESIS predecessor")
		}
	} else if !isLowerHash(line.PreviousSegmentHash) {
		return errors.New("journal segment predecessor hash is invalid")
	}
	if !isUTCMillis(line.CreatedAt) {
		return errors.New("journal segment created_at is not canonical UTC milliseconds")
	}
	return nil
}

func validateJournalRecordBody(body journalRecordBody) (float64, error) {
	if !validBootID(body.BootID) || !isUTCMillis(body.CapturedAt) || !isCanonicalEUI(body.GatewayID) ||
		body.JournalVersion != journalVersion || body.Source != journalSource || body.Sequence < 1 ||
		body.FrequencyHz < 1 || body.FrequencyHz > 10_000_000_000 || body.RSSIDbm < -200 || body.RSSIDbm > 0 ||
		!isHashOrGenesis(body.PreviousRecordHash) {
		return 0, errors.New("journal record body violates identity/range contract")
	}
	if body.SourceEventSHA256 != nil && !isLowerHash(*body.SourceEventSHA256) {
		return 0, errors.New("journal source_event_sha256 is invalid")
	}
	if _, err := decodeCanonicalBase64(body.PHYPayloadBase64, false); err != nil {
		return 0, fmt.Errorf("journal PHYPayload Base64: %w", err)
	}
	if body.GatewayContextBase64 != nil {
		if _, err := decodeCanonicalBase64(*body.GatewayContextBase64, true); err != nil {
			return 0, fmt.Errorf("journal gateway context Base64: %w", err)
		}
	}
	canonicalSNR, snr, err := canonicalJSONNumber(body.SNRDb.String())
	if err != nil || canonicalSNR != body.SNRDb.String() || snr < -100 || snr > 100 {
		return 0, errors.New("journal snr_db is not canonical finite evidence number")
	}
	return snr, nil
}

func validateJournalFooter(line journalFooterLine) error {
	if line.Kind != "footer" || line.LastSequence < 1 || line.RecordCount < 1 ||
		!isLowerHash(line.FinalRecordHash) || !isLowerHash(line.ContentSHA256) || !isLowerHash(line.SegmentHash) ||
		!isUTCMillis(line.ClosedAt) {
		return errors.New("invalid journal segment footer")
	}
	return nil
}

func canonicalJournalHeader(line journalHeaderLine) ([]byte, error) {
	return []byte(fmt.Sprintf(
		`{"created_at":%s,"first_sequence":%d,"gateway_id":%s,"journal_version":%s,"kind":"header","previous_segment_hash":%s,"segment_id":%d,"segment_version":%s}`,
		jsonQuote(line.CreatedAt), line.FirstSequence, jsonQuote(line.GatewayID), jsonQuote(line.JournalVersion),
		jsonQuote(line.PreviousSegmentHash), line.SegmentID, jsonQuote(line.SegmentVersion),
	)), nil
}

func canonicalJournalRecordBody(body journalRecordBody) ([]byte, error) {
	snr, _, err := canonicalJSONNumber(body.SNRDb.String())
	if err != nil {
		return nil, err
	}
	return []byte(fmt.Sprintf(
		`{"boot_id":%s,"captured_at":%s,"frequency_hz":%d,"gateway_context_base64":%s,"gateway_id":%s,"journal_version":%s,"phy_payload_base64":%s,"previous_record_hash":%s,"rssi_dbm":%d,"sequence":%d,"snr_db":%s,"source":%s,"source_event_sha256":%s}`,
		jsonQuote(body.BootID), jsonQuote(body.CapturedAt), body.FrequencyHz, jsonNullableString(body.GatewayContextBase64),
		jsonQuote(body.GatewayID), jsonQuote(body.JournalVersion), jsonQuote(body.PHYPayloadBase64), jsonQuote(body.PreviousRecordHash),
		body.RSSIDbm, body.Sequence, snr, jsonQuote(body.Source), jsonNullableString(body.SourceEventSHA256),
	)), nil
}

func canonicalJournalRecordLine(canonicalBody []byte, recordHash string) []byte {
	return []byte(`{"kind":"record","record_body":` + string(canonicalBody) + `,"record_hash":` + jsonQuote(recordHash) + `}`)
}

func canonicalJournalFooter(line journalFooterLine) []byte {
	return []byte(fmt.Sprintf(
		`{"closed_at":%s,"content_sha256":%s,"final_record_hash":%s,"kind":"footer","last_sequence":%d,"record_count":%d,"segment_hash":%s}`,
		jsonQuote(line.ClosedAt), jsonQuote(line.ContentSHA256), jsonQuote(line.FinalRecordHash),
		line.LastSequence, line.RecordCount, jsonQuote(line.SegmentHash),
	))
}

func journalSegmentHash(header journalHeaderLine, footer journalFooterLine) (string, error) {
	if err := validateJournalHeader(header); err != nil {
		return "", err
	}
	if err := validateJournalFooter(footer); err != nil {
		return "", err
	}
	fields := []string{
		header.SegmentVersion,
		header.GatewayID,
		strconv.FormatInt(header.SegmentID, 10),
		strconv.FormatInt(header.FirstSequence, 10),
		header.PreviousSegmentHash,
		header.CreatedAt,
		header.JournalVersion,
		strconv.FormatInt(footer.LastSequence, 10),
		strconv.FormatInt(footer.RecordCount, 10),
		footer.FinalRecordHash,
		footer.ClosedAt,
		footer.ContentSHA256,
	}
	digest := sha256.Sum256([]byte(strings.Join(fields, "\x00")))
	return hex.EncodeToString(digest[:]), nil
}

func decodeStrictJSON(data []byte, target any) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			return errors.New("multiple JSON values")
		}
		return err
	}
	return nil
}

func canonicalJSONNumber(raw string) (string, float64, error) {
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil || math.IsNaN(value) || math.IsInf(value, 0) {
		return "", 0, errors.New("non-finite JSON number")
	}
	if value == 0 {
		return "0", value, nil
	}
	abs := math.Abs(value)
	if abs >= 1e-6 && abs < 1e21 {
		return strconv.FormatFloat(value, 'f', -1, 64), value, nil
	}
	encoded := strconv.FormatFloat(value, 'e', -1, 64)
	parts := strings.Split(encoded, "e")
	if len(parts) != 2 {
		return "", 0, errors.New("invalid exponent encoding")
	}
	exponent := parts[1]
	sign := "+"
	if strings.HasPrefix(exponent, "-") {
		sign = "-"
		exponent = exponent[1:]
	} else if strings.HasPrefix(exponent, "+") {
		exponent = exponent[1:]
	}
	exponent = strings.TrimLeft(exponent, "0")
	if exponent == "" {
		exponent = "0"
	}
	return parts[0] + "e" + sign + exponent, value, nil
}

func jsonQuote(value string) string {
	encoded, _ := json.Marshal(value)
	return string(encoded)
}

func jsonNullableString(value *string) string {
	if value == nil {
		return "null"
	}
	return jsonQuote(*value)
}

func isUTCMillis(value string) bool {
	parsed, err := time.Parse("2006-01-02T15:04:05.000Z", value)
	return err == nil && parsed.UTC().Format("2006-01-02T15:04:05.000Z") == value
}

func validBootID(value string) bool {
	if len(value) < 1 || len(value) > 128 {
		return false
	}
	for i := 0; i < len(value); i++ {
		b := value[i]
		if !((b >= '0' && b <= '9') || (b >= 'a' && b <= 'z') || (b >= 'A' && b <= 'Z') || b == '-' || b == '_') {
			return false
		}
	}
	return true
}

func isCanonicalEUI(value string) bool {
	if len(value) != 16 {
		return false
	}
	for i := 0; i < len(value); i++ {
		if !isLowerHex(value[i]) {
			return false
		}
	}
	return true
}

func isLowerHash(value string) bool {
	if len(value) != 64 {
		return false
	}
	for i := 0; i < len(value); i++ {
		if !isLowerHex(value[i]) {
			return false
		}
	}
	return true
}

func isHashOrGenesis(value string) bool {
	return value == journalGenesis || isLowerHash(value)
}

func isLowerHex(value byte) bool {
	return (value >= '0' && value <= '9') || (value >= 'a' && value <= 'f')
}

func decodeCanonicalBase64(value string, allowEmpty bool) ([]byte, error) {
	decoded, err := base64.StdEncoding.Strict().DecodeString(value)
	if err != nil {
		return nil, errors.New("invalid RFC4648 Base64")
	}
	if !allowEmpty && len(decoded) == 0 {
		return nil, errors.New("empty Base64 value is not allowed")
	}
	if base64.StdEncoding.EncodeToString(decoded) != value {
		return nil, errors.New("non-canonical RFC4648 Base64")
	}
	return decoded, nil
}
