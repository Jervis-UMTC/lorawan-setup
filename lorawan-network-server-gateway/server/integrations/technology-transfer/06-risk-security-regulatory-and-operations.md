# 6. Risk, Security, Regulation, and Operations

A domain transfer changes the risk profile even when the software is unchanged. Port operations add mobile assets, industrial equipment, multiple organizations, large outdoor areas, and potentially safety or environmental obligations.

## 6.1 Safety boundary

Classify every output:

| Output | Example | Default treatment |
|---|---|---|
| Observation | Temperature or humidity | Store and visualize |
| Advisory | Inspect a reefer or check a pump | Notify a responsible operator |
| Operational workflow | Create a maintenance task | Require owner and audit trail |
| Control command | Change equipment state | Separate engineering and safety approval |
| Safety function | Emergency stop or collision prevention | Do not use this platform without a formal safety case |

The platform can report that a condition may exist. An approved control system must decide whether an action is safe.

## 6.2 Cybersecurity boundaries

- Keep gateways, ChirpStack, MQTT, databases, Grafana, and Node-RED on controlled networks.
- Do not expose internal services directly to the public internet.
- Use separate credentials and roles for each domain.
- Use TLS for external integrations.
- Store secrets outside flow files and dashboards.
- Segment port operational technology from general office networks.
- Restrict outbound access from the integration adapter.
- Log configuration, identity, and data-sharing changes.
- Rotate certificates, API credentials, and Fabric identities.
- Back up the telemetry data and integration configuration separately.
- Test restoration and credential revocation.

For a multi-organization port system, confirm who can see raw telemetry, exceptions, asset locations, and historical records.

## 6.3 Privacy and commercial sensitivity

Review whether telemetry can reveal:

- worker location or behavior;
- vehicle or vessel movement;
- cargo condition;
- customer or supplier activity;
- commercially sensitive throughput;
- security-sensitive site layout;
- personal or credential information.

Use aggregation, pseudonymous identifiers, access control, private collections, or a separate evidence store when required. A hash on Fabric does not make sensitive data harmless.

## 6.4 RF and environmental risk

Document:

- approved frequency plan and local regulatory requirements;
- gateway placement and antenna installation;
- coverage and interference results;
- lightning and grounding;
- enclosure and ingress protection;
- hazardous-area certification where applicable;
- battery replacement and safe maintenance;
- device tamper detection;
- loss-of-connectivity behavior.

The agriculture AS923-3 assumption from this project must be revalidated against the receiving site's country, regulator, device frequency variant, antenna, gateway channel plan, ChirpStack region, and operating environment. **Stop here. Do not transmit** until those items agree and local authorization is confirmed.

## 6.5 Availability and degraded operation

Define behavior for:

- gateway outage;
- backhaul outage;
- MQTT outage;
- Node-RED restart;
- TimescaleDB unavailable;
- external system unavailable;
- Fabric unavailable;
- sensor battery depletion;
- incorrect asset assignment.

The system must show stale, delayed, missing, and unknown data explicitly. Define freshness from the approved reporting interval and grace period for each device class. A missing value, old last-known value, or failed query must never be displayed or transmitted as a safe current value.

## 6.6 Maintenance and lifecycle

For every device class, define:

- commissioning and verification procedure;
- asset assignment process;
- calibration certificate and due date;
- firmware update method;
- battery estimate and replacement;
- enclosure inspection;
- decommissioning;
- lost or stolen device revocation;
- decoder version;
- end-of-life replacement.

For mobile port assets, track assignment history. A sensor's location at the time of an event is part of the evidence.

## 6.7 Operational KPIs

Measure both technical and business outcomes:

| Category | Example KPI |
|---|---|
| Coverage | Percentage of expected messages received |
| Freshness | Time from observation to usable dashboard |
| Quality | Percentage passing validation |
| Reliability | Gateway and pipeline availability |
| Battery | Estimated remaining life |
| Alerts | False-positive and missed-event rate |
| Operations | Response time to actionable exception |
| Maintenance | Sensor service completion rate |
| Integration | Accepted and reconciled external events |
| Business | Delay, waste, inspection effort, or incident reduction |

Do not declare transfer success from coverage alone.

References:

- [IMO strategy and maritime digitalization](https://www.imo.org/en/mediacentre/pressbriefings/pages/facilitation-committee-approves-digitalization-strategy-cyber-security-measures.aspx)
- [IMO cyber-resilience guidance for emerging technologies](https://wwwcdn.imo.org/localresources/en/OurWork/Security/Documents/IAPH%20Cyber%20resilience%20guidelines%20for%20emerging%20technologies%20in%20the%20maritime%20supply%20chain%20ENG.pdf)

Next: [07-domain-transfer-handoff-template.md](07-domain-transfer-handoff-template.md)
