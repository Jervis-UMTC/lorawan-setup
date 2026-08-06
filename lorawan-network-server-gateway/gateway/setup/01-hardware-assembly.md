# Gateway 1. Assemble the Raspberry Pi 4B and RAK5146 SPI

Run this step at the workbench with all power disconnected.

## Required parts

- Raspberry Pi 4B
- RAK5146 **SPI** concentrator in the correct regional frequency variant
- RAK2287/RAK5146 Pi HAT or the exact approved adapter
- LoRa antenna matched to the confirmed band
- u.FL/IPEX-to-SMA pigtail for the LoRa port
- optional GNSS antenna when GNSS will be commissioned
- Raspberry Pi 5.1 V / 3 A supply with a short suitable cable
- high-endurance microSD card
- standoffs, enclosure, cooling, grounding, and surge protection appropriate to the site

Treat model labels and the matching hardware datasheets as the source of truth.

## Step 1: Verify the parts

```text
Host: Raspberry Pi 4B
Concentrator: RAK5146 / SX1303
Host interface: SPI
Pi HAT: exact RAK5146-compatible revision
Frequency variant: matches the approved regional plan
Antenna band: matches module and legal channel plan
```

**Stop here. Do not continue until this condition is resolved.** Do not infer the RF variant from a product photo or from the generic label `AS923`.

## Step 2: Mount the RAK5146

1. Insert the RAK5146 into the mini-PCIe-form-factor socket at a shallow angle.
2. Press it down gently.
3. Install the retaining screws without flexing the PCB.
4. Confirm the card is fully seated and level.

The connector uses a mini-PCIe mechanical form factor. The module is not a general PCIe or mSATA device.

## Step 3: Connect RF pigtails

1. Identify the LoRa RF connector from the board label.
2. Align the u.FL connector vertically.
3. Press straight down once; do not twist while pressing.
4. Route the cable so the enclosure cannot pull on the connector.
5. Connect GNSS only to the GNSS-labelled port.

## Step 4: Mount the HAT on the Raspberry Pi

1. Align the 40-pin header correctly.
2. Press evenly until fully seated.
3. Install standoffs and screws.
4. Confirm no cable is pinched and no metal part can short the boards.

The RAK Pi HAT maps the concentrator reset signal to Raspberry Pi GPIO17 and uses SPI0 CE0 for this project. Verify the installed HAT revision before relying on these mappings.

## Step 5: Connect the antenna before any transmit test

Do not run a downlink or another test that can transmit with a missing, damaged, or wrong-band antenna.

GNSS is optional for the first bench test. System time must still be synchronized for TLS and ordinary gateway timing.

## Step 6: Check power and cooling after Gateway OS installation

On Gateway OS over SSH, first check whether Raspberry Pi utilities are present:

```bash
command -v vcgencmd || true
```

When available:

```bash
vcgencmd get_throttled
vcgencmd measure_temp
```

Healthy bench evidence includes:

```text
get_throttled=0x0
```

When `vcgencmd` is absent, inspect Gateway OS logs and available hardware-monitoring interfaces instead of installing an unreviewed package during commissioning.

Interpret any non-zero bit mask rather than assuming one cause. Test while the modem is active, Concentratord initializes the RAK5146, MQTT Forwarder is connected, and a safe downlink is transmitted.

Correct power, cable, connector, or cooling problems before changing Concentratord or RF configuration.

## Step 7: Keep the hardware values used by configuration and recovery

Retain the values below with the gateway asset entry. They are needed to select the correct Gateway OS profile, calculate RF limits, reproduce the wiring, and replace failed hardware:

```text
Raspberry Pi serial or asset ID:
Pi HAT model and revision:
RAK5146 model, SPI interface, serial, and frequency variant:
Antenna model, band, gain, and cable loss:
Source that confirms the GPIO17 reset mapping:
Source that confirms the SPI0 CE0 mapping:
Power supply and cable specification:
Enclosure, cooling, grounding, and surge arrangement:
```

Success means every RF and interface value can be traced to the installed labels or matching hardware documentation. A blank or assumed frequency variant, antenna band, or reset/SPI mapping must be resolved before the radio is enabled.
