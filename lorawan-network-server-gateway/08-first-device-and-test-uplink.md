# 8. Your First Application and Device

With the gateway online, the last step is setting up ChirpStack's side of the LoRaWAN network — the layers that turn raw radio packets into decoded, usable data.

## The object model, briefly

ChirpStack organizes things as: **Tenant** → **Application** → **Device Profile** (defines LoRaWAN version, class, OTAA/ABP, and so on — reusable across many devices of the same type) → **Device** (one physical thing, with its own identity/keys).

## Step 1: Create an application

**Applications → Add application.** Name it after whatever this device (or group of devices) is for — e.g. "Soil Sensors" or "Test Bench."

## Step 2: Create a device profile

**Device profiles → Add device profile.**

Key fields:
- **Region**: AS923-3 (or your actual region) — must match the gateway's region
- **MAC version**: match what your end device actually implements — check its datasheet. LoRaWAN 1.0.3 is common for many off-the-shelf sensors
- **Join type**: OTAA (over-the-air activation) is strongly preferred over ABP for anything beyond a quick bench test — it's more secure and handles session renewal automatically
- **Device class**: Class A unless your device specifically needs B or C

## Step 3: Add the device

**Applications → (your application) → Add device.**

You'll need, from your physical end device (printed on it, in its manual, or in its manufacturer's app):
- **DevEUI** — the device's unique identifier
- **AppKey** — for OTAA join (LoRaWAN 1.0.x) or the appropriate key set for 1.1 if applicable

Don't have a physical LoRaWAN end device yet? A couple of options:
- Many LoRaWAN dev boards (Heltec, RAK's own WisBlock line, Seeed, etc.) ship with example OTAA join firmware you can flash and test with immediately.
- ChirpStack has a device simulator project if you want to verify the server side works before any RF hardware is involved — search "ChirpStack simulator" in their docs if you want to go that route first.

## Step 4: Power on the device and watch it join

Back in the ChirpStack UI, open the device's page and go to its **LoRaWAN Frames** (or **Events**, depending on UI version) tab — this shows live traffic.

For an OTAA device, you're watching for:
1. A **JoinRequest** uplink frame arriving
2. A **JoinAccept** downlink being sent back
3. Regular data uplinks afterward

If the join request shows up but no JoinAccept goes out, or the device never re-joins successfully, check:
- **AppKey** typos — this is the single most common cause
- Gateway downlink capability — confirm the gateway's antenna and RF path are solid (a device can often *reach* a gateway on uplink from farther/weaker conditions than the gateway can reliably reach it back on downlink)

## Step 5: You're running

Once you're seeing decoded uplinks in the device's frame log, the full chain — end device → RF → RAK5146 → packet forwarder → Gateway Bridge → ChirpStack core → application — is working end to end.

From here, ChirpStack's **Integrations** (on the application) let you forward decoded payloads to MQTT, HTTP webhooks, InfluxDB, and others if you want to pipe this data somewhere for storage or dashboards — that's outside the scope of this gateway-focused guide, but it's the natural next step.

---
Next: [09-autostart-persistence-hardening.md](09-autostart-persistence-hardening.md)
