#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
RETIRED INSTALLER - NO CHANGES WERE MADE

This repository uses the official ChirpStack Gateway OS Base factory image for Raspberry Pi 4B + RAK5146.

A shell installer is not supported. Follow:

  gateway/setup/02-install-chirpstack-gateway-os.md
  gateway/setup/03-configure-concentratord.md
  gateway/setup/04-configure-local-mqtt-buffer.md
  gateway/setup/05-configure-mqtt-forwarder.md
  gateway/setup/06-verify-gateway-os.md

This file exits before installing packages, editing boot files, changing GPIO, deriving a Gateway ID, importing certificates, or starting services.
EOF

exit 1
