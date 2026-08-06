# 4. Adaptation Workflow and Stakeholders

Use a staged process so that a new domain does not inherit hidden assumptions from agriculture.

## 4.1 Stage 1: discovery

Meet the people who perform the work, not only the IT team. Capture:

- the operational decision that needs better information;
- who currently observes the condition;
- what happens when the condition is abnormal;
- the cost of a missed or false alert;
- the time window in which an action is useful;
- the assets and locations involved;
- current manual records and existing systems;
- the data that may be shared with other organizations;
- the acceptable outage and stale-data behavior.

Output:

~~~text
domain problem statement
operational owner
candidate use case
asset list
decision and escalation map
initial success metrics
known exclusions
~~~

## 4.2 Stage 2: site and asset survey

For each proposed sensor location, record:

| Category | Questions |
|---|---|
| Asset | What real asset is being measured? Who owns it? |
| Location | Is the location fixed, mobile, or temporary? |
| Environment | Temperature, water, dust, chemicals, impact, corrosion? |
| Radio | Can the gateway hear the device in normal and worst-case conditions? |
| Power | Battery, mains, solar, equipment power, replacement access? |
| Mounting | Is drilling, enclosure work, or a permit required? |
| Maintenance | Who inspects, calibrates, replaces, and removes it? |
| Safety | Could the installation create a trip, electrical, or operational hazard? |
| Security | Can someone tamper with or steal the device? |
| Data | What is the classification and retention requirement? |

The site survey is evidence for the design. Do not mark coverage as complete based on a map or a single indoor test.

## 4.3 Stage 3: domain profile

Create the profile before building dashboards:

1. asset and site hierarchy;
2. device-to-asset assignment;
3. metric dictionary;
4. units and valid ranges;
5. quality and missing-data rules;
6. alert conditions;
7. escalation owner;
8. retention and access;
9. external identifier mappings;
10. version and migration plan.

## 4.4 Stage 4: technical prototype

Prototype one sensor, one gateway path, one normalized record, one dashboard, and one operational notification. Verify:

- actual decoded payload;
- timestamp behavior;
- device replacement behavior;
- database insert and query;
- alert delay;
- dashboard interpretation;
- recovery after a broker or database restart;
- duplicate and replay behavior.

Do not add Fabric, a port community system, or a complex AI model until the base observation path is trusted.

## 4.5 Stage 5: controlled pilot

Use a defined pilot boundary:

~~~text
pilot start and end date
sites and assets in scope
devices and gateways in scope
operator group
support contacts
approved thresholds
data retention
daily review method
failure escalation
go/no-go meeting
~~~

The pilot should compare the new method with the current method. Measure missed events, false alarms, response time, battery consumption, coverage, and operator effort.

## 4.6 Stage 6: production acceptance

Require sign-off from:

- domain owner;
- site or facilities owner;
- operations users;
- security owner;
- data steward;
- platform owner;
- integration owner;
- maintenance owner.

Production acceptance must include a rollback plan. A rollback means the old operating process remains usable while the new telemetry path is disabled or corrected.

## 4.7 Change-control rules

Every change to a domain profile should identify:

- the profile version;
- affected devices and assets;
- decoder changes;
- database migration;
- dashboard and alert changes;
- expected historical-data impact;
- test evidence;
- approver;
- deployment and rollback time.

Never silently change a threshold or unit in a production dashboard.

Next: [05-port-interoperability-and-integration.md](05-port-interoperability-and-integration.md)
