# SEC RAK4631 / RUI3 — Physical Identity, Security Fixtures and Safe Restore

Expands [technology guide 20](20-rui3-security-node.md). This is the **separate project-owned, authorized lab security fixture**, variously called SEC-01/SEC-02 in historical docs. The shared name describes **one physical security node**, not evidence of two independent transmitters. Do not install EMU-01's legitimate AppKey or session keys, register SEC as EMU, or use the project procedures on an unrelated network.

## 1. Approved physical/firmware baseline

| Item | Commissioned SEC contract |
|---|---|
| WisCore | RAK4631 Core B on **RAK19007**, antenna attached |
| RUI3 | `RUI_4.2.4_RAK4631` |
| Normal mode | `NWM=1` LoRaWAN |
| Region selector | `BAND=8`, supported AS923-family fixture; match actual gateway plain AS923 RF channels for any authorized transmission |
| Activation / class | `NJM=1` OTAA; `CLASS=A` |
| Parked status | `NJS=0`, `DEVEUI=0000000000000000`, never EMU AppKey/session keys |
| Historical workstation port | COM16 at 2026-09-21 rehearsal; **rediscover**, never hard-code |

The older RUI3 3.4.2 lacked controls required by the commissioned raw RF rehearsal. A board marked RAK4630 on its shield may still be the correct full RAK4631 WisBlock Core. Do **not** flash EMU-01 Arduino firmware onto SEC just because the MCU family matches.

### RAK19007 assembly and B-copy acceptance history

RAK19007 has **four Sensor slots A–D and one IO slot**; it does not have EMU-01's six sensor slots/two IO slots. Before conversion to RUI3, the B-copy sensor kit was verified in two separate, **unpowered rebuild** profiles:

| Profile | Actual module placement |
|---|---|
| A | Sensor A=RAK1903 OPT3001, B=RAK12010 VEML7700, C=RAK12019 UV, D=RAK12011 barometer; IO=RAK12023 soil probe |
| B | Sensor A=RAK1906 BME680, B/C/D empty; IO=RAK12005 rain |
| **Current security baseline** | RAK19007 + Core B + antenna; Sensor A–D and IO **empty** |

Disconnect USB/battery/solar before profile changes and save pin-mapper/sensor evidence. **Never** restore Profile A/B over a physically transmitting current SEC merely to improve a report. `WB_IO2` remains shared sensor-power control on this base; profile A deliberately keeps its slot-B module I²C-only.

## 2. Start with read-only serial and identity

From Windows PowerShell (repo parent cwd):

~~~powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Description,PNPDeviceID
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'
python $R status
~~~

If the recorder currently owns SEC serial and an authorized firmware/AT action is scheduled, first use `python $R serial-pause --device sec`, and **resume** after the action. Do not open a second COM owner while counted recording.

At the positively identified SEC RUI3 AT console, read only:

~~~text
AT+VER=?
AT+BUILDTIME=?
AT+REPOINFO=?
AT+HWMODEL=?
AT+HWID=?
~~~

Then use the installed version's read-only commands for NWM, BAND, NJM, CLASS, NJS and DEVEUI; require current approved RUI3 firmware and the exact parked profile. A test must fail closed if the board identity, serial port, keys or state cannot be established without guesswork. Sanitize AT output and do **not** query/print key material into research captures.

## 3. Controlled fixture sequence — distinguish send from RF reception

Each authorized experiment has a **preplanned fixture**, a clock/source observation window and a defined expected decision. For S1, approved helper `test/automation/research-recorder/sec02_replay.py` uses captured *authorized* gateway evidence, safety checks, exact retained PHYPayload or reviewed modified-MIC bytes, and restores SEC after the action. Its dry-run is the only appropriate example here:

~~~powershell
python .\lorawan-network-server-gateway\test\automation\research-recorder\sec02_replay.py send --fixture '<APPROVED_RUN_DIR>\replay-R01\fixture.json' --dry-run
~~~

