# 4. Register the Dragino Device in ChirpStack

This document creates the application and one physical device. The device's OTAA credentials are the identity of the sensor. Copy them carefully and never store them in this repository.

## 4.1 Create or select an application

1. Select **Applications** in ChirpStack.
2. Create an application if one does not already exist.
3. Use a clear name such as Dragino Environmental Sensors.
4. Add a description such as Battery-powered Dragino sensors on the Pi RAK5146 AS923-3 gateway.
5. Save the application.

Keep unrelated device families in separate applications when their payload formats or data consumers differ. Identical Dragino sensors can share one application and one device profile.

## 4.2 Create the device

1. Open the application.
2. Select **Devices**.
3. Select **Create** or **Add device**.
4. Enter a human-readable name, for example:

~~~text
Dragino-S31-01
~~~

5. Select the Dragino device profile created in [03-create-chirpstack-device-profile.md](03-create-chirpstack-device-profile.md).
6. Enter the sensor's DevEUI exactly as supplied by Dragino.
7. Save the device.

Recommended device naming format:

~~~text
<vendor>-<model>-<site-or-purpose>-<number>
~~~

Example:

~~~text
Dragino-LSN50v2-S31-greenhouse-01
~~~

## 4.3 Enter OTAA keys

Open the device's **Keys (OTAA)**, **OTAA keys**, or equivalent page and enter the values from the physical sensor's secure record.

| Key | Expected form | Handling |
|---|---|---|
| DevEUI | 16 hexadecimal characters | Device identity; usually already entered |
| JoinEUI/AppEUI | 16 hexadecimal characters | Use the sensor's actual value when required |
| AppKey | 32 hexadecimal characters | Secret; verify twice |
| NwkKey | 32 hexadecimal characters | Enter only for a LoRaWAN 1.1 device when requested |

Rules while copying:

- remove spaces, colons, and hyphens unless the UI explicitly accepts them;
- preserve every hexadecimal digit;
- do not replace a leading zero;
- do not use sample values from another document;
- do not paste keys into a shell command; and
- do not send keys in chat or screenshots.

The JoinEUI is also called AppEUI in many older Dragino documents. Use the name shown by the sensor firmware and the name expected by the ChirpStack page, but keep the value unchanged.

## 4.4 Add safe metadata

Useful non-secret tags and variables include:

~~~text
model=LSN50v2-S31
region=AS923-3
site=greenhouse
installation=2026-08-05
firmware=<recorded firmware version>
~~~

Do not use variables to store an AppKey, NwkKey, password, or access token unless you have intentionally designed and secured a secret-management process.

## 4.5 Confirm the stored identity

Before powering the device, compare the DevEUI shown in ChirpStack with the label or vendor export. The two must be identical. A device with a wrong DevEUI will not match the incoming JoinRequest even when the AppKey is correct.

The device is now provisioned, but it is not active until it sends an OTAA JoinRequest and receives a JoinAccept.

Next: [05-install-and-test-payload-codec.md](05-install-and-test-payload-codec.md)
