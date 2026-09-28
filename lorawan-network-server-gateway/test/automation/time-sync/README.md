# Root PDC Time Repair

The Chapter IV research recorder requires the Windows workstation clock to be within ±0.250 s of cloud UTC. The workstation is domain-joined and correctly follows `svtgm-ad.ad.hijo.com`; therefore the workstation must **not** be pointed directly at public NTP.

Live diagnosis on 2026-09-14 found the root PDC advertising `Stratum 1`, `RefID=LOCL`, source `Local CMOS Clock`, while its Windows Time client type was `NT5DS (Policy)`. The workstation matched the PDC within milliseconds but the PDC was about 119 seconds behind cloud/public UTC. Gateway LTE/NTP, cloud spread, EMU, SEC, database topology, and evidence readiness were otherwise healthy.

The supported Active Directory model is: domain members follow the domain hierarchy, while the forest-root PDC emulator synchronizes with an external authoritative NTP source and is marked reliable.

`repair-root-pdc-time.ps1` implements that model without weakening the recorder clock gate. It must run **on the PDC emulator** from an elevated account authorized to administer Group Policy. By default it is plan-only. `-Apply` saves the existing W32Time state, creates a PDC-only GPO linked first on the Domain Controllers OU, scopes Apply permission to the PDC computer, sets the client type to `NTP`, configures the external peer list, enables the NTP client and server providers, sets `AnnounceFlags=5`, refreshes policy, restarts W32Time, and verifies that the source is no longer a local/virtual clock.

The live 2026-09-14 repair used the dedicated GPO `SmartAgri PDC Authoritative Time Source` with `time.windows.com,0x8`. After `gpupdate /force`, W32Time restart, and `w32tm /resync /rediscover`, the PDC reported `time.windows.com,0x8` at Stratum 5. A second deliberate policy refresh/restart/resync kept the same source, proving the repair survives normal Group Policy refresh and service restart. Domain workstations remain on the normal AD hierarchy rather than public NTP.

Example from an authorized elevated PowerShell session on the PDC:

```powershell
.\repair-root-pdc-time.ps1
.\repair-root-pdc-time.ps1 -Apply
```

The default peer is `time.windows.com,0x8`. A different approved peer list can be supplied:

```powershell
.\repair-root-pdc-time.ps1 -Peers @("ntp1.example.org,0x8","ntp2.example.org,0x8") -Apply
```

Before changing anything, the script saves W32Time query output and registry state under `%ProgramData%\SmartAgri\PdcTimeRepair\<timestamp>`. If rollback is required:

```powershell
.\repair-root-pdc-time.ps1 -RollbackFrom "C:\ProgramData\SmartAgri\PdcTimeRepair\<timestamp>"
```

After the PDC source is verified, keep domain workstations on `NT5DS`; allow/request a normal domain resync, then rerun:

```powershell
python -u test\automation\research-recorder\research_recorder.py preflight --require-emu --require-sec
```

Do not start counted research trials until the recorder reports `CLOCK_GATE=PASS`.

Post-repair verification on 2026-09-14 passed the full recorder clock gate: workstation-to-cloud skew `+0.036231 s` (limit `±0.250 s`), three-cloud-node spread `0.009252 s` (limit `0.250 s`), and Gateway-01-to-cloud skew `-0.373203 s` (limit `±1.500 s`). The same preflight found `EMU_PORT=COM11`, `SEC_PORT=COM16`, ULC01 as PostgreSQL leader, ULC02/ULC03 as replicas, all evidence readiness endpoints HTTP 200, and zero evidence gaps or integrity failures.

## One-prompt remote launcher

From the research workstation, use `launch-pdc-time-repair.ps1` instead of pasting a multiline repair block. It prompts once with `Get-Credential`, opens a Kerberos PowerShell remoting session to `svtgm-ad.ad.hijo.com`, copies the verified repair utility to the PDC, runs plan/preflight and then `-Apply`, prints the resulting W32Time source/status, removes the temporary remote copy, closes the session, and discards the in-memory credential variable. The administrator password is not written to repository files.

The launcher itself does not weaken the recorder clock gate. If the supplied account is not authorized to administer the PDC/Group Policy, the remote session or guarded repair fails and the counted study remains blocked.
