# 3. Agriculture to Port Services Case Study

The example reuses the platform for port services while changing the day-to-day workflows, data model, ownership, and acceptance tests.

## 3.1 What can be reused?

The following may remain the same:

- RAK5146 gateway service, subject to site coverage;
- ChirpStack and MQTT;
- Node-RED runtime and validation pattern;
- PostgreSQL and TimescaleDB;
- Grafana;
- backup and monitoring practices;
- optional Fabric attestation adapter;
- common UTC timestamp and event-key rules.

## 3.2 What changes?

The port project must redesign:

- asset and location hierarchy;
- sensor enclosure and mounting;
- device model and payload decoder;
- radio coverage around steel, containers, cranes, and buildings;
- alarm ownership and escalation;
- maintenance and calibration;
- connection to port operating systems;
- data classification and access between terminal, shipping line, customs, and authorities.

## 3.3 Candidate port-service use cases

| Port service | Possible telemetry | Operational action | LoRaWAN suitability |
|---|---|---|---|
| Reefer container monitoring | Temperature, humidity, door state, power state | Exception ticket or inspection | Often suitable for low-rate monitoring |
| Yard environmental monitoring | Air quality, noise, weather, dust | Environmental report or mitigation | Often suitable |
| Tank or water monitoring | Level, temperature, leak indication | Maintenance or environmental response | Depends on sensor and safety case |
| Gate and parking occupancy | Space state, queue estimate | Dispatch or traffic notification | Possible with site survey |
| Equipment condition | Vibration, temperature, runtime | Predictive maintenance work order | Possible at low rate; validate metal and motion |
| Berth or mooring observation | Position or tension-related data | Operator review | Requires domain and safety assessment |
| Worker-worn alerting | Man-down or panic signal | Safety response | Do not assume LoRaWAN is sufficient for critical life-safety |

The platform can transport a measurement. It does not by itself prove sensor truth or define whether an operator may stop a crane, release cargo, or declare a safety incident. Those decisions require approved operational procedures and, where applicable, independent safety systems.

## 3.4 Example mapping

| Agriculture concept | Port equivalent | Transfer action |
|---|---|---|
| Greenhouse | Reefer yard zone or controlled storage area | Replace asset taxonomy |
| Plant or crop zone | Container, tank, berth, gate lane, or equipment | Define new asset IDs |
| Temperature threshold | Cargo or equipment exception band | Get approved operational range |
| Farm operator | Terminal operator, maintenance, or safety desk | Define escalation |
| Irrigation action | Inspection, dispatch, or work-order action | Do not reuse the workflow automatically |
| Farm dashboard | Yard, reefer, environment, or maintenance dashboard | Redesign panels and filters |
| Agricultural retention | Commercial, safety, environmental, or regulatory retention | Define the required period and deletion constraints |
| Farm asset history | Chain of custody or maintenance history | Consider Fabric attestation |

## 3.5 Port physical constraints

Before ordering sensors:

- perform an RF survey with representative containers and equipment;
- account for metal shielding and changing container stacks;
- define indoor, outdoor, below-deck, and hazardous-area requirements;
- confirm antenna placement and enclosure ratings;
- confirm battery behavior at the desired reporting interval;
- test roaming or asset movement assumptions;
- define what happens when a device is unreachable;
- verify whether a sensor is certified for the installation environment;
- determine whether cellular, Wi-Fi, wired, or private LTE is required for part of the site.

The agriculture gateway location may not cover a port yard. Gateway count, antenna height, backhaul, and lightning protection may all change.

## 3.6 Port architecture

~~~text
Port sensors and equipment
  -> LoRaWAN gateways
  -> ChirpStack
  -> MQTT
  -> Node-RED domain profile
  -> TimescaleDB
  -> Grafana operations views
  -> Port system adapters
       -> terminal operating system
       -> CMMS or maintenance system
       -> environmental reporting
       -> port community system
       -> optional Fabric attestation
~~~

Keep the telemetry platform as an observation system. Existing port systems remain the systems of record for cargo, vessel calls, work orders, customs, and official reporting unless the port authority explicitly changes that decision.

## 3.7 Port pilot recommendation

Start with one non-safety-critical, measurable use case:

~~~text
Pilot: reefer temperature exception monitoring
Scope: one yard zone and a small number of assets
Input: approved temperature sensor and asset assignment
Action: create a review task when the approved band is exceeded
Success: fewer missed exceptions, acceptable battery life, and reliable coverage
No-go: automatic cargo release, crane control, or emergency shutdown
~~~

Use the pilot to validate operational value, not only MQTT packet delivery. Retain coverage maps, expected-versus-received message counts, stale-data behavior, operator response evidence, battery observations, and a documented no-go decision if the safety or coverage case fails.

References:

- [IMO Maritime Single Window](https://www.imo.org/en/ourwork/facilitation/pages/maritimesinglewindow-default.aspx)
- [IMO Compendium data harmonization](https://www.imo.org/en/ourwork/facilitation/pages/imocompendium.aspx)

Next: [04-adaptation-workflow-and-stakeholders.md](04-adaptation-workflow-and-stakeholders.md)
