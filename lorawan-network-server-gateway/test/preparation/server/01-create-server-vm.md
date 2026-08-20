# Server 1. Create and Prepare the Local Test Server VM

This procedure creates and prepares the single **Ubuntu Server 24.04 LTS VM** specifically tailored for **Track 1: Barebones Dissertation Testing**.

Unlike the full High-Availability deployment track, this manual is streamlined for local VM development (VirtualBox, Hyper-V, VMware, Proxmox) on a resource-constrained host (e.g., 8 GiB physical RAM host).

---

## 1. Resource Sizing & Profile

Allocate only a portion of your physical host's hardware so the host OS and hypervisor continue running smoothly:

```text
Guest OS: Ubuntu Server 24.04 LTS (No desktop GUI)
RAM:  5 GiB (Absolute minimum: 4 GiB)
vCPU: 4 vCPU cores
Disk: 50 GiB SSD-backed minimum
Network Adapter: Bridged Adapter (or Host-Only with Port Forwarding for SSH :22 / MQTT :8883)
```

> [!CAUTION]
> Do not give the test VM 8 GiB RAM if your physical host only has 8 GiB RAM. Sustained host swapping will invalidate latency and throughput measurement data during test runs.

---

## 2. Step-by-Step Installation & Host Setup

### Step 1: Install Ubuntu Server 24.04 LTS

1. Boot the VM from the official Ubuntu Server 24.04 LTS ISO.
2. Complete the wizard:
   - Set **Hostname** to `lora-test-server` (or your chosen test hostname).
   - Create your administrative user account (e.g., `jervis`).
   - Enable **OpenSSH Server** (`sshd`).
   - Do **NOT** install desktop GUI or Docker Snap packages.
3. Reboot into the VM.

