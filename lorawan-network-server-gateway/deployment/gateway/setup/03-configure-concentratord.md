# Gateway 3. Configure Concentratord for RAK5146-115 (Philippines AS923)

This procedure configures **Concentratord** (the ChirpStack radio control daemon) to communicate with the **RAK5146-115** SPI LoRaWAN concentrator board on the Raspberry Pi 4B, specifically tailored for the **Philippines (AS923 / AS923-1)** LoRaWAN region.

Concentratord interfaces directly with the SX1303 baseband processor over the SPI bus. **MQTT Forwarder** consumes the supported Concentratord event interface for the delivery path. The software integrity journal added in Gateway 4A consumes that same supported event stream independently for evidence. Neither downstream service may take ownership of the SPI radio.

> [!CAUTION]
> Only one service may control the LoRa concentrator hardware at a time. Never run another packet forwarder daemon (such as the legacy Semtech UDP packet forwarder) simultaneously on the same radio hardware.

---

## Hardware and Regional Specifications

Confirm these confirmed hardware and regional parameters before enabling radio transmissions:

```text
Module model: RAK5146-115
Bus interface: SPI
Hardware frequency variant: 915 MHz High-Frequency (902–928 MHz)
Onboard features: Integrated ZOE-M8Q GPS / Non-LBT
Baseband chipset: Semtech SX1303
Deployment country: Philippines
Approved LoRaWAN region: AS923 (AS923-1 / Group 1)
Frequency spectrum: 920 MHz – 925 MHz (Join channels: 923.2 MHz & 923.4 MHz)
Selected channel plan: AS923 (or AS923_1)
MQTT region topic prefix: as923
Antenna frequency band: 900–930 MHz (Matches RAK5146-115)
```

> [!IMPORTANT]
> The RAK5146-115 uses the 915 MHz high-frequency front-end (902–928 MHz), which fully covers the Philippines AS923-1 frequency band (920–925 MHz). Selecting `AS923` in Gateway OS configures the correct center frequencies and multi-channel decoders for the Philippines.

---

## Step 1: Open the Concentratord page

### What this step does

Navigates to the Concentratord management interface within OpenWrt LuCI (**ChirpStack > Concentratord**).

### Why we do it

Opens the graphical configuration interface where Gateway OS configures baseband hardware drivers, SPI device paths (`/dev/spidev0.0`), GPIO reset pin mappings, and frequency channel plans for the concentrator HAT.

### Procedure

1. Sign in to the Gateway OS LuCI web interface (`http://<GATEWAY_IP>/`).
2. Navigate to **ChirpStack > Concentratord**.
3. Locate the configuration section for the concentrator card.

---

## Step 2: Select the RAK5146 profile and AS923 channel plan

### What this step does

Enables Concentratord and configures it to use the RAK5146 hardware driver profile matched with the **AS923** regional channel plan for the Philippines.

### Why we do it

* **Hardware Reset & SPI Mapping:** The RAK5146-115 uses an SX1303 baseband processor connected over SPI. Selecting the dedicated `RAK5146` profile ensures Gateway OS uses the correct GPIO pin numbers to reset the board and initializes the correct SPI bus interface (`/dev/spidev0.0`).
* **Frequency & Channel Decoding:** Selecting `AS923` configures center frequencies for Radio 0 (923.2 MHz) and Radio 1 (924.0 MHz) and binds multi-SF multi-channel decoders so the gateway can receive and decode node transmissions across the 920–925 MHz spectrum used in the Philippines.

### Procedure

#### Tab 1: Global configuration

1. In LuCI, open **ChirpStack > Concentratord**.
2. Stay on the **Global configuration** tab.
3. Configure:
   * **Enabled:** **`Checked` [x]**
   * **Enabled chipset:** **`SX1302 / SX1303`**

#### Tab 2: SX1302 / SX1303 configuration

1. Select the **SX1302 / SX1303** tab at the top of the page.
2. Configure the hardware fields:

