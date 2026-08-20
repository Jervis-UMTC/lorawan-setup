# Gateway 1. Assemble the Raspberry Pi 4B and RAK5146 SPI

This procedure installs the RAK5146 SPI concentrator on its Raspberry Pi HAT and mounts the HAT on a Raspberry Pi 4B.

Keep every power source disconnected until the antenna and all boards are installed.

## What you need

- Raspberry Pi 4B
- RAK5146 **SPI** concentrator
- compatible RAK Pi HAT for the RAK5146
- mounting screws and standoffs supplied with the HAT
- LoRa antenna matched to the concentrator frequency band
- u.FL-to-SMA pigtail when the HAT or enclosure uses an external SMA connector
- stable Raspberry Pi USB-C power supply
- microSD card for ChirpStack Gateway OS Base

The RAK5146 uses an mPCIe-shaped connector, but the module in this manual communicates through SPI. Do not install it in a laptop or normal PCIe slot.

## Step 1: Check the module and antenna labels

Read the labels before assembling anything.

Confirm:

```text
Raspberry Pi model: Raspberry Pi 4B
Concentrator model: RAK5146-115 (Onboard GPS, Non-LBT)
Concentrator interface: SPI
Concentrator frequency band: 915 MHz High-Frequency (902–928 MHz)
Target region: Philippines (AS923 / AS923-1, 920–925 MHz)
Antenna frequency band: 900–930 MHz (Matches concentrator & AS923 spectrum)
```

The software channel plan can only use frequencies supported by the installed radio module and antenna. Stop here when the module label, interface, or antenna band is uncertain.

## Step 2: Fit the RAK5146 into the Pi HAT

1. Place the Pi HAT on a clean, non-conductive surface.
2. Hold the RAK5146 by its edges.
3. Align the module edge connector with the HAT socket.
4. Insert the module at a shallow angle until the connector is fully seated.
5. Press the free end of the module down onto the mounting posts.
6. Install the retaining screws and tighten them only until the module is secure.

The module should sit flat and parallel with the HAT. Remove and reseat it when the gold contacts remain visibly exposed or one side is higher than the other.

## Step 3: Connect the LoRa pigtail

The small u.FL connector is easy to damage. Press it straight down; do not slide or twist it into place.

1. Find the RAK5146 connector labelled for the LoRa RF path.
2. Hold the pigtail connector directly above it.
3. Check that both connectors are centered.
4. Press straight down until the connector snaps into place.
5. Route the cable without sharp bends, pinching, or tension.
6. Secure the external SMA end to the enclosure or HAT bracket when one is used.

Do not connect the LoRa pigtail to a GNSS connector. Use the board labels rather than the connector position alone.

## Step 4: Mount the HAT on the Raspberry Pi

1. Install the Raspberry Pi standoffs in the mounting holes.
2. Check the 40-pin Raspberry Pi header for bent pins.
3. Align the HAT socket with all 40 pins. Verify that it is not shifted by one row or one column.
4. Press evenly above the header until the HAT is fully seated.
5. Fasten the HAT to the standoffs.
6. Check the underside of the HAT for contact with the Raspberry Pi USB, Ethernet, or display connector shells.

Do not force the HAT onto a misaligned header. A shifted connector can place supply voltage on the wrong signal pins.

## Step 5: Attach the LoRa antenna

1. Confirm again that the antenna band matches the RAK5146 frequency variant.
2. Screw the antenna or antenna feed cable onto the LoRa SMA connector.
3. Tighten it by hand until secure.
4. Position the antenna vertically for normal bench testing.

Always attach a suitable antenna before powering the gateway or enabling the concentrator transmitter. Transmitting into an open RF connector can damage the radio front end.

## Step 6: Perform the final visual check

Before inserting the microSD card or connecting power, verify:

- the RAK5146 is the SPI model;
- the module is fully seated and secured;
- the u.FL connector is centered and snapped into place;
- the pigtail is not trapped under a board or screw;
- the HAT uses all 40 header pins without an offset;
- the HAT is supported by standoffs;
- no loose screw or metal part is under either board;
- the LoRa antenna is connected to the correct SMA port.

## Common assembly problems

### The RAK5146 will not lie flat

Remove the screws, lift the module, and insert the edge connector farther into the socket. Do not pull the module flat with the screws.

### The u.FL connector will not snap into place

Lift it away and realign it. Pressing harder while it is off-center can damage both connectors.

### The HAT does not align with the mounting holes

Check that the 40-pin header is not shifted. Also confirm that the standoff height matches the supplied HAT hardware.

### The Raspberry Pi power LED is unstable after power is connected

Disconnect power immediately. Inspect for a shifted HAT, a loose metal object, or an unsuitable power supply before trying again.

## Next step

Leave the antenna attached and continue with [02-install-chirpstack-gateway-os.md](02-install-chirpstack-gateway-os.md).
