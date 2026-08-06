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

For each proposed sensor location, answer the questions below. The answers determine enclosure, antenna, power, mounting, maintenance access, data handling, and whether the location is suitable:

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

The site survey is evidence for the design. Do not mark coverage as complete from a map or one indoor packet. Keep the test equipment, gateway and antenna configuration, device firmware, confirmed regional plan, test locations and conditions, expected-versus-received counts, and repeated RSSI/SNR observations so another engineer can reproduce the result.

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
pilot decision criteria
~~~

The pilot should compare the new method with the current method. Measure missed events, false alarms, response time, battery consumption, coverage, and operator effort.

## 4.6 Stage 6: verify production readiness

Before expanding beyond the pilot, verify that each operating boundary has a named owner and a tested procedure:

- the domain owner confirms what the measurements mean and which action follows an exception;
- the site or facilities owner confirms mounting, power, access, and removal procedures;
- operations users can recognize current, delayed, stale, missing, and invalid data;
- the security owner confirms network exposure, identities, credential rotation, and incident handling;
- the data steward confirms identifiers, access, retention, and deletion behavior;
- the platform and integration owners can diagnose, restore, reconcile, and roll back the service;
- the maintenance owner can inspect, calibrate, replace, reassign, and decommission devices.

Test rollback before production use. Define the trigger, the person who decides to roll back, the exact configuration or workflow restoration steps, the data-reconciliation method, and the communication path. The previous operating process must remain usable while the new telemetry path is disabled or corrected.

## 4.7 Change-control rules

Every change to a domain profile should identify:

- the profile version;
- affected devices and assets;
- decoder changes;
- database migration;
- dashboard and alert changes;
- expected historical-data impact;
- test evidence and observed result;
- owner of the deployment decision;
- deployment window and tested rollback trigger.

Never silently change a threshold or unit in a production dashboard.

Next: [05-port-interoperability-and-integration.md](05-port-interoperability-and-integration.md)
