# 4A. Host Security Hardening Execution Runbook

This file is the **live record of the hardening we actually perform** on each provisioned LoRaWAN cloud server.

Do not mark a step complete just because a command was typed. A step is complete only after its verification command passes and the observed result is recorded.

This runbook is based on two inputs:

1. the supplied `UBUNTU SERVER SECURITY HARDENING.docx`; and
2. additional controls required for this LoRaWAN HA design.

The supplied DOCX has **Section 12 / 12.1 / 12.2 / 12.3 / 12.4 highlighted yellow**. Those web-server/Nginx/basic-authentication steps are intentionally excluded from this hardening run. Public HTTPS/TLS will be implemented later through the LoRaWAN deployment's own HAProxy/PKI design, not by installing a generic Nginx site during base-host hardening.

## Status legend

```text
[ ] NOT STARTED
[~] IN PROGRESS / waiting for verification
[x] PASS
[!] BLOCKED / failed verification
[-] NOT APPLICABLE or deliberately not applied
```

For every host, keep evidence in this form:

```text
Host:
Date:
Operator:
Command(s):
Expected:
Observed:
Status:
Reason / notes:
```

Never paste passwords, private keys, API tokens, AppKeys, recovery keys, or complete secret-bearing connection strings into this file.

---

# Phase 0 - Safety before hardening

## 0.1 Keep a recovery path

[ ] Confirm the cloud provider console/recovery console works before changing SSH or firewall rules.

**Why:** SSH and firewall hardening can lock us out. The provider console is the recovery path if a rule is wrong.

## 0.2 Keep the current SSH session open

[ ] Keep the original SSH session connected while testing every SSH/firewall change from a second terminal.

**Why:** never replace a known-good management path until the new path has been proven.

---

# Phase 1 - Inspect the provisioned server before changing it

## 1.1 Baseline inspection

[x] Run on the newly provisioned server:

```bash
hostnamectl
cat /etc/os-release
uname -a
nproc
free -h
lsblk -f
df -hT
ip -br address
ip route
ss -lntup
systemctl --failed
timedatectl status
```

**Why each check exists:**

- `hostnamectl` - confirms hostname and architecture.
- `/etc/os-release` - confirms the actual distribution/version before we use distro-specific instructions.
- `uname -a` - confirms the running kernel.
- `nproc` - confirms the provisioned vCPU count.
- `free -h` - confirms RAM and whether swap is already enabled.
- `lsblk -f` and `df -hT` - confirm disk size, filesystem, and mounts before Docker/PostgreSQL consume space.
- `ip -br address` and `ip route` - identify public/private interfaces and the default route.
- `ss -lntup` - reveals services already accepting network connections.
- `systemctl --failed` - catches failed boot/services before we add more software.
- `timedatectl status` - confirms time synchronization, required later for TLS, PostgreSQL, etcd leases, logs, and LoRaWAN event timestamps.

**Stop condition:** investigate any unexpected listener, failed service, unexpected OS, missing/private network interface, or incorrect machine size before proceeding.

### Execution records - all three provisioned servers

All three hosts were inspected before any application-stack installation. Their baseline is intentionally nearly identical so later HA failures are not confused with OS/version drift.

```text
Host: ulc-01
Date: 2026-08-20
Operator: root session used for initial provider bootstrap
Expected OS: Ubuntu Server 24.04 LTS x64 (Noble)
Expected minimum POC resources: 1 vCPU / 2 GiB RAM / approximately 50 GiB disk
Observed OS: Ubuntu 24.04.4 LTS (Noble Numbat), kernel 6.8.0-124-generic, x86-64, DigitalOcean KVM Droplet
Observed CPU/RAM: 1 vCPU; 1.9 GiB RAM; no swap configured
Observed disk: /dev/vda1 ext4 root, 48 GiB usable filesystem, ~46 GiB available; separate /boot and /boot/efi; DigitalOcean config-drive ISO present as /dev/vdb
Observed network: eth0 = public IPv4 143.198.205.54/20 plus 10.15.0.5/16; eth1 = 10.104.0.2/20; default route exits through eth0
Observed listeners: only systemd-resolved loopback DNS and SSH TCP/22; SSH currently listens on 0.0.0.0 and [::]
Observed services: 0 failed systemd units
Observed time: UTC; system clock synchronized; NTP active
Status: PASS
Reason / notes: Baseline matches the intended Ubuntu/CPU/RAM/disk profile. At this early inspection point, `10.104.0.2/20` on `eth1` was only a candidate east-west address; it was later operationally validated by cross-node ICMP and TCP `2380` testing before etcd bootstrap. SSH broad-listening was expected before hardening.

Host: ulc-02
Date: 2026-08-20
Operator: root session used for initial provider bootstrap
Observed OS: Ubuntu 24.04.4 LTS (Noble Numbat), kernel 6.8.0-124-generic, x86-64, DigitalOcean KVM Droplet
Observed CPU/RAM: 1 vCPU; 1.9 GiB RAM; no swap configured
Observed disk: /dev/vda1 ext4 root, 48 GiB usable filesystem, ~46 GiB available; separate /boot and /boot/efi; DigitalOcean config-drive ISO present as /dev/vdb
Observed network: eth0 = public IPv4 165.22.253.127/20 plus 10.15.0.7/16; eth1 = 10.104.0.4/20; default route exits through eth0
Observed listeners: only systemd-resolved loopback DNS and SSH TCP/22; SSH currently listens on 0.0.0.0 and [::]
Observed services: 0 failed systemd units
Observed time: UTC; system clock synchronized; NTP active
Status: PASS
Reason / notes: Matches ulc-01 baseline. At this early inspection point, `10.104.0.4/20` on `eth1` was only a candidate east-west address; it was later operationally validated during the three-host network checks recorded in `00-build-execution-log.md`.

Host: ulc-03
Date: 2026-08-20
Operator: root session used for initial provider bootstrap
Observed OS: Ubuntu 24.04.4 LTS (Noble Numbat), kernel 6.8.0-124-generic, x86-64, DigitalOcean KVM Droplet
Observed CPU/RAM: 1 vCPU; 1.9 GiB RAM; no swap configured
Observed disk: /dev/vda1 ext4 root, 48 GiB usable filesystem, ~46 GiB available; separate /boot and /boot/efi; DigitalOcean config-drive ISO present as /dev/vdb
Current replacement network: eth0 = public IPv4 159.223.50.57/20 plus 10.15.0.6/16; eth1 = 10.104.0.8/20; default route = 159.223.48.1 via eth0
Observed listeners: only systemd-resolved loopback DNS and SSH TCP/22; SSH currently listens on 0.0.0.0 and [::]
Observed services: 0 failed systemd units
Observed time: UTC; system clock synchronized; NTP active
Status: PASS
Reason / notes: Replacement `ulc-03` matches the active host baseline after patch/reboot and SSH hardening. At this inspection point `10.104.0.8/20` on `eth1` was a candidate east-west address; it was later operationally validated with the other active nodes. The retired Droplet's `10.104.0.3/20` must not be used.

Three-host conclusion: PASS. All nodes run the same Ubuntu release and kernel, have the same CPU/RAM class, no swap, no failed systemd units, synchronized NTP, and no unexpected application listeners. The actual hostnames ulc-01/02/03 are already consistent; keep them stable and map them to logical HA roles in the documentation rather than renaming them after quorum services are created.
```

---

# Phase 2 - Patch the clean OS

## 2.1 Refresh package metadata and install security/bug-fix updates

### 2.1A Refresh metadata and preview pending upgrades

[~] Run on **all three hosts**, one host at a time, and save each result separately:

```bash
apt update
apt list --upgradable 2>/dev/null
```

Recommended order:

```text
ulc-01 -> ulc-02 -> ulc-03
```

Because the current bootstrap shell is already `root`, `sudo` is not required for this inspection. Later administrative work will move to a named sudo user.

