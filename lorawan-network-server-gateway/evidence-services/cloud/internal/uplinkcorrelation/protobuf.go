package uplinkcorrelation

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
)

const (
	Version       = "concentratord-uplink-correlation-v1"
	GWProtoSHA256 = "227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b"
)

type Projection struct {
	GatewayID      string
	UplinkID       uint32
	PHYPayload     []byte
	FrequencyHz    uint32
	RSSIDbm        int32
	SNRDb          float32
	GatewayContext []byte
}

func DecodeUplinkFrame(data []byte, expectedGatewayID string) (Projection, error) {
	if !validGatewayID(expectedGatewayID) {
		return Projection{}, errors.New("expected Gateway EUI must be canonical lowercase 16-hex")
	}
	var out Projection
	var gotPHY, gotTX, gotRX bool
	for offset := 0; offset < len(data); {
		key, err := consumeVarint(data, &offset)
		if err != nil {
			return Projection{}, fmt.Errorf("decode UplinkFrame field key: %w", err)
		}
		field, wire := key>>3, key&7
		if field == 0 {
			return Projection{}, errors.New("UplinkFrame contains field number zero")
		}
		switch field {
		case 1:
			if wire != 2 {
				return Projection{}, errors.New("UplinkFrame phy_payload has wrong wire type")
			}
			value, err := consumeBytes(data, &offset)
			if err != nil {
				return Projection{}, err
			}
			out.PHYPayload = append(out.PHYPayload[:0], value...)
			gotPHY = true
		case 4:
			if wire != 2 {
				return Projection{}, errors.New("UplinkFrame tx_info has wrong wire type")
			}
			value, err := consumeBytes(data, &offset)
			if err != nil {
				return Projection{}, err
			}
			out.FrequencyHz, err = decodeTXInfo(value)
			if err != nil {
				return Projection{}, err
			}
			gotTX = true
		case 5:
			if wire != 2 {
				return Projection{}, errors.New("UplinkFrame rx_info has wrong wire type")
			}
			value, err := consumeBytes(data, &offset)
			if err != nil {
				return Projection{}, err
			}
			rx, err := decodeRXInfo(value)
			if err != nil {
				return Projection{}, err
			}
			out.GatewayID = rx.GatewayID
			out.UplinkID = rx.UplinkID
			out.RSSIDbm = rx.RSSIDbm
			out.SNRDb = rx.SNRDb
			out.GatewayContext = rx.Context
			gotRX = true
		default:
			if err := skipValue(data, &offset, wire); err != nil {
				return Projection{}, fmt.Errorf("skip UplinkFrame field %d: %w", field, err)
			}
		}
	}
	if !gotPHY || len(out.PHYPayload) == 0 || !gotTX || !gotRX {
		return Projection{}, errors.New("UplinkFrame is missing required evidence fields")
	}
	if !validGatewayID(out.GatewayID) || out.GatewayID != expectedGatewayID {
		return Projection{}, errors.New("UplinkFrame Gateway EUI does not match MQTT topic")
	}
	if out.FrequencyHz == 0 {
		return Projection{}, errors.New("UplinkFrame frequency is zero")
	}
	if out.RSSIDbm < -200 || out.RSSIDbm > 0 {
		return Projection{}, errors.New("UplinkFrame RSSI is outside evidence contract")
	}
	if math.IsNaN(float64(out.SNRDb)) || math.IsInf(float64(out.SNRDb), 0) || out.SNRDb < -100 || out.SNRDb > 100 {
		return Projection{}, errors.New("UplinkFrame SNR is outside evidence contract")
	}
	return out, nil
}

func (p Projection) PHYPayloadSHA256() string {
	digest := sha256.Sum256(p.PHYPayload)
	return hex.EncodeToString(digest[:])
}

func (p Projection) CorrelationDigest() (string, error) {
	if !validGatewayID(p.GatewayID) || len(p.PHYPayload) == 0 || p.FrequencyHz == 0 {
		return "", errors.New("incomplete uplink projection")
	}
	preimage := strings.Join([]string{
		Version,
		p.GatewayID,
		strconv.FormatUint(uint64(p.UplinkID), 10),
		p.PHYPayloadSHA256(),
		strconv.FormatUint(uint64(p.FrequencyHz), 10),
		base64.StdEncoding.EncodeToString(p.GatewayContext),
	}, "\x00")
	digest := sha256.Sum256([]byte(preimage))
	return hex.EncodeToString(digest[:]), nil
}

type rxProjection struct {
	GatewayID string
	UplinkID  uint32
	RSSIDbm   int32
	SNRDb     float32
	Context   []byte
}

