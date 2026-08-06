# Horizontal Technology Transfer

This folder explains how to transfer the current agriculture LoRaWAN platform into another operational domain, such as port services, logistics, facilities, utilities, or environmental monitoring.

The goal is reuse with controlled adaptation:

~~~text
Reusable platform core
  -> domain profile
  -> site and asset registry
  -> device and decoder mapping
  -> workflows and dashboards
  -> domain integrations
~~~

Do not copy an agriculture dashboard and rename the title to port dashboard. Transfer the technical foundation, then redesign the data model, operational process, security boundary, and acceptance criteria for the new domain.

## Current platform core

The current project provides:

- RAK5146 gateway hardware;
- ChirpStack LoRaWAN network server;
- MQTT event delivery;
- Node-RED processing;
- PostgreSQL and TimescaleDB telemetry storage;
- Grafana dashboards and alerts;
- optional Hyperledger Fabric attestation;
- documented backups, roles, and troubleshooting.

The current application profile is agriculture, including Dragino S31/S31B temperature, humidity, and battery values. That profile is replaceable.

## Recommended order

1. [01-transfer-framework-and-roles.md](01-transfer-framework-and-roles.md) — Define what is reusable and who owns the new domain.
2. [02-core-platform-and-domain-profile.md](02-core-platform-and-domain-profile.md) — Separate the common data model from domain-specific configuration.
3. [03-agriculture-to-port-case-study.md](03-agriculture-to-port-case-study.md) — Work through port services as a concrete transfer example.
4. [04-adaptation-workflow-and-stakeholders.md](04-adaptation-workflow-and-stakeholders.md) — Run discovery, site surveys, pilots, and acceptance.
5. [05-port-interoperability-and-integration.md](05-port-interoperability-and-integration.md) — Connect port telemetry to existing operational systems.
6. [06-risk-security-regulatory-and-operations.md](06-risk-security-regulatory-and-operations.md) — Handle safety, cyber risk, RF, privacy, and lifecycle operations.
7. [07-domain-transfer-handoff-template.md](07-domain-transfer-handoff-template.md) — Reuse the questionnaire for the next domain.

## Transfer principle

Keep the stable parts stable:

- radio gateway and network-server operations;
- MQTT topic handling;
- normalized timestamps and identifiers;
- TimescaleDB storage mechanics;
- Node-RED deployment and observability;
- Grafana provisioning and backups;
- identity, audit, and change-control practices.

Change the parts that express business meaning:

- assets and locations;
- sensor models and decoder fields;
- units and thresholds;
- workflows and escalation;
- access roles;
- retention and evidence rules;
- external system integrations;
- site-specific radio and safety constraints.

## Important limitation

LoRaWAN telemetry is appropriate for monitoring and low-rate control where the risk assessment permits it. It must not be assumed suitable for emergency shutdowns, collision avoidance, crane interlocks, navigation safety, or other safety-critical functions without a separate approved safety system.

References:

- [IMO Maritime Single Window](https://www.imo.org/en/ourwork/facilitation/pages/maritimesinglewindow-default.aspx)
- [IMO Compendium on Facilitation and Electronic Business](https://www.imo.org/en/ourwork/facilitation/pages/imocompendium.aspx)

Next: [01-transfer-framework-and-roles.md](01-transfer-framework-and-roles.md)
