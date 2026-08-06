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
| Grafana runtime | Usually | Dashboards and users | If enterprise analytics is required |
| Sensor decoder | No | Select model | New decoder or codec |
| Asset model | No | Map to profile | Domain-specific design |
| Alert thresholds | No | Domain-approved values | Safety or compliance redesign |
| External integrations | No | Endpoint settings | Domain system integration |
| Governance and approvals | No | Local roles | New operating model |

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

No domain transfer should proceed with only a software developer and no operational owner.

## 1.4 Minimum transfer gates

Pass these gates in order:

1. Business problem is documented.
2. Domain owner accepts the proposed sensor data.
3. Site survey confirms coverage and installation feasibility.
4. Data dictionary and identifiers are approved.
5. Security and privacy review is complete.
6. One small pilot has measurable success criteria.
7. Operators validate that alerts are actionable.
8. Maintenance and ownership are funded.
9. Production support and rollback are defined.

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