### Step 2: Update Operating System & OS Packages

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### Step 3: Add Swap Safety Net (2 GiB)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
printf 'vm.swappiness=10\n' | sudo tee /etc/sysctl.d/99-lorawan-test-memory.conf
sudo sysctl --system
```

---

## 3. Automated Static IP & DHCP Helper (`set-ip.sh`)

To easily switch between **DHCP** (for initial setup) and a **Static IP** (for stable gateway mTLS / MQTT communication), install the automated Netplan helper script.

### Single-Line Installation Command (Zero Copy-Paste Error):

Paste this command into your Ubuntu VM terminal:

```bash
echo "IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWUKCklGQUNFPSQoaXAgLTQgcm91dGUgc2hvdyBkZWZhdWx0IHwgYXdrICd7cHJpbnQgJDV9JyB8IGhlYWQgLW4xKQppZiBbIC16ICIkSUZBQ0UiIF07IHRoZW4KICAgIElGQUNFPSQoaXAgbGluayB8IGdyZXAgLUUgJ15bMC05XSs6IChlbnxldGgpJyB8IGF3ayAne3ByaW50ICQyfScgfCB0ciAtZCAnOicgfCBoZWFkIC1uMSkKZmkKCk5FVFBMQU5fRklMRT0iL2V0Yy9uZXRwbGFuLzAxLW5ldGNmZy55YW1sIgpNT0RFPSIkezE6LX0iCgppZiBbICIkTU9ERSIgPSAiZGhjcCIgXTsgdGhlbgogICAgZWNobyAiWytdIENvbmZpZ3VyaW5nICRJRkFDRSBmb3IgREhDUC4uLiIKICAgIHN1ZG8gdGVlICIkTkVUUExBTl9GSUxFIiA+IC9kZXYvbnVsbCA8PEVPRgpuZXR3b3JrOgogIHZlcnNpb246IDIKICByZW5kZXJlcjogbmV0d29ya2QKICBldGhlcm5ldHM6CiAgICAkSUZBQ0U6CiAgICAgIGRoY3A0OiB0cnVlCkVPRgogICAgc3VkbyBjaG1vZCA2MDAgIiRORVRQTEFOX0ZJTEUiCiAgICBzdWRvIG5ldHBsYW4gYXBwbHkKICAgIGVjaG8gIlsrXSBBcHBsaWVkIERIQ1AgY29uZmlndXJhdGlvbiB0byAkSUZBQ0UuIgoKZWxpZiBbICIkTU9ERSIgPSAic3RhdGljIiBdOyB0aGVuCiAgICBJUD0iJHsyOi19IgogICAgR0FURVdBWT0iJHszOi19IgogICAgRE5TMT0iJHs0Oi04LjguOC44fSIKICAgIEROUzI9IiR7NTotMS4xLjEuMX0iCgogICAgaWYgWyAteiAiJElQIiBdIHx8IFsgLXogIiRHQVRFV0FZIiBdOyB0aGVuCiAgICAgICAgZWNobyAiVXNhZ2U6IHN1ZG8gc2V0LWlwLnNoIHN0YXRpYyA8SVAvQ0lEUj4gPEdBVEVXQVk+IFtETlMxXSBbRE5TMl0iCiAgICAgICAgZWNobyAiRXhhbXBsZTogc3VkbyBzZXQtaXAuc2ggc3RhdGljIDE5Mi4xNjguMS4xNTAvMjQgMTkyLjE2OC4xLjEiCiAgICAgICAgZXhpdCAxCiAgICBmaQoKICAgIGVjaG8gIlsrXSBDb25maWd1cmluZyAkSUZBQ0Ugd2l0aCBTdGF0aWMgSVA6ICRJUCAoR2F0ZXdheTogJEdBVEVXQVkpLi4uIgogICAgc3VkbyB0ZWUgIiRORVRQTEFOX0ZJTEUiID4gL2Rldi9udWxsIDw8RU9GCm5ldHdvcms6CiAgdmVyc2lvbjogMgogIHJlbmRlcmVyOiBuZXR3b3JrZAogIGV0aGVybmV0czoKICAgICRJRkFDRToKICAgICAgZGhjcDQ6IGZhbHNlCiAgICAgIGFkZHJlc3NlczoKICAgICAgICAtICRJUAogICAgICByb3V0ZXM6CiAgICAgICAgLSB0bzogZGVmYXVsdAogICAgICAgICAgdmlhOiAkR0FURVdBWQogICAgICBuYW1lc2VydmVyczoKICAgICAgICBhZGRyZXNzZXM6CiAgICAgICAgICAtICRETlMxCiAgICAgICAgICAtICRETlMyCkVPRgogICAgc3VkbyBjaG1vZCA2MDAgIiRORVRQTEFOX0ZJTEUiCiAgICBzdWRvIG5ldHBsYW4gYXBwbHkKICAgIGVjaG8gIlsrXSBBcHBsaWVkIFN0YXRpYyBJUCBjb25maWd1cmF0aW9uIHRvICRJRkFDRS4iCmVsc2UKICAgIGVjaG8gIlVzYWdlOiIKICAgIGVjaG8gIiAgU3dpdGNoIHRvIERIQ1A6ICAgc3VkbyBzZXQtaXAuc2ggZGgjcCIKICAgIGVjaG8gIiAgU3dpdGNoIHRvIFN0YXRpYzogc3VkbyBzZXQtaXAuc2ggc3RhdGljIDxJUC9DSURSPiA8R0FURVdBWT4gW0ROUzFdIFtETlMyXSIKICAgIGV4aXQgMQpmaQo=" | base64 -d | sudo tee /usr/local/bin/set-ip.sh > /dev/null && sudo chmod +x /usr/local/bin/set-ip.sh
```

### Usage Examples:

- **Configure Static IP**:
  ```bash
  sudo set-ip.sh static 192.168.1.150/24 192.168.1.1
  ```
- **Switch back to DHCP**:
  ```bash
  sudo set-ip.sh dhcp
  ```

---

## 4. Install Docker Engine & Docker Compose v2

Run the official Docker repository setup on the test VM:

```bash
# Add Docker's official GPG key:
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow non-root docker commands for admin user:
sudo usermod -aG docker $USER
```

Log out and back in over SSH to apply group membership, then verify:

```bash
docker version
docker compose version
```

---

## 5. Next Steps

Proceed to [02-build-minimum-testbed.md](02-build-minimum-testbed.md) to set up the seven-service dissertation test server.
