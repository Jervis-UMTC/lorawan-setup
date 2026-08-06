# ChirpStack Gateway OS Security

## 1. Management access

- Change the default root password immediately.
- Disable the commissioning access point after setup.
- Restrict LuCI and SSH to an approved management network or VPN.
- Do not publish gateway management ports to the internet.
- Keep DNS and time synchronization healthy.

## 2. Gateway services

Enable only:

```text
Concentratord
MQTT Forwarder
required OpenWrt networking and supervision services
```

Keep UDP Forwarder disabled. Do not install Gateway OS Full, LoRa Basics Station, Docker, a local ChirpStack server, or another packet forwarder.

## 3. MQTT identity

Each gateway receives a unique certificate and private key. The certificate Common Name equals the Gateway ID used in broker ACLs.

Protect:

```text
broker CA certificate
gateway client certificate
gateway private key
Gateway OS configuration backup
certificate serial, fingerprint, and expiry
```

Never copy the MQTT CA private key to a gateway.

## 4. Certificate lifecycle

Keep the certificate serial, SHA-256 fingerprint, expiry, protected backup location, renewal trigger, and revocation/replacement procedure. These values identify the active credential and allow it to be replaced without storing the private key in documentation.

Test rejection of an expired or untrusted certificate in staging. Verify recovery with a valid replacement bundle.

## 5. Firewall and 4G

The gateway initiates outbound MQTT. Do not configure inbound 4G port forwarding. Dynamic carrier addresses make source filtering unreliable; mutual TLS and ACLs remain mandatory.

## 6. Backup and upgrades

Preserve:

- the exact Gateway OS Base factory image reference and calculated hash;
- an encrypted configuration archive;
- an encrypted MQTT identity backup;
- the confirmed Gateway EUI, RF plan, management address, and broker endpoint;
- tested rollback instructions.

Test upgrades on spare hardware before fleet rollout. Do not factory-reset as the first recovery action.

## 7. Acceptance

- management access is private;
- default credentials and setup AP are removed;
- the tested Gateway OS Base release and rollback image can be identified;
- RAK5146 and the legal RF plan are confirmed;
- MQTT certificate and ACL isolation pass;
- UDP Forwarder is disabled;
- backup, restore, reboot, and WAN recovery pass.