| Field Name | Setting Value | Purpose / Requirement |
| :--- | :--- | :--- |
| **Antenna gain (dBi)** | `2` *(or 3 depending on antenna)* | Matches your physical omni antenna. |
| **Shield model** | `RAK - RAK5146` | Binds SPI GPIO reset and SX1303 driver. |
| **Channel-plan** | `AS923 - Standard channels + 923.6, 923.8, ... 924.6` | Philippines AS923-1 channel allocation. |
| **Gateway ID (optional)** | *(Leave empty)* | Auto-detects factory EUI from SX1303 chip. |
| **GNSS** | **`Checked` [x]** | Enables uBlox ZOE-M8Q GPS on RAK5146-115. |
| **USB** | **`Unchecked` [ ]** | RAK5146-115 uses SPI bus, not USB. |

> [!IMPORTANT]
> * **GNSS Checkbox:** Must be **Checked [x]** because your RAK5146-115 module includes an onboard uBlox GNSS module for fine time-stamping.
> * **USB Checkbox:** Must be **Unchecked [ ]** because your module communicates over the SPI bus interface.
> * **Gateway ID Field and inactive SX1301 values:**
>   * **Leave `Gateway ID (optional)` EMPTY on the active `SX1302 / SX1303` tab.**
>   * When the global chipset is `sx1302`, ignore any `gateway_id` displayed under inactive SX1301 configuration.
>   * The stale SX1301 example `2ccf67fffe0abee3` is not the RAK5146 identity and must never be registered in ChirpStack.
>   * The authoritative EUI is the `Gateway ID retrieved` value Concentratord reports after the active RAK5146 successfully starts.

3. Select **Save & Apply** at the bottom right.

---

## Step 3: Review antenna gain and transmit power settings

### What this step does

Configures antenna gain (dBi) and cable loss parameters matching your physical 900–930 MHz antenna installation.

### Why we do it

* **Regulatory Compliance (EIRP Limits):** Transmit power in the Philippines must adhere to NTC (National Telecommunications Commission) limits for short-range wireless devices. Entering accurate antenna gain allows Concentratord to calculate proper power attenuation for downlink transmissions.
* **Downlink Reliability:** Setting inaccurate gain values can cause downlink Join-Accept packets or Class A/C acknowledgments to fail or be transmitted at incorrect power levels.

### Procedure

When antenna gain, cable loss, LBT (Listen Before Talk), or transmit power fields are displayed:

1. Enter the verified gain for your 900–930 MHz antenna (typically `2` or `3` dBi for standard omni antennas).
2. Keep regional default values when no site-specific calibration data exists.
3. Do not arbitrarily increase transmit power to solve receive sensitivity issues.
4. Do not copy antenna settings from a different region (e.g. EU868 or US915).

---

## Step 4: Save and start Concentratord

### What this step does

Saves the configuration to OpenWrt UCI storage (`uci commit`) and starts the `chirpstack-concentratord` background daemon via Monit / system init.

### Why we do it

Applies power to the RAK5146-115 HAT, executes the GPIO reset pulse sequence, loads radio firmware into the SX1303 baseband chip over SPI, and starts real-time multi-channel spectrum listening on AS923 frequencies.

### Procedure

1. Select **Save & Apply**.
2. Wait for LuCI to finish applying the configuration.
3. Allow 10–15 seconds for the SPI hardware initialization sequence to complete.
4. Refresh the browser page.

> [!CAUTION]
> Do not repeatedly click **Save & Apply** while the service is initializing over SPI.

---

## Step 5: Confirm and record the Gateway EUI

### What this step does

Reads and displays the unique 64-bit (16 hexadecimal character) **Gateway EUI** generated from the RAK5146-115 concentrator chip's internal hardware ID.

### Why we do it

