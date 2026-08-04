# RAK Gateway Security Hardening & VPN Backhaul Handbook

This handbook provides production-grade security practices, operating system hardening rules, firewall configurations, WireGuard VPN tunnel setups, and TLS certificate authentication workflows for securing RAKwireless LoRaWAN gateways deployed in untrusted field environments.

---

## 1. System Hardening & Credential Protection

Edge gateways deployed in public or outdoor environments are prime targets for unauthorized access attempts. Hardening the OS kernel and network layer is mandatory.

```text
+-----------------------------------------------------------------------------------+
|                           GATEWAY SECURITY DEFENSE LAYERS                         |
|                                                                                   |
|  [Physical Enclosure Lock / Tamper Switch]                                        |
|        |                                                                          |
|        v                                                                          |
|  [SSH Key Enforcement & Password Authentication Disable]                           |
|        |                                                                          |
|        v                                                                          |
|  [Host Firewall (nftables) -> Drop All Inbound Except WireGuard/SSH]              |
|        |                                                                          |
|        v                                                                          |
|  [Encrypted VPN Tunnel (WireGuard UDP 51820) / mTLS TLS 1.3 WebSockets]          |
|        |                                                                          |
|        v                                                                          |
|  [Central Network Server / LNS Infrastructure]                                    |
+-----------------------------------------------------------------------------------+
```

### 1.1 Root & User Password Rotation
Immediately change default factory credentials on both WisGate OS and Raspberry Pi OS:

```bash
# On Raspberry Pi OS: Change 'pi' user password
passwd

# On WisGate OS / OpenWrt: Change 'root' password
passwd root
```

---

## 2. SSH Service Hardening

Edit the SSH daemon configuration file `/etc/ssh/sshd_config` (or `/etc/config/dropbear` on OpenWrt):

### 2.1 Raspberry Pi OS (`/etc/ssh/sshd_config`)

```ini
# Change default SSH port to a non-standard port
Port 2222

# Disable root login over SSH
PermitRootLogin no

# Enforce SSH Public Key Authentication
PubkeyAuthentication yes
PasswordAuthentication no
ChallengeResponseAuthentication no

# Limit login attempts and timeout inactive sessions
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
```

Restart the SSH service to apply changes:
```bash
sudo systemctl restart ssh
```

---

## 3. Host Firewall Configuration (`nftables` / `ufw`)

Block all incoming connection attempts except stateful return traffic and required administrative ports.

### 3.1 `ufw` Configuration for Raspberry Pi OS

```bash
# Install ufw
sudo apt-get install -y ufw

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow custom SSH port (e.g., 2222) from management subnet only
sudo ufw allow from 192.168.1.0/24 to any port 2222 proto tcp

# Allow WireGuard VPN port
sudo ufw allow 51820/udp

# Enable firewall
sudo ufw enable
```

---

## 4. Encrypted Backhaul via WireGuard VPN

When gateways connect over cellular networks (4G LTE), carriers assign CGNAT (Carrier-Grade NAT) private IP addresses, preventing direct inbound management access. A **WireGuard VPN tunnel** provides an encrypted static IP overlay.

```text
[RAK Gateway] (CGNAT 4G LTE IP) ===WireGuard Tunnel (UDP 51820)===> [Central VPN Server] (Public IP)
  Virtual IP: 10.8.0.2                                                 Virtual IP: 10.8.0.1
```

### 4.1 Installing WireGuard on RAK Gateway (Raspberry Pi OS)

```bash
sudo apt-get install -y wireguard
```

### 4.2 Gateway WireGuard Configuration (`/etc/wireguard/wg0.conf`)

Generate keypair:
```bash
wg genkey | tee privatekey | wg pubkey > publickey
```

Create configuration file `/etc/wireguard/wg0.conf`:

```ini
[Interface]
# Private IP assigned to this Gateway within the VPN
Address = 10.8.0.2/24
PrivateKey = YOUR_GATEWAY_PRIVATE_KEY_HERE
DNS = 1.1.1.1

[Peer]
# Central VPN Server Public Key
PublicKey = YOUR_VPN_SERVER_PUBLIC_KEY_HERE

# Tunnel endpoints allowed
AllowedIPs = 10.8.0.0/24

# Central VPN Server Public IP and Port
Endpoint = vpn.yourdomain.com:51820

# Keep-alive pulse to maintain NAT binding through 4G carrier networks
PersistentKeepalive = 25
```

### 4.3 Enabling WireGuard Service
```bash
sudo systemctl enable --now wg-quick@wg0
sudo wg show
```

---

## 5. Mutual TLS (mTLS) Authentication for Basic Station

To prevent unauthorized rogue gateways from connecting to your Network Server, configure **mTLS (Mutual TLS)** certificate authentication.

```text
               +-------------------------------------------------------+
               |                  mTLS HANDSHAKE FLOW                  |
               |                                                       |
               |  1. Gateway connects to LNS Port 8887 (TLS)          |
               |  2. LNS sends Server Certificate -> Gateway validates  |
               |  3. Gateway sends Client Certificate -> LNS validates |
               |  4. Encrypted session established                     |
               +-------------------------------------------------------+
```

### 5.1 Certificate File Structure in `/etc/station/`
- `tc.trust`: Root CA certificate (verifies the Network Server).
- `tc.crt`: Gateway Client Certificate (signed by internal PKI).
- `tc.key`: Gateway Client Private Key (generated securely on the gateway).

### 5.2 File Permission Security
Restrict read access of TLS private keys to the daemon user only:

```bash
sudo chmod 600 /etc/station/tc.key
sudo chmod 644 /etc/station/tc.crt
sudo chmod 644 /etc/station/tc.trust
sudo chown -R root:root /etc/station/
```

---

## 6. Fail2ban Brute-Force Prevention

Install **Fail2ban** to automatically ban IP addresses that perform failed SSH login attempts:

```bash
sudo apt-get install -y fail2ban
```

Create `/etc/fail2ban/jail.local`:

```ini
[sshd]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
findtime = 600
bantime = 86400
```

Enable and start fail2ban:
```bash
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```