**Why:** `apt update` downloads the current package indexes but does not install upgrades. Previewing `apt list --upgradable` gives us a before-state and lets us spot kernel, OpenSSH, networking, or cloud-agent changes before modifying the host.

Record the command output before continuing.

### Execution deviation - `ulc-01` was upgraded before the preview was captured

`ulc-01` was upgraded before its `apt list --upgradable` pre-upgrade evidence was saved. This is acceptable because no etcd, Patroni/PostgreSQL, OpenBao, ChirpStack, or other HA/quorum workload has been installed yet. Do not roll it back just to recreate the missing preview.

Post-upgrade evidence captured on 2026-08-20:

```text
Running kernel before reboot: 6.8.0-124-generic
Pending packages before reboot: none shown by apt list --upgradable
Reboot required before reboot: yes
Failed systemd units before reboot: 0
Unexpected listeners before reboot: none
Post-reboot hostname: ulc-01
Post-reboot running kernel: 6.8.0-138-generic
Post-reboot failed systemd units: 0
Post-reboot NTP synchronized: yes
Post-reboot listeners: only systemd-resolved loopback DNS plus SSH TCP/22 on 0.0.0.0 and [::]
Status: PASS - patched, rebooted, and basic post-reboot health verified
```

**Why this passes:** the host successfully booted the newer installed kernel, systemd reports no failed units, time synchronization recovered, and no unexpected network listener appeared. SSH remains intentionally unhardened at this stage and will be restricted later.

The `/var/run/reboot-required` file was not rechecked in the captured post-reboot output. This does not block the current PASS because the required reboot demonstrably occurred and the new kernel is running; check the file again during the final Phase 2 convergence check.

Next, patch `ulc-02` and then `ulc-03` to converge all three hosts before any cluster software is installed.

### 2.1B Install the reviewed pending updates

[~] `ulc-01` and `ulc-02` are complete. The **replacement `ulc-03` has also already run `apt full-upgrade`** on 2026-08-20. Do not repeat the upgrade just to satisfy the runbook; verify the resulting package/kernel/service state instead.

Verification on the replacement host:

```bash
apt list --upgradable 2>/dev/null
sudo dpkg --audit
systemctl --failed
uname -r
test -f /var/run/reboot-required && cat /var/run/reboot-required || echo 'no reboot-required marker'
sudo sshd -t
sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|usepam|maxauthtries|logingracetime)'
```

**Why:** a newly created cloud image can already be behind current security and bug-fix packages even when the image itself is recent. Since the upgrade is already complete, post-upgrade verification is more useful and safer than rerunning it.

Verification:

```bash
apt list --upgradable 2>/dev/null
systemctl --failed
```

Record whether a reboot is required:

```bash
if [ -f /var/run/reboot-required ]; then cat /var/run/reboot-required; else echo 'No reboot required'; fi
```

Do not reboot until the provider-console recovery path is known and SSH access is healthy. If a reboot is required, reboot deliberately and then repeat the Phase 1 health checks that can change across a kernel/system update.

### Execution note - OpenSSH conffile prompt on `ulc-01` and `ulc-02`

During the base OS upgrade, `openssh-server` reported that `/etc/ssh/sshd_config` had been locally modified. The operator selected **install the package maintainer's version** on both `ulc-01` and `ulc-02`.

`ulc-01` has already rebooted successfully, accepted a new SSH login, and passed post-reboot checks with kernel `6.8.0-138-generic`, 0 failed systemd units, synchronized NTP, and the expected SSH/DNS listener set. This proves the maintainer-version choice did not break remote access on `ulc-01`.

The choice is therefore not treated as a failure. It does mean any provider/local directives in the main `/etc/ssh/sshd_config` may have been replaced. The final SSH hardening phase must inspect the effective configuration and apply the project policy deliberately rather than assuming the pre-upgrade settings survived.

`ulc-02` has now rebooted successfully and passed post-reboot verification:

```text
Hostname: ulc-02
Running kernel: 6.8.0-138-generic
Failed systemd units: 0
NTP synchronized: yes
Unexpected listeners: none
SSH listener: TCP/22 on 0.0.0.0 and [::], still expected before Phase 4 hardening
Status: PASS
```

`ulc-01` and `ulc-02` therefore share the same patched running-kernel baseline.

### Incident - `ulc-03` lost remote SSH during the OpenSSH upgrade

During `apt full-upgrade -y` on `ulc-03`, the upgrade was visibly still unpacking packages (approximately 38% progress, including `openssh-server`) when remote SSH became unavailable. The exact cause is **not yet confirmed**; do not assume the maintainer config alone caused it. Possible boundaries include an sshd/socket configuration change, authentication change, service state change, or an interrupted package transaction.

Status of the **old `ulc-03` Droplet: RETIRED / DECOMMISSIONED after a suspected security incident.** The operator reported that its account password changed without authorization. That installation is no longer part of the deployment and must never be reintroduced through a snapshot, image, disk, copied system files, or reused server-side credentials.

A **new replacement Droplet has been created for `ulc-03`** from a fresh provider image. Treat this replacement as a new bootstrap host: it is not considered cluster-ready until it independently passes the same Ubuntu baseline, patching, named-admin, Ed25519 key-only SSH, listener, IPv6, logging, and later firewall checks used on `ulc-01` and `ulc-02`.

Replacement bootstrap evidence captured on 2026-08-20:

```text
hostname: ulc-03
public IPv4: 159.223.50.57
running kernel: 6.8.0-124-generic
named administrator: jervis
whoami: jervis
sudo whoami: root
Ed25519 login: PASS - operator confirms this is the working login method
password SSH: disabled
status: full SSH hardening PASS on the replacement ulc-03; effective sshd policy confirms PermitRootLogin no, PasswordAuthentication no, KbdInteractiveAuthentication no, PubkeyAuthentication yes, UsePAM yes, MaxAuthTries 3, and LoginGraceTime 30
package state: operator reports `apt full-upgrade` has already been run on the replacement host; `sudo dpkg --audit` returned no output on 2026-08-20 (package database audit PASS). A controlled reboot was then completed. Post-reboot evidence: `systemctl --failed` reports 0 failed units; effective SSH policy remains hardened (`PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PubkeyAuthentication yes`, `UsePAM yes`, `MaxAuthTries 3`, `LoginGraceTime 30`); listeners remain only loopback `systemd-resolved` DNS and SSH TCP/22 on IPv4/IPv6 sockets; `/var/run/reboot-required` is absent. The post-reboot `uname -r` output was not captured in the latest paste and remains the only kernel-convergence check still required. A mistyped `sudo` password during verification is not treated as a failure because subsequent privileged commands succeeded.
```

### Current three-host convergence checkpoint

As of 2026-08-20, all three active Droplets have working named `jervis` administration and Ed25519 key-only SSH with direct root/password SSH disabled. `ulc-01` and `ulc-02` already passed pwquality, firewall/listener inspection, and IPv6 inspection.

Replacement `ulc-03` convergence evidence captured on 2026-08-20:

```text
empty-password check: PASS - no output
libpam-pwquality: installed
pam_pwquality PAM hook: PASS - `/etc/pam.d/common-password` line 25 contains `password requisite pam_pwquality.so retry=3`
/etc/security/pwquality.conf.d/99-lorawan.conf: PASS - `minlen = 16`, mode `644`, owner `root:root`
unattended-upgrades: installed, version 2.9.1+nmu4ubuntu1
20auto-upgrades: daily package-list refresh + unattended upgrades enabled
unattended-upgrades.service: enabled and active
automatic reboot: NOT enabled; only commented examples exist
UFW: inactive
nftables: no loaded rules returned
listeners: only systemd-resolved loopback DNS + SSH TCP/22 on 0.0.0.0 and [::]
IPv6: ::1 plus link-local fe80::/64 only; no global IPv6 address and no default IPv6 route
```

