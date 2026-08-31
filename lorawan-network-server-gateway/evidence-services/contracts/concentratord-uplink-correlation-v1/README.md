# concentratord-uplink-correlation-v1

This contract freezes the uplink identity shared by the commissioned ChirpStack Concentratord event stream and MQTT Forwarder `event/up` payload. It deliberately compares semantic fields rather than raw Protobuf byte equality.

## Pinned producer and forwarder

Commissioned gateway evidence:

```text
chirpstack-concentratord-sx1302 4.7.1
  tag commit: 0904a8ddf4eeb3150b4675b35f067865cb68827d
  chirpstack_api: 4.17.0
  crate checksum: 1eecb20855db95448fb6bbb26bd56187efca90cfe2b486e205dfdaa98ec38ee1

chirpstack-mqtt-forwarder 4.6.0
  tag commit: 04e870b4af97bebb278ab29259941fd8b3aad72b
  chirpstack_api: 4.18.0
  crate checksum: dc57e0b0e8dca97c85058ded65c5420430cc9d97d65a9cfbee973ce258e93362
```

The published `chirpstack_api` 4.17.0 and 4.18.0 artifacts contain byte-identical `proto/chirpstack/gw/gw.proto`:

```text
gw.proto bytes  = 18459
gw.proto sha256 = 227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b
```

Concentratord 4.7.1 uses `prost 0.14.3`; its declared minimum Rust version is 1.82 and its crate checksum is `d2ea70524a2f82d518bce41317d0fae74151505651af45faf1ffbd6fd33f0568`.

## Proven transport path

At the pinned Concentratord commit, `libconcentratord/src/events.rs` wraps a `gw::UplinkFrame` as `gw::Event.event.uplink_frame` and publishes `event.encode_to_vec()` on the ZeroMQ event socket.

At the pinned MQTT Forwarder commit, the Concentratord backend decodes that ZeroMQ message as `gw::Event`, selects `Event::UplinkFrame`, and, with JSON disabled, publishes `UplinkFrame.encode_to_vec()` to:

```text
<topic_prefix>/gateway/<gateway_id>/event/up
```

For this gateway that is:

```text
as923/gateway/0016c001f139a1cb/event/up
```

Therefore the ZeroMQ and MQTT payloads are **not raw-byte identical**: the former is an `Event` envelope, while the latter is the contained `UplinkFrame` re-encoded. The contract must not hash raw Protobuf bytes as the cross-path identity.

## Exact wire fields used

The adapter uses only fields whose tags are identical in the pinned 4.17.0/4.18.0 schema:

```text
gw.Event.uplink_frame         tag 1, message gw.UplinkFrame

gw.UplinkFrame.phy_payload   tag 1, bytes
gw.UplinkFrame.tx_info       tag 4, message gw.UplinkTxInfo
gw.UplinkFrame.rx_info       tag 5, message gw.UplinkRxInfo

gw.UplinkTxInfo.frequency    tag 1, uint32

gw.UplinkRxInfo.gateway_id   tag 1, string
gw.UplinkRxInfo.uplink_id    tag 2, uint32
gw.UplinkRxInfo.rssi         tag 6, int32
gw.UplinkRxInfo.snr          tag 7, float
gw.UplinkRxInfo.context      tag 13, bytes
```

Unknown fields remain Protobuf-compatible and are ignored by the minimal evidence adapter.

## Correlation digest

The semantic preimage is the following UTF-8 fields joined by one NUL byte (`0x00`), with no trailing NUL:

```text
concentratord-uplink-correlation-v1
lowercase_gateway_eui
base10(uplink_id)
lowercase_hex(SHA256(exact_phy_payload_bytes))
base10(frequency_hz)
canonical_RFC4648_Base64(rx_info.context)
```

Then:

```text
correlation_digest_sha256 = lowercase_hex(SHA256(exact_preimage_bytes))
```

`rx_info.context` uses the empty string in the digest when the Protobuf bytes field is empty. In the journal record itself, an empty context is normalized to JSON `null`; a non-empty context is stored as canonical Base64.

`gateway-journal-v1.source_event_sha256` is the correlation digest for records created by this adapter. It is **not** a hash of the raw ZeroMQ `gw.Event` bytes.

Why these fields are used:

- Gateway EUI scopes the identity to the commissioned radio gateway.
- `uplink_id` is generated for one gateway reception and survives MQTT Forwarder unchanged.
- PHYPayload digest prevents a random-ID collision from silently correlating different radio bytes.
- frequency and gateway context add independent radio-reception discrimination.
- RSSI/SNR remain evidence fields but are not digest inputs, avoiding cross-language floating-point text formatting as an identity dependency.

## Synthetic fixed vector

This is a **schema fixture**, not a captured production gateway event.

```text
gateway_id       = 0016c001f139a1cb
uplink_id        = 16909060
phy_payload_hex  = 01020304
frequency_hz     = 923200000
rssi_dbm         = -72
snr_db           = 8.5
context_hex      = deadbeef
context_base64   = 3q2+7w==
phy_sha256       = 9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a
```

Exact synthetic MQTT `gw.UplinkFrame` bytes:

```text
0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef
```

Its SHA-256 is:

```text
a4abfda57c8137349760020a89ba55274bd6627828de95f655f14013cfb6150b
```

Exact synthetic Concentratord `gw.Event` bytes wrapping that frame:

```text
0a3d0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef
```

Its raw-event SHA-256 is:

```text
7846aeaf29959211c58060916ef06e3a56283326388f4ee8dc43f5a33d1f2a5d
```

Both paths must produce this semantic correlation digest:

```text
a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494
```

The vector was independently constructed with a Python Protobuf-wire encoder and SHA-256 calculation, not by calling the Rust adapter.

## Live acceptance boundary

This contract removes the **schema ambiguity** that previously blocked implementation, but it does not manufacture physical evidence. Final gateway acceptance still requires one real `ipc:///tmp/concentratord_event` uplink captured from the commissioned Concentratord 4.7.1 runtime and the corresponding local/remote MQTT `event/up` observation. Both must decode through the reviewed implementation and produce the same correlation digest before live correlation is claimed.
