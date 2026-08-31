use base64::{engine::general_purpose::STANDARD, Engine as _};
use prost::{Message, Oneof};

use crate::contract::{sha256_hex, validate_gateway_id};
use crate::{Error, RecordBody, Result, JOURNAL_VERSION, SOURCE_CONCENTRATORD};

pub const CORRELATION_VERSION: &str = "concentratord-uplink-correlation-v1";
pub const GW_PROTO_SHA256: &str =
    "227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b";

#[derive(Debug, Clone, PartialEq)]
pub struct ConcentratordUplink {
    pub gateway_id: String,
    pub uplink_id: u32,
    pub phy_payload: Vec<u8>,
    pub frequency_hz: u32,
    pub rssi_dbm: i32,
    pub snr_db: f32,
    pub gateway_context: Vec<u8>,
}

impl ConcentratordUplink {
    pub fn decode_event(bytes: &[u8], expected_gateway_id: &str) -> Result<Self> {
        validate_gateway_id(expected_gateway_id)?;
        let event = EventMessage::decode(bytes)
            .map_err(|err| Error::InvalidOwned(format!("Concentratord Event protobuf: {err}")))?;
        let uplink = match event.event {
            Some(event_message::Event::UplinkFrame(value)) => value,
            Some(event_message::Event::GatewayStats(_)) | Some(event_message::Event::Mesh(_)) => {
                return Err(Error::Invalid("Concentratord event is not an uplink frame"));
            }
            None => {
                return Err(Error::Invalid(
                    "Concentratord Event contains no supported event",
                ))
            }
        };
        Self::from_wire(uplink, expected_gateway_id)
    }

    pub fn decode_mqtt_uplink(bytes: &[u8], expected_gateway_id: &str) -> Result<Self> {
        validate_gateway_id(expected_gateway_id)?;
        let uplink = UplinkFrame::decode(bytes)
            .map_err(|err| Error::InvalidOwned(format!("MQTT UplinkFrame protobuf: {err}")))?;
        Self::from_wire(uplink, expected_gateway_id)
    }

    fn from_wire(uplink: UplinkFrame, expected_gateway_id: &str) -> Result<Self> {
        if uplink.phy_payload.is_empty() {
            return Err(Error::Invalid("UplinkFrame PHYPayload is empty"));
        }
        let tx_info = uplink
            .tx_info
            .ok_or(Error::Invalid("UplinkFrame tx_info is missing"))?;
        let rx_info = uplink
            .rx_info
            .ok_or(Error::Invalid("UplinkFrame rx_info is missing"))?;
        validate_gateway_id(&rx_info.gateway_id)?;
        if rx_info.gateway_id != expected_gateway_id {
            return Err(Error::Invalid(
                "UplinkFrame Gateway EUI does not match configured gateway",
            ));
        }
        if tx_info.frequency == 0 {
            return Err(Error::Invalid("UplinkFrame frequency is zero"));
        }
        if !(-200..=0).contains(&rx_info.rssi) {
            return Err(Error::Invalid(
                "UplinkFrame RSSI is outside journal contract",
            ));
        }
        if !rx_info.snr.is_finite() || rx_info.snr < -100.0 || rx_info.snr > 100.0 {
            return Err(Error::Invalid(
                "UplinkFrame SNR is outside journal contract",
            ));
        }
        Ok(Self {
            gateway_id: rx_info.gateway_id,
            uplink_id: rx_info.uplink_id,
            phy_payload: uplink.phy_payload,
            frequency_hz: tx_info.frequency,
            rssi_dbm: rx_info.rssi,
            snr_db: rx_info.snr,
            gateway_context: rx_info.context,
        })
    }

    pub fn phy_payload_sha256(&self) -> String {
        sha256_hex(&self.phy_payload)
    }

    pub fn correlation_digest(&self) -> Result<String> {
        validate_gateway_id(&self.gateway_id)?;
        if self.phy_payload.is_empty() || self.frequency_hz == 0 {
            return Err(Error::Invalid("cannot correlate incomplete UplinkFrame"));
        }
        let fields = [
            CORRELATION_VERSION.to_string(),
            self.gateway_id.clone(),
            self.uplink_id.to_string(),
            self.phy_payload_sha256(),
            self.frequency_hz.to_string(),
            STANDARD.encode(&self.gateway_context),
        ];
        Ok(sha256_hex(fields.join("\0").as_bytes()))
    }

    pub fn to_record_body(
        &self,
        boot_id: impl Into<String>,
        sequence: u64,
        captured_at: impl Into<String>,
        previous_record_hash: impl Into<String>,
    ) -> Result<RecordBody> {
        let body = RecordBody {
            journal_version: JOURNAL_VERSION.to_string(),
            gateway_id: self.gateway_id.clone(),
            boot_id: boot_id.into(),
            sequence,
            captured_at: captured_at.into(),
            source: SOURCE_CONCENTRATORD.to_string(),
            source_event_sha256: Some(self.correlation_digest()?),
            phy_payload_base64: STANDARD.encode(&self.phy_payload),
            frequency_hz: u64::from(self.frequency_hz),
            rssi_dbm: self.rssi_dbm,
            snr_db: f64::from(self.snr_db),
            gateway_context_base64: if self.gateway_context.is_empty() {
                None
            } else {
                Some(STANDARD.encode(&self.gateway_context))
            },
            previous_record_hash: previous_record_hash.into(),
        };
        body.validate()?;
        Ok(body)
    }
}

#[derive(Clone, PartialEq, Message)]
struct EventMessage {
    #[prost(oneof = "event_message::Event", tags = "1, 2, 3")]
    event: Option<event_message::Event>,
}

mod event_message {
    use super::{IgnoredMessage, UplinkFrame};
    use prost::Oneof;

    #[derive(Clone, PartialEq, Oneof)]
    pub enum Event {
        #[prost(message, tag = "1")]
        UplinkFrame(UplinkFrame),
        #[prost(message, tag = "2")]
        GatewayStats(IgnoredMessage),
        #[prost(message, tag = "3")]
        Mesh(IgnoredMessage),
    }
}

#[derive(Clone, PartialEq, Message)]
struct IgnoredMessage {}

#[derive(Clone, PartialEq, Message)]
struct UplinkFrame {
    #[prost(bytes = "vec", tag = "1")]
    phy_payload: Vec<u8>,
    #[prost(message, optional, tag = "4")]
    tx_info: Option<UplinkTxInfo>,
    #[prost(message, optional, tag = "5")]
    rx_info: Option<UplinkRxInfo>,
}

#[derive(Clone, PartialEq, Message)]
struct UplinkTxInfo {
    #[prost(uint32, tag = "1")]
    frequency: u32,
}

#[derive(Clone, PartialEq, Message)]
struct UplinkRxInfo {
    #[prost(string, tag = "1")]
    gateway_id: String,
    #[prost(uint32, tag = "2")]
    uplink_id: u32,
    #[prost(int32, tag = "6")]
    rssi: i32,
    #[prost(float, tag = "7")]
    snr: f32,
    #[prost(bytes = "vec", tag = "13")]
    context: Vec<u8>,
}
