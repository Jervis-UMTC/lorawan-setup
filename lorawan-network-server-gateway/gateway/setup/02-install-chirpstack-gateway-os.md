# Gateway 2. Install ChirpStack Gateway OS Base

Run this procedure for a Raspberry Pi 4B with a verified RAK5146 SPI shield.

## Step 1: Confirm the hardware target

Check the labels on the Raspberry Pi, RAK5146, and Pi HAT before downloading an image. This prevents selecting an image or radio profile for different hardware.

```text
Raspberry Pi: 4B
RAK module: RAK5146
Interface: SPI
RAK frequency variant: RAK5146 US915
Pi HAT revision: <CONFIRMED_HAT_REVISION>
```

Do not proceed when the module or frequency variant is uncertain.

## Step 2: Select the Base image

Open the official ChirpStack Gateway OS Raspberry Pi download page and select:

```text
Target: Raspberry Pi 4B
Image type: Base
Artifact: SD card factory image
Version: <GATEWAY_OS_VERSION>
Filename: <GATEWAY_OS_IMAGE_FILENAME>
```

Do not select **Full**. It includes a local ChirpStack Network Server and does not match this repository's external-server architecture.

Do not use an image copied from an unknown mirror, forum attachment, or old workstation cache.

## Step 3: Verify and retain the exact image artifact

Run this on the workstation that downloaded the factory image:

```bash
sha256sum <GATEWAY_OS_IMAGE_FILENAME>
```

`<GATEWAY_OS_IMAGE_FILENAME>` comes from the official download selected in Step 2. Compare the calculated SHA-256 with trusted release metadata when the publisher provides one. Keep the official source, version, filename, calculated hash, and protected artifact location together because they identify the image used for a later rebuild or rollback.

A locally calculated hash detects later file changes but does not independently prove publisher authenticity. A mismatch means the download or retained artifact is not the expected file; download it again from the official source rather than flashing it.

## Step 4: Preserve rollback capability

Before overwriting an existing card:

1. export the current gateway configuration to encrypted off-gateway storage;
2. keep the existing Gateway EUI, region, certificate references, management address, and network settings because the restored gateway must use the same identity and RF plan;
3. create a verified image backup when recovery is required;
4. confirm a spare SD card and card reader are available.

**Stop here. Do not continue until this condition is resolved.** Do not overwrite the only recoverable gateway image.

## Step 5: Flash the factory image

Use Raspberry Pi Imager, Balena Etcher, or another approved raw-image writer.

Select exactly `<GATEWAY_OS_IMAGE_FILENAME>`, select the intended SD card, flash, and run the tool's verification step.

Do not preconfigure Raspberry Pi OS options; this is a Gateway OS image.

## Step 6: Perform the first boot on an isolated network

Connect:

- the LoRa antenna before powering the gateway;
- Ethernet to a commissioning network when available;
- a stable Raspberry Pi power supply.

Power on and allow the first boot to complete. Do not power-cycle during automatic first-boot changes.

Gateway OS normally uses DHCP on Ethernet. When Wi-Fi AP mode is available, the setup network is named similar to `ChirpStackAP-XXXXXX` and the initial password is `ChirpStackAP`. The setup address is normally `192.168.0.1`.

## Step 7: Set the root password immediately

Open:

```text
http://<GATEWAY_IP_ADDRESS>/
```

Follow the Gateway OS redirect when present. The browser may warn about the image's self-signed management certificate during commissioning.

Use the current Gateway OS login shown by the pinned release documentation. On current images the web user is `root` and the password is initially unset.

Set a strong unique password through the web interface before connecting the gateway to an untrusted network.

For SSH:

```bash
ssh root@<GATEWAY_IP_ADDRESS>
```

Do not permit passwordless root access after commissioning.

## Step 8: Configure management networking

In the Gateway OS web interface:

1. configure the approved Ethernet or Wi-Fi client network;
2. set hostname, DNS, and NTP sources;
3. verify the default route and time;
4. disable the setup access point when it is no longer required;
5. restrict web and SSH access to the management network.

Do not expose LuCI or SSH directly to the public internet.

## Step 9: Verify the running image

Run on Gateway OS over SSH:

```bash
cat /etc/os-release
uname -a
uci show system
monit status
```

Compare the observed Gateway OS, OpenWrt, kernel, and service state with the selected release. Keep these observed versions with the rollback image reference because package behavior and available configuration fields can differ between releases.

A healthy result shows the expected release and supervised gateway services without restart loops. A different release, failed service, or repeated restart means the flashed artifact or first-boot state must be corrected before radio configuration.

Continue with [03-configure-concentratord.md](03-configure-concentratord.md).