func decodeTXInfo(data []byte) (uint32, error) {
	var frequency uint32
	var got bool
	for offset := 0; offset < len(data); {
		key, err := consumeVarint(data, &offset)
		if err != nil {
			return 0, err
		}
		field, wire := key>>3, key&7
		if field == 1 {
			if wire != 0 {
				return 0, errors.New("UplinkTxInfo frequency has wrong wire type")
			}
			value, err := consumeVarint(data, &offset)
			if err != nil || value > uint64(1<<32-1) {
				return 0, errors.New("UplinkTxInfo frequency is invalid")
			}
			frequency = uint32(value)
			got = true
		} else if err := skipValue(data, &offset, wire); err != nil {
			return 0, err
		}
	}
	if !got {
		return 0, errors.New("UplinkTxInfo frequency is missing")
	}
	return frequency, nil
}

func decodeRXInfo(data []byte) (rxProjection, error) {
	var out rxProjection
	var gotGateway bool
	for offset := 0; offset < len(data); {
		key, err := consumeVarint(data, &offset)
		if err != nil {
			return rxProjection{}, err
		}
		field, wire := key>>3, key&7
		switch field {
		case 1:
			if wire != 2 {
				return rxProjection{}, errors.New("UplinkRxInfo gateway_id has wrong wire type")
			}
			value, err := consumeBytes(data, &offset)
			if err != nil {
				return rxProjection{}, err
			}
			out.GatewayID = string(value)
			gotGateway = true
		case 2:
			if wire != 0 {
				return rxProjection{}, errors.New("UplinkRxInfo uplink_id has wrong wire type")
			}
			value, err := consumeVarint(data, &offset)
			if err != nil || value > uint64(1<<32-1) {
				return rxProjection{}, errors.New("UplinkRxInfo uplink_id is invalid")
			}
			out.UplinkID = uint32(value)
		case 6:
			if wire != 0 {
				return rxProjection{}, errors.New("UplinkRxInfo rssi has wrong wire type")
			}
			value, err := consumeVarint(data, &offset)
			if err != nil {
				return rxProjection{}, err
			}
			out.RSSIDbm = int32(uint32(value))
		case 7:
			if wire != 5 {
				return rxProjection{}, errors.New("UplinkRxInfo snr has wrong wire type")
			}
			value, err := consumeFixed32(data, &offset)
			if err != nil {
				return rxProjection{}, err
			}
			out.SNRDb = math.Float32frombits(value)
		case 13:
			if wire != 2 {
				return rxProjection{}, errors.New("UplinkRxInfo context has wrong wire type")
			}
			value, err := consumeBytes(data, &offset)
			if err != nil {
				return rxProjection{}, err
			}
			out.Context = append(out.Context[:0], value...)
		default:
			if err := skipValue(data, &offset, wire); err != nil {
				return rxProjection{}, err
			}
		}
	}
	if !gotGateway {
		return rxProjection{}, errors.New("UplinkRxInfo gateway_id is missing")
	}
	return out, nil
}

func consumeVarint(data []byte, offset *int) (uint64, error) {
	var value uint64
	for index := 0; index < 10; index++ {
		if *offset >= len(data) {
			return 0, errors.New("truncated protobuf varint")
		}
		b := data[*offset]
		(*offset)++
		if index == 9 && b > 1 {
			return 0, errors.New("protobuf varint overflow")
		}
		value |= uint64(b&0x7f) << (7 * index)
		if b < 0x80 {
			return value, nil
		}
	}
	return 0, errors.New("protobuf varint overflow")
}

func consumeBytes(data []byte, offset *int) ([]byte, error) {
	length, err := consumeVarint(data, offset)
	if err != nil {
		return nil, err
	}
	if length > uint64(len(data)-*offset) {
		return nil, errors.New("truncated protobuf bytes field")
	}
	start := *offset
	*offset += int(length)
	return data[start:*offset], nil
}

func consumeFixed32(data []byte, offset *int) (uint32, error) {
	if len(data)-*offset < 4 {
		return 0, errors.New("truncated protobuf fixed32")
	}
	value := binary.LittleEndian.Uint32(data[*offset : *offset+4])
	*offset += 4
	return value, nil
}

func skipValue(data []byte, offset *int, wire uint64) error {
	switch wire {
	case 0:
		_, err := consumeVarint(data, offset)
		return err
	case 1:
		if len(data)-*offset < 8 {
			return errors.New("truncated protobuf fixed64")
		}
		*offset += 8
		return nil
	case 2:
		_, err := consumeBytes(data, offset)
		return err
	case 5:
		_, err := consumeFixed32(data, offset)
		return err
	default:
		return fmt.Errorf("unsupported protobuf wire type %d", wire)
	}
}

func validGatewayID(value string) bool {
	if len(value) != 16 {
		return false
	}
	for _, b := range []byte(value) {
		if !((b >= '0' && b <= '9') || (b >= 'a' && b <= 'f')) {
			return false
		}
	}
	return true
}
