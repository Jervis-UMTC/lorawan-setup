# RAK Gateway Troubleshooting & Diagnostic Runbook

This runbook provides an exhaustive diagnostic flowchart, failure category breakdown, log inspection tool guide, and root-cause resolution strategies for troubleshooting the **Raspberry Pi 4 + RAK5146 SPI Gateway** and **Standalone All-In-One ChirpStack v4 Stack**.

---

## 1. Master Troubleshooting Flowchart

```text
+-----------------------------------------------------------------------------------+
|                           SYSTEMIC DIAGNOSTIC FLOWCHART                           |
|                                                                                   |
|                           [Gateway Issue Reported]                                |
|                                      |                                            |
|                                      v                                            |
|                    (Can You SSH into Raspberry Pi 4?)                             |
|                       /                          \                                |
|                     NO                            YES                             |
|                     /                              \                              |
|                    v                                v                             |
|    [Check Network & SSH Service]            (Does Concentratord Start?)           |
|    - Is IP 169.254.x.x? (Local PC IP!)       /                          \          |
|    - Run ping rak-pi4-gateway.local        NO                            YES      |
|    - Check blank 'ssh' file on SD card    /                              \     |
|                                          v                                v    |
|                        [Check SPI & Reset Pin]            (Is Local Web UI Up?)|
|                        - ls -l /dev/spidev0.0                /               \ |
|                        - Run reset_rak_gateway.sh          NO                 YES|
|                        - Check 5V/3A Power Supply         /                    \ |
|                                                          v                      v|
|                                             [Check Docker Stack]           [OK]  |
|                                             - docker compose ps                  |
|                                             - Check Port 8080                    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Failure Category 1: SSH Access & Network Connection Issues

### 2.1 Symptom: `ssh: connect to host 169.254.x.x port 22: Connection refused`
- **Root Cause**: `169.254.x.x` is a Link-Local (APIPA) IP address assigned to your Windows PC's own network adapter, NOT the Raspberry Pi 4! When you SSH to your own PC's IP, Windows rejects Port 22 with `Connection refused`.
- **Resolution**:
  1. Use hostname in SSH command: `ssh pi@rak-pi4-gateway.local`.
  2. Find real network IP in PowerShell: `ping rak-pi4-gateway.local` or `arp -a`. Look for a `192.168.x.x` or `10.x.x.x` address.
  3. If SSH daemon was disabled during flashing: Eject microSD card, insert into PC, create a blank file named **`ssh`** (no file extension) and **`userconf.txt`** (`pi:$6$c70Vzham...`) in the root `boot` drive, re-insert into Pi 4 and power on.

### 2.2 Symptom: Windows Cannot See SD Card `boot` Partition / Prompts "Format Disk"
- **Root Cause**: Windows does not recognize Linux `rootfs` (`ext4`) partitions and pops up *"You need to format the disk"*. Additionally, Windows often fails to auto-assign a drive letter to the FAT32 `boot` partition.
- **Resolution**:
  1. ⚠️ **Click CANCEL on the format prompt! Do NOT format the SD card.**
  2. Press `Win + X` -> Open **Disk Management** (`diskmgmt.msc`).
  3. Right-click the small FAT32 `boot` partition (~256MB) at the bottom -> **Change Drive Letter and Paths** -> **Add** -> Assign drive letter `E:` or `F:`.

### 2.3 Symptom: Windows Network Bridge Fails / No Internet on Raspberry Pi
- **Root Cause**: Windows Network Bridge (`Bridge Connections` in `ncpa.cpl`) fails when bridging Wi-Fi and Ethernet adapters due to 802.11 MAC restrictions.
- **Resolution**:
  1. Delete any existing `Network Bridge` adapter in `ncpa.cpl`.
  2. Right-click **Wi-Fi** -> **Properties** -> **Sharing** tab -> Check *"Allow other network users to connect through this computer's Internet connection"*.
  3. Under *Home networking connection*, select your **Ethernet** port connected to the Pi.
  4. If checkbox is grayed out or throws a service error: Press `Win + R`, type `services.msc`, locate **Internet Connection Sharing (ICS)** (`SharedAccess`), set **Startup type** to **Automatic**, click **Start**, and retry.

---

## 3. Failure Category 2: Concentrator SPI Initialization Failures (`lgw_start failed`)

### 3.1 Symptoms & Error Logs
- Daemon logs display:
  ```text
  ERROR: [main] failed to start the concentrator
  ERROR: lgw_connect failure
  ERROR: [SX1302] Failed to connect to SPI device /dev/spidev0.0
  ```

### 3.2 Root Cause Analysis Matrix

| Cause | Verification Command | Resolution |
| :--- | :--- | :--- |
| **Kernel SPI Interface Disabled** | `ls -l /dev/spidev0.*` (Returns `No such file or directory`) | Run `sudo raspi-config nonint do_spi 0` and reboot. |
| **Concentrator Reset Pin Stuck** | Concentrator has not received hardware reset pulse on GPIO 17. | Run `sudo /usr/local/bin/reset_rak_gateway.sh` before starting daemon. |
| **Physical mPCIe Seating** | Card loose in WisLink Pi HAT socket. | Power off, unfasten standoffs, re-seat mini-PCIe card at 30 degrees, re-tighten M2 screws. |
| **Undervoltage Power Drop** | `vcgencmd get_throttled` (Returns `0x50005`) | Replace USB cable/power supply with official **5.1V / 3.0A USB-C** power adapter. |

---

## 4. Failure Category 3: Local All-In-One ChirpStack Docker Stack Issues

### 4.1 Symptoms: Web UI `http://<PI_IP>:8080` Unreachable
- **Verification**: Run `docker compose ps` in `/opt/chirpstack-docker`.
- **Resolution**:
  ```bash
  cd /opt/chirpstack-docker
  docker compose down
  docker compose up -d
  docker compose logs -f chirpstack
  ```

### 4.2 Symptoms: Gateway Status "Never Seen" in Local Web UI
1. Verify `chirpstack-gateway-bridge` container status:
   ```bash
   docker compose logs chirpstack-gateway-bridge
   ```
2. Verify UDP 1700 packet exchange on loopback interface:
   ```bash
   sudo tcpdump -ni lo port 1700
   ```
3. Confirm Gateway EUI registered in Web UI matches `eth0` MAC derivation:
   ```bash
   MAC=$(cat /sys/class/net/eth0/address | tr -d ':')
   echo "${MAC:0:6}fffe${MAC:6:6}" | tr '[:lower:]' '[:upper:]'
   ```

---

## 5. Live Diagnostic Commands Quick Reference

Save this list of operational diagnostic commands:

```bash
# 1. Inspect live ChirpStack Concentratord logs
sudo journalctl -u chirpstack-concentratord-sx1302 -f -o cat

# 2. Inspect Docker container status and logs
cd /opt/chirpstack-docker && docker compose ps
docker compose logs -f chirpstack
docker compose logs -f chirpstack-gateway-bridge

# 3. Monitor live UDP port 1700 packet flow on loopback
sudo tcpdump -ni lo port 1700

# 4. Test concentrator hardware reset pin (GPIO 17)
sudo /usr/local/bin/reset_rak_gateway.sh

# 5. Check SPI device nodes
ls -l /dev/spidev0.*

# 6. Check Raspberry Pi 4 CPU temperature and power throttling
vcgencmd measure_temp
vcgencmd get_throttled
```
