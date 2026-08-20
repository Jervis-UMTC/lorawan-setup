# Horizontal Technology Transfer

Use these guides to adapt the agriculture LoRaWAN platform for ports, logistics, facilities, utilities, environmental monitoring, or another domain. Reuse the technical foundation, then verify the receiving site's assets, devices, radio conditions, operations, security, retention, and integration requirements.

```text
Reusable platform core
  -> domain profile
  -> site and asset registry
  -> device and decoder mapping
  -> workflows and dashboards
  -> domain integrations
```

Do not copy an agriculture dashboard and only rename its title. A successful transfer preserves the reliable gateway, MQTT, storage, and observability mechanisms while replacing the business meaning, device mapping, thresholds, workflows, and acceptance tests.

## Current platform core

Confirm the deployed versions and capacity before treating a component as reusable:

- Raspberry Pi 4B and RAK5146 Gateway OS path;
- ChirpStack LoRaWAN network server;
- MQTT event delivery and gateway buffering;
- Node-RED validation and normalization;
- PostgreSQL and TimescaleDB telemetry storage;
- Grafana dashboards and alerts;
- optional Hyperledger Fabric attestation;
- backup, restore, identity, and troubleshooting procedures.

The current agriculture example profile uses the WisBlock/EMU-01 payload-v2 field set (soil, UV, barometer, two light sensors, environmental metrics, rain, battery, and validity bitmap). Those field names and validity semantics are still a **domain profile**, not a generic platform contract.

## Read in this order

1. [01-transfer-framework-and-roles.md](01-transfer-framework-and-roles.md) — Separate reusable platform behavior from the new domain's ownership and decisions.
2. [02-core-platform-and-domain-profile.md](02-core-platform-and-domain-profile.md) — Define assets, locations, devices, metrics, units, quality states, and versions.
3. [03-agriculture-to-port-case-study.md](03-agriculture-to-port-case-study.md) — Work through port services as a concrete adaptation example.
4. [04-adaptation-workflow-and-stakeholders.md](04-adaptation-workflow-and-stakeholders.md) — Perform discovery, site survey, pilot, and evidence-based acceptance.
5. [05-port-interoperability-and-integration.md](05-port-interoperability-and-integration.md) — Connect telemetry to existing operational systems without losing identifiers or retry behavior.
6. [06-risk-security-regulatory-and-operations.md](06-risk-security-regulatory-and-operations.md) — Define radio, cyber, privacy, safety, and lifecycle boundaries.
7. [07-domain-transfer-handoff-template.md](07-domain-transfer-handoff-template.md) — Collect the concrete inputs and test outcomes for the next domain.

## Keep these platform mechanisms stable

- gateway and network-server operating boundaries;
- Gateway EUI, Device EUI, region, and topic normalization;
- MQTT retry and duplicate-handling behavior;
- UTC timestamps and stable event keys;
- TimescaleDB storage, backup, and restore mechanics;
- Node-RED deployment and observability;
- Grafana provisioning and freshness handling;
- identity, access, credential rotation, and recovery procedures.

## Redesign these domain-specific parts

- sites, zones, assets, and assignment history;
- sensor models, firmware, payload codecs, and metric dictionary;
- units, valid ranges, stale thresholds, and quality states;
- dashboards, alerts, response actions, and escalation;
- access roles, data classification, and retention;
- external interfaces and acknowledgement/reconciliation behavior;
- site-specific coverage, interference, installation, and safety constraints.

## Safety boundary

LoRaWAN telemetry is suitable for monitoring and low-rate control only where the risk assessment permits it. Do not use this platform as an emergency shutdown, collision-avoidance, crane-interlock, navigation-safety, or other safety-critical control system unless a separately engineered and validated safety system provides that function.

Next: [01-transfer-framework-and-roles.md](01-transfer-framework-and-roles.md)
