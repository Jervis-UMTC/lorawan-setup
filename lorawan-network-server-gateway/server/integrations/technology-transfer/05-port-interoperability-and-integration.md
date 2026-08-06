# 5. Port Interoperability and Integration

Port telemetry will normally coexist with larger operational systems. The LoRaWAN platform should provide clean observations and exceptions; it should not pretend to replace systems that manage vessel calls, cargo, gate operations, customs, maintenance, or official reporting.

## 5.1 Integration targets

Possible targets include:

| Target | Typical purpose | Integration direction |
|---|---|---|
| Terminal operating system | Yard, container, gate, and equipment operations | Telemetry or exception into TOS |
| Port community system | Shared logistics and stakeholder exchange | Approved events and references |
| Maritime Single Window | Ship and port-call information exchange | Domain-approved port-call data |
| CMMS or EAM | Maintenance and work orders | Condition exception to work order |
| Environmental reporting | Air, noise, water, and emissions evidence | Aggregated measurements and evidence |
| ERP or billing | Settlement or service evidence | Approved business attestation |
| Security operations | Access, incidents, and cyber monitoring | Alerts and audit metadata |
| Fabric network | Multi-organization attestation | Digest, approval, and provenance |

The integration owner must identify the system of record for every field. The same container temperature must not be independently editable in five systems without a reconciliation rule.

## 5.2 Use an integration contract

For each outbound event, define:

~~~json
{
  "event_type": "reefer_temperature_exception",
  "event_id": "REPLACE_WITH_STABLE_EVENT_ID",
  "occurred_at": "<OCCURRED_AT_UTC>",
  "site_id": "port-01",
  "asset_id": "container-ABC123",
  "source_device_id": "sensor-01",
  "metric": "cargo_temperature",
  "value": 9.8,
  "unit": "Cel",
  "quality": "measured",
  "threshold_profile": "reefer-profile-v1",
  "severity": "high",
  "recommended_action": "inspect_asset",
  "evidence_reference": "telemetry-window:REPLACE_WITH_REFERENCE"
}
~~~

The event ID must remain stable across retries. The receiving system should acknowledge whether it accepted, rejected, or already processed the event.

## 5.3 Integration patterns

Choose the least complex pattern that meets the operational need:

| Pattern | Use when | Main risk |
|---|---|---|
| Read-only SQL view | Internal dashboard or analytics | Tight coupling to database schema |
| MQTT subscription | Near-real-time internal event flow | Consumer must handle duplicates |
| REST or HTTPS API | Controlled system-to-system exchange | API lifecycle and authentication |
| Scheduled file exchange | Legacy or regulated batch process | Delay and file reconciliation |
| Message queue | High volume or multiple consumers | Operational complexity |
| Fabric transaction | Multi-party attestation or approval | Governance and endorsement delay |

Keep one canonical normalized event in the telemetry system, then create adapters for target systems. Do not create a different decoder and business interpretation for every consumer. Every adapter must authenticate the target, use TLS where traffic leaves the trusted container network, preserve a stable idempotency key, and store an explicit accepted, rejected, duplicate, or unknown outcome for reconciliation.

## 5.4 Maritime data harmonization

Port systems need shared meaning for identifiers, events, and organizations. The IMO Compendium is a reference model for harmonizing maritime information and supporting exchange between ships, ports, and authorities. Treat it as a domain reference to consult with the port data owner, not as a plug-and-play LoRaWAN API.

For port-call or official reporting data:

- use the port authority's approved identifiers;
- distinguish observation data from declared or legally submitted data;
- preserve the source and time of each value;
- use the required approval and retention process;
- never send a sensor value directly into an official reporting workflow without validation.

References:

- [IMO Compendium on Facilitation and Electronic Business](https://www.imo.org/en/ourwork/facilitation/pages/imocompendium.aspx)
- [IMO Maritime Single Window](https://www.imo.org/en/ourwork/facilitation/pages/maritimesinglewindow-default.aspx)

## 5.5 Port and Fabric integration

Fabric is most useful where organizations need a shared record:

~~~text
TimescaleDB:
  full reefer history
  raw telemetry
  dashboards
  retention and analytics

Fabric:
  exception attestation
  custody or inspection approval
  evidence digest
  organization approvals
~~~

Example:

1. TimescaleDB records the full temperature history.
2. Node-RED creates an exception when an approved band is exceeded.
3. The port application verifies the asset and operational context.
4. The Fabric adapter submits the exception digest and evidence reference.
5. The terminal system receives the work item.
6. The final inspection or custody decision is recorded according to the agreed workflow.

Do not place the entire time series on Fabric merely because the data is important.

## 5.6 Interoperability acceptance tests

Test with sanitized but realistic events. Keep the source event key and target acknowledgement so these behaviors can be compared:

- identifier mapping;
- units and timestamp conversion;
- duplicate delivery;
- delayed delivery;
- out-of-order delivery;
- asset replacement;
- device reassignment;
- missing readings;
- sensor calibration status;
- target-system outage;
- correction and cancellation;
- access by each stakeholder;
- audit trail from dashboard to source row and external event.

Next: [06-risk-security-regulatory-and-operations.md](06-risk-security-regulatory-and-operations.md)
