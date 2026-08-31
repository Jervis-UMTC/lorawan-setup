package verifier

import "testing"

const (
	correlationRecordHash  = "55f3ec5893ab80e889b71b74cdeaf58b5140582dc581bb37f28f7120470752f4"
	correlationContentSHA  = "cdd5bfb3f539b76b9a0abe2ff31b900421915404b2b2a9b0ca1ef4866c5ff6e4"
	correlationSegmentHash = "244da3566b01cd6557f8f3303266a7b118afdf065f7516782b3c1bbabafef32d"
	correlationObjectSHA   = "ba15861a63ea3f294db11322d7279f5f3b676049d661125cd2a2bb6d66ff221b"
	correlationDigest      = "a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494"
)

var correlationJournalFixture = []byte(
	`{"created_at":"2000-01-01T00:01:00.000Z","first_sequence":1,"gateway_id":"0016c001f139a1cb","journal_version":"gateway-journal-v1","kind":"header","previous_segment_hash":"GENESIS","segment_id":1,"segment_version":"gateway-journal-segment-v1"}` + "\n" +
		`{"kind":"record","record_body":{"boot_id":"boot-correlation-1","captured_at":"2000-01-01T00:01:01.000Z","frequency_hz":923200000,"gateway_context_base64":"3q2+7w==","gateway_id":"0016c001f139a1cb","journal_version":"gateway-journal-v1","phy_payload_base64":"AQIDBA==","previous_record_hash":"GENESIS","rssi_dbm":-72,"sequence":1,"snr_db":8.5,"source":"concentratord","source_event_sha256":"a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494"},"record_hash":"55f3ec5893ab80e889b71b74cdeaf58b5140582dc581bb37f28f7120470752f4"}` + "\n" +
		`{"closed_at":"2000-01-01T00:01:02.000Z","content_sha256":"cdd5bfb3f539b76b9a0abe2ff31b900421915404b2b2a9b0ca1ef4866c5ff6e4","final_record_hash":"55f3ec5893ab80e889b71b74cdeaf58b5140582dc581bb37f28f7120470752f4","kind":"footer","last_sequence":1,"record_count":1,"segment_hash":"244da3566b01cd6557f8f3303266a7b118afdf065f7516782b3c1bbabafef32d"}` + "\n",
)

func TestVerifyClosedJournalSegmentCorrelationVector(t *testing.T) {
	verified, err := verifyClosedJournalSegment(correlationJournalFixture)
	if err != nil {
		t.Fatal(err)
	}
	if verified.Header.SegmentID != 1 || verified.Footer.RecordCount != 1 || verified.ObjectSHA256 != correlationObjectSHA {
		t.Fatalf("unexpected verified segment: %+v", verified)
	}
	if verified.Footer.ContentSHA256 != correlationContentSHA || verified.Footer.SegmentHash != correlationSegmentHash {
		t.Fatal("fixed segment digests changed")
	}
	if verified.Records[0].RecordHash != correlationRecordHash || verified.Records[0].Body.SourceEventSHA256 == nil || *verified.Records[0].Body.SourceEventSHA256 != correlationDigest {
		t.Fatal("fixed correlated record changed")
	}
}

func TestVerifyClosedJournalSegmentRejectsNonCanonicalMutation(t *testing.T) {
	mutated := append([]byte(nil), correlationJournalFixture...)
	for i := range mutated {
		if mutated[i] == ':' {
			mutated = append(mutated[:i+1], append([]byte(" "), mutated[i+1:]...)...)
			break
		}
	}
	if _, err := verifyClosedJournalSegment(mutated); err == nil {
		t.Fatal("accepted non-canonical journal bytes")
	}
}

func TestCanonicalJSONNumberMatchesJCSBoundaries(t *testing.T) {
	cases := map[string]string{
		"8.5":      "8.5",
		"-0":       "0",
		"0.000001": "0.000001",
		"1e-7":     "1e-7",
		"1e+21":    "1e+21",
	}
	for input, expected := range cases {
		actual, _, err := canonicalJSONNumber(input)
		if err != nil {
			t.Fatalf("canonicalJSONNumber(%q): %v", input, err)
		}
		if actual != expected {
			t.Fatalf("canonicalJSONNumber(%q)=%q want %q", input, actual, expected)
		}
	}
	if _, _, err := canonicalJSONNumber("NaN"); err == nil {
		t.Fatal("accepted non-finite JSON number")
	}
}