Replacement `ulc-03` now passes the same baseline as `ulc-01` and `ulc-02`: no empty-password accounts were found, the `pam_pwquality` hook is active, and the project `minlen = 16` drop-in exists with `root:root` ownership and mode `0644`. Post-reboot convergence is also confirmed: kernel `6.8.0-138-generic`; public IPv4 `159.223.50.57/20`; eth0 secondary `10.15.0.6/16`; later operationally validated HA/east-west IPv4 `10.104.0.8/20` on eth1; default route via `159.223.48.1` on eth0. The three-host baseline convergence checkpoint is now PASS.

**Historical stop point:** after replacement `ulc-03` reached the baseline above, the remaining common hardening work was SSH-log verification, Fail2ban, AppArmor/time/logging checks, and host-security acceptance. Those later steps were completed/accepted before the etcd phase; the current state is recorded in `00-build-execution-log.md`. Cloud-firewall enforcement remained outside the operator's authority and UFW remained intentionally deferred.

At this point in the execution history, quorum services were still blocked until the remaining host checks were complete. That stop condition was later satisfied before the documented etcd bootstrap. Do not read this historical gate as saying the current etcd deployment was started prematurely.

The security incident therefore does **not** permanently taint the hostname `ulc-03`; trust is attached to the actual fresh host installation, not the name.

The recovery commands below are retained only as incident-history reference for the retired Droplet. They are **not** to be run against the new replacement `ulc-03` unless an equivalent package interruption actually occurs there.

Recovery order:

```bash
ps -eo pid,ppid,stat,etime,cmd | grep -E '[a]pt|[d]pkg|[u]nattended'
systemctl status ssh.socket ssh --no-pager -l
ss -lntp | grep ':22' || true
sshd -t
```

If `apt` or `dpkg` is still active, leave that transaction alone until it completes or clearly exits; do not run another `apt`/`dpkg` concurrently. If no package process remains, inspect/repair the package state before rebooting:

```bash
dpkg --audit
```

Only if the transaction was interrupted and no apt/dpkg process is running, continue with the documented repair sequence such as `dpkg --configure -a` and `apt -f install`, then validate SSH again before reboot.

### Emergency `ulc-03` anti-bot fast track after access is restored

Do not start with Fail2ban, UFW, or more package installation. The first goal is to remove password/root SSH exposure using the already-proven workstation Ed25519 key. This sequence is intentionally short because it does not depend on installing new packages.

1. Confirm no package transaction is still running and that SSH syntax is valid:

```bash
ps -eo pid,ppid,stat,etime,cmd | grep -E '[a]pt|[d]pkg|[u]nattended'
sudo sshd -t
sudo sshd -T | grep -E '^(port|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|usepam)'
```

2. Create the named administrator if it is still missing, prove `sudo`, then install **only the existing workstation public key** for `jervis`. Do not copy the private key to the server.

3. From Windows, prove key authentication with password fallback disabled before changing SSH policy:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" -o IdentitiesOnly=yes -o PasswordAuthentication=no jervis@<ULC-03-PUBLIC-IP>
```

4. After that succeeds, create `/etc/ssh/sshd_config.d/00-lorawan-hardening.conf` with the same reviewed policy already proven on `ulc-01` and `ulc-02`:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
UsePAM yes
MaxAuthTries 3
LoginGraceTime 30
```

5. Run `sudo sshd -t` and inspect `sudo sshd -T` before reloading. Only if both are correct, run `sudo systemctl reload ssh`, keep the old session open, and prove a fresh Ed25519 login.

6. Finally prove password-only login for both `jervis` and `root` is denied. Only after this anti-bot SSH boundary is complete should package repair/patching, pwquality, Fail2ban, and firewall work continue.

If `ulc-03` is still unreachable, there is no safe host-side command to run remotely. The project owner/provider-console holder must first restore access or apply an external cloud-firewall rule. Do not guess with a power cycle while the interrupted package state is unknown.

### `ulc-03` suspected-compromise evidence and rebuild rule

Before destroying/rebuilding the current installation, capture enough evidence to understand what happened without spending days trying to prove a negative on a host that can no longer be trusted:

```bash
date -u
hostnamectl
who -a
w
last -ai | head -n 80
sudo lastb -ai | head -n 80
sudo journalctl -u ssh --since '2026-08-20 00:00:00' --no-pager
sudo journalctl _COMM=sshd --since '2026-08-20 00:00:00' --no-pager
sudo journalctl --since '2026-08-20 00:00:00' --no-pager | grep -Ei 'passwd|chpasswd|usermod|useradd|sudo|sshd'
sudo find /root /home -type f -path '*/.ssh/authorized_keys' -print -exec stat -c '%y %U:%G %a %n' {} \;
sudo awk -F: '($3 == 0) || ($3 >= 1000 && $3 < 65534) {print $1 ":" $3 ":" $7}' /etc/passwd
sudo ss -lntup
sudo ss -tpn
sudo systemctl list-unit-files --state=enabled
sudo systemctl list-timers --all
sudo dpkg -V
```

Do not enter valuable new production secrets into this installation while investigating it. If the same human password was reused on `ulc-01` or `ulc-02`, change those passwords on the clean hosts to unique values. The workstation Ed25519 private key does **not** need to be rotated merely because its public key existed on `ulc-03`; rotate it only if there is evidence the private key/workstation or SSH agent forwarding was compromised.

Rebuild acceptance rule:

```text
old ulc-03 installation -> never joins cluster
fresh Ubuntu 24.04 LTS -> patch -> jervis + Ed25519 -> key-only SSH -> hardening checks -> only then eligible as ha-03
```

Ask the DigitalOcean account holder to isolate or rebuild the Droplet from the provider control plane as soon as possible. If forensic preservation matters, retain a snapshot/image only as evidence and do not use that snapshot as the trusted replacement image.

**Why:** Internet bots commonly probe SSH passwords continuously. Disabling password authentication and direct root SSH removes that credential-guessing path immediately, but an unexplained password change means we must assume the attacker may already have crossed that boundary. A fresh rebuild is what restores host trust.

**Future conffile rule for remote-only hosts:** when `openssh-server` asks what to do with a locally modified `/etc/ssh/sshd_config`, default to **keep the local version currently installed** unless the diff has been reviewed and an independent recovery path is already proven. We can replace/harden SSH deliberately in Phase 4 after named-key access is tested. This avoids changing the remote-access boundary in the middle of an unrelated OS patch run.

**Why:** detailed `PermitRootLogin`, password-authentication, PAM, and listener hardening is intentionally deferred to Phase 4, where the same reviewed policy will be applied consistently to all three hosts.

## 2.2 Automatic security updates - adapted from supplied guide

**Historical incident-state note:** this instruction applied while the original `ulc-03` was inaccessible. That Droplet was retired and replaced. The replacement later passed the baseline and unattended-upgrade checks; current completion is recorded in `00-build-execution-log.md`. Keep the commands below as the reusable inspection procedure, not as a claim that the replacement is still blocked.

First inspect whether Ubuntu already installed/enabled unattended upgrades before changing anything:

```bash
dpkg-query -W -f='${Status} ${Version}\n' unattended-upgrades 2>/dev/null || echo 'unattended-upgrades not installed'
cat /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null || echo '20auto-upgrades not present'
systemctl status unattended-upgrades --no-pager -l || true
systemctl list-timers 'apt-daily*' --all
grep -Rns 'Unattended-Upgrade::Automatic-Reboot' /etc/apt/apt.conf.d 2>/dev/null || true
```

Run this inspection separately on `ulc-01` and `ulc-02` and record both outputs before installing or reconfiguring anything.

Execution evidence captured on 2026-08-20:

```text
ulc-01
  unattended-upgrades package: installed, version 2.9.1+nmu4ubuntu1
  20auto-upgrades: present; package-list refresh and unattended upgrades enabled daily
  unattended-upgrades.service: enabled and active
  apt-daily.timer: active
  apt-daily-upgrade.timer: active
  automatic reboot: not enabled; only commented example directives are present
  Status: PASS - no reconfiguration required

ulc-02
  unattended-upgrades.service: enabled and active
  apt-daily.timer: active
  apt-daily-upgrade.timer: active
  package/config evidence: mixed with accidentally pasted ulc-01 terminal transcript; clean recheck required
  automatic reboot: not yet cleanly reverified from ulc-02-specific output
  Status: IN PROGRESS - clean recheck only; no failure indicated
```

