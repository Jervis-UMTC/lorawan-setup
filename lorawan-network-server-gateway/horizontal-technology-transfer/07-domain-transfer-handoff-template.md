# 7. Domain Transfer Handoff Template

Copy this template for a new domain. Complete it with the domain owner, site owner, security owner, and platform owner. A blank field is a project decision, not an assumption.

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
Coverage evidence:
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

## 7.8 Acceptance checklist

- [ ] Domain owner approved the business problem.
- [ ] Site survey and coverage evidence are complete.
- [ ] Sensor model and installation are approved.
- [ ] Decoder and profile version are recorded.
- [ ] Asset identifiers are mapped.
- [ ] Units and quality states are approved.
- [ ] Data classification and retention are approved.
- [ ] Dashboards were reviewed by operators.
- [ ] Alerts were tested with real response owners.
- [ ] External integrations passed duplicate and outage tests.
- [ ] Security review is complete.
- [ ] Backup and restore were tested.
- [ ] Maintenance and battery ownership are assigned.
- [ ] Rollback and incident contacts are documented.
- [ ] Fabric handoff is complete, if applicable.
- [ ] Production owner signed off.

## 7.9 Reusable transfer decision

At the end of the pilot, record one outcome:

~~~text
reuse as-is
reuse with profile changes
reuse with new sensor and adapter
redesign platform component
stop and return to discovery
~~~

Explain the decision using evidence from coverage, data quality, operations, security, cost, and business value.

Next: [00-README.md](00-README.md)
