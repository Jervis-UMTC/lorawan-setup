# Dragino Sensor Setup for the Raspberry Pi RAK5146 Gateway

This folder documents how to add a Dragino LoRaWAN sensor to the gateway and ChirpStack installation already built in this project.

It is written for the current deployment:

~~~text
Raspberry Pi 4B
  -> RAK5146 / SX1303 concentrator
  -> native lora_pkt_fwd packet forwarder
  -> ChirpStack Gateway Bridge over UDP 1700
  -> ChirpStack v4 in Docker
  -> AS923-3 regional configuration
~~~

## Compatibility verdict

The gateway is ready to receive a Dragino sensor. The sensor will work when all of these conditions are true:

1. The sensor is a LoRaWAN device, not a proprietary 915/923 MHz radio device.
2. Its firmware is configured for the same regional sub-band as the gateway: **AS923-3**.
3. It uses an activation method and LoRaWAN version that are represented correctly in ChirpStack.
4. The sensor's own DevEUI, JoinEUI/AppEUI, and AppKey are entered correctly.
5. The correct payload codec is used for the exact Dragino model.

Do not assume that a label saying only AS923 means AS923-3. AS923 has multiple regional variants. Verify the exact variant before attempting enrollment.

## Guide map

| File | Purpose |
|---|---|
| [01-identify-sensor-and-verify-compatibility.md](01-identify-sensor-and-verify-compatibility.md) | Identify the exact model, band, firmware, activation method, and credentials |
| [02-prepare-and-verify-current-stack.md](02-prepare-and-verify-current-stack.md) | Prove the gateway and ChirpStack path is healthy before blaming the sensor |
| [03-create-chirpstack-device-profile.md](03-create-chirpstack-device-profile.md) | Create the correct ChirpStack v4 profile |
| [04-register-dragino-device.md](04-register-dragino-device.md) | Create the application and device and enter OTAA credentials |
| [05-install-and-test-payload-codec.md](05-install-and-test-payload-codec.md) | Configure the S31/S31B decoder or choose the correct alternative |
| [06-power-on-join-and-first-uplink.md](06-power-on-join-and-first-uplink.md) | Trigger the sensor, observe OTAA, and capture the first uplink |
| [07-acceptance-test-and-operations.md](07-acceptance-test-and-operations.md) | Verify the complete path and operate the sensor safely |
| [08-dragino-troubleshooting.md](08-dragino-troubleshooting.md) | Troubleshoot by symptom and by LoRaWAN stage |
| [09-device-inventory-template.md](09-device-inventory-template.md) | Record non-secret device details for repeatable maintenance |

## Important distinction from the older master guide

[The older master deployment guide](../../docs/01-master-deployment-guide.md) contains useful Dragino LSN50v2-S31/S31B payload information, but its main architecture assumes an Ubuntu VM, a Milesight gateway, and EU868. Those assumptions do not describe this installation. Reuse its Dragino-specific codec and payload concepts only after confirming the exact sensor model; use this folder for the current Pi, RAK5146, ChirpStack, and AS923-3 workflow.

Never copy example credentials from any guide. The DevEUI, JoinEUI/AppEUI, and AppKey in a device's label or vendor configuration are device-specific.

## Definition of done

The sensor setup is complete when:

- the gateway is online in ChirpStack;
- ChirpStack receives a JoinRequest from the sensor;
- ChirpStack sends a JoinAccept;
- the sensor sends a normal uplink;
- the uplink is decrypted and decoded into sensible values;
- the device's frame counters and last-seen time continue to advance; and
- the device record is documented without storing secret keys in this repository.

## Safety and security rules

- Keep the antenna connected whenever the concentrator is powered.
- Do not put an AppKey, NwkKey, API token, or password in Git, screenshots, shell history, or chat.
- Do not reuse sample credentials found in the older documentation.
- Do not change the gateway's region while diagnosing one sensor. First prove the sensor's exact regional firmware.
- Do not send a downlink repeatedly to a battery-powered Class A sensor.

Next: [01-identify-sensor-and-verify-compatibility.md](01-identify-sensor-and-verify-compatibility.md)