The `command not found` and shell syntax errors seen on `ulc-02` came from pasting terminal prompts/output text into Bash. They do not by themselves indicate package or service damage. Do not install or reconfigure unattended-upgrades on `ulc-02` until the clean recheck below is complete.

Clean `ulc-02` recheck, one command at a time:

```bash
dpkg-query -W -f='${Status} ${Version}\n' unattended-upgrades 2>/dev/null || echo 'unattended-upgrades not installed'
cat /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null || echo '20auto-upgrades not present'
grep -Rns 'Unattended-Upgrade::Automatic-Reboot' /etc/apt/apt.conf.d 2>/dev/null || true
```

**Why inspect first:** Ubuntu cloud images often already include part or all of this mechanism. Reconfiguring it blindly can create duplicate policy or accidentally enable behavior we do not want, especially unattended reboots.

[ ] If inspection shows it is missing or disabled, install/configure unattended security updates after the base patching pass.

For Debian/Ubuntu-family hosts:

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

**Important adaptation:** do **not** configure an unattended automatic reboot on HA nodes. Security updates can be automatic, but reboots must later be coordinated one host at a time so etcd, PostgreSQL/Patroni, Valkey/Sentinel, and OpenBao quorum are not accidentally disrupted together.

Verification:

```bash
systemctl status unattended-upgrades --no-pager
systemctl list-timers 'apt-daily*' --all
```

---

# Phase 3 - Named administrator account and privilege control

## 3.1 Use a named operator account instead of routine root login

**Historical incident-state note:** this was the safe sequencing rule while the original `ulc-03` was inaccessible. The replacement `ulc-03` later completed named-admin, sudo, and key-only SSH validation. The procedure below remains the rebuild method; the old blocked state is not current.

Use the project operator name `jervis` unless the operator intentionally chooses another name before running these commands.

### Authentication discovery before creating the account

The initial assumption that root was using `/root/.ssh/authorized_keys` was disproved on both healthy hosts:

```text
ulc-01: /root/.ssh/authorized_keys missing or empty
ulc-02: /root/.ssh/authorized_keys missing or empty
```

Do not create/copy an `authorized_keys` file until the actual SSH policy is known. The effective policy was inspected on both healthy hosts with:

```bash
sshd -T | grep -E '^(port|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|authorizedkeysfile|authorizedkeyscommand|usepam)'
grep -RnsE '^(Include|Port|PermitRootLogin|PasswordAuthentication|KbdInteractiveAuthentication|PubkeyAuthentication|AuthorizedKeysFile|AuthorizedKeysCommand|UsePAM)' /etc/ssh/sshd_config /etc/ssh/sshd_config.d 2>/dev/null
```

Observed identically on `ulc-01` and `ulc-02`:

```text
port 22
usepam yes
permitrootlogin yes
pubkeyauthentication yes
passwordauthentication yes
kbdinteractiveauthentication no
authorizedkeyscommand none
authorizedkeysfile .ssh/authorized_keys .ssh/authorized_keys2
```

Relevant source directives:

```text
/etc/ssh/sshd_config: PermitRootLogin yes
/etc/ssh/sshd_config: KbdInteractiveAuthentication no
/etc/ssh/sshd_config: UsePAM yes
/etc/ssh/sshd_config.d/50-cloud-init.conf: PasswordAuthentication yes
/etc/ssh/sshd_config.d/60-cloudimg-settings.conf: PasswordAuthentication no
```

`sshd -T` is the authoritative effective result, therefore password authentication is currently enabled despite the later-looking `60-cloudimg-settings.conf` line. OpenSSH uses the first value obtained for these single-valued directives; the included drop-ins are processed in lexical order, so `50-cloud-init.conf` establishes `PasswordAuthentication yes` before `60-cloudimg-settings.conf` is reached.

Security conclusion: direct root login and password authentication are both currently enabled on the two healthy hosts. This is acceptable only as a temporary bootstrap/recovery state. Phase 3 will create and prove the named sudo administrator, then Phase 4 will install a dedicated Ed25519 public key and finally disable root/password SSH after a second-session test.

### Account creation after the authentication path is understood

Create the named administrator while the current root session remains available as the recovery path:

```bash
adduser jervis
usermod -aG sudo jervis
id jervis
sudo -l -U jervis
```

`adduser` prompts interactively for a local password. Do not record that password in this runbook.

Then provision SSH access using the **verified** mechanism. If public-key authentication is used, install only the administrator workstation's intended public key into `/home/jervis/.ssh/authorized_keys` with owner `jervis:jervis`, directory mode `700`, and file mode `600`. Do not fabricate or copy a missing root key file.

Keep the current root session open and, from a second workstation terminal, prove the new login works:

```bash
ssh jervis@<HOST_PUBLIC_IP>
```

Inside that new `jervis` session:

```bash
whoami
sudo -v
sudo whoami
```

Expected:

```text
whoami       -> jervis
sudo whoami  -> root
```

Only after both checks pass may this host be marked PASS for Phase 3.1. Repeat the same procedure on `ulc-02`.

`ulc-01` evidence captured on 2026-08-20:

```text
id jervis -> uid=1000(jervis) gid=1000(jervis) groups=1000(jervis),27(sudo),100(users)
whoami -> jervis
sudo whoami -> root
Status: PASS - named SSH login and sudo elevation both proven
```

`ulc-02` evidence captured on 2026-08-20:

```text
whoami -> jervis
sudo whoami -> root
Status: PASS - named SSH login and sudo elevation both proven
```

Both healthy hosts now have a proven named sudo administrator:

```text
ulc-01 -> PASS
ulc-02 -> PASS
ulc-03 replacement -> PASS for named `jervis` administrator + sudo
```

The replacement `ulc-03` has already completed key-only SSH hardening as well; its remaining Phase 3 gap is the same password-quality/pwquality verification applied to `ulc-01` and `ulc-02`.

**Why:** routine root SSH removes user-level accountability and makes an accidental command immediately privileged. A named account plus `sudo` gives a clearer audit trail and creates the safe prerequisite for disabling direct root SSH later. Authentication is discovered first so we do not accidentally remove the only proven access path.

Do not delete, lock, or disable root SSH yet. Root remains the recovery path until Phase 4 key-only SSH hardening is proven from a second session.

## 3.2 Password quality for any password that still exists

[x] Empty-password check completed on `ulc-01` and `ulc-02`:

```bash
sudo awk -F: '($2==""){print $1}' /etc/shadow
```

Observed result on both healthy hosts: no output. Therefore no account currently has an empty password field.

[x] `libpam-pwquality` is installed successfully on both healthy hosts (`ulc-01` and `ulc-02`). The install completed cleanly, required no service restart, and the running kernel remained current.

The original post-install inspection showed no explicit local `minlen`, `minclass`, or credit settings, so the project policy was added deliberately rather than assuming a default.

PAM hook evidence:

```text
ulc-01: /etc/pam.d/common-password:25: password requisite pam_pwquality.so retry=3
ulc-02: /etc/pam.d/common-password:25: password requisite pam_pwquality.so retry=3
```

A dedicated project drop-in now exists on both healthy hosts:

```text
/etc/security/pwquality.conf.d/99-lorawan.conf
minlen = 16
```

`ulc-01` permission evidence:

```text
644 root:root /etc/security/pwquality.conf.d/99-lorawan.conf
```

`ulc-02` returned the expected file contents (`minlen = 16`) after the same `install`, `tee`, and `chmod 644` sequence.

