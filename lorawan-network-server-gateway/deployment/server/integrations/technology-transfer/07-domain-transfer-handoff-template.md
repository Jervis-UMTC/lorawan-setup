# 7. Domain Transfer Handoff Template

Copy this template when adapting the platform to a new domain. Fill each section with facts that change the technical design: assets, locations, devices, radio plan, data contract, workflows, integrations, security boundaries, and recovery needs. A blank field is an unresolved input, not permission to assume a value.

## 7.1 Domain summary

~~~text
Domain:
Organization:
Site or sites:
Business problem:
Operational owner:
Technical owner:
Security owner:
Target pilot date:
Production decision date:
Out of scope:
~~~

## 7.2 Asset and location model

~~~text
Site identifier:
Zone identifiers:
Asset types:
Asset identifier source:
Device-to-asset assignment owner:
Mobile asset behavior:
Location update method:
Historical assignment required: yes/no
~~~

## 7.3 Sensor and radio model

~~~text
Sensor model:
Firmware:
Decoder:
Frequency plan:
Gateway model:
Gateway locations:
Expected reporting interval:
Battery or power:
Environmental rating:
Calibration requirement:
Coverage evidence location and test date:
Regional authorization evidence:
~~~

## 7.4 Data contract

~~~text
Profile ID:
Profile version:
Canonical metrics:
Units:
Valid ranges:
Quality states:
Timestamp source:
Duplicate key:
Retention:
Data classification:
Raw-payload policy:
~~~

## 7.5 Workflow and alerting

~~~text
Normal condition:
Exception condition:
Alert recipient:
Response time:
Required action:
Escalation:
False-positive owner:
After-hours process:
Safety boundary:
~~~

## 7.6 External integrations

~~~text
System name:
System of record:
Interface type:
Authentication:
Identifier mapping:
Event schema:
Acknowledgement:
Retry behavior:
Correction behavior:
Owner:
~~~

## 7.7 Fabric handoff, if required

~~~text
Use case requiring shared ledger:
Submitting organization:
MSP ID:
Channel:
Chaincode:
Transaction function:
Query function:
Endorsement policy:
Client identity owner:
TLS and certificate process:
On-chain fields:
Off-chain fields:
Digest algorithm:
Idempotency key:
Commit-status handling:
~~~

## 7.8 Verify the pilot before production use

Use the checks below as test outcomes, not paperwork fields:

1. Confirm the business problem, affected assets, expected reporting interval, and decision that telemetry will support.
2. Complete the site survey and prove coverage with representative devices and conditions.
3. Verify the exact sensor model, firmware, installation, decoder/profile version, units, valid ranges, and quality states.
4. Demonstrate device-to-asset mapping and historical assignment behavior.
5. Confirm data classification, retention, access roles, and raw-payload handling in the deployed systems.
6. Have the people who will respond review the dashboards, then inject delayed, stale, missing, and threshold events and confirm the expected notification and action.
7. Test every external integration for duplicate delivery, outage, retry, correction, and reconciliation behavior.
8. Restore the telemetry database and service configuration in isolation, then verify the recovered data and application path.
9. Exercise rollback in the pilot environment and confirm the previous operating method remains usable.
10. Complete the Fabric endpoint, identity, contract, commit-status, and reconciliation tests when Fabric is part of the design.

A healthy pilot produces repeatable coverage, plausible decoded data, actionable alerts, bounded failure behavior, and a tested recovery path. Any safety, ownership, retention, or rollback gap remains a production blocker even when MQTT packets are arriving.

## 7.9 Reusable transfer decision

At the end of the pilot, choose one outcome:

~~~text
reuse as-is
reuse with profile changes
reuse with new sensor and adapter
redesign platform component
stop and return to discovery
~~~

Explain the decision using evidence from coverage, data quality, operations, security, cost, and business value.

Next: [00-README.md](00-README.md)
