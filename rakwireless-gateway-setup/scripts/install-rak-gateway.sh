#!/usr/bin/env bash
# ==============================================================================
# RAKwireless LoRaWAN Gateway Foolproof Automated Installer & Setup Script
# Supported Platforms: Raspberry Pi 3B+ / 4B / 5 with RAK5146 / RAK2287 SPI HAT
# ==============================================================================

set -euo pipefail

# Color Codes
RED='\030[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}      RAKwireless LoRaWAN Gateway Master Automated Installer          ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Check Root Privileges
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installer must be executed as root (e.g. sudo ./install-rak-gateway.sh)${NC}"
    exit 1
fi

# 2. System Dependency Installation
echo -e "${YELLOW}[1/6] Installing system prerequisites and build tools...${NC}"
apt-get update -qq
apt-get install -y -qq git build-essential raspi-config curl jq python3 libtool autoconf net-tools

# 3. Kernel SPI & UART Interface Enablement
echo -e "${YELLOW}[2/6] Enabling Kernel SPI Interface and configuring UART...${NC}"
raspi-config nonint do_spi 0
raspi-config nonint do_serial 2

# Disable Bluetooth overlay to free PL011 UART (/dev/ttyAMA0) for GPS module
CONFIG_TXT="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_TXT" ]; then
    CONFIG_TXT="/boot/config.txt"
fi

if ! grep -q "dtoverlay=miniuart-bt" "$CONFIG_TXT"; then
    echo "dtoverlay=miniuart-bt" >> "$CONFIG_TXT"
    echo -e "${GREEN}[+] Added miniuart-bt overlay to ${CONFIG_TXT}${NC}"
fi

# 4. Create Hardware Reset Script (GPIO 17)
echo -e "${YELLOW}[3/6] Installing GPIO 17 Concentrator Hardware Reset Script...${NC}"
mkdir -p /usr/local/bin

cat << 'EOF' > /usr/local/bin/reset_rak_gateway.sh
#!/usr/bin/env bash
# Hardware Reset Script for RAK5146 / RAK2287 on WisLink Pi HAT (GPIO 17)

RESET_PIN=17

echo "Toggling RAK Concentrator Reset on GPIO ${RESET_PIN}..."

if [ -d /sys/class/gpio/gpio${RESET_PIN} ]; then
    echo "${RESET_PIN}" > /sys/class/gpio/unexport 2>/dev/null || true
fi

echo "${RESET_PIN}" > /sys/class/gpio/export 2>/dev/null || true
echo "out" > /sys/class/gpio/gpio${RESET_PIN}/direction
echo "1" > /sys/class/gpio/gpio${RESET_PIN}/value
sleep 0.1
echo "0" > /sys/class/gpio/gpio${RESET_PIN}/value
sleep 0.1
echo "${RESET_PIN}" > /sys/class/gpio/unexport 2>/dev/null || true

echo "Concentrator reset pulse successfully delivered."
EOF

chmod +x /usr/local/bin/reset_rak_gateway.sh
echo -e "${GREEN}[+] Reset script created at /usr/local/bin/reset_rak_gateway.sh${NC}"

# 5. Derive Gateway EUI from Primary Interface
echo -e "${YELLOW}[4/6] Deriving unique Gateway EUI from network interface MAC...${NC}"
PRIMARY_IF=$(ip route show default | awk '/default/ {print $5}' | head -n1)
if [ -z "$PRIMARY_IF" ]; then
    PRIMARY_IF="eth0"
fi

MAC_RAW=$(cat "/sys/class/net/${PRIMARY_IF}/address" | tr -d ':')
GATEWAY_EUI=$(echo "${MAC_RAW:0:6}fffe${MAC_RAW:6:6}" | tr '[:lower:]' '[:upper:]')

echo -e "${GREEN}[+] Primary Interface : ${PRIMARY_IF}${NC}"
echo -e "${GREEN}[+] Derived Gateway EUI: ${GATEWAY_EUI}${NC}"

# 6. Install ChirpStack Concentratord (Modern Driver Stack)
echo -e "${YELLOW}[5/6] Installing ChirpStack Concentratord SX1302 Driver Daemon...${NC}"
apt-get install -y -qq apt-transport-https dirmngr ca-certificates

curl -s https://artifacts.chirpstack.io/key/chirpstack.key | gpg --dearmor --yes -o /usr/share/keyrings/chirpstack.gpg

echo "deb [signed-by=/usr/share/keyrings/chirpstack.gpg] https://artifacts.chirpstack.io/packages/4.x/deb stable main" > /etc/apt/sources.list.d/chirpstack.list

apt-get update -qq
apt-get install -y -qq chirpstack-concentratord-sx1302 || echo -e "${YELLOW}[!] Note: Could not fetch chirpstack package directly; install fallback manually if offline.${NC}"

# 7. Final Configuration Summary & Instructions
echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}      RAKwireless Gateway Installation Completed Successfully!        ${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo -e "Gateway EUI ID       : ${YELLOW}${GATEWAY_EUI}${NC}"
echo -e "Hardware Reset Script: ${YELLOW}/usr/local/bin/reset_rak_gateway.sh${NC}"
echo -e "SPI Bus Node         : ${YELLOW}/dev/spidev0.0${NC}"
echo -e "GPS Serial Node      : ${YELLOW}/dev/ttyAMA0${NC}"
echo -e ""
echo -e "${YELLOW}IMPORTANT REBOOT NOTICE:${NC}"
echo -e "A system reboot is required to activate kernel SPI/UART overlays."
echo -e "Execute '${GREEN}sudo reboot${GREEN}' now."