Status: **PASS on all three active hosts for Phase 3.2.** `ulc-01`, `ulc-02`, and the replacement `ulc-03` have no observed empty-password accounts, an active `pam_pwquality` PAM hook, and the project minimum length of 16 characters for future password changes.

The policy affects future password changes; it does not retroactively prove that an already-created password meets the rule.

**Why:** SSH will ultimately use keys, but the local `jervis` password still protects `sudo` and recovery access. A minimum length policy reduces the chance of weak future passwords without changing the working SSH path during this step. A dedicated drop-in also avoids overwriting package-maintained configuration during future upgrades.

---

# Phase 4 - SSH key authentication and SSH daemon hardening

This phase is intentionally done **before** firewall tightening and is always tested using a second terminal.

## 4.1 Create/use an Ed25519 SSH key on the administrator workstation

[~] The administrator workstation is Windows. An existing Ed25519 keypair was found on 2026-08-20:

```text
%USERPROFILE%\.ssh\id_ed25519
%USERPROFILE%\.ssh\id_ed25519.pub
```

Do **not** overwrite this keypair. Before installing it on a server, identify the public-key fingerprint without printing or exposing the private key:

```powershell
ssh-keygen -lf "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

If this is the intended administrator key, reuse it for the two healthy hosts. If it is an unrelated identity, create a dedicated operator key instead.

If no suitable `id_ed25519` / `id_ed25519.pub` pair exists, create a dedicated operator key:

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519_lorawan" -C "jervis-lorawan-admin"
```

Use a strong key passphrase. The private key (`id_ed25519_lorawan`) stays only on the administrator workstation; only the `.pub` file is copied to servers.

If a suitable existing Ed25519 key already exists and is intentionally approved for this administration role, it can be reused instead of creating another key. Never overwrite an existing key merely to follow this runbook.

**Why:** possession of a private key plus its passphrase is significantly stronger than exposing reusable SSH passwords to Internet guessing. Checking first also prevents accidental destruction of an unrelated SSH identity on the workstation.

## 4.2 Install the public key and prove key login

[~] Install only the `.pub` public key on the server and test a second SSH session. The administrator workstation is Windows PowerShell, so commands using `$env:USERPROFILE` must be run **from Windows**, not from an SSH/Linux shell.

`ulc-01` evidence captured on 2026-08-20:

```text
Public IPv4: 143.198.205.54
Test command forced IdentitiesOnly=yes and PasswordAuthentication=no
Private key passphrase prompt appeared
Login succeeded as jervis
Running kernel shown at login: 6.8.0-138-generic
Status: PASS - Ed25519 public-key authentication proven without password fallback
```

A first attempt against `ulc-02` was accidentally run from the `jervis@ulc-02` Linux shell using Windows syntax (`$env:USERPROFILE`). Linux therefore reported the identity path as inaccessible and the login failed. This was an operator-shell mistake, not a server failure.

A correct Windows PowerShell test was then performed against `165.22.253.127` with `IdentitiesOnly=yes` and `PasswordAuthentication=no`. The private-key passphrase prompt appeared and the login succeeded as `jervis` on kernel `6.8.0-138-generic`.

Status: **PASS - Ed25519 public-key authentication is proven on both `ulc-01` and `ulc-02` without password fallback.** The earlier accidental Linux-side attempt also added `ulc-02`'s public-IP host key to that server user's local `~/.ssh/known_hosts`; this is harmless and can be left in place or cleaned later.

For Windows without `ssh-copy-id`, install the **public key only** from PowerShell:

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | ssh jervis@<SERVER_IP> "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
```

Then prove key authentication while explicitly disabling password fallback:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" -o IdentitiesOnly=yes -o PasswordAuthentication=no jervis@<SERVER_IP>
```

Verification on the server:

```bash
stat -c '%a %U:%G %n' ~/.ssh ~/.ssh/authorized_keys
```

Typical expected permissions:

```text
700 ~/.ssh
600 ~/.ssh/authorized_keys
```

### 4.2B Add a separate SSH administrator for a second device

Use this when a second device must have its **own user account and its own SSH key**. Do not copy the existing `jervis` private key to the second device. The example account below is `opsadmin`; replace that name everywhere if a different human-readable username is preferred.

Because global SSH password authentication is already disabled, create the account from an existing working `jervis` session and install the second device's public key before attempting the first login.

**If the second device cannot be brought to the commissioning location:** the preferred method is still to generate its key directly on that device. If that is impractical and access must be prepared now, generate a **new dedicated keypair** on the currently trusted workstation, protect it with a strong passphrase, authorize only its public key on the servers, and later transfer that dedicated keypair to the home device using offline/removable media such as a USB drive. Do not reuse or copy the existing `jervis` private key, and do not temporarily re-enable SSH password authentication.

This fallback is slightly weaker than generating the private key directly on the home device because the dedicated private key temporarily exists on another workstation. Use it only as a deliberate operational tradeoff. After the home device proves the new key works, remove the temporary copy from the commissioning workstation and transfer media. Do not assume deletion from SSD/flash media provides forensic secure erasure; if that level of key-origin assurance is required, wait and generate the key directly on the home device instead.

The `opsadmin` account can be created and its dedicated public key authorized now, before the home device receives the private key. That lets the later home login work without weakening the global SSH policy.

On the second device, generate a dedicated Ed25519 key. Windows PowerShell example:

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519_lorawan_ops" -C "opsadmin-lorawan"
Get-Content "$env:USERPROFILE\.ssh\id_ed25519_lorawan_ops.pub"
```

Linux/macOS equivalent:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_lorawan_ops -C 'opsadmin-lorawan'
cat ~/.ssh/id_ed25519_lorawan_ops.pub
```

Copy **only the single `ssh-ed25519 ...` public-key line**. Never copy the private key into the server or documentation.

On `ulc-01`, from the already-proven `jervis` session, create the account and grant sudo only if this is intended to be a second administrator:

```bash
sudo adduser opsadmin
sudo usermod -aG sudo opsadmin
id opsadmin
sudo -l -U opsadmin
```

`adduser` asks for a local password. This password protects `sudo`/console recovery; it is not usable for SSH because `PasswordAuthentication no` remains in force. The current pwquality policy requires future password changes to be at least 16 characters.

Create the SSH directory and key file with strict ownership/modes:

```bash
sudo install -d -m 700 -o opsadmin -g opsadmin /home/opsadmin/.ssh
sudo install -m 600 -o opsadmin -g opsadmin /dev/null /home/opsadmin/.ssh/authorized_keys
```

Then append the second device's public key. Replace the placeholder with the exact `.pub` line copied from that device:

```bash
printf '%s\n' 'ssh-ed25519 AAAA_REPLACE_WITH_SECOND_DEVICE_PUBLIC_KEY opsadmin-lorawan' | sudo tee -a /home/opsadmin/.ssh/authorized_keys >/dev/null
sudo chown opsadmin:opsadmin /home/opsadmin/.ssh/authorized_keys
sudo chmod 700 /home/opsadmin/.ssh
sudo chmod 600 /home/opsadmin/.ssh/authorized_keys
sudo sshd -t
```

