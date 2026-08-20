# Server 1. Create and Prepare the Application Server VM

This procedure creates the single Ubuntu Server VM used by the complete Docker lab, assigns a stable network identity, installs Docker Engine and Compose v2, and prepares the host for the etcd, Spilo/Patroni/PostgreSQL, HAProxy, PgBouncer, Mosquitto, Valkey, ChirpStack, TimescaleDB, Node-RED, Grafana, and Fabric-adapter containers.

The lab uses one VM on purpose. Docker containers simulate the production service roles and failure behavior without requiring a separate VM for every database or DCS member.

---

## Before you begin

Confirm these network and profile parameters before deploying the server:

```text
VM hostname: <SERVER_VM_HOSTNAME> (e.g., lora-cloud-sim or lora-lab-server)
VM static IP address: <SERVER_VM_IP_ADDRESS>
VM management FQDN: <SERVER_VM_FQDN> (e.g., lora-server.local)
MQTT broker FQDN: <MQTT_BROKER_FQDN> (e.g., mqtt.lorawan.local)
Evidence ingest FQDN when implemented: <EVIDENCE_INGEST_FQDN>
Management subnet: <MANAGEMENT_SUBNET_CIDR> (e.g., 192.168.1.0/24)
Gateway IP address: <GATEWAY_IP_ADDRESS>
Lab Compose directory: /opt/lorawan-lab
```

### Choose the correct VM profile

For dissertation testing, **do not use this full-stack profile**. Use [Server Preparation](../../../test/preparation/server/00-README.md): 5 GiB RAM, 4 vCPU, and 50 GiB disk on the 8 GiB / 8-thread physical host.

For the complete one-VM architecture reference, use a **larger physical host**. A practical low-rate starting point is:

```text
Guest OS: Ubuntu Server 24.04 LTS, no desktop GUI
vCPU: 8
RAM: 12 GiB
Disk: 160 GiB SSD-backed minimum
Firmware: UEFI recommended
Network: Bridged Adapter or Hyper-V External Switch
```

Do not create a 12 GiB VM on the dissertation's 8 GiB physical host. Use another/larger machine or the production multi-host/cloud path.

The per-container values in [Server 2](02-docker-topology-and-network.md) are low-load safety ceilings for the full-stack simulation, not production sizing.

---

## Step 1: Create the virtual machine

Create one Linux VM using the profile appropriate to the selected path. For the full-stack deployment described by this manual, use the larger profile above. For dissertation testing, return to Testing 01 instead.

### Procedure

1. Open your hypervisor manager (Hyper-V, VirtualBox, VMware, or Proxmox/KVM).
2. For the full-stack one-VM reference, allocate **12 GiB RAM**, **8 vCPU**, and at least **160 GiB SSD-backed disk** on a physical host with additional headroom.
3. Configure the virtual network interface:
   * **For Local Lab:** Select **Bridged Adapter** (or Hyper-V External Switch) so the Raspberry Pi 4B gateway and server VM reside on the same LAN subnet.
   * **For Cloud Simulation:** Follow the [cloud simulation network profile](../cloud-production/simulation/01-create-cloud-simulation-vm.md).

> [!CAUTION]
> Do not use an isolated NAT-only adapter unless you configure explicit port forwarding rules for TCP ports `22` (SSH) and `8883` (MQTT TLS).

---

## Step 2: Install Ubuntu Server

Use Ubuntu Server without a desktop GUI so RAM stays available for the containers.

### Procedure

1. Boot the VM from the official Ubuntu Server 24.04 LTS ISO image.
2. Complete the installation wizard with these choices:
   * Set **Hostname** to `<SERVER_VM_HOSTNAME>`.
   * Create a unique **Administrative User Account** (do not use default `admin`).
   * **Enable OpenSSH Server** (install `sshd`).
   * Do **NOT** install desktop GUI packages.
   * Do **NOT** install Docker via Snap.
