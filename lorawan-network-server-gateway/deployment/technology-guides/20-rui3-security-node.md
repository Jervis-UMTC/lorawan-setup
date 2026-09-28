# RUI3 Security Node — Operator Manual

## What this technology does

SEC is the separate RAK4631 security-test node used only for authorized LoRaWAN authentication/replay/spoofing fixtures in this project lab.

Project history calls the same physical role both SEC-01 and SEC-02. Do not treat those names as two separate nodes unless the topology is deliberately changed.

SEC must never receive EMU-01's legitimate AppKey or session keys.

## Current accepted baseline

~~~text
Hardware             RAK4631 on RAK19007
Firmware             RUI_4.2.4_RAK4631
Normal mode          LoRaWAN
Band                 BAND=8 / AS923 family fixture baseline
Join mode            OTAA
Class                A
Parked joined state  not joined
Parked DevEUI        0000000000000000
~~~

Older RUI3 3.4.2 is historical; it lacked controls required by the accepted raw-RF fixture.

## Safe parked state

~~~text
NWM=1
BAND=8
NJM=1
CLASS=A
NJS=0
DEVEUI=0000000000000000
no EMU-01 AppKey
no EMU-01 session key material
~~~

Keep the LoRa antenna attached.

## Step 1 — Identify the physical node

~~~text
[ ] physical board is SEC
[ ] base is RAK19007
[ ] normal sensor/IO slots empty unless a specific fixture requires them
[ ] LoRa antenna attached
[ ] this is not EMU-01
~~~

Stop if identity is uncertain.

## Step 2 — Discover the current COM port

~~~powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Description,PNPDeviceID
~~~

Historical accepted state used COM16, but reset/DFU may change it.

## Step 3 — Pause recorder ownership if needed

~~~powershell
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'; python $R serial-pause --device sec
~~~

After the approved action:

~~~powershell
python $R serial-resume --device sec
~~~

## Step 4 — Verify RUI3 identity read-only

At the AT console:

~~~text
AT+VER=?
AT+BUILDTIME=?
AT+REPOINFO=?
AT+HWMODEL=?
AT+HWID=?
~~~

**PASS means:** the expected RAK4631/RUI3 family is present and the accepted current firmware is identified.

Save only sanitized output.

## Step 5 — Verify parked state before transmission

Use current RUI3 read-only status queries to prove:

~~~text
LoRaWAN mode
BAND=8
OTAA
Class A
not joined
all-zero parked DevEUI
~~~

If SEC unexpectedly contains a production identity, stop before transmitting.

## Step 6 — Prefer the reviewed fixture helper

Use:

~~~text
test/automation/research-recorder/sec02_replay.py
~~~

The helper selects already-captured authorized evidence, enforces replay-age checks, correlates with gateway evidence, supports dry-run review, performs the approved SEC fixture action and restores the parked state.

Do not manually decrypt/re-encrypt or reconstruct EMU-01 traffic for replay.

## Step 7 — Dry-run before RF transmission

~~~powershell
python .\lorawan-network-server-gateway\test\automation\research-recorder\sec02_replay.py send --fixture '<RUN-DIR>\replay-R01\fixture.json' --dry-run
~~~

Review the fixture and restoration plan before a real authorized transmission.

Use the real transmit action only through a currently READY test procedure.

## Step 8 — Require gateway reception

SEC reporting transmit success is not enough.

A counted RF security attempt is valid only when:

~~~text
SEC transmits
-> Gateway-01 / RAK5146 receives a distinct RF frame
-> downstream security behavior can be classified
~~~

If RAK5146 did not receive it, the attack attempt is invalid and must be repeated according to the experiment manual.

## Step 9 — Keep LoRaWAN security enabled

Do not disable or weaken:

~~~text
frame-counter validation
MIC validation
OTAA key validation
normal ChirpStack security behavior
~~~

The experiment measures the commissioned security controls.

## Step 10 — Prove downstream outcome

For a gateway-received rejected frame, require recorder evidence that no new legitimate application event, telemetry row or Fabric outbox item was produced from that rejected frame.

Do not infer rejection only from Grafana.

## Step 11 — Restore parked state after every fixture

Verify:

~~~text
LoRaWAN mode
BAND=8
OTAA
Class A
not joined
all-zero parked DevEUI
no EMU-01 key/session material
~~~

Do not leave SEC in P2P/raw transmit mode between trials.

## Step 12 — RUI3/DFU recovery

If SEC has the wrong firmware:

1. positively identify SEC;
2. use the approved RAK4631-R DFU/conversion procedure;
3. hash the selected package;
4. require Device programmed;
5. rediscover the application COM port;
6. verify RUI3 identity;
7. restore parked state;
8. perform only an uncounted reception rehearsal before counted testing.

Do not copy old package names blindly from historical screenshots.

## Current accepted capability

RUI3 4.2.4 previously demonstrated the required raw-RF controls and one uncounted transmission was received by Gateway-01.

Each counted security attempt still requires its own gateway-reception proof.

## Troubleshooting order

| Symptom | First check |
|---|---|
| no SEC COM | USB / application-vs-DFU mode |
| AT command missing | wrong RUI3 version/family |
| serial busy | recorder/other terminal owns port |
| SEC TX, gateway no RX | antenna/RF parameters/current conditions |
| gateway RX, unexpected acceptance | preserve evidence; inspect frame/session/security state |
| SEC left in raw mode | restore parked state immediately |
| EMU-01 secret material present | stop; remove it and treat as trust-boundary violation |

## Security boundary

- authorized lab fixture only;
- never install EMU-01 legitimate AppKey/session keys;
- use dedicated temporary fixture identities where required;
- do not store secret keys in result files;
- dry-run first;
- prove RF reception;
- restore parked state after each fixture.

## Completion checklist

- correct SEC hardware identified;
- current COM discovered;
- RUI3 4.2.4 verified;
- parked state verified;
- no EMU-01 secret material present;
- reviewed helper/fixture used;
- dry-run reviewed;
- gateway reception proven for counted attempts;
- recorder captures downstream outcome;
- parked state restored;
- evidence preserved unmodified.

## Complete SEC hardware/security-fixture companion

Use [SEC RAK4631/RUI3 physical identity, authorized RF fixture workflow, evidence requirements and parked-state restore](SEC-RUI3-HARDWARE-SECURITY-RESTORE.md). An RF send result is not gateway reception, and a non-counted rehearsal is not formal S1 completion.

## Detailed references

- [Sensor/RUI3 preparation](../../test/preparation/sensor/01-configure-rak4631-emulators.md)
- [Replay/spoofing experiment](../../test/execution/04-replay-spoofing.md)
- [Research recorder](../../test/automation/research-recorder/README.md)