Keep the existing `jervis` session open. From the second device, prove key-only login to `ulc-01`:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_lorawan_ops" -o IdentitiesOnly=yes -o PasswordAuthentication=no opsadmin@143.198.205.54
```

Linux/macOS equivalent:

```bash
ssh -i ~/.ssh/id_ed25519_lorawan_ops -o IdentitiesOnly=yes -o PasswordAuthentication=no opsadmin@143.198.205.54
```

Inside the new session verify:

```bash
whoami
sudo whoami
```

Expected: `whoami -> opsadmin`, then after the local sudo password `sudo whoami -> root`.

Only after this succeeds on `ulc-01`, repeat the same account + **same second-device public key** on `ulc-02` (`165.22.253.127`) and replacement `ulc-03` (`159.223.50.57`). Do not weaken `PasswordAuthentication no`, `PermitRootLogin no`, or the existing `jervis` access to make this work.

**Why:** a separate user plus a separate device key gives an independently revocable access path. If that second device is lost, remove its account/key without rotating the existing `jervis` key. The private key always remains on the device that generated it.

## 4.3 Harden the SSH server - corrected from supplied guide

[~] Apply to **one healthy host at a time**, starting with `ulc-01`. Keep the current proven `jervis` SSH session open until a new post-change key session succeeds.

Back up both the main file and current drop-ins first:

```bash
sudo cp -a /etc/ssh/sshd_config /etc/ssh/sshd_config.before-lorawan-hardening
sudo cp -a /etc/ssh/sshd_config.d /etc/ssh/sshd_config.d.before-lorawan-hardening
```

Use a dedicated early drop-in:

```text
/etc/ssh/sshd_config.d/00-lorawan-hardening.conf
```

**Why the `00-` prefix matters on these hosts:** the current main file includes `/etc/ssh/sshd_config.d/*.conf` before its later `PermitRootLogin yes`, and the existing drop-ins include `50-cloud-init.conf` with `PasswordAuthentication yes` plus `60-cloudimg-settings.conf` with `PasswordAuthentication no`. `sshd -T` proved that the earlier `50-` value wins. Therefore a late `99-...conf` would not reliably override the existing effective value. `00-lorawan-hardening.conf` is deliberately parsed first so our reviewed policy becomes the effective setting.

Create the drop-in:

```bash
sudo tee /etc/ssh/sshd_config.d/00-lorawan-hardening.conf >/dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
UsePAM yes
MaxAuthTries 3
LoginGraceTime 30
EOF
sudo chmod 644 /etc/ssh/sshd_config.d/00-lorawan-hardening.conf
```

Target effective policy:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
UsePAM yes
MaxAuthTries 3
LoginGraceTime 30
```

**Why `UsePAM yes`:** password SSH is disabled independently. Keeping PAM enabled preserves Ubuntu account/session controls instead of bypassing distribution security policy.

Validate **before** reloading SSH:

```bash
sudo sshd -t
sudo sshd -T | grep -E '^(port|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|permitemptypasswords|pubkeyauthentication|usepam|maxauthtries|logingracetime)'
```

Expected effective values include:

```text
port 22
permitrootlogin no
passwordauthentication no
kbdinteractiveauthentication no
permitemptypasswords no
pubkeyauthentication yes
usepam yes
maxauthtries 3
logingracetime 30
```

`ulc-01` pre-reload evidence captured on 2026-08-20:

```text
sshd -t: PASS (no output)
port 22
usepam yes
logingracetime 30
maxauthtries 3
permitrootlogin no
pubkeyauthentication yes
passwordauthentication no
kbdinteractiveauthentication no
permitemptypasswords no
Status: PASS - syntax and effective policy validated before reload
```

Only if `sshd -t` returns no error and `sshd -T` shows the target values:

```bash
sudo systemctl reload ssh
```

Do **not** close the current session. From Windows PowerShell, open a second connection using the known-good key and explicitly disallow password fallback:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" -o IdentitiesOnly=yes -o PasswordAuthentication=no jervis@<SERVER_IP>
```

`ulc-01` live enforcement evidence captured on 2026-08-20 after the hardened configuration was loaded:

```text
jervis password-only SSH test -> denied: Permission denied (publickey)
root password-only SSH test   -> denied: Permission denied (publickey)
```

These denials are expected and prove that new connections are not permitted to use password authentication for either the named administrator or root.

Fresh post-reload access was then proven from Windows PowerShell using the workstation Ed25519 key. The connection prompted for the private-key passphrase and opened a new `jervis@ulc-01` session. Inside that fresh session:

```text
whoami -> jervis
sudo whoami -> root
```

Status: **PASS on `ulc-01` for Phase 4.3.** The legitimate Ed25519 administrator path works after reload, `sudo` still works, password SSH is denied, and direct root password SSH is denied.

Proceed with the same reviewed hardening process on `ulc-02`, one host at a time. Direct root SSH and password SSH must remain disabled after the final `sshd -T` and live-login verification.

`ulc-02` pre-reload validation captured on 2026-08-20:

```text
sshd -t -> no output (syntax PASS)
port 22
usepam yes
logingracetime 30
maxauthtries 3
permitrootlogin no
pubkeyauthentication yes
passwordauthentication no
kbdinteractiveauthentication no
permitemptypasswords no
Status: PASS - effective hardened SSH policy is correct before reload
```

`ulc-02` live post-reload verification captured on 2026-08-20:

```text
Fresh Ed25519 login from Windows PowerShell -> succeeded
Private-key passphrase prompt -> shown
whoami -> jervis
sudo whoami -> root
jervis password-only SSH -> denied: Permission denied (publickey)
root password-only SSH   -> denied: Permission denied (publickey)
```

Status: **PASS on `ulc-02` for Phase 4.3.** The legitimate Ed25519 administrator path works after reload, `sudo` still works, password SSH is denied, and direct root password SSH is denied.

Phase 4.3 status on the currently reachable hosts:

```text
ulc-01 -> PASS
ulc-02 -> PASS
ulc-03 replacement -> PASS
```

All three active hosts now enforce the reviewed key-only SSH policy. At this point in the historical sequence, replacement `ulc-03` still needed the remaining non-SSH checks before quorum services. Those checks were later completed/accepted before the etcd phase; see `00-build-execution-log.md` for the current checkpoint.

## 4.4 SSH port decision

[-] Changing SSH away from TCP/22 is **not counted as a primary security control** for this deployment.

**Why:** changing the port mainly reduces log noise from commodity scanners; it does not replace key authentication or source-IP firewall restrictions. The **target** LoRaWAN cloud design calls for SSH source restriction at the provider firewall, but that provider-side control is not verified or managed by the current operator and must not be described as active until the account owner supplies evidence.

If organizational policy explicitly requires a custom port, document the port and update the cloud firewall first, then test it from a second terminal before removing TCP/22 access.

---

# Phase 5 - Firewall and network exposure

## 5.1 Provider cloud-firewall boundary

[!] **BLOCKED / EXTERNALLY MANAGED.** The current operator is not authorized to modify or verify the DigitalOcean Cloud Firewall. Keep this section as a provider-owner handoff target, not an execution step for the current operator.

Observed administrator public IPv4 on 2026-08-20 from the Windows workstation:

```text
203.177.194.77
```

Use the exact source CIDR for the current commissioning session:

```text
203.177.194.77/32
```

Status: **BLOCKED / externally controlled.** The operator cannot inspect or change the DigitalOcean Cloud Firewall from this project session, so its current rule state is unknown. Do not pretend the provider firewall is configured and do not ask the operator to guess.

If the account owner later performs this work, they should preserve the working SSH path, apply the reviewed source restriction, and provide enough evidence to record the resulting rule state. The old warning that replacement `ulc-03` was inaccessible no longer applies; all three replacement/current hosts later passed SSH hardening.

Because there is still no independent provider recovery path available to the operator, any host-firewall change that could restrict SSH by source IP also remains a separate controlled task. Continue to document the actual UFW/nftables state rather than marking a restrictive host firewall as complete.

The initial inbound cloud-firewall rule, once provider access is available, is intentionally only:

```text
TCP 22 from 203.177.194.77/32
```

Do not pre-open `443`, `8883`, database, Grafana, Node-RED, OpenBao, or other future service ports before those services are actually installed and their listener/bind policy is verified. The `10.104.0.0/20` path is now **operationally validated from the hosts** by cross-node ICMP and TCP `2380` tests and is the current east-west service network. That does not prove the DigitalOcean control-plane VPC/firewall object or rule state; provider-side confirmation remains separate.

**Why:** unwanted traffic is dropped before it reaches the VM. A `/32` limits SSH to the exact current administrator public IPv4, but it can cause lockout if the ISP address changes, so every firewall edit is followed immediately by a second-session SSH test.

Later LoRaWAN public ingress is limited to the explicitly approved services. Database/quorum/control ports remain private.

## 5.2 Host firewall

[x] Existing host firewall state inspected on `ulc-01` and `ulc-02` on 2026-08-20:

```text
ulc-01
  UFW: inactive
  nftables: no loaded rules returned by `nft list ruleset`
  listeners: only systemd-resolved loopback DNS plus SSH TCP/22 on 0.0.0.0 and [::]

ulc-02
  UFW: inactive
  nftables: no loaded rules returned by `nft list ruleset`
  listeners: only systemd-resolved loopback DNS plus SSH TCP/22 on 0.0.0.0 and [::]
```

At the 2026-08-20 inspection point, no unexpected application listener was exposed on the two inspected hosts; SSH was the only non-loopback listener. This is historical pre-etcd evidence, not a claim about today's listener list. After Fail2ban activation, nftables also contains Fail2ban-managed rules, so the current ruleset must not be described as empty.

Status: **INSPECTION PASS; enforcement deferred.** Because the operator currently has neither DigitalOcean control-panel access nor an independent provider-console recovery path, do not enable a restrictive UFW policy yet. A mistaken source CIDR or ISP address change could otherwise create a full remote lockout with no independent recovery mechanism.

This is a temporary operational exception, not the final production firewall state. When provider/recovery access is available, apply the cloud firewall first, prove SSH from a second session, then enable the reviewed host firewall.

If UFW is later selected as the host firewall, allow the **currently proven SSH path first**, then enable it.

Example for TCP/22 only when TCP/22 is the proven management port:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <ADMIN_SOURCE_CIDR> to any port 22 proto tcp
sudo ufw enable
sudo ufw status numbered
```

Immediately prove a new SSH connection.

**Docker warning:** Docker can manage packet-filter rules for published container ports. Therefore UFW alone must never be treated as the only boundary for Docker-published services. This project also requires the cloud firewall, explicit private/listener binds, and `ss -lntup` verification.

## 5.3 IPv6 decision - conditional, not automatic

[x] IPv6 state inspected on `ulc-01` and `ulc-02`:

```bash
ip -6 address
ip -6 route
```

Observed on both healthy hosts:

```text
lo: ::1/128 only
eth0: fe80::/64 link-local address only
eth1: fe80::/64 link-local address only
IPv6 routes: fe80::/64 on eth0 and eth1 only
Global IPv6 address: none
Default IPv6 route: none
```

Decision: **leave IPv6 enabled**. There is currently no globally routable IPv6 address or default IPv6 route on either host, so the `[::]:22` SSH listener does not create a separate Internet-routable IPv6 path. Link-local IPv6 remains useful for normal host/network behavior and does not justify a blanket disable.

Status: **PASS on `ulc-01` and `ulc-02` for Phase 5.3.** Re-evaluate this decision if DigitalOcean later assigns global IPv6; any future global IPv6 path must receive firewall policy equivalent to IPv4.

**Why:** blindly disabling IPv6 can break provider networking or future services; leaving a global unfiltered IPv6 path can also bypass an IPv4-only firewall. The secure choice is to inspect the real addressing/routing state and act on that evidence.

## 5.4 Do not block ICMP echo merely to 'stay hidden'

[-] The supplied guide's ping-blocking step is not applied by default.

**Why:** blocking ping does not make an Internet host meaningfully invisible, while ICMP is useful for diagnostics and parts of normal IP operation. Exposure is controlled by the cloud firewall and service listeners instead.

---

# Phase 6 - Brute-force protection

## 6.1 Confirm SSH logging before Fail2ban

[x] SSH journal logging verified on all three active hosts on 2026-08-20.

```text
ulc-01
  systemd-journald: active
  ssh.service journal: populated with live pre-authentication SSH probes
  examples: repeated root probes, invalid `admin` usernames, connections closed before authentication
  Status: PASS

ulc-02
  systemd-journald: active
  ssh.service journal: populated with live pre-authentication SSH probes
  examples: invalid `ubuntu`, `pi`, `baikal`, `admin`; excessive authentication attempts; obsolete/invalid SSH protocol and host-key negotiation attempts
  Status: PASS

ulc-03 replacement
  systemd-journald: active
  ssh.service journal: populated with live pre-authentication SSH probes
  examples: invalid `exx`, `radar`, `sybase`, `delta`, `sniper-bot`, `sniper`
  expected administrator login also recorded as `Accepted publickey for jervis` from the commissioning source `203.177.194.77`
  Status: PASS
```

The observed `Invalid user`, `authenticating user root`, `[preauth]`, negotiation errors, and connection-close lines are failed/probing traffic, not evidence of a successful login. No unauthorized `Accepted publickey`/successful session is shown in the captured samples.

**Why:** this proves that the systemd journal contains the events that Fail2ban needs to match. It also demonstrates that public TCP/22 is already receiving automated Internet scanning even though password/root SSH authentication has been disabled.

## 6.2 Fail2ban for SSH

[x] Fail2ban deployment is complete on all three active hosts. `ulc-01` was fully evidenced: configuration test PASS, service active/enabled, `sshd` jail loaded, and a fresh Ed25519 SSH connection remained available. The operator then repeated the same proven configuration on `ulc-02` and `ulc-03` and confirmed completion. Because their detailed terminal outputs were not pasted, those two are recorded as operator-confirmed rather than inventing counters or banned-IP evidence.

Execution evidence for `ulc-01` on 2026-08-20:

```text
configuration test: PASS (`fail2ban-client -t` returned OK)
allowipv6 warning: informational only; packaged default `auto` is being used
fail2ban.service: active and enabled
sshd jail: loaded successfully with systemd backend
initial counters: 0 failed / 0 banned immediately after startup, expected because old journal events are not retroactively counted
fresh Ed25519 SSH login after enabling Fail2ban: PASS
Status: PASS
```

The working `ulc-01` policy is now the template for `ulc-02` and `ulc-03`; do not change values between hosts without a documented reason.

Install the packaged service:

```bash
sudo apt install -y fail2ban
```

Use a small project override instead of copying the full packaged `jail.conf`:

```bash
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 10m
ignoreip = 127.0.0.1/8 ::1 203.177.194.77
EOF
```

Then validate and start it:

```bash
sudo fail2ban-client -t
sudo systemctl enable --now fail2ban
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

Keep the existing SSH session open and prove a second fresh Ed25519 login before closing it.

**Why this conservative policy:** SSH keys and future cloud-firewall source restrictions remain the primary controls. Fail2ban only suppresses repeated scanners that still reach TCP/22. The ten-minute ban is intentionally temporary, and the current commissioning IPv4 is ignored, because the operator still lacks independent DigitalOcean recovery-console access. If the administrator source address later changes, update/remove that `ignoreip` entry deliberately; do not treat it as a permanent trusted network.

---

# Phase 7 - Additional LoRaWAN host hardening

These controls are additions to the supplied document.

## 7.1 Verify AppArmor status

[~] Run these read-only checks on all three active hosts:

```bash
systemctl is-active apparmor
systemctl is-enabled apparmor
sudo aa-status
```

`ulc-01` evidence captured on 2026-08-20:

```text
apparmor.service: active and enabled
AppArmor kernel module: loaded
profiles loaded: 117
profiles in enforce mode: 23
profiles in complain mode: 4 (`transmission-*` profile definitions)
running processes in complain mode: 0
running processes unconfined while having a defined profile: 0
rsyslogd: running under its enforced AppArmor profile
Status: PASS
```

The four `transmission-*` profiles being loaded in complain mode do **not** mean a Transmission process is currently bypassing enforcement; `aa-status` explicitly reports zero running processes in complain mode. Likewise, the long list of profiles reported as unconfined mode is not by itself evidence that those applications are running. Do not change those profiles merely to make the counts look smaller.

Detailed `aa-status` output was captured for `ulc-01`. Completion on `ulc-02` and `ulc-03` was later operator-confirmed, but their full profile counts were not preserved in the pasted evidence. Treat the three-host AppArmor checkpoint as accepted with that evidence limitation; do not copy `ulc-01`'s exact counts onto the other hosts.

Do not install, disable, or alter AppArmor profiles yet. If a later LoRaWAN service receives a denial, investigate the denial and use a reviewed profile/exception instead of disabling AppArmor globally.

**Why:** mandatory access control limits what a compromised service can access beyond normal Unix permissions.

## 7.2 Time synchronization

[x] `ulc-01` has detailed pasted evidence for `Timezone=Etc/UTC`, `NTP=yes`, and `NTPSynchronized=yes`. Later three-host completion was operator-confirmed; where the individual `ulc-02`/`ulc-03` terminal output is not preserved, do not invent it.

Confirm synchronization remains healthy on all three hosts:

```bash
timedatectl show -p Timezone -p NTP -p NTPSynchronized
```

Expected baseline: `Timezone=Etc/UTC`, `NTP=yes`, and `NTPSynchronized=yes`.

If `chrony` is selected later:

```bash
chronyc tracking
chronyc sources -v
```

**Why:** TLS validation, logs, PostgreSQL, etcd leases, Patroni and security investigation all depend on reliable time.

## 7.3 Confirm persistent system logging

[x] `ulc-01` PASS on 2026-08-20: `systemd-journald` is active, `/var/log/journal` exists, journal storage uses about 8.0 MiB, and privileged boot-history verification shows both boot `-1` and current boot `0`. This proves previous-boot logs survive reboot on `ulc-01`.

Confirm journald is active and previous-boot logs are retained before installing the application stack:

```bash
systemctl is-active systemd-journald
test -d /var/log/journal && echo 'persistent journal directory present' || echo 'persistent journal directory missing'
journalctl --list-boots --no-pager | tail -n 5
journalctl --disk-usage
```

`ulc-03` showed records from both sides of its controlled reboot, while `ulc-01` has the clearest pasted `--list-boots` evidence. Later persistent-logging completion was operator-confirmed for the accepted baseline. If exact per-host boot-history output is needed for the final DOCX, recapture it rather than reconstructing it from memory.

If the deployment requires stronger host audit evidence, install/configure `auditd` only after checking the 2-GiB POC resource budget and define a small targeted ruleset rather than a noisy generic rules dump.

**Why:** hardening without usable logs makes failures and intrusions much harder to investigate.

## 7.4 File-permission and secret-storage baseline

[ ] Create secrets/configuration directories only when their consuming services are ready. Service secrets must remain outside Git, normally root-owned with least-privilege service access.

Example later layout:

```text
/etc/lorawan-cloud/
/etc/lorawan-pki/
```

**Why:** the Git repository is documentation/deployment logic, not a secret store.

## 7.5 Kernel/sysctl policy - no generic hardening bundle

[ ] Record existing relevant values before changing them.

Do not paste a large Internet 'secure sysctl' list into these small HA nodes. Apply a setting only when it has a documented security/operational reason and verify that it does not break VPC, Docker, PostgreSQL, MQTT, TLS, or failover behavior.

**Why:** several popular hardening bundles contain obsolete or workload-breaking settings.

## 7.6 Swap and OpenBao safety

[ ] Record swap state during baseline inspection.

A small host swap file may be useful as an emergency cushion, but OpenBao secrets must not be allowed to page into ordinary unencrypted swap. When OpenBao is deployed, enforce the runtime-specific no-swap control for that service.

**Why:** swap can leak sensitive in-memory key material and can also hide a genuinely undersized 2-GiB node.

---

# Phase 8 - Remove or disable unnecessary software carefully

## 8.1 Inventory before purge

[ ] Check whether legacy network-server packages are actually installed:

```bash
dpkg -l | grep -E '(^ii[[:space:]]+(telnetd|ftp|vsftpd|samba|nfs-kernel-server|nfs-common)[[:space:]])' || true
```

Only purge confirmed-unused packages.

**Why:** the supplied guide suggests removing Telnet/FTP/Samba/NFS packages, which is sensible when unused, but `nfs-common` may be required if backups or deployment storage actually use NFS. Never remove a dependency without checking the server's intended storage path.

After any purge:

```bash
sudo apt autoremove --purge
systemctl --failed
ss -lntup
```

---

# Phase 9 - Final hardening acceptance checklist

This is a reusable checklist, **not an all-green current-status table**. The live build proceeded to Docker/etcd with two explicitly documented infrastructure exceptions: the DigitalOcean Cloud Firewall is externally controlled/unverified by this operator, and UFW remains inactive to avoid an unrecoverable remote lockout. Current evidence is authoritative in `00-build-execution-log.md`; do not convert unchecked provider/firewall items below into PASS without new evidence.

[ ] OS/version and machine resources match the approved build.

[ ] System fully patched; reboot requirement handled deliberately.

[ ] Named operator account works with `sudo`.

[ ] SSH key login works from a fresh terminal.

[ ] Root SSH login is disabled.

[ ] SSH password and keyboard-interactive authentication are disabled unless an explicitly documented recovery policy requires otherwise.

[ ] `sshd -t` passes.

[ ] Provider console/recovery path is known.

[ ] Cloud firewall restricts management access.

[ ] Host firewall policy is known and tested without SSH lockout.

[ ] No unexpected public listeners exist.

[ ] IPv6 is either deliberately secured or deliberately disabled after verification.

[ ] Fail2ban SSH jail is healthy if installed.

[ ] AppArmor is active where supported and not intentionally disabled.

[ ] Time synchronization is healthy.

[ ] No unexplained failed systemd units remain.

[ ] No empty passwords exist on login-capable accounts.

[ ] Unnecessary legacy network services are absent/disabled.

[ ] Secrets are not stored in Git or shell history.

[ ] Section 12 of the supplied DOCX remains excluded; Nginx/basic-auth/DNS/Certbot website setup is not part of this base-host phase.

## Final evidence commands

Run and save sanitized output for the later DOCX hardening report:

```bash
hostnamectl
cat /etc/os-release
uname -r
nproc
free -h
df -hT
ip -br address
ip route
ss -lntup
systemctl --failed
timedatectl status
sudo sshd -t
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication|permitemptypasswords|pubkeyauthentication|maxauthtries|logingracetime|usepam'
sudo ufw status verbose 2>/dev/null || true
sudo fail2ban-client status 2>/dev/null || true
sudo aa-status 2>/dev/null || true
```

Redact public IPs if the final report is meant for wide distribution, and never include credentials/private keys.

---

# Execution log

Append one entry after every step we actually perform.

## 2026-08-20 - Initial provisioned server

```text
Action: Created hardening execution record before changing the server.
Source guide: supplied Ubuntu Server Security Hardening DOCX reviewed.
Yellow-highlight exclusion: Section 12 (web server / Nginx / subdomain / Certbot / Nginx hardening) excluded.
Additional project hardening: added safe SSH-change procedure, cloud-firewall boundary, Docker/UFW warning, AppArmor, logging, time, IPv6 decision gate, OpenBao swap boundary, and acceptance evidence.
Historical state at document creation: Phase 1.1 baseline inspection; waiting for server output.
```

## 2026-08-21 - Hardening-document closure checkpoint

```text
Host baseline / patching / SSH / pwquality / unattended upgrades: accepted
Fail2ban: deployed on all three; detailed ulc-01 evidence plus operator-confirmed ulc-02/03 completion
AppArmor / time / persistent logging: accepted with evidence-scope caveats documented above
DigitalOcean Cloud Firewall: externally controlled; current operator not authorized; rule state unknown
UFW: inactive by deliberate remote-lockout decision
East-west 10.104.0.0/20: later operationally validated from the hosts
Later infrastructure state: Docker runtime and three-member etcd quorum were subsequently deployed and validated; see 00-build-execution-log.md
```

This closes the stale `WAITING FOR SERVER COMMAND OUTPUT` marker without inventing provider-side or per-host evidence that was never captured.
