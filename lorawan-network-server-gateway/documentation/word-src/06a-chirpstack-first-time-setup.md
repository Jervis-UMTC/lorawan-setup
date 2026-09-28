## 6.1A First-time cloud enrollment - gateway, device profile, application and sensor

Do this sequence only for a **new, authorized installation or a documented rebuild**. The commissioned Gateway-01 and EMU-01 already exist in the live cloud; do not create duplicates just to follow pictures. For a working system, open the existing entries and compare the values instead. This is the cloud step after gateway hardware, firmware, AS923/forwarding, LTE and certificates from Chapters 2-5 are ready.

**Setup sequence:** log in -> select the intended tenant -> add gateway (only if absent) -> create the correct device profile (only if absent) -> create application (only if absent) -> add the *new* sensor -> securely configure OTAA keys -> power sensor and verify an accepted `up` event.

### 6.1A.1 Add a new gateway to ChirpStack

1. In the browser open the cloud ChirpStack login shown above; verify the tenant selector is **ChirpStack**. In the left navigation under **Tenant**, open **Gateways**. Confirm the list does not already contain Gateway ID `0016c001f139a1cb` (commissioned Gateway-01).
2. If absent **and** this is the approved original Gateway-01 commissioning/rebuild, select **Add gateway**. The real form in Screen 6K shows all fields through **Submit**, not only the top of the browser. Enter **Name = Gateway-01**, **Gateway ID (EUI64) = 0016c001f139a1cb**, **Stats interval (secs) = 30** and **Downlink priority = 10** (the form's current defaults). Description/location are optional; enter a location only if confirmed. Do not generate a new gateway EUI.
3. Verify the EUI against the actual gateway's Concentratord footer and Chapter 3 readout. If both agree and no record existed, submit once and return to **Gateways -> Gateway-01**. If the record already exists, use it; never submit duplicate registration. **AS923 is established at the actual gateway and cloud region configuration**, not by selecting a region field that does not exist on the Add gateway form.
4. Observe **Last seen**, then **LoRaWAN frames** when an authorized sensor is active. Gateway stats can update even without a sensor uplink; only a fresh LoRaWAN frame proves radio reception.

[[CH6_ADD_GATEWAY_FULLPAGE]]

Screen 6.1A-1. Full Add gateway form - name, real EUI, status interval, downlink priority, location and Submit.

### 6.1A.2 Create the matching AS923 device profile

1. In the intended tenant navigation open **Device Profiles**. If **EMU-01 RAK4631 AS923** already exists, open it and compare the live configuration; do not create a second similarly named profile.
2. On a genuinely new tenant click **Add device profile**. The blank form's default **LoRaWAN 1.0.3**, revision **A**, expected interval **3600 seconds** and device-status request **1/day** are **NOT** the project's current EMU-01 values. Do not press Submit until they have been corrected against firmware.
3. For the commissioned EMU-01 Arduino firmware, set **Name = EMU-01 RAK4631 AS923**, **Region = AS923**, **Region configuration = AS923**, **MAC version = LoRaWAN 1.0.2**, **Regional parameters revision = B**, **Expected uplink interval = 15 seconds**, **Device-status request frequency = 0/day**, **RX1 Delay = 0 (use system default)**. Keep **Default ADR algorithm (LoRa only)** and **Allow roaming off**. Check that **Join (OTAA / ABP)** uses OTAA and that the device has no unsupported Class B or Class C features. Use the compiled device firmware and registered profile as your final source for any additional features or payload codec; don't copy a public tutorial's EU868 profile.
4. The saved profile on the real project screen (Screen 6M) shows the checked settings. A different firmware build or SEC-01 RUI3 board requires a **separately verified compatible profile**, not a blind clone. Submit only for an approved missing profile and confirm it appears in Device Profiles.

[[CH6_ADD_PROFILE_FULLPAGE]]

Screen 6.1A-2. Entire blank device-profile form - check every required field before creating a new profile.

[[CH6_EXISTING_PROFILE_FULLPAGE]]

Screen 6.1A-3. Existing commissioned EMU-01 AS923 profile - reference values to compare with firmware.

### 6.1A.3 Create or select the sensor application

1. Select **Applications** in the tenant sidebar. If **dissertation-sensors** is listed, click that application; do not create another application for the same sensors.
2. For a first-time deployment when absent, choose **Add application**. Enter **Name = dissertation-sensors**, **Description = Permanent Agriculture Kit LoRaWAN sensor application**. The application groups sensors; it is not the gateway or device-profile record. Only after checking duplicates should you click Submit once.
3. Open the application's **Devices** tab. Keep this application selected for all subsequent device onboarding and tests.

[[CH6_ADD_APPLICATION_FULLPAGE]]

Screen 6.1A-4. Entire Add application form - verify name and description before Submit.

### 6.1A.4 Register a new EMU-01 (or an authorized additional sensor)

1. In **Applications -> dissertation-sensors -> Devices**, first check whether DevEUI `ac1f09fffe296d29` already exists as `dissertation-emu-01`. The live project presently has this record; for routine checks, open it instead of selecting Add device.
2. When authorized to enroll a **new device**, select **Add device**. Set **Name** to the approved unique sensor name, **Device EUI (EUI64)** to the actual hardware/firmware DevEUI (the commissioned EMU-01 reference is `ac1f09fffe296d29`), **Join EUI** to the firmware's actual JoinEUI (existing EMU-01 uses `0000000000000000`), and select **EMU-01 RAK4631 AS923** only for compatible EMU firmware. Optionally enter the device description. Leave **Device is disabled** OFF and **Disable frame-counter validation** OFF. Frame-counter validation is an important anti-replay check.
3. Read every field through Submit in Screen 6.1A-5. Never click the refresh/random-EUI icon for an already programmed device and never reuse EMU-01's DevEUI or root key for SEC-01. If the profile, EUI, or JoinEUI differs from the actual firmware, stop and reconcile before submitting.
4. After submitting a genuinely new approved device, open **OTAA keys**. Supply the exact protected **AppKey** that belongs to this sensor and matches the programmed firmware. For LoRaWAN 1.0.x this is the OTAA root-key step; LoRaWAN 1.1 introduces a separate network root key. Do not invent or publish keys, regenerate independent values on only one side, paste secrets into Word, or screenshot any revealed key field. Confirm the key is saved using a masked/redacted UI only.
5. With antennas attached and the correct firmware programmed, power the authorized sensor. Observe a new JoinRequest/JoinAccept (gateway LoRaWAN frames), then a new ChirpStack **Devices -> selected sensor -> Events -> up** entry. Compare timestamp, DevEUI, frame counter and decoded payload. A saved record, gateway Last seen or Wi-Fi/LTE connectivity alone is not a successful sensor join.

[[CH6_ADD_DEVICE_FULLPAGE]]

Screen 6.1A-5. Entire Add device form - verify both EUIs, profile and frame-counter switch; never submit a duplicate to stage a screenshot.

**Do not use SEC-01 as a demonstration join:** this second security-case RAK4631 has its own RUI3 firmware and authorization boundary. The approved `test/preparation/sensor/` and RAK4631 operator firmware guide are required before any new SEC-01 onboarding.


