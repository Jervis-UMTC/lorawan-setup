# Grafana Local Access for Research Tests

## Current working access

Grafana remains private on `ulc-03` and is not exposed on a public interface. The research workstation reaches it through an SSH local-forward only:

- local Grafana health: `http://127.0.0.1:3000/api/health`
- research dashboard: `http://127.0.0.1:3000/d/lorawan-research-cockpit/lorawan-research-test-cockpit?orgId=1&refresh=15s`
- local recorder cockpit: `http://127.0.0.1:8765/`

The Grafana research dashboard UID is `lorawan-research-cockpit`. The commissioned dashboard has 14 panels and a 15-second refresh interval. Grafana authentication remains enabled; the tunnel does not bypass the normal login policy.

## Tunnel identity and restriction

The workstation uses a dedicated SSH identity outside the repository:

```text
%USERPROFILE%\.ssh\id_ed25519_grafana_tunnel_v2
```

Public-key fingerprint:

```text
SHA256:VkB5oVhTf5/dryIVJS+C9lrc8Dj6Ey7Eo6xKyR58JaI
```

The key is intentionally separate from the administrator SSH identity so the unattended visualization tunnel never needs the administrator key passphrase. The corresponding `opsadmin` authorization on `ulc-03` is restricted to the Grafana loopback destination and a non-shell forced command:

```text
restrict,port-forwarding,permitopen="127.0.0.1:3000",command="/usr/bin/sleep 2147483647" <public-key> lorawan-grafana-tunnel-v2
```

Do not replace this with an unrestricted SSH key, public Grafana bind, anonymous Grafana access, or a firewall exception.

## Workstation startup

The tunnel command is stored outside the repository at:

```text
%LOCALAPPDATA%\LoRaWAN\grafana-tunnel.cmd
```

It starts OpenSSH with the following effective controls:

```text
-N -T
-L 127.0.0.1:3000:127.0.0.1:3000
BatchMode=yes
IdentitiesOnly=yes
StrictHostKeyChecking=yes
ExitOnForwardFailure=yes
ServerAliveInterval=30
ServerAliveCountMax=3
```

A hidden per-user Startup launcher runs the command at Windows logon:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lorawan-grafana-tunnel.vbs
```

Windows Task Scheduler is not required. This design was selected because Task Scheduler creation is denied by workstation policy for the current user.

## Verification

From the workstation, verify the private Grafana path with:

```powershell
curl.exe -fsS http://127.0.0.1:3000/api/health
```

Expected health characteristics:

```text
database: ok
version: 13.2.0
```

Verify the tunnel process with:

```powershell
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
  Where-Object { $_.CommandLine -like '*id_ed25519_grafana_tunnel_v2*' } |
  Select-Object ProcessId, CommandLine
```

Verify the presentation cockpit independently with:

```powershell
curl.exe -fsS http://127.0.0.1:8765/
```

The local Research Cockpit is the convenient presentation surface. Grafana is the deeper read-only database/evidence view. Neither dashboard replaces recorder raw evidence, sealed hashes, generated research summaries, or Fabric/evidence truth.

## Recovery

If `127.0.0.1:3000` is unavailable after logon:

1. Confirm `ulc-03` is reachable over SSH and Grafana is healthy on its loopback listener.
2. Confirm the v2 tunnel key exists at the path above and that its public fingerprint still matches this document.
3. Confirm `ulc-03` still has exactly one `lorawan-grafana-tunnel-v2` authorization with the restricted options above.
4. Run `%LOCALAPPDATA%\LoRaWAN\grafana-tunnel.cmd` manually once and repeat the health check.
5. If that succeeds, verify the Startup VBS path exists. Re-create only the launcher if it was removed; do not broaden server authorization.

If the tunnel key must be rotated, create a new dedicated key, replace only the matching restricted authorization on `ulc-03`, update the local launcher to the new identity, prove the health endpoint through the new tunnel, and delete the old key and authorization only after the new path passes.

## Security boundary

The tunnel changes only workstation-to-`ulc-03` visualization access. It does not change Grafana authentication, PostgreSQL permissions, firewall policy, public listeners, LoRaWAN traffic, evidence capture, Fabric adapter ownership, or the current ULC-01/ULC-02 Fabric write-safety state.
