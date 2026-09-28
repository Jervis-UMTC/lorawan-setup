# Chapter 2 — Gateway-01: Install and Access Gateway OS

## 2.1 What ChirpStack Gateway OS does

Gateway-01 is a **Raspberry Pi 4B running a custom ChirpStack Gateway OS Base 4.12.0 / OpenWrt image**. The gateway receives LoRaWAN radio packets and forwards them to the separate cloud network server; it is not itself a ChirpStack Full network-server deployment. The custom image includes the SIM7600/QMI driver stack, local Mosquitto and gateway-evidence services.

This chapter covers the operating system, installation and access. RAK5146 radio tuning, SIM7600 LTE routing and MQTT certificates have separate setup chapters.

## 2.2 Gather the correct hardware

1. Prepare Raspberry Pi 4B, the RAK5146-115 **SPI** concentrator and matching Raspberry Pi HAT, compatible LoRa antenna/pigtail, SIM7600 USB dongle with SIM and antennas, stable Pi power supply, microSD card and management Ethernet cable.
2. **Disconnect Pi power.** Fit the RAK5146 module and HAT on the appropriate headers/standoffs; do not use the mPCIe-shaped concentrator as a PCIe card. Seat the LoRa u.FL connector on the **LoRa** RF port, not the GNSS port. Attach the matching antenna before power-up.
3. Connect the SIM7600 only to its commissioned USB/power connection. Insert the verified microSD card after flashing.

**Expected result:** board and HAT lie flat, headers are aligned, no cables are pinched, and LoRa/LTE antennas are securely attached. If a connector, radio band, or power arrangement is uncertain, stop before applying power.

<!-- RAK_IMAGE: Figure 2.1 exact RAKwireless RAK5146 Pi HAT product photograph, cropped only to remove reflection; confirm LoRa (not GPS) port; do not depict unrelated RAK2013 or claim this is installed Gateway-01. -->

## 2.3 Find the approved gateway image — do not choose an arbitrary latest image