The **Gateway EUI** is the permanent hardware identity of your gateway. It is required for:
* Registering the gateway on the ChirpStack Network Server.
* Generating the gateway's MQTT topic hierarchy (`as923/gateway/<GATEWAY_EUI>/...`).
* Provisioning TLS client certificates and setting broker Access Control List (ACL) permissions.

### Procedure

After clicking **Save & Apply**, Concentratord initializes the RAK5146 hardware over SPI and extracts the chip's unique 16-character factory Gateway EUI.

#### Method A: Read the authoritative EUI from Concentratord startup logs

1. SSH into the gateway from your administration workstation terminal:
   ```bash
   ssh root@<GATEWAY_IP>
   ```
2. Read the successful Concentratord startup directly:
   ```sh
   logread -e chirpstack-concentratord | tail -n 100
   ```
3. Filter hardware/identity lines when needed:
   ```sh
   logread -e chirpstack-concentratord | \
   grep -Ei 'gateway|eui|sx130|rak5146|error|fail'
   ```
4. Record the EUI from:
   ```text
   Gateway ID retrieved, gateway_id: "<REAL_GATEWAY_EUI>"
   ```

Do not scrape an arbitrary 16-hex string from all configuration/log text. The running active concentrator is the authority.

#### Method B: Check LuCI Status Page

1. Refresh the Concentratord page (**ChirpStack > Concentratord**) or open **Status > Overview**.
2. Locate the **Gateway ID** or **Gateway EUI** display field.

#### Record the Gateway EUI

Record the 16-character hexadecimal string as `<GATEWAY_EUI>` (e.g. `ac1f09fffe05abcd`).

> [!IMPORTANT]
> The Gateway EUI is permanent and tied to the RAK5146 hardware. Reboot the gateway once and verify `<GATEWAY_EUI>` remains identical across reboots.

---

## Step 6: Verify the effective configuration over SSH

### What this step does

Connects to the gateway via SSH and inspects saved OpenWrt Unified Configuration Interface (UCI) options and background daemon status.

### Why we do it

Confirms that configuration values persisted correctly in file storage (`/etc/config/chirpstack-concentratord`) and that Monit reports the service is running healthily without crash-reboot loops.

### Procedure

Run these commands in an SSH terminal:

```sh
uci show chirpstack-concentratord
/etc/init.d/chirpstack-concentratord status
ps w | grep concentratord
```

Verify that:
* `chirpstack-concentratord.@global[0].enabled='1'`
* `chirpstack-concentratord.@global[0].chipset='sx1302'`
* `chirpstack-concentratord.@sx1302[0].model='rak_5146'` (or `rak5146`)
* `chirpstack-concentratord.@sx1302[0].channel_plan='as923'`
* `chirpstack-concentratord.@sx1302[0].gnss='1'`
* Service status reports **running** and `ps w` shows active `chirpstack-concentratord` processes.

---

## Step 7: Troubleshoot hardware detection or a missing Gateway EUI

### What this step does

Inspects OpenWrt system logs (`logread`) to diagnose SPI communication failures, pin alignment errors, or missing Gateway EUI issues.

### Why we do it

Identifies physical layer issues (unseated HAT, wrong 40-pin GPIO alignment, disabled SPI interface, or wrong voltage rail) before proceeding to software network configuration.

### Procedure

If the Gateway EUI is missing or Concentratord fails to start, view the log output over SSH:

```sh
logread -e chirpstack-concentratord
```

Match the error output against this guide:

| Log Message / Error | Root Cause & Action |
|---|---|
| `SPI device cannot be opened` | Check RAK5146 SPI variant, 40-pin GPIO header alignment, and Raspberry Pi SPI interface status. |
| `Reset or GPIO error` | Check HAT seating, pin alignment, and confirm `RAK5146` profile is selected. |
| `SX1250 or calibration error` | Check module frequency variant (confirm RAK5146-115 915MHz model), power supply, and antenna connection. |
| `Service repeatedly restarts` | Inspect UCI saved settings (`uci show chirpstack-concentratord`) for invalid channel plan names. |
| `Gateway EUI changes after reboot` | Check for competing packet forwarder services or wrong shield profile selection. |

