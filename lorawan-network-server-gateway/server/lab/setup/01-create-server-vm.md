# Server 1. Create the Host-Server Virtual Machine

Use a Linux VM instead of running ChirpStack directly in Docker Desktop. A VM gives the lab its own operating system, IP address, firewall, storage, boot process, and service lifecycle, which is closer to a cloud server.

## Step 1: Create the VM

Use Hyper-V, VirtualBox, VMware, KVM/libvirt, or another maintained hypervisor.

Recommended starting size for ChirpStack, TimescaleDB, Node-RED, Grafana, and the Fabric adapter:

```text
Guest OS: Ubuntu Server 24.04 LTS
vCPU: 4
RAM: 8 GB
Disk: 80 GB, dynamically allocated or larger
Network: bridged adapter or Hyper-V external switch
Hostname: lora-lab-server
```

This is a starting point, not a capacity guarantee. Measure database growth, container memory, disk latency, and host pressure. The host computer must also have enough resources for the separate Fabric VM.

A NAT-only VM is harder for the Raspberry Pi to reach. Use a bridged or external-switch network so the VM receives a normal LAN address.

## Step 2: Install Ubuntu Server

During installation:

- create a unique administrative account;
- enable OpenSSH Server;
- do not install a desktop environment;
- use automatic security updates if this matches the lab policy;
- keep the virtual disk on storage that is backed up.

After first login:

```bash
cat /etc/os-release
uname -a
ip -brief address
ip route
lsblk -f
df -h
```

Keep the VM UUID, host hypervisor, virtual-disk location, Ubuntu release, management IP address, and default route with the lab configuration. The IP/FQDN is used by the gateway and SSH procedures; the VM and disk identifiers are needed for backup and recovery. A missing default route or unexpected address must be corrected before installing the server stack.

## Step 3: Reserve the address and create DNS

Create a DHCP reservation for `<LAB_SERVER_IP_ADDRESS>`, using the address observed in Step 2 and reserved by the network administrator. Map `<LAB_SERVER_FQDN>` to that address in local DNS or a managed hosts entry:

```text
<LAB_SERVER_IP_ADDRESS> <LAB_SERVER_FQDN>
```

Verify from the gateway management network and the workstation used to administer the server:

```bash
getent hosts <LAB_SERVER_FQDN>
ping -c 4 <LAB_SERVER_FQDN>
```

## Step 4: Update and harden SSH

Run on the server VM:

```bash
sudo apt update
sudo apt full-upgrade
sudo reboot
```

After reconnecting, verify key-based SSH in a second session. Then:

```bash
sudo cp -pn /etc/ssh/sshd_config /etc/ssh/sshd_config.before-lorawan-lab
sudoedit /etc/ssh/sshd_config
sudo sshd -t
sudo systemctl reload ssh
```

Required settings:

```text
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
```

## Step 5: Apply the server firewall

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <MANAGEMENT_SUBNET_CIDR> to any port 22 proto tcp
sudo ufw allow from <GATEWAY_IP_ADDRESS> to any port 8883 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Do not open 1883, 5432, 6379, or 8080 to the LAN.

## Step 6: Configure VM autostart

Enable autostart in the selected hypervisor. Verify it with a controlled host reboot before relying on it.

A successful autostart test returns the VM with the same reserved address and reachable SSH service after the host reboot. A VM snapshot is useful before risky upgrades, but it is not a database backup. Keep PostgreSQL dumps and configuration archives separately.