This is a **template** until the approved run directory exists and its SHA-256/fixture is verified. A dry-run is not a transmission. Actual transmit is only under the currently commissioned **non-counted** test protocol or a later formally released READY counted S1 runner. Do not manually improvise production key material or continuously transmit in P2P mode.

**Order of proof:**
1. Approved EMU real control accepted; capture original RF identity/hash, DevAddr/frame counter and source event, before selecting the old-frame or forgery fixture.
2. SEC positively identified and initially parked. Confirm intended RF frequency/SF/BW against actual Gateway-01 and AS923 authorization.
3. Record the distinct controlled SEC transmit action. `TXP2P DONE` is **not** gateway reception.
4. Prove a new physical **RAK5146 uplink ID**, timestamp and immutable gateway journal sequence/hash for the attack packet. If this boundary is absent, classify attempted RF fixture **INVALID**, not “rejected by ChirpStack”.
5. Check ChirpStack application acceptance, database and Fabric outbox independently for the attack identity. Distinguish explicit radio/MIC/counter rejection log (if actually observed) from inference based only on absence of accepted events.
6. Positively restore and read back **parked SEC**. Hash/seal all attempted, rejected, invalid and recovery evidence without rewriting failures.

**Important 2026-09-21 proven non-counted checkpoint:** one exact old-ciphertext replay and one new-counter wrong-MIC DevAddr spoof were independently received by RAK5146 (uplink IDs 1391523988 and 3113324003; journal sequences 4280 and 4315). Neither yielded an accepted ChirpStack application uplink, database row or outbox event. A later legitimate FCnt 307 was accepted, but an explicit ChirpStack **MIC-specific error log was not observed**. Report actual evidence, not invented error codes. All formal S1 attempts remain uncounted until the complete 10+10+10+10 orchestration has been commissioned.

## 4. Fix serial/RUI3 failures at the right layer

Real SEC hardware exposed three former helper defects: forcing USB DTR/RTS low muted AT replies, keeping one serial handle across `AT+NWM=0/1` failed when USB re-enumerated, and `AT+PCRYPT=0` was unsupported in RUI3 4.2.4. The corrected helper reopens a USB handle for each command, uses normal DTR/RTS, rejects `AT_COMMAND_NOT_FOUND` promptly, and **does not automatically resend** an ambiguous `AT+PSEND`—a timeout after possible RF transmit must not silently double the experiment denominator.

No SEC COM: inspect data cable/app-vs-DFU mode and current port. Wrong RUI3 version: use only the reviewed **SEC-only** DFU/conversion procedure with approved package SHA-256, require `Device programmed.`, rediscover COM then re-prove parked state. SEC transmit without new RAK uplink ID: compare antenna/frequency/SF/BW/radio conditions before blaming server security. Gateway RX with app acceptance unexpectedly present: preserve original evidence, investigate frame/session and controls; **do not** alter ChirpStack security settings or erase counters to make rejection happen.

## 5. Restore parked state and protect identity

After every fixture require all of: `NWM=1`, `BAND=8`, `NJM=1`, `CLASS=A`, `NJS=0`, `DEVEUI=0000000000000000`, no retained legitimate EMU keys/session secrets. No active raw/P2P transmitter or orphan serial process remains. The researcher records restoration time and command outputs separately from sealed RF evidence. Returning to parked state is part of a valid attack trial, **not** an optional cleanup.

Never use these rehearsals to claim the formal research S1 block is READY. Other methodology gaps, e.g. S2 application-layer replay definition, are independent of whether SEC has good radio hardware.

Source maintenance: [RAK19007 fixed profiles](../../test/preparation/sensor/assembly/02b-rak19007-sec02-fixed-profiles.md), [SEC preparation](../../test/preparation/sensor/01-configure-rak4631-emulators.md), [exact non-counted S1 evidence](../../test/automation/research-manual/S1-LIVE-REHEARSAL-20260921.md). The Word document must include physical identity, approved state, safe operator workflow, expected results and restoring the fixture within its own pages.
