# S1 physical replay and spoofing — non-counted live commissioning (2026-09-21)

**Outcome:** One genuine old-frame replay and one address-level modified-MIC spoof were each **transmitted by SEC-01, independently received by Gateway-01/RAK5146, and NOT accepted as application uplinks**. No attack-associated telemetry/DB/Fabric outbox row was created. Both runs used real LoRaWAN packets, not synthetic packets, and the security node was restored to its parked state. These are **two non-counted rehearsals**, NOT the 40-attempt formal S1 experiment.

## Environment and trust boundary

- Gateway-01 on AS923; RAK5146 received both frames on **923.400 MHz / SF7 / BW125 kHz**; server had cloud packet-flow correlation.
- EMU-01 was the registered physical-sensor control. SEC-01 was USB `COM16`, RUI3 `RUI_4.2.4_RAK4631`, parked `NWM=1,BAND=8,NJM=1,CLASS=A,NJS=0,DEVEUI=0000000000000000` before and independently after every attempt. SEC never received EMU-01 AppKey/session keys.
- Research-recorder PRE at authoritative cloud UTC `2026-09-21T07:22:46.227Z` passed, with `CLOCK_SERVER_MINUS_WORKSTATION_SECONDS=-86.403517`. **Do not compare the workstation `sent_at` directly to cloud UTC**: e.g., workstation `07:19:36.818Z` starts at calibrated cloud `07:18:10.414Z`.
- Original ciphertext captured from immutable gateway journal, packet-flow accepted row and concentratord radio log, with baseline proof of minimum FCnt age. The session contains one originally accepted control **reused for both uncounted demonstrations**; this does not qualify formal 10-per-condition controls.

## Actual real-world observations

| Proof | Old-frame replay | Invalid-MIC spoof |
|---|---|---|
| SHA-256 of RF PHYPayload | `ee93f1299e77f9371c65c8a2d15f3ffd0e93b538727362dc5377f7d236dc7ad0` | `e3add7a8ec4de6cb06212548409ae23afde71d8c4252e4a71de3aff9de35a9f1` |
| Control | originally accepted FCnt 212, event `2f3d728d-1897-4eed-a3cb-af8f144161f9`, Fabric TXID retained | same authorized control; DevAddr unchanged `0199DDF0` |
| Attack construction | retransmitted **exact 59-byte old ciphertext**; at fixture capture FCnt age 7 | new unaccepted FCnt **307**, latest accepted before forging **275**; MIC final byte XOR `01`, not recomputed |
| SEC transmission | `TXP2P DONE` | `TXP2P DONE` |
| Gateway journal sequence | **4280** | **4315** |
| RAK5146 uplink ID | **1391523988** | **3113324003** |
| Gateway capture UTC | `07:18:13.561Z` | `07:26:34.807Z` |
| Accepted application/DB event | **none** (gateway event only) | **none** (gateway event only) |
| New Fabric outbox work from attack | **none** | **none** |
| SEC post-test state | independently VERIFIED parked | independently VERIFIED parked |

ChirpStack's MQTT/app path generated **no accepted application uplink** corresponding to either attack SHA-256 even though `as923/gateway/.../event/up` recorded the frames. This is actual RF reception plus downstream rejection, not merely a UART transmit acknowledgement. The original legitimate control still has its accepted event and confirmed Fabric transaction.

**Additional spoof state proof:** At `07:33:03Z`, ChirpStack accepted a later *genuine* EMU-01 packet with **FCnt 307 and the same DevAddr**, event `2f15b9ee-286f-4ed7-ab7d-8bd2fcc4a05f`. Thus the prior forged FCnt-307 frame did **not** consume/advance the legitimate session's accepted counter. Its MIC was invalid by controlled construction; an **explicit ChirpStack MIC-error log was NOT_OBSERVED** in a bounded container log query. Do not claim a directly logged MIC error or formal MIC-specific scoring from these observations; preserve the actual construction/receipt/non-acceptance and later accepted genuine FCnt evidence.

## Test-code problems fixed by live hardware

The original helper `sec02_replay.py` forced DTR/RTS low on RUI3 USB, giving no AT responses, and kept one serial handle across `AT+NWM=0/1`, which can re-enumerate the port. Switched to one fresh USB handle per AT command, default DTR/RTS, bounded retries for configuration, **never** automatic retransmission on an ambiguous `AT+PSEND`, and independent post-restore readback. A second attempt then exposed the unsupported `AT+PCRYPT=0` (`AT_COMMAND_NOT_FOUND` on RUI3 4.2.4); removed that command and the unnecessary receive-mode setup for transmit-only P2P. `AT_COMMAND_NOT_FOUND` now fails promptly rather than timing out. Saved result JSON includes failure and restoration if a send fails. Successful exact replay and forged spoof now passed via the same helper. Two earlier failed/non-transmitted attempts are troubleshooting, not replay denominators.

Added `forge-invalid-mic` for reproducible ciphertext-only spoof fixture creation. It uniquely binds to an accepted control by RF SHA-256+uplink ID, checks the live highest accepted FCnt, preserves DevAddr/MType, advances FCnt16, flips one MIC byte, and never obtains or recomputes a valid key/MIC. It refuses overwrite or a missing accepted control.

All **14/14 S1 targeted code tests PASS**; complete fixed allowlist after this change **205/205 PASS across 16 suites**, `chapter4-results/code-qualification/offline-code-20260921T073413715890Z/code-only-summary.json`.

## Files, boundaries, next step

Immutable observation/evidence inputs and derived result files live in `chapter4-results/security/S1-rehearsal-20260921/`: `replay-R01/{fixture,baseline,send,replay-decision}.json`, `spoof-S01/{fixture,send,spoof-decision}.json`, `session-summary.json`, and `metadata/SHA256SUMS.csv` covering **8** evidence files. `session-summary.json` explicitly sets `counted_research=false`, `formal=false`, 2/2 gateway-received, 0/2 accepted attacks, and formal release `NOT_READY`.

The one-block S1 manual remains `CAPTURE_READY`, **not formal READY**: it must orchestrate **10 fresh replay controls + 10 independently received replays + 10 distinct genuine spoof controls + 10 independently received forged attempts**, full reception and ChirpStack MIC/counter decision capture, reject/no-DB/outbox checks and dedicated CSV scoring in one operator action. No formal Chapter 4 trial was counted. Avoid repeating the already proven two non-counted RF probes until the missing 40-attempt orchestration and explicit MIC/counter evidence capture are ready.