3. After installation completes, reboot the VM and log in.
4. Run diagnostic checks:

```bash
hostnamectl
cat /etc/os-release
uname -a
ip -brief address
ip route
df -h
```

Confirm that the hostname, network interface, disk space, and OS version match your specifications.

---

## Step 3: Update the operating system

Patch the VM before creating persistent container data so later troubleshooting is not mixed with an unfinished OS upgrade.

### Procedure

Run on the server VM:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

After reconnecting over SSH, verify system health:

```bash
uname -a
systemctl --failed
```

Confirm that no system daemons report failed states.

### Step 3A: Add a small swap safety net when the VM has none

Check first:

```bash
swapon --show
```

If no swap exists, create **2 GiB**:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
printf 'vm.swappiness=10\n' | sudo tee /etc/sysctl.d/99-lorawan-lab-memory.conf
sudo sysctl --system
swapon --show
```

Swap is only an OOM safety net for short spikes. It is not capacity; sustained swapping means the VM or a container/workload is undersized.

---

## Step 4: Set stable hostname, static IP, and DNS resolution

Use stable names and addresses because gateway routing, node-to-node communication, and MQTT certificate validation depend on them.

### Procedure

1. Verify system hostname:

```bash
sudo hostnamectl set-hostname <SERVER_VM_HOSTNAME>
hostnamectl
```

2. **Automated Network Configuration Helper (`set-ip.sh`)**:

   Install the automated Netplan network helper script on the Ubuntu server. Paste this single command into the terminal to create `/usr/local/bin/set-ip.sh`:

```bash
echo "IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWUKCklGQUNFPSQoaXAgLTQgcm91dGUgc2hvdyBkZWZhdWx0IHwgYXdrICd7cHJpbnQgJDV9JyB8IGhlYWQgLW4xKQppZiBbIC16ICIkSUZBQ0UiIF07IHRoZW4KICAgIElGQUNFPSQoaXAgbGluayB8IGdyZXAgLUUgJ15bMC05XSs6IChlbnxldGgpJyB8IGF3ayAne3ByaW50ICQyfScgfCB0ciAtZCAnOicgfCBoZWFkIC1uMSkKZmkKCk5FVFBMQU5fRklMRT0iL2V0Yy9uZXRwbGFuLzAxLW5ldGNmZy55YW1sIgpNT0RFPSIkezE6LX0iCgppZiBbICIkTU9ERSIgPSAiZGhjcCIgXTsgdGhlbgogICAgZWNobyAiWytdIENvbmZpZ3VyaW5nICRJRkFDRSBmb3IgREhDUC4uLiIKICAgIHN1ZG8gdGVlICIkTkVUUExBTl9GSUxFIiA+IC9kZXYvbnVsbCA8PEVPRgpuZXR3b3JrOgogIHZlcnNpb246IDIKICByZW5kZXJlcjogbmV0d29ya2QKICBldGhlcm5ldHM6CiAgICAkSUZBQ0U6CiAgICAgIGRoY3A0OiB0cnVlCkVPRgogICAgc3VkbyBjaG1vZCA2MDAgIiRORVRQTEFOX0ZJTEUiCiAgICBzdWRvIG5ldHBsYW4gYXBwbHkKICAgIGVjaG8gIlsrXSBBcHBsaWVkIERIQ1AgY29uZmlndXJhdGlvbiB0byAkSUZBQ0UuIgoKZWxpZiBbICIkbW9kZSIgPSAic3RhdGljIiBdOyB0aGVuCiAgICBJUD0iJHsyOi19IgogICAgR0FURVdBWT0iJHszOi19IgogICAgRE5TMT0iJHs0Oi04LjguOC44fSIKICAgIEROUzI9IiR7NTotMS4xLjEuMX0iCgogICAgaWYgWyAteiAiJElQIiBdIHx8IFsgLXogIiRHQVRFV0FZIiBdOyB0aGVuCiAgICAgICAgZWNobyAiVXNhZ2U6IHN1ZG8gc2V0LWlwLnNoIHN0YXRpYyA8SVAvQ0lEUj4gPEdBVEVXQVk+IFtETlMxXSBbRE5TMl0iCiAgICAgICAgZWNobyAiRXhhbXBsZTogc3VkbyBzZXQtaXAuc2ggc3RhdGljIDE5Mi4xNjguMS4xNTAvMjQgMTkyLjE2OC4xLjEiCiAgICAgICAgZXhpdCAxCiAgICBmaQoKICAgIGVjaG8gIlsrXSBDb25maWd1cmluZyAkSUZBQ0Ugd2l0aCBTdGF0aWMgSVA6ICRJUCAoR2F0ZXdheTogJEdBVEVXQVkpLi4uIgogICAgc3VkbyB0ZWUgIiRORVRQTEFOX0ZJTEUiID4gL2Rldi9udWxsIDw8RU9GCm5ldHdvcms6CiAgdmVyc2lvbjogMgogIHJlbmRlcmVyOiBuZXR3b3JrZAogIGV0aGVybmV0czoKICAgICRJRkFDRToKICAgICAgZGhjcDQ6IGZhbHNlCiAgICAgIGFkZHJlc3NlczoKICAgICAgICAtICRJUAogICAgICByb3V0ZXM6CiAgICAgICAgLSB0bzogZGVmYXVsdAogICAgICAgICAgdmlhOiAkR0FURVdBWQogICAgICBuYW1lc2VydmVyczoKICAgICAgICBhZGRyZXNzZXM6CiAgICAgICAgICAtICRETlMxCiAgICAgICAgICAtICRETlMyCkVPRgogICAgc3VkbyBjaG1vZCA2MDAgIiRORVRQTEFOX0ZJTEUiCiAgICBzdWRvIG5ldHBsYW4gYXBwbHkKICAgIGVjaG8gIlsrXSBBcHBsaWVkIFN0YXRpYyBJUCBjb25maWd1cmF0aW9uIHRvICRJRkFDRS4iCmVsc2UKICAgIGVjaG8gIlVzYWdlOiIKICAgIGVjaG8gIiAgU3dpdGNoIHRvIERIQ1A6ICAgc3VkbyBzZXQtaXAuc2ggZGgjcCIKICAgIGVjaG8gIiAgU3dpdGNoIHRvIFN0YXRpYzogc3VkbyBzZXQtaXAuc2ggc3RhdGljIDxJUC9DSURSPiA8R0FURVdBWT4gW0ROUzFdIFtETlMyXSIKICAgIGV4aXQgMQpmaQo=" | base64 -d | sudo tee /usr/local/bin/set-ip.sh > /dev/null && sudo chmod +x /usr/local/bin/set-ip.sh
```

3. **Configure Network Mode**:

   - **To set Static IP**:
     ```bash
     sudo set-ip.sh static <SERVER_VM_IP_ADDRESS>/24 <GATEWAY_IP_ADDRESS> 8.8.8.8,1.1.1.1
     # Example: sudo set-ip.sh static 192.168.1.150/24 192.168.1.1
     ```
   - **To switch back to DHCP**:
     ```bash
     sudo set-ip.sh dhcp
     ```

4. Add local DNS resolution on your administration workstation and physical gateway (`/etc/hosts`):

```text
<SERVER_VM_IP_ADDRESS> <SERVER_VM_FQDN>
<SERVER_VM_IP_ADDRESS> <MQTT_BROKER_FQDN>
```

5. Test hostname resolution from workstation and gateway:

```bash
ping -c 4 <SERVER_VM_FQDN>
ping -c 4 <MQTT_BROKER_FQDN>
```

> [!IMPORTANT]
> `<MQTT_BROKER_FQDN>` will be embedded into the MQTT server certificate's Subject Alternative Name (SAN). It must resolve correctly on both the gateway and server.

---

## Step 5: Configure key-based SSH

Use SSH keys and disable remote root/password login after confirming the key works.

### Procedure

1. From your administration workstation, copy your SSH public key:

```bash
ssh-copy-id <ADMIN_USER>@<SERVER_VM_IP_ADDRESS>
ssh <ADMIN_USER>@<SERVER_VM_IP_ADDRESS>
```

2. Verify passwordless key login in a second terminal window before hardening SSH.
3. On the VM, back up and edit `/etc/ssh/sshd_config`:

```bash
sudo cp -pn /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sudo nano /etc/ssh/sshd_config
```

4. Enforce these security directives:

```text
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
```

5. Test and reload SSH configuration:

```bash
sudo sshd -t
sudo systemctl reload ssh
```

> [!CAUTION]
> Do not close your initial SSH terminal session until you open a second terminal and confirm key-based login succeeds.

---

## Step 6: Apply the host firewall

Expose only management SSH and the gateway-facing MQTT TLS listener. Keep internal database, cache, and web ports off the LAN.

### Procedure

Run on the server VM:

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <MANAGEMENT_SUBNET_CIDR> to any port 22 proto tcp
sudo ufw allow from <GATEWAY_IP_ADDRESS> to any port 8883 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Verify that UFW reports `Status: active` and lists allowed rules for ports `22` and `8883`.

When—and only when—the reviewed gateway evidence-ingest HTTPS service is later implemented on this VM, add the exact required TLS listener through a separate reviewed step, normally scoped to the gateway source network on TCP 443. Do not open port 443 now for a service that does not yet exist.

> [!NOTE]
> Web access to ChirpStack (port 8080) and Grafana (port 3000) will be accessed securely via SSH port forwarding (`ssh -L 8080:127.0.0.1:8080 ...`) rather than opening unencrypted web ports to the network.

---

## Step 7: Install Docker Engine and Compose v2

Docker runs every server-side lab technology on this one VM. Use the Docker Engine packages and Compose v2 plugin, not the Snap package.

### Procedure

Run on the server VM:

```bash
# Add official Docker GPG key & repository
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine & Compose plugin
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable Docker service
sudo systemctl enable --now docker
```

Add your user to the `docker` group:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

Verify installation:

```bash
docker version
docker compose version
docker run --rm hello-world
```

---

## Step 8: Create the lab Compose project directory

Use one fixed project root so every later manual modifies the same Compose stack.

### Procedure

```bash
sudo install -d -m 0755 -o "$USER" -g "$USER" /opt/lorawan-lab
cd /opt/lorawan-lab
pwd
```

Expected output:

```text
/opt/lorawan-lab
```

Do not clone the upstream ChirpStack example Compose stack as the lab architecture. The next manuals build the project explicitly so ChirpStack cannot accidentally start its own standalone PostgreSQL or Redis service and bypass the Patroni / HAProxy / PgBouncer / Valkey path.

---

## Step 9: Configure VM autostart

Enable VM autostart so a workstation or hypervisor reboot does not leave the entire lab offline until someone starts it manually.

### Procedure

1. In your hypervisor settings (Hyper-V / VirtualBox / VMware / Proxmox), enable **Automatic Startup on Host Boot**.
2. Perform a test host reboot and confirm that:
   * VM boots automatically.
   * IP address `<SERVER_VM_IP_ADDRESS>` remains unchanged.
   * SSH access is available immediately.
   * Docker daemon starts automatically (`systemctl is-active docker`).

---

## Troubleshooting

### Gateway cannot reach server port 8883
- Confirm VM uses Bridged Network Mode (not NAT).
- Check UFW status on VM (`sudo ufw status`).
- Verify gateway source IP matches the UFW rule.

### Docker permission denied errors
- Run `sudo usermod -aG docker $USER` and log out/in to refresh group tokens.

---

## Next Step

Continue with [02-docker-topology-and-network.md](02-docker-topology-and-network.md).
