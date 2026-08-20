# Deployment Track: Gateway Setup & Field Operations

Use this directory for the complete physical gateway: Gateway OS setup, persistent buffering, the software integrity journal when its reviewed implementation exists, field operations, and security hardening.

---

## Directory Organization

```text
deployment/gateway/
├── 00-README.md     # This file
├── setup/           # Complete 6-step Gateway OS setup + 04a integrity journal guide
│   ├── 00-README.md
│   ├── 01-hardware-assembly.md
│   ├── 02-install-chirpstack-gateway-os.md
│   ├── 03-configure-concentratord.md
│   ├── 04-configure-local-mqtt-buffer.md
│   ├── 04a-configure-gateway-integrity-journal.md
│   ├── 05-configure-mqtt-forwarder.md
│   └── 06-verify-gateway-os.md
├── operations/      # Full operations suite (01-07)
│   ├── 01-register-and-test.md
│   ├── 02-backup-and-recovery.md
│   ├── 03-availability-tests.md
│   ├── 04-migrate-to-cloud.md
│   ├── 05-troubleshooting.md
│   ├── 06-rf-planning-and-site-survey.md
│   └── 07-security-hardening-and-vpn.md
└── references/      # Vendor datasheets, RAK5146 module specs, & hardware checklists
    └── README.md
```

---

## Operational Procedures Summary

- **[setup/](setup/00-README.md)**: Install ChirpStack Gateway OS Base, configure Concentratord for AS923, establish persistent loopback Mosquitto buffer, and enable the software integrity journal v2.
- **[operations/](operations/01-register-and-test.md)**: Register gateways in ChirpStack, execute automated static configuration backups (`sysupgrade -b`), run 4G migration and outage availability tests, perform RF site surveys, and configure SSH/VPN security hardening.
- **[references/](references/README.md)**: Consult hardware checklist PDFs and official RAK5146 datasheets.
