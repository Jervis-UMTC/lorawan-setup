# Sensor + Gateway Readiness Consolidation Design

**Date:** 2026-09-02

## Goal

Make the repository safe to operate tomorrow without reconstructing state from historical checkpoints. Preserve detailed historical evidence in `deployment/server/cloud-production/00-build-execution-log.md`, while operator-facing documentation states only the newest accepted truth.

## Decisions

1. Keep one historical audit trail: `00-build-execution-log.md`.
2. Remove clearly superseded chat-continuation checkpoint documents instead of maintaining multiple conflicting resume points.
3. Convert the current server continuation document into a concise current-state source of truth rather than another chronological log.
4. Correct stale status prose in live gateway/sensor manuals where later evidence already proves PASS.
5. Add a single tomorrow bring-up runbook covering flashed gateway -> service checks -> EMU-01 -> OTAA -> payload-v2 -> telemetry/evidence -> sensor preflight.
6. Add the final EMU-01 Arduino source tree. Keep OTAA AppKey local in ignored `secrets.h`; commit only a template.
7. Preserve the frozen 46-byte payload-v2 contract, plain AS923, Class A, unconfirmed telemetry, 15-second monotonic schedule, seven validity bits, and deterministic `SENSOR_TX` output.
8. Do not claim hardware PASS from static repository checks. Hardware-dependent gates remain explicit tomorrow checks.
9. Keep Reserved-IP failover and external Fabric activation separate from normal sensor/gateway bring-up; they must not block basic RF/telemetry acceptance.

## Tomorrow success path

`flash accepted Gateway OS release -> boot -> verify RAK5146/AS923/EUI/SIM7600/local MQTT/evidence services -> provision protected identities -> verify public MQTT/evidence reachability -> flash EMU-01 -> 10 healthy serial cycles -> OTAA -> 10 decoded payload-v2 comparisons -> Node-RED/TimescaleDB/Grafana/evidence lineage -> SENSOR_PREFLIGHT_STATUS=GO`.

## Safety boundaries

- Never commit AppKeys, private keys, passwords, tokens, or recovery material.
- Do not rebuild the accepted Gateway OS image tomorrow unless its integrity check fails.
- Do not redesign payload-v2 or change region/profile during bring-up.
- Do not convert SEC-02 to its security firmware until its remaining decoded-vs-Serial legitimate-node check is complete and its temporary credential is retired.
- A failed hardware check stops at the first failing layer; passed infrastructure is not rebuilt without evidence that it regressed.
