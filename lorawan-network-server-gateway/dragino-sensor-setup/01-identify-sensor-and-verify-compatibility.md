# 1. Identify the Dragino Sensor and Verify Compatibility

Do this before creating a ChirpStack device. A Dragino label such as LSN50v2, S31, or AS923 is not enough by itself to determine the complete configuration.

## 1.1 Record the exact hardware identity

Read the label, packaging, purchase record, or Dragino configuration tool and record:

| Field | Example format | Why it matters |
|---|---|---|
| Manufacturer | Dragino | Confirms the vendor family |
| Exact model | LSN50v2-S31, LSN50v2-S31B, LHT65, etc. | Selects the payload format and codec |
| Hardware revision | Any printed revision | Some revisions change sensors or payloads |
| Frequency marking | AS923, AS923-3, 915, etc. | Must match the gateway's regional plan |
| Firmware version | 1.x.y or vendor-specific value | Determines LoRaWAN behavior and payload details |
| Activation | OTAA or ABP | Determines the ChirpStack enrollment fields |
| LoRaWAN version | 1.0.x or 1.1 | Determines the keys and profile fields |
| Battery state | New, charged, or unknown | A weak battery can prevent a join or uplink |

Use the exact model name in the ChirpStack device name and in the inventory template later in this folder.

## 1.2 Verify the regional band

The current gateway and ChirpStack stack use **AS923-3**. The sensor must use a firmware configuration that can operate on AS923-3.

Do not treat these as interchangeable:

| Sensor marking/configuration | Can it be assumed compatible? |
|---|---|
| AS923-3 | Yes, subject to correct keys and profile |
| AS923 | Not without checking the device's selectable sub-band and firmware |
| AS923-1 | No assumption; it may use different channels and RX2 parameters |
| AS923-2 or AS923-4 | No; verify or reconfigure before use |
| EU868, US915, AU915, or another plan | No; it requires the matching gateway region and legal deployment |

Dragino's official frequency-band guidance explains that AS923-1 through AS923-4 are distinct configurations. It also lists AS923-3 defaults around 916.6 MHz and 916.8 MHz, which is consistent with this gateway's AS923-3 channel plan.

If the sensor's firmware cannot select AS923-3, do not change the gateway to guess. Obtain the correct sensor firmware or use a gateway/network configuration that is legally and technically correct for the sensor.

## 1.3 Confirm that it is LoRaWAN

The device must advertise or document:

- LoRaWAN;
- OTAA or ABP;
- a DevEUI or device address; and
- a regional frequency plan.

A sensor that only advertises a proprietary LoRa, FSK, BLE, or cellular mode cannot join ChirpStack as a LoRaWAN end device.

## 1.4 Confirm the activation method

Prefer OTAA. For an OTAA device, obtain the following from the device label, vendor tool, or secure provisioning record:

- DevEUI: 16 hexadecimal characters;
- JoinEUI/AppEUI: 16 hexadecimal characters, if the device requires it;
- AppKey: 32 hexadecimal characters for LoRaWAN 1.0.x; and
- NwkKey as well if the device is LoRaWAN 1.1 and ChirpStack requests it.

For ABP, the required values are different: DevAddr, network session key, and application session key. Do not put an ABP device into an OTAA profile.

## 1.5 Credential handling

Record the location of the credentials, not the secret itself. A safe record looks like this:

~~~text
Device label: stored in the locked device cabinet
Vendor export: stored in the approved password manager
ChirpStack device: Dragino-Sensor-01
AppKey copied: yes, verified twice, not stored in this repository
~~~

The older documentation contains example values. They are not safe defaults and must not be entered for a different physical sensor.

## 1.6 Select the correct codec path

Use the local S31/S31B decoder only when the exact model is LSN50v2-S31 or LSN50v2-S31B and the payload format matches the vendor documentation:

[05-install-and-test-payload-codec.md](05-install-and-test-payload-codec.md)

For any other Dragino model, leave the codec unset until its own payload specification is identified. A successful LoRaWAN join with a wrong codec is still a valid network connection; only the application decoding is wrong.

## 1.7 Stop/go decision

Proceed to the next document only if you can answer all of these:

- What is the exact model and hardware revision?
- Is the firmware AS923-3-compatible?
- Is the device OTAA or ABP?
- Which LoRaWAN MAC version does it implement?
- Where are the device credentials stored securely?
- Which payload codec belongs to this exact model?

If any answer is unknown, identify it first. The most common failed enrollment is not a broken gateway; it is a device configured for a different regional plan or a key copied incorrectly.

Next: [02-prepare-and-verify-current-stack.md](02-prepare-and-verify-current-stack.md)
