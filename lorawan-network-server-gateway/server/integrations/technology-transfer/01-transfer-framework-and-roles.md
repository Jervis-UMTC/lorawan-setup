# 1. Transfer Framework and Roles

Horizontal technology transfer is the controlled movement of a proven capability from one domain to another. It is not only a software port. The receiving domain changes the assets, terminology, operating hours, risk tolerance, data owners, and integration obligations.

## 1.1 Three-layer model

### Layer A: reusable platform core

This layer should be operated once and reused:

- gateway registration and radio configuration;
- ChirpStack tenants, applications, and device profiles;
- MQTT broker and topic conventions;
- Node-RED runtime and deployment;
- telemetry database administration;
- Grafana runtime;
- backups, monitoring, and access control;
- optional Fabric adapter runtime.

### Layer B: domain profile

This layer describes meaning:

- domain name;
- site, zone, and asset hierarchy;
- device models and decoders;
- metric names and units;
- normal ranges and alert thresholds;
- data quality rules;
- user roles;
- retention and evidence policy.

### Layer C: site and workflow adaptation

This layer changes for each deployment:

- physical sensor placement;
- RF coverage;
- asset identifiers;
- maintenance and calibration;
- shift and escalation process;
- existing systems and APIs;
- local safety and cybersecurity controls.

## 1.2 Reuse decision matrix

Before changing code, classify each item:

| Item | Reuse as-is | Configure | Redesign |
|---|---:|---:|---:|
| Gateway service | Usually | Region and site | Only if hardware changes |
| ChirpStack | Usually | Tenant and device profiles | Only if scale or tenancy changes |
| MQTT topic handling | Usually | Application names | If external broker is required |
| TimescaleDB mechanics | Usually | Retention and indexes | If data volume or residency changes |
| Node-RED runtime | Usually | Flows and credentials | If workflow reliability needs another service |
| Grafana runtime | Usually | Dashboards and users | If central analytics is required |
| Sensor decoder | No | Select model | New decoder or codec |
| Asset model | No | Map to profile | Domain-specific design |
| Alert thresholds | No | Domain-approved values | Safety or compliance redesign |
| External integrations | No | Endpoint settings | Domain system integration |
| Ownership and operating decisions | No | Assign local owners | New operating model |

## 1.3 Transfer roles

| Role | Main responsibility |
|---|---|
| Platform owner | Keeps the common stack stable and versioned |
| Domain owner | Defines what the measurements mean and what action follows |
| Site engineer | Performs placement, power, RF, and maintenance assessment |
| Data steward | Defines identifiers, quality, privacy, retention, and access |
| Integration owner | Connects APIs, databases, CMMS, PCS, ERP, or Fabric |
| Security owner | Approves credentials, network boundaries, logging, and incident response |
| Operations owner | Accepts alarms, owns escalation, and measures outcomes |
| Vendor or sensor owner | Supplies device limits, calibration, battery, and support information |

**Stop here. Do not begin a domain transfer** with only a software developer and no named operational owner, security owner, data steward, maintenance owner, and rollback authority. Blank ownership is an unresolved risk, not an implicit assignment.

## 1.4 Inputs to resolve before the pilot

Resolve these items in order because each one changes the device, data model, deployment, or operating procedure. Retain the decision and the evidence that another engineer needs to reproduce it; separate approval forms and operator/date fields are not required by this guide.

1. State the operational problem and the decision that telemetry should support.
2. Identify the team that owns the measured condition and the response when it is abnormal.
3. Complete a site survey that proves coverage, power, mounting, and maintenance access under representative conditions.
4. Define the asset identifiers, device assignments, metric names, units, valid ranges, and stale-data rules.
5. Define who may access the data, how long it is retained, and which fields may leave the site or organization.
6. Set a small pilot scope with measurable coverage, data-quality, battery, alert, and recovery targets.
7. Have the people who will respond test delayed, missing, stale, and threshold events.
8. Assign ongoing device maintenance, platform support, credential rotation, backup, and rollback responsibilities.
9. Keep the previous operating method available until the pilot proves the replacement path.

## 1.5 Technology-transfer anti-patterns

Avoid:

- starting from a dashboard instead of an operational decision;
- assuming the agriculture sensor is suitable for port equipment;
- using a device EUI as the only business asset identifier;
- putting all raw telemetry on Fabric;
- exposing internal services to the internet for convenience;
- using the same thresholds in every climate or operating environment;
- treating an alert as a control command without a safety review;
- deploying without a calibration and battery-replacement process;
- calling a pilot successful only because packets arrived.

Next: [02-core-platform-and-domain-profile.md](02-core-platform-and-domain-profile.md)
