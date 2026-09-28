# First-Day Operator Guide

This guide is for new operators of the commissioned LoRaWAN cloud and gateway. Start with the [technology index](00-README.md) and [dated baseline](CURRENT-DOCUMENTATION-BASELINE.md). Check real runtime state before making a claim about present health.

## Understand the actual system

EMU-01 collects agricultural measurements and transmits the frozen 46-byte payload-v2 over plain AS923. RAK5146/Concentratord receives the LoRaWAN radio frame; MQTT Forwarder stores it through loopback-only Mosquitto. SIM7600 LTE normally carries the mTLS bridge to cloud MQTT. ChirpStack validates LoRaWAN identity/session state; a single active Node-RED writes measurements and durable outbox records to PostgreSQL/TimescaleDB. Grafana reads from that database but never writes evidence or blockchain claims. A separately authenticated gateway journal/MQTT witness and verifier establish whether the original event's evidence is trustworthy. Eligible exact finalized payload bytes can then be anchored by the single enabled HRC Fabric adapter, with OpenBao signing authority. The research recorder, rather than dashboard screenshots, preserves counted experiment evidence.

## Which machine is it?

| Place | Purpose | Correct command environment |
|---|---|---|
| Gateway-01, Raspberry Pi 4B / RAK5146 | Radio, persistent local MQTT, SIM7600 and gateway journal | OpenWrt/BusyBox |
| ULC-01 | HA services, preferred cloud MQTT and enabled Fabric adapter | Ubuntu/Bash |
| ULC-02 | HA services, backup MQTT and fenced Node-RED/Fabric standby | Ubuntu/Bash |
| ULC-03 | HA services, normal active Node-RED and Grafana | Ubuntu/Bash |
| Research workstation | USB-attached EMU-01/SEC and supervised recorder | Windows/PowerShell |
| HRC Fabric hosts | Independently operated blockchain peers/orderers | Fabric-side procedures |

Database, OpenBao and Valkey leaders are elected roles: never assume they permanently belong to a particular ULC host. Private ULC addresses at the documented checkpoint are 10.104.0.2, 10.104.0.4 and 10.104.0.8 respectively; inspect live routes before changing them.

## First safe checks

On each approved ULC Ubuntu host, first identify the host and read its health without changing anything:

~~~bash
hostname -f
date -u
uptime
df -h
sudo systemctl --failed --no-pager
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
~~~

**PASS:** intended host, plausible UTC, adequate storage and no relevant crash loop. This does not prove a successful MQTT, SQL, evidence or Fabric operation; the numbered guide provides the next protocol-level check.

On the gateway (not on Ubuntu), use:

~~~sh
ubus call system board
date -u
df -h
ip route
logread | tail -n 80
~~~

**PASS:** expected platform, usable storage, plausible time and identifiable route. Confirm normal production Internet remains health-managed LTE; do not force the management Ethernet route. Do not reboot or reflash for an isolated service failure.

On the research workstation, from the parent folder containing the project repository:

~~~powershell
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'
python $R status
Get-Content '.\lorawan-network-server-gateway\test\automation\research-manual\CURRENT-READINESS.md'
~~~

**PASS for a counted experiment** additionally requires the overall technical gate, the selected individual test's READY state, hardware/clock preflight and that experiment's condition-specific GO/NO-GO. Old checkpoints are not current health reports. Do not launch experiments simply to complete a documentation-only inspection.

## Choose the correct procedure

- For one component, read its numbered technology operator guide (01–20).
- For cross-system tracing, read [guide 21](21-end-to-end-integration-and-data-lineage.md).
- For cloud installation and recovery, use the full deployment runbooks under `deployment/server/cloud-production/`.
- For hardware and image recovery, use `deployment/gateway/`.
- For formal experiments, use `test/`, including `test/automation/research-manual/CURRENT-READINESS.md` and the recorder. Do not use a technical preflight failure as a successful counted run.

Never mix the minimal dissertation test VM procedure with the production ULC-01/02/03 three-server topology. The experiment instructions and the deployment instructions are different tracks.