The accepted commissioned custom production image is:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
Size: 28,900,364 bytes
SHA-256: bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d
```

**Note:** The tested build target uses `bcm27xx/bcm2709` and the `rpi-2` image name even though the installed board is a Raspberry Pi 4B. Match the actual approved image **hash and size**, not a target name you think looks more appropriate. The public stock Gateway OS download is not an equivalent replacement for the custom SIM7600/evidence image.

**Windows PowerShell — run before selecting a microSD card:**

```powershell
$Image = (Read-Host 'Paste the full path to the approved .img.gz').Trim([char]34)
$ExpectedName = 'chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz'
$ExpectedHash = 'bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d'
if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) {
    throw 'FAIL: image file not found. Stop; do not flash.'
}
$File = Get-Item -LiteralPath $Image
if ($File.Name -ne $ExpectedName -or $File.Length -ne 28900364) {
    throw 'FAIL: wrong image name or size. Stop; do not flash.'
}
if ((Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedHash) {
    throw 'FAIL: image SHA-256 mismatch. Stop; do not flash.'
}
'IMAGE_VERIFIED=PASS (correct custom gateway image)'
```

**Expected result:** `IMAGE_VERIFIED=PASS`. Any `FAIL` means stop before flashing. A newer intentional custom build needs its own accepted release manifest; never apply the old hash to a different release.

## 2.4 Preserve the running gateway before any replacement

**Skip flashing when the current Gateway-01 is already operating correctly.** If an approved rebuild is required:

1. Preserve an off-gateway encrypted configuration archive and the protected MQTT/evidence client identities.
2. Preserve the local Mosquitto queue and the gateway journal/checkpoint/receipt continuity according to the recovery chapter.
3. Verify a readable rollback image and a spare microSD card where possible.
4. Record the current management IP and last cloud-accepted evidence checkpoint before replacing media.

A normal OpenWrt configuration backup may omit protected keys, buffered packets and gateway journal state. **Do not reset OverlayFS, erase a queue or discard a journal merely to reach a clean setup screen.**

## 2.5 Flash the approved factory image (new card / authorized rebuild only)

**Workstation: Windows; gateway: powered off.**

1. Insert the intended microSD in the workstation. Confirm its identity and capacity; disconnect unrelated removable media to avoid erasing the wrong disk.
2. Open **Raspberry Pi Imager**. In **Device**, select **Raspberry Pi 4** and click **Next** as shown in **Screen 2A**. Then select **OS → Use custom** (Figure 2.2), browse to the verified custom `.img.gz` and click **Next**. **Do not choose Raspberry Pi 5 or Raspberry Pi OS (64-bit)** even if a reference screenshot elsewhere shows them. If you use balenaEtcher instead, its screens differ; follow its image/target/verify workflow rather than these Raspberry Pi Imager screenshots.

<!-- IMAGER_PI4_DEVICE_IMAGE: Real Imager v2 screenshot with Pi4 selected (step 2 device tab), not a fake live screenshot. -->

<!-- IMAGER_OS_IMAGE: Imager 2.0 screenshot showing exact Use custom entry, not stock Raspberry Pi OS selection. Third-party screenshot labeled with source; do not pretend selected project image appears. -->

3. In **Storage**, select the removable microSD card by its capacity and reader name. Keep **Exclude system drives** enabled. If unsure, unplug the other removable drives and identify the correct card before continuing.

<!-- IMAGER_STORAGE_IMAGE: Windows Imager 2.0 screen identifying removable USB/SD reader by capacity and checked Exclude system drives; reader example differs from ours. -->
4. If Imager offers **Raspberry Pi OS customisation**, skip it: our custom OpenWrt Gateway OS does not inherit those Raspberry Pi OS user/Wi-Fi settings. On **Writing → Summary**, confirm three items before clicking **Write**: device **Raspberry Pi 4**, operating system **the approved custom Gateway OS `.img.gz`**, and storage **your identified removable microSD**. **Screen 2B deliberately shows wrong example values** so you can recognize the summary layout; do not click Write on a summary resembling that example. On the erase dialog, read the actual device name and click **I understand, erase and write** only if it is your card. Wait for writing **and verification** to finish. If verification fails, stop; do not boot an unverified card.

<!-- IMAGER_WRITE_SUMMARY_IMAGE: Real official Writing Summary screenshot used as explicit WRONG VALUES / STOP example; a Pi4 + approved custom image actual screenshot requires the approved image and removable card present. -->
5. Safely eject the card. Ignore Windows requests to format the Linux/OpenWrt partitions.
6. With antennas attached and power disconnected, insert the card in Gateway-01. Connect management Ethernet, then power the Pi; allow first-boot initialization and a possible automatic reboot.

**Expected result:** Raspberry Pi boots from the custom Gateway OS image. Do not assume the default management IP of a stock tutorial is active after the commissioned configuration is restored.

## 2.6 Open the gateway management interface

The commissioned management Ethernet address is **192.168.20.11/24**, on `br-lan`. This is a local administration path; it is **not** the production Internet backhaul.

1. Connect the workstation to Gateway-01's management network.
2. In the workstation browser, open `http://192.168.20.11/` (or the approved HTTPS endpoint if that is what the current configuration exposes).
3. On an existing commissioned gateway, sign in with the protected **root** credential from the approved workstation vault; do not use documentation-era empty passwords. On a truly fresh stock image, follow the first-login workflow to set a root password immediately.
4. To administer by SSH from **Windows PowerShell**, use:

```powershell
ssh root@192.168.20.11
```

Enter the credential at the password prompt; do not put it in a command argument. The approved Windows workstation stores the commissioned Gateway-01 password in its current-user DPAPI credential custody, not in the Word manual.

**Expected result:** OpenWrt administration interface or Gateway-01 BusyBox shell. If unreachable, confirm the correct workstation network, Pi boot/power, cable and address before changing cloud firewall or LTE configuration.

## 2.7 Confirm OS identity and storage — safe read-only check

**Gateway-01 OpenWrt BusyBox shell** (not Windows PowerShell):

```sh
cat /etc/os-release
ubus call system board
date -u
df -h
ip route
```

**Expected result:** correct OpenWrt/Gateway OS platform, plausible UTC, usable writable overlay/storage, management address and intended route ownership. A route via `wwan0` belongs to the LTE route controller; a temporary absence during modem convergence is not permission to install a permanent Ethernet Internet default.

Inspect core services without restarting them:

```sh
ps w | grep -E '[c]hirpstack-concentratord|[c]hirpstack-mqtt-forwarder|[m]osquitto|[l]te-route-health'
logread | tail -n 80
```

**Expected result:** intended processes present and no immediate crash loop. Detailed radio/MQTT/LTE checks appear in their own chapters.

## 2.8 Backup and quick troubleshooting

**Create the configuration archive:** in OpenWrt/LuCI choose **System → Backup / Flash Firmware → Generate archive**; store the archive **off-gateway** in protected custody. Separately preserve journal/queue and certificate material before a reflash. ChirpStack Gateway OS uses OverlayFS, so check which files the upgrade archive actually includes. An ordinary backup is not a substitute for a complete recovery set.

| Problem | Check first |
|---|---|
| No boot / LEDs | Pi power, SD writing/verification, card and board seating. |
| No web/SSH access | Correct management network and `192.168.20.11`, link, boot completion, credentials. |
| OS runs, no RF | RAK5146 HAT/SPI, correct LoRa antenna and Concentratord chapter. |
| RF works, no cloud traffic | Local Mosquitto and SIM7600/LTE chapters. |
| Storage full | Locate the consuming path; **do not delete** evidence journal or MQTT queue without recovery review. |

**Chapter 2 complete when:** correct custom OS identity, safe physical connections, management access, sound storage and expected gateway services are confirmed. Continue to RAK5146 / Concentratord for AS923 radio configuration.

**Figure sources:** 2.1 RAKwireless official RAK5146 Pi HAT product photo (not a photograph of our installed gateway/SIM7600); 2.2 Onefinity CNC Raspberry Pi Imager 2.0 Use custom screenshot; 2.3 SunFounder Windows Imager 2.0 removable storage screenshot; 2.4 Raspberry Pi official erase-warning example. Source URLs, project-specific cautions and archived excluded stock images are recorded in `documentation/assets/VISUAL-SOURCES.md`. No stock EU868 screen is evidence of our AS923 settings.
