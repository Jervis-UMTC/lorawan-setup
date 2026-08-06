# 3. Create the ChirpStack v4 Device Profile

A device profile describes the behavior ChirpStack expects from a family of sensors. Create one profile per genuinely different device behavior; reuse it for multiple identical Dragino sensors after the first device is proven.

## 3.1 Open the profile page

1. Sign in to the ChirpStack web interface.
2. Select the correct tenant.
3. Open **Device profiles**.
4. Select **Create** or **Add device profile**.

UI labels vary slightly between ChirpStack v4 releases. The important values are the same even when the page layout changes.

## 3.2 Recommended profile values

Use the sensor's datasheet and firmware information for the fields marked **verify**.

| Profile field | Value for the current Dragino test | Rule |
|---|---|---|
| Name | Dragino-<exact-model>-AS923-3 | Include the exact model |
| Region | AS923-3 | Must match the gateway and sensor firmware |
| Region configuration | AS923-3 configuration, if shown | Select the exact sub-configuration |
| Activation | OTAA | Use ABP only when the device is truly ABP |
| Device class | Class A | Most battery Dragino sensors are Class A |
| MAC version | Usually LoRaWAN 1.0.3, verify | Use the vendor specification |
| Regional Parameters revision | Verify | Match the sensor firmware documentation |
| Supports 32-bit frame counter | Leave at the device default unless documented | Do not guess |
| ADR | Usually enabled for a fixed gateway installation | Disable only for a specific test reason |
| Codec | Add after model confirmation | A codec does not affect joining |

If the UI presents AS923 and a separate region-configuration selector, choose the AS923-3 configuration. If only AS923-3 is available as a region, select it directly.

## 3.3 Do not manually force RX2 values without evidence

The regional plan and device profile determine the initial RX parameters. Do not copy EU868 RX2 values from the older master guide into this profile. Do not copy a value from an AS923-1 device into an AS923-3 device.

Only override RX1/RX2 settings when the exact sensor documentation requires it and the ChirpStack version exposes the corresponding option.

## 3.4 Add the codec only when the model is confirmed

For LSN50v2-S31 and LSN50v2-S31B, follow [05-install-and-test-payload-codec.md](05-install-and-test-payload-codec.md) after creating the profile.

For another Dragino model, create the profile without the S31 codec until that model's payload specification is confirmed. A wrong codec can make correct packets appear broken.

## 3.5 Save and record the profile

After saving, record:

- profile name;
- profile ID, if displayed;
- selected region and region configuration;
- MAC version;
- Regional Parameters revision;
- activation method;
- class; and
- codec status.

The profile ID is not the device's DevEUI and is not the AppEUI. Keep those identifiers separate in your records.

## 3.6 Profile validation checklist

Before moving on, confirm:

- the profile does not say EU868;
- the profile does not say US915 or AU915;
- activation is OTAA when the sensor is OTAA;
- class is A unless the sensor documentation says otherwise;
- the MAC version was not guessed from the model name; and
- the S31 decoder is not attached to an unrelated Dragino model.

Next: [04-register-dragino-device.md](04-register-dragino-device.md)