> [!CAUTION]
> Always power down the Raspberry Pi before reseating the 40-pin HAT or RAK5146 module.

---

## Step 8: Disable legacy UDP Packet Forwarder

### What this step does

Disables and stops the legacy Semtech UDP packet forwarder service (`chirpstack-udp-forwarder`) in OpenWrt.

### Why we do it

* **Prevent Hardware Conflicts:** Multiple daemons attempting to control the same SPI bus interface simultaneously will cause bus collision errors and crash the radio.
* **Prevent Packet Duplication & Insecure Transmission:** Legacy UDP forwarders transmit unencrypted packet data over UDP port 1700. Disabling UDP Forwarder ensures all radio traffic flows exclusively through the secure Concentratord -> MQTT Forwarder architecture.

### Procedure

1. In LuCI, navigate to **ChirpStack > UDP Forwarder**.
2. On the **Global configuration** tab, ensure **Enabled** is **`Unchecked` [ ]**.
3. Select **Save & Apply**.
4. Verify over SSH that UDP Forwarder remains disabled:

```sh
uci show chirpstack-udp-forwarder
```

*Expected SSH Output:*
```text
chirpstack-udp-forwarder.@global[0].enabled='0'
```

---

## Step 9: Confirm the MQTT region topic prefix (`as923`)

### What this step does

Inspects the MQTT topic prefix generated by ChirpStack Gateway OS for the **AS923** regional channel plan.

### Why we do it

MQTT Forwarder constructs MQTT payload topics using the format `<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/<EVENT_TYPE>`. For this Philippines AS923 / AS923-1 setup, the working MQTT topic prefix is exactly `as923`. Keep that same value in MQTT Forwarder, the local bridge, server ACLs, and ChirpStack region backend.

### Procedure

Inspect the topic prefix in LuCI under **ChirpStack > MQTT Forwarder**, or read it over SSH:

```sh
uci show chirpstack-mqtt-forwarder | grep -i topic
```

Confirm the output value is:
```text
as923
```

Record this value as `<REGION_TOPIC_PREFIX>`.

---

## Step 10: Prepare the gateway MQTT identity

### What this step does

Links the confirmed `<GATEWAY_EUI>` to the downstream server provisioning workflow to prepare TLS certificates.

### Why we do it

Secure gateway communication uses Mutual TLS (mTLS). The remote ChirpStack Network Server generates client certificates where the **Common Name (CN)** strictly matches your `<GATEWAY_EUI>`.

### Procedure

Complete the server-side identity provisioning manual:

[Provision the gateway MQTT identity](../../server/ha-cluster/12-provision-gateway-mqtt-identity.md)

Obtain the following files for deployment in manual 04:
* Remote MQTT Broker CA Certificate (`ca.crt`)
* Gateway Client Certificate (`<GATEWAY_EUI>.crt`)
* Gateway Private Key (`<GATEWAY_EUI>.key`)
* Remote Broker FQDN / Hostname and TLS Port

---

## Completion check

Before moving to the next setup guide, verify that:
- [ ] `chirpstack-concentratord` is active and running (`monit status`).
- [ ] RAK5146-115 SPI profile is selected.
- [ ] Philippines **AS923** channel plan is active.
- [ ] `<GATEWAY_EUI>` is recorded and remains stable across reboots.
- [ ] `<REGION_TOPIC_PREFIX>` is confirmed as `as923`.
- [ ] `chirpstack-udp-forwarder` is completely disabled.

---

## Next step

Continue with [04-configure-local-mqtt-buffer.md](04-configure-local-mqtt-buffer.md), then add the independent [04a-configure-gateway-integrity-journal.md](04a-configure-gateway-integrity-journal.md) before final gateway verification.
