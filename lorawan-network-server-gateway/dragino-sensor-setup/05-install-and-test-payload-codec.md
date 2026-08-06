# 5. Install and Test the Dragino Payload Codec

LoRaWAN encryption and application decoding are separate stages:

~~~text
RF packet -> gateway receives packet -> ChirpStack validates/decrypts packet -> codec decodes bytes -> JSON measurements
~~~

A sensor can successfully join while its application payload is still undecoded. Diagnose those stages separately.

## 5.1 S31/S31B codec scope

The repository contains a decoder for these exact models:

- Dragino LSN50v2-S31;
- Dragino LSN50v2-S31B.

The canonical decoder is here:

[dragino-lsn50v2-s31-decoder.js](../../docs/codecs/dragino-lsn50v2-s31-decoder.js)

Do not attach this decoder to an LHT65, LDS02, LHT52, LT-22222, or another Dragino model merely because both devices use LoRaWAN. The payload layout is model-specific.

## 5.2 Configure the S31/S31B decoder in ChirpStack

1. Open **Device profiles**.
2. Open the exact S31/S31B profile.
3. Open the **Codec** or **Payload codec** section.
4. Choose **JavaScript**.
5. Open the canonical decoder file listed above on your workstation.
6. Copy the complete file, including the decodeUplink function and helper functions.
7. Paste it into the ChirpStack codec editor.
8. Save the profile.

The file uses the ChirpStack v4 decodeUplink(input) interface and calls the Dragino decoder for the supplied fPort and byte array.

## 5.3 S31/S31B payload map

The local decoder supports the following ports:

| FPort | Meaning in the local decoder | Typical output |
|---:|---|---|
| 2 | Normal sensor uplink | Battery voltage, temperature, humidity, time, door/trigger status |
| 3 | Historical/datalog payload | Temperature, humidity, and timestamp entries |
| 5 | Device status | Firmware version, frequency band, sub-band, transmission interval |

For a normal S31/S31B payload, the decoder expects an 11-byte payload. It identifies the normal mode and returns fields such as BatV, TempC_SHT31, Hum_SHT31, and Data_time.

## 5.4 Verify the regional status

If the sensor sends a status packet on FPort 5, the decoder maps the AS923-3 band code to:

~~~text
FREQUENCY_BAND: AS923_3
~~~

If the status reports EU868, AS923_1, AS923_2, or another value, stop. The sensor is not configured for the same regional plan as this gateway, even if a radio packet was received.

## 5.5 Test a real uplink in the UI

Do not invent a payload for the first test. Wait for a real frame from the sensor.

1. Open the device in ChirpStack.
2. Open **LoRaWAN frames**, **Events**, or the device event view.
3. Locate an uplink with the expected fPort.
4. Confirm that the raw payload is present.
5. Confirm that the decoded JSON contains sensible values.

Interpretation:

- no frame: RF, region, activation, or gateway-path problem;
- frame with decryption/MIC error: identity or key/profile problem;
- decrypted frame with no decoded fields: codec configuration or codec syntax problem;
- decoded fields with impossible values: wrong model, wrong payload revision, or sensor hardware problem.

## 5.6 Codec security and maintenance

Treat a codec as application code. Keep a dated copy of the exact version used, record the model and firmware it was tested against, and retest after changing the codec or firmware.

Next: [06-power-on-join-and-first-uplink.md](06-power-on-join-and-first-uplink.md)
