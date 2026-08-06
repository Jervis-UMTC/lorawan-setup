# 1. Hardware & Assembly

## Parts list

| Part | Notes |
|---|---|
| Raspberry Pi 4B | 2 GB RAM is workable; 4 GB or 8 GB is more comfortable once ChirpStack's containers are running alongside the packet forwarder |
| RAK5146 concentrator module | SX1303-based mini-PCIe LPWAN concentrator card. Confirm the **SPI** variant (not USB) — this guide is written around the SPI/Pi HAT setup |
| RAK2287/RAK5146 Pi HAT | The carrier board that the RAK5146 module plugs into, and which itself plugs onto the Pi's 40-pin GPIO header. Some kits ship the module already mounted on the HAT — check yours before assuming you need to seat it |
| Antenna, correct band | Must match your regional frequency plan (≈915–928 MHz hardware for AS923-3/Philippines). An antenna cut for 868 MHz (EU) will work poorly or not at all outside its band |
| GPS antenna (optional) | The RAK5146 kit typically includes an onboard ZOE-M8Q GPS chip, used for precise time sync and Class B support. Skip if you don't need Class B |
| microSD card, 16 GB+ | A reputable brand matters more than raw size here — packet-forwarder logs and Docker both do a fair amount of small writes |
| USB-C power supply, **3 A** | RAK's own documentation specifies at least 3 A for a Pi 4 running the concentrator — a phone charger rated for less will cause brownouts under load |
| Ethernet cable | Strongly recommended over Wi-Fi for this build — see [02](02-flash-raspberry-pi-os.md) for why |
| Case with GPIO clearance | Standard Pi cases often don't leave room for a HAT — check compatibility, or go heatsink-only/open-frame |

## Assembly steps

1. **If the RAK5146 module isn't already mounted**, seat it into its mPCIe-style slot on the Pi HAT and secure it per the HAT's screw/standoff points. Handle both boards by the edges — the module and HAT carry static-sensitive RF components.
2. **Attach the antenna to the HAT/module before you ever power it on.** Powering an LPWAN concentrator with no antenna (or load) connected risks reflecting RF energy back into the power amplifier and damaging it. This is the single most common way to kill a concentrator module during first setup — attach the antenna first, every time, no exceptions.
3. If your kit includes GPS, connect the GPS antenna to its dedicated u.FL/SMA connector (separate from the LoRa antenna connector — don't mix them up).
4. Align the Pi HAT's 40-pin socket with the Raspberry Pi's GPIO header and press down evenly until fully seated. Both boards have a 40-pin connector; it only fits one way.
5. Insert the microSD card (you'll flash it in the next step — do that on your main computer first, then bring the card here) into the slot on the underside of the Pi.
6. Mount everything in your case, leaving the antenna connector(s) accessible.
7. **Don't connect power yet.** The next step is flashing the OS on a separate computer.

## A note on antennas and legality

LoRaWAN gateways transmit on regulated ISM bands, and the specific sub-band and power limits vary by country. Using the wrong frequency plan isn't just a technical mismatch (your devices simply won't join) — it can also put you outside what your local telecom regulator permits. Confirm your region's plan before going further; this guide flags where that setting gets applied (concentrator side and ChirpStack side both need to agree).

---
Next: [02-flash-raspberry-pi-os.md](02-flash-raspberry-pi-os.md)
