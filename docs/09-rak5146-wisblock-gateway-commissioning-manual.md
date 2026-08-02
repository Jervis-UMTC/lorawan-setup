# RAK5146 + WisBlock AS923 Gateway Commissioning Manual

This is the arrival-to-working-system manual for the hardware listed in [hardware-checklist.pdf](../hardware-checklist.pdf).

It covers the incoming custom gateway and WisBlock field-node hardware:

~~~text
WisBlock node
  RAK4631 + RAK19007 or RAK19001 + one sensor + LoRa antenna
        |
        | AS923 LoRaWAN radio, 900-928 MHz
        v
RAK5146 gateway
  RAK5146 SPI concentrator + WisLink Pi HAT + Raspberry Pi 4
        |
        | Semtech UDP packet forwarder, UDP 1700
        v
Private ChirpStack v4
  Gateway Bridge -> MQTT -> ChirpStack -> PostgreSQL / Grafana / Node-RED
~~~

This is a separate hardware path from the existing Milesight UG65/UG67 and Dragino LSN50v2-S31 path described in documents 01-05. Do not substitute one architecture for the other without deliberately changing the gateway, region, packet-forwarder, device profile, and payload decoder.

## 0. Non-negotiable rules

1. The purchased radio variant must be RAK5146 SPI for the AS923 900-928 MHz band. Do not accept EU868, US915, USB-only, or unverified hardware as an equivalent replacement.
2. Never power the gateway until the LoRa and GPS antenna paths are connected. RAK warns that powering the gateway without antennas can damage the radio hardware.
3. The RAK5146 is a concentrator, not a complete gateway. It requires the WisLink Pi HAT, Raspberry Pi 4, software image, packet-forwarder, network, antennas, and power.
4. Use a dedicated private test application and synthetic keys. Do not reuse the existing Dragino DevEUI, AppKey, or production credentials.
5. Do not mix AS923 and EU868 settings. The current repository Gateway Bridge templates are EU868-oriented and require an explicit AS923 decision before this gateway is connected.
6. Commission one gateway and one node on a bench before installing anything outdoors.
7. Do not connect batteries, solar, actuators, or multiple sensors during the first bring-up.

If any rule is not satisfied, stop and resolve it before continuing.

## 1. What the PDF specifies

### 1.1 Gateway materials

| Item | Expected specification | Acceptance check |
|---|---|---|
| Gateway computer | Raspberry Pi 4 Model B | Confirm Pi 4; do not substitute Pi 3 or Pi Zero. |
| LoRa concentrator | RAK5146, SPI, 900-928 MHz / AS923 | Read the board label and order confirmation. |
| Interface board | WisLink Pi HAT / RAK5146 Pi HAT | Must have the mini-PCIe socket and Pi 40-pin interface. |
| LoRa antenna | Outdoor antenna for approximately 900-930 MHz | Must be a LoRa antenna, not GPS or cellular. |
| GPS antenna | Active GPS antenna | Connect only to the GPS path. |
| RF adapters | Two u.FL/IPEX-to-SMA-family pigtails | One LoRa path and one GPS path; do not force connectors. |
| Power | Official or known-good 5 V / 3 A USB-C supply | Do not use a weak phone charger. |
| Storage | 32 GB or 64 GB high-endurance microSD and reader | Keep the image and checksum record. |
| Backhaul | Cat5e or Cat6 Ethernet | Use wired Ethernet first. |
| Mechanical parts | Enclosure, brass standoffs, screws, weatherproof mounting | Leave the cover off until bench tests pass. |

### 1.2 WisBlock materials

| Item | Expected part | First-test guidance |
|---|---|---|
| Core | RAK4631 WisBlock Core | Requires a compatible WisBlock base. |
| Base | RAK19007 or RAK19001 | RAK19007 is the standard base; RAK19001 is expanded. |
| Antenna | Matching 900 MHz LoRa antenna | Connect before radio testing. |
| Programming | USB-C data cable | Use for power, programming, and serial logs. |
| Sensor | One compatible sensor module | Use the module's current official example and library. |
| Battery | 3.7-4.2 V rechargeable Li-Ion/LiPo | Optional; leave disconnected initially. |
| Solar | 5 V solar panel only | Optional; never connect 12 V to the base-board solar input. |
| Cellular | RAK5860 or RAK13101 | Not needed for the first LoRaWAN path; select None for cellular. |

The PDF lists soil, environmental, UV, ambient-light, rain, RS485, 4-20 mA, and SDI-12 modules. These are application choices, not gateway prerequisites. Start with one sensor.

### 1.3 Important corrections

- The gateway forwards encrypted LoRaWAN frames. ChirpStack verifies and decrypts them only when the correct device configuration and keys are present.
- The PDF's 5-15 km range is a planning estimate, not a test guarantee.
- GPS is useful for timing, location, and advanced features, but a GPS fix is not required to prove basic packet forwarding.
- The PDF's example sensor slot letters are illustrative. Use the actual base-board silkscreen and the module's current guide.
- The existing Dragino JavaScript decoder is not automatically correct for a RAK4631 payload.

## 2. Relation to the existing Markdown manuals

| Document | Use here |
|---|---|
| [01: Master Deployment Guide](./01-master-deployment-guide.md) | Existing Ubuntu VM, Docker, ChirpStack v4, MQTT, PostgreSQL, Redis, and server operations. Its Milesight gateway section is not the RAK assembly procedure. |
| [02: Offline Direct-AP Setup Guide](./02-offline-direct-ap-setup-guide.md) | Milesight UG65 direct-AP networking. Do not use Gateway_F94C0B or 192.168.23.150 for this Pi unless the network team explicitly creates that topology. |
| [03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md) | Persist RAK events after the first accepted uplink. |
| [04: Grafana Integration Guide](./04-grafana-integration-guide.md) | Visualize RAK telemetry after it is stored. |
| [05: Node-RED Integration Guide](./05-node-red-integration-guide.md) | Add automation only after a human-reviewed event is visible. |
| [06: Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md) | RF, protocol, evidence, and security-tool boundaries. |
| [07: RF and Protocol Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md) | Optional SDR/IQ/PHY bench. Not required for normal gateway commissioning. |
| [08: Security Testing Runbook](./08-lorawan-security-testing-runbook.md) | Use only after normal gateway and node operation passes. |

The first successful path is:

~~~text
RAK5146 gateway online
  -> one RAK4631 node joins over OTAA
  -> one uplink appears in ChirpStack
  -> raw payload is recorded
  -> a WisBlock-specific decoder is added later
  -> PostgreSQL/Grafana/Node-RED are enabled last
~~~

## 3. Freeze the plan before opening the box

| Field | Value to record |
|---|---|
| Country and regulatory region | <COUNTRY_AND_REGION> |
| LoRa region | AS923 and the approved local sub-band |
| ChirpStack server IP or DNS | <CHIRPSTACK_SERVER_IP> |
| RAK gateway IP or DHCP reservation | <RAK_GATEWAY_IP> |
| Gateway Bridge UDP port | 1700 |
| ChirpStack URL | http://<CHIRPSTACK_SERVER_IP>:8080 |
| MQTT topic prefix | as923 |
| Gateway EUI | <16_HEX_CHAR_GATEWAY_EUI> |
| Node DevEUI | <16_HEX_CHAR_NODE_DEVEUI> |
| Node JoinEUI/AppEUI | <16_HEX_CHAR_JOIN_EUI> |
| Node AppKey | <32_HEX_CHAR_SYNTHETIC_APPKEY> |
| LoRaWAN version | 1.0.3 for the first RAK example path |
| Activation | OTAA |
| Class | Class A |

### 3.1 Resolve the AS923 versus EU868 conflict

The repository currently has:

- AS923 enabled in the ChirpStack region list.
- EU868 topic templates in the Gateway Bridge TOML.
- EU868 topic-template environment variables in Docker Compose.

For an AS923 commissioning stack, the effective Gateway Bridge values must be:

~~~toml
event_topic_template = "as923/gateway/{{ .GatewayID }}/event/{{ .EventType }}"
command_topic_template = "as923/gateway/{{ .GatewayID }}/command/{{ .CommandType }}"
~~~

If Docker environment variables override the file, they must also use AS923:

~~~yaml
environment:
  - INTEGRATION__MQTT__EVENT_TOPIC_TEMPLATE=as923/gateway/{{ .GatewayID }}/event/{{ .EventType }}
  - INTEGRATION__MQTT__COMMAND_TOPIC_TEMPLATE=as923/gateway/{{ .GatewayID }}/command/{{ .CommandType }}
~~~

Choose one mode:

| Mode | Rule |
|---|---|
| Private AS923 test stack | Use AS923 in the Gateway Bridge, restart it, and test only the RAK path. |
| Shared EU868 and AS923 service | Use a separate Gateway Bridge route or instance; do not repoint the only EU868 route. |
| Temporary migration | Back up the current files, change both templates, test, then restore or formally document the new region. |

Do not connect the Pi until the mode is approved.

### 3.2 Server preflight

Run on the Ubuntu VM hosting the private stack:

~~~bash
docker compose ps
sudo ss -ulnp | grep ':1700'
curl -I http://127.0.0.1:8080
docker compose logs -f chirpstack-gateway-bridge
~~~

Expected:

- Gateway Bridge is running.
- UDP port 1700 is listening.
- The web service answers on port 8080.
- Active MQTT topic templates use AS923 for the RAK path.

If a firewall is enabled, allow only the approved gateway source:

~~~bash
sudo ufw status verbose
sudo ufw allow from <RAK_GATEWAY_SUBNET_OR_IP> to any port 1700 proto udp
~~~

Do not expose UDP 1700 to the public Internet.

### 3.3 Prepare the workstation

Have these ready:

- Current RAK5146 image from the official RAK page.
- microSD reader and balenaEtcher or an approved image writer.
- Ethernet cable and laptop USB Ethernet adapter if needed.
- USB-C data cable for the WisBlock node.
- Screwdriver set, ESD protection, labels, notebook, and camera.
- Arduino IDE and current RAKwireless Arduino BSP.
- Serial terminal or Arduino Serial Monitor.
- Private ChirpStack administrator account.
- Approved password manager and secret storage.

## 4. Arrival-day acceptance

Do this before connecting power.

1. Photograph the shipment, labels, board markings, connectors, and serial numbers.
2. Label the equipment: GW-RAK-01, NODE-RAK-01, and so on.
3. Record the RAK5146 variant, frequency, interface, Gateway EUI if printed, and Raspberry Pi model.
4. Confirm the pigtails, LoRa antenna, GPS antenna, power supply, microSD, HAT, and enclosure are present.
5. Confirm the WisBlock core, base, antenna, USB-C cable, and at least one sensor are present.
6. Keep every original label and QR code.
7. Do not write keys or passwords on the hardware.

Stop and escalate if:

- RAK5146 is EU868, EU433, USB-only, or not marked clearly.
- The Pi HAT is not RAK5146-compatible.
- The LoRa antenna is not a 900 MHz antenna.
- The pigtails do not match the board and enclosure connectors.
- The power supply is not a stable 5 V / 3 A supply.
- The delivered core is RAK4631-R but the planned firmware is only for RAK4631, or vice versa.
- Any PCB, connector, or antenna is damaged.

Inventory record:

| Item | Expected | Actual | Serial / EUI | Pass |
|---|---|---|---|---|
| Raspberry Pi | Pi 4 Model B |  |  |  |
| Concentrator | RAK5146 SPI, AS923 |  |  |  |
| Pi HAT | RAK5146/WisLink compatible |  |  |  |
| LoRa antenna | 900-930 MHz |  |  |  |
| GPS antenna | Active GPS |  |  |  |
| Pigtails | Two u.FL/IPEX to SMA-family |  |  |  |
| Power | 5 V / 3 A USB-C |  |  |  |
| microSD | 32 or 64 GB high endurance |  |  |  |
| RAK core | RAK4631 or RAK4631-R |  | DevEUI:  |  |
| WisBlock base | RAK19007 or RAK19001 |  |  |  |
| Sensor | One selected module |  |  |  |
| Node antenna | Matching 900 MHz |  |  |  |

## 5. Assemble the gateway with no power

Work on a clean, dry, static-safe bench. Keep the Pi supply unplugged.

### 5.1 Mount the concentrator

1. Place the Pi HAT with the mini-PCIe socket visible.
2. Identify the RAK5146 keyed edge and HAT orientation.
3. Insert the RAK5146 into the mini-PCIe socket at approximately 45 degrees.
4. Press it down gently until the screw holes align.
5. Secure it with the supplied screws without flexing the PCB.
6. If it does not seat easily, stop and re-check orientation.

### 5.2 Mount the HAT on the Pi

1. Fit the correct standoffs.
2. Align the HAT's 40-pin connector with the Pi 4 GPIO header.
3. Press straight down evenly.
4. Secure the HAT and Pi.
5. Check that no screw or spacer can touch exposed solder.
6. Leave the cover off for first boot.

### 5.3 Connect the pigtails

| Path | Board connector | External connector | Destination |
|---|---|---|---|
| LoRa | RAK5146 LoRa IPEX/u.FL | LoRa SMA-family bulkhead | 900-930 MHz LoRa antenna |
| GPS | RAK5146 GPS IPEX/u.FL | GPS SMA bulkhead | Active GPS antenna |

1. Align each tiny connector vertically.
2. Press straight down until it clicks.
3. Do not twist or bend the cable at the connector.
4. Label the external ends LORA and GPS.
5. Verify bulkhead washers and nuts are secure.

### 5.4 Attach antennas before power

1. Attach the 900-930 MHz LoRa antenna to the LoRa connector.
2. Attach the active GPS antenna to the GPS connector.
3. Hand-tighten the connectors; do not use pliers.
4. Keep the LoRa antenna vertical and away from metal during testing.
5. Connect Ethernet.
6. Insert the flashed microSD.
7. Only now connect the 5 V / 3 A USB-C supply.

Never test a powered gateway with its LoRa antenna disconnected. Disconnect power before removing any RF cable.

## 6. Flash and first-boot the gateway

### 6.1 Flash the RAK image

Use the current image linked from the official [RAK5146 Quick Start Guide](https://docs.rakwireless.com/product-categories/wislink/rak5146/quickstart/).

1. Insert the microSD into the workstation.
2. Verify the selected drive by capacity twice.
3. Flash the vendor image.
4. Safely eject the card.
5. Verify the checksum if RAK publishes one.
6. Record image filename, version, date, and checksum.

Do not flash the Ubuntu server image or a generic Pi image unless the RAK documentation explicitly confirms RAK5146 SPI support.

### 6.2 First access by isolated Ethernet

RAK documents these stock-image defaults, which may differ in a newer image:

- Ethernet address: 192.168.10.10
- Wi-Fi AP address: 192.168.230.1
- AP name: RAKwireless_XXXX
- AP password: rakwireless
- SSH user/password: pi / raspberry

Use the isolated Ethernet method first:

1. Disconnect the laptop from other wired networks.
2. Connect the laptop directly to the Pi Ethernet port.
3. Temporarily set the laptop to 192.168.10.20/24 with no default gateway.
4. Test reachability:

~~~powershell
ping 192.168.10.10
~~~

5. Connect:

~~~powershell
ssh pi@192.168.10.10
~~~

6. On this isolated cable only, use the stock default password if required.
7. Change it immediately:

~~~bash
sudo passwd pi
~~~

8. Save the new password in the approved password manager, never in Git or Markdown.

If Ethernet fails, use the isolated RAK Wi-Fi AP fallback. If the image does not present the documented defaults, stop guessing and check the release-specific image notes, SD card, link LEDs, and Pi model.

### 6.3 Record identity and software

~~~bash
hostname
uname -a
ip -br address
sudo gateway-version
~~~

Record:

- Gateway EUI.
- RAK image or Gateway OS version.
- Raspberry Pi model.
- RAK5146 variant and serial.
- Ethernet MAC and IP.
- First-boot date and time.

The Gateway EUI entered in ChirpStack must be exactly the EUI reported by the running gateway software.

### 6.4 Configure the packet-forwarder

Run the RAK menu if available:

~~~bash
sudo gateway-config
~~~

Configure:

1. Pi password.
2. RAK Gateway LoRa concentrator.
3. AS923 regional plan.
4. ChirpStack as the network server.
5. Server address: <CHIRPSTACK_SERVER_IP>.
6. Uplink port: 1700.
7. Downlink port: 1700.
8. Save.
9. Restart the packet-forwarder.

If the menu lacks the required fields, locate the active files:

~~~bash
sudo find /etc /opt -type f \( -name 'global_conf.json' -o -name 'local_conf.json' \) 2>/dev/null
~~~

The effective Semtech UDP values must be equivalent to:

~~~json
{
  "gateway_conf": {
    "server_address": "<CHIRPSTACK_SERVER_IP>",
    "serv_port_up": 1700,
    "serv_port_down": 1700
  }
}
~~~

Preserve all other vendor fields. If both global and local configuration files exist, verify which values win.

### 6.5 Join the real network

Use wired Ethernet and a DHCP reservation first.

1. Reserve the Pi's MAC address as <RAK_GATEWAY_IP>.
2. Connect it to the approved switch or router.
3. Restore the laptop's normal network settings.
4. Restart the Pi network or reboot.
5. From the Pi:

~~~bash
ip -br address
ip route
ping -c 4 <CHIRPSTACK_SERVER_IP>
~~~

6. From the server:

~~~bash
ping -c 4 <RAK_GATEWAY_IP>
~~~

Do not use the Milesight direct-AP values 192.168.23.150 and 192.168.23.137 unless the network design explicitly assigns them to the RAK path.

## 7. Connect the gateway to ChirpStack

### 7.1 Validate the regional route

On the Ubuntu VM:

~~~bash
docker compose restart chirpstack-gateway-bridge
docker compose ps
docker compose logs --tail=100 chirpstack-gateway-bridge
~~~

Check:

- UDP 1700 is listening.
- MQTT topic templates use AS923, not EU868.
- Gateway Bridge connects to MQTT.
- Existing EU868 traffic is not being rerouted.

If the server is shared, stop and use the approved separate multi-region Bridge design.

### 7.2 Add the gateway

1. Open http://<CHIRPSTACK_SERVER_IP>:8080.
2. Sign in to the private tenant.
3. Open Gateways and choose Add gateway.
4. Name it RAK-AS923-GW-01.
5. Enter the exact Gateway EUI from gateway-version.
6. Select or record AS923 if the UI exposes a region field.
7. Save.

### 7.3 Verify statistics and UDP

On the server:

~~~bash
sudo tcpdump -ni any host <RAK_GATEWAY_IP> and udp port 1700
~~~

In another terminal:

~~~bash
docker compose logs -f chirpstack-gateway-bridge
~~~

On the Pi, discover the service name:

~~~bash
systemctl list-units --type=service | grep -Ei 'packet|lora|gateway|forward'
ps aux | grep -Ei 'packet_forwarder|gateway|lora' | grep -v grep
~~~

Expected:

- Periodic gateway statistics leave the Pi.
- The server sees UDP 1700.
- The Bridge acknowledges the packet-forwarder.
- ChirpStack shows a recent Last seen value.

Interpret failures by layer:

- No UDP: Pi network, server address, firewall, or packet-forwarder.
- UDP but no Bridge event: Bridge backend, firewall, or MQTT route.
- Bridge event but unknown gateway: wrong EUI or tenant.
- Online gateway but no node frames: node RF or firmware.

## 8. Assemble the first WisBlock node

Start indoors with USB power only.

### 8.1 Golden first node

~~~text
RAK4631
  + RAK19007 or RAK19001
  + one sensor with a matching official example
  + one AS923 LoRa antenna
  + USB-C data cable
~~~

If RAK1906 is included, it is a reasonable first environmental-sensor candidate if the current example supports the exact revision. Otherwise prove the core LoRaWAN example before adding a sensor.

### 8.2 Assembly

1. Disconnect USB, battery, and solar power.
2. Install RAK4631 in the base board CPU/Core slot.
3. Press evenly and install the retaining screw.
4. Install one sensor into a compatible sensor slot identified by the base-board silkscreen.
5. Install the sensor retaining screw.
6. Connect the node's 900 MHz LoRa antenna.
7. Confirm no cable is trapped under a board or screw.
8. Connect only the USB-C data/power cable.

A WisBlock core requires a base. A sensor module must use a compatible slot and current library.

### 8.3 Battery and solar safety

Leave both disconnected for the first test.

Later:

- Use only a 3.7-4.2 V rechargeable Li-Ion/LiPo battery.
- Use only a 5 V solar panel on the RAK19007 solar input.
- Confirm polarity.
- Do not connect a non-rechargeable battery and USB together.
- Never connect 12 V to the solar input.
- Protect the battery from moisture, crushing, and overheating.

## 9. Program the node for AS923 OTAA

### 9.1 Tools and board identity

Use the official [RAK4631 Quick Start Guide](https://docs.rakwireless.com/product-categories/wisblock/rak4631/quickstart/).

1. Install the official Arduino IDE.
2. Install the current RAKwireless Arduino BSP.
3. Connect the node over USB-C.
4. Identify the COM port.
5. Confirm the board marking: RAK4631 or RAK4631-R.
6. Select the matching board definition.
7. Use the current RAK LoRaWAN OTAA example or the current WisBlock example matching the installed sensor libraries.

A power-only USB-C cable will not program the node.

### 9.2 Firmware values

Replace every public example identity and key:

| Setting | First-test value |
|---|---|
| Region | RAK_REGION_AS923 or the current BSP equivalent |
| Activation | OTAA |
| Class | Class A |
| LoRaWAN version | Match the profile; use 1.0.3 for the first RAK example path |
| Device EUI | Exact board DevEUI in the byte order required by the example |
| JoinEUI/AppEUI | Exact value registered in ChirpStack |
| AppKey | Newly generated synthetic 128-bit key |
| Uplink interval | About 60 seconds for bench observation |
| Payload | Documented test payload; not automatically Dragino-compatible |

RAK documents MSB order for the EUI in its example path. Do not reverse bytes unless the selected sketch explicitly requires it.

### 9.3 Upload and serial checks

1. Compile before upload.
2. Select the exact board and COM port.
3. Upload.
4. If upload fails, press reset twice or follow the exact board bootloader procedure.
5. Open Serial Monitor at the example's baud rate. Many RAK examples use 115200.
6. Record the firmware, libraries, board selection, port, and upload result.

Expected state transitions:

~~~text
Region: AS923
Type: OTAA
LoRaWAN initialization succeeded
Join request sent
Join accepted
Uplink sent
~~~

The wording may differ. The required states are AS923, OTAA, join request, join accept, and uplink.

## 10. Add the node to ChirpStack

### 10.1 Create a separate application

1. Create an application named wisblock-as923-lab.
2. Do not place it in the existing Dragino application unless approved.
3. Leave the decoder empty for the first raw-payload test.

### 10.2 Create a matching device profile

Match the firmware:

- Region: AS923 and the approved local regional-parameters revision.
- MAC version: 1.0.3 for the first RAK example path unless firmware differs.
- Activation: OTAA.
- Class: A.
- Join-server behavior: match the private ChirpStack deployment.
- Uplink interval and payload: record in the device note.

### 10.3 Create the device and key

1. Create device wisblock-as923-01.
2. Enter the exact DevEUI.
3. Enter the exact JoinEUI/AppEUI.
4. Generate an AppKey in ChirpStack.
5. Copy it once into protected firmware configuration.
6. Save the device.
7. Remove the key from terminal history and screenshots.

A one-character identity or key mismatch produces a failed join that can look like RF failure.

## 11. End-to-end acceptance gates

Do not install outdoors until every gate passes.

### Gate 1: Power and RF

- [ ] Gateway LoRa antenna connected.
- [ ] Gateway GPS antenna connected.
- [ ] Node LoRa antenna connected.
- [ ] No active RF path is open.
- [ ] Pi uses 5 V / 3 A.
- [ ] Node uses USB only.

### Gate 2: Gateway configuration

- [ ] RAK5146 variant recorded as SPI and AS923.
- [ ] Gateway image version recorded.
- [ ] Gateway EUI recorded.
- [ ] Packet-forwarder region is AS923.
- [ ] Server address is reachable from the Pi.
- [ ] Uplink and downlink are UDP 1700.
- [ ] Firewall allows the approved source.
- [ ] Gateway Bridge MQTT route is AS923.

### Gate 3: Gateway online

- [ ] Gateway exists in the correct tenant.
- [ ] Last seen is recent.
- [ ] Statistics are visible.
- [ ] UDP or Bridge activity is logged.
- [ ] No EU868 service was disrupted.

### Gate 4: Node firmware

- [ ] Correct RAK4631 or RAK4631-R board selected.
- [ ] Region AS923.
- [ ] OTAA.
- [ ] Class A.
- [ ] Synthetic DevEUI, JoinEUI/AppEUI, and AppKey recorded securely.
- [ ] Serial log shows the intended region and activation.
- [ ] Node antenna connected.

### Gate 5: Join and uplink

- [ ] Gateway frames show JoinRequest.
- [ ] Device frames show JoinRequest.
- [ ] JoinAccept is sent.
- [ ] Node reports joined.
- [ ] First uplink appears.
- [ ] Raw payload is saved.
- [ ] Dragino decoder was not assumed compatible.

### Gate 6: Downstream services

Only after Gate 5:

- [ ] MQTT event visible.
- [ ] PostgreSQL event visible through [document 03](./03-postgres-integration-guide.md).
- [ ] Dedicated WisBlock dashboard added through [document 04](./04-grafana-integration-guide.md).
- [ ] Node-RED automation reviewed and disabled by default.
- [ ] Actuators and irrigation rules remain disabled.

## 12. Troubleshooting matrix

| Symptom | Likely layer | Checks |
|---|---|---|
| Pi will not boot | Power, SD, Pi | Antenna connected, 5 V / 3 A supply, correct image, card seating, Pi 4 model, LEDs. |
| RAK5146 not detected | HAT or card | Power off, reseat at 45 degrees, inspect HAT connector, confirm SPI variant and vendor image. |
| No Gateway EUI | Image or service | Run sudo gateway-version; inspect the service; do not invent an EUI. |
| No Ethernet address | Network | Cable, link LEDs, DHCP reservation, ip -br address, switch port. |
| Pi cannot ping server | Network/firewall | Server IP, route, firewall, and bridged VM address. |
| No UDP 1700 | Packet-forwarder | Server address, both ports, service, region, tcpdump. |
| UDP but gateway offline | Identity/Bridge | Gateway EUI, tenant, Bridge backend, MQTT prefix. |
| Gateway online but no JoinRequest | Node/RF | Node antenna, AS923, node power, serial log, node transmission. |
| JoinRequest but no JoinAccept | Keys/profile | DevEUI, JoinEUI, AppKey, MAC version, region, tenant. |
| JoinAccept but node never joins | Downlink/timing | UDP downlink, antenna path, receive-window settings. |
| Uplink accepted but no decoded data | Payload | Save raw bytes, confirm FPort, write WisBlock decoder. |
| Sensor example does not compile | Board/library | Exact core, module revision, BSP, matching example and libraries. |
| Node resets during transmit | Power | Return to USB, new data cable, battery/solar disconnected, supply path. |
| GPS never fixes | GPS path | Correct pigtail, active antenna, sky view, time. Basic forwarding can be tested first. |

## 13. Outdoor installation gate

Do not install outdoors until the indoor acceptance gates pass.

Before mounting:

- Use a weatherproof enclosure and cable glands.
- Add drip loops and strain relief.
- Keep the LoRa antenna vertical and clear of nearby metal.
- Use qualified grounding, surge, and lightning protection for the antenna mast.
- Keep the Pi and supply dry and within their environmental limits.
- Give GPS a suitable sky view if timing/location is required.
- Use approved mains or solar/battery power; never improvise 12 V into a 5 V input.
- Record antenna height, cable length, enclosure location, gateway IP, and node locations.
- Repeat the gateway-online and node-join checks after installation.

Use one node at a known distance for the first field test. Do not deploy every node until that test passes.

## 14. Rollback and safe shutdown

1. Stop the node firmware or disconnect node USB power.
2. Disconnect Pi power only after the LoRa antenna remains connected until power is off.
3. Never remove an RF cable from a powered gateway.
4. Stop the packet-forwarder before changing its configuration.
5. Restore the last known-good Gateway Bridge configuration if a shared service was changed.
6. Disable or remove the test device from ChirpStack.
7. Preserve logs, Gateway EUI, DevEUI, configuration versions, and UTC timestamps.
8. Destroy synthetic keys according to project policy after the report is complete.

## 15. Commissioning record

~~~text
Commissioning ID:
Date / time UTC:
Operator:
Country / regulatory region:
RAK image filename and checksum:
Raspberry Pi model / serial:
RAK5146 variant / serial:
RAK5146 interface: SPI / USB:
RAK5146 band:
Gateway EUI:
Gateway IP / DHCP reservation:
Packet-forwarder type:
Packet-forwarder version:
ChirpStack server IP:
Gateway Bridge UDP port:
MQTT topic prefix:
WisBlock core: RAK4631 / RAK4631-R:
WisBlock base: RAK19007 / RAK19001:
Sensor module and revision:
Node DevEUI:
Node JoinEUI/AppEUI:
LoRaWAN MAC version:
Activation / class:
Firmware repository and commit:
Arduino BSP / library versions:
First JoinRequest UTC:
JoinAccept UTC:
First accepted uplink UTC:
First raw payload:
Decoder status:
PostgreSQL/Grafana/Node-RED status:
Known limitations:
Operator sign-off:
~~~

## 16. Source references

- [RAK5146 product overview](https://docs.rakwireless.com/product-categories/wislink/rak5146/overview/)
- [RAK5146 Raspberry Pi quick-start guide](https://docs.rakwireless.com/product-categories/wislink/rak5146/quickstart/)
- [RAK RPi DIY Gateway Kit installation guide](https://docs.rakwireless.com/product-categories/accessories/rak-rpi-diy-gateway-kit/installation-guide/)
- [RAK4631 WisBlock quick-start guide](https://docs.rakwireless.com/product-categories/wisblock/rak4631/quickstart/)
- [RAK19007 WisBlock base-board guide](https://docs.rakwireless.com/product-categories/wisblock/rak19007/quickstart/)
- [WisBlock Agriculture Kit datasheet](https://docs.rakwireless.com/product-categories/wisblock/kit7-agriculture/datasheet/)
- [ChirpStack: connecting a gateway](https://www.chirpstack.io/docs/guides/connect-gateway.html)
- [ChirpStack: gateway configuration](https://www.chirpstack.io/docs/gateway-configuration/index.html)
- [ChirpStack: Raspberry Pi Gateway Bridge installation](https://www.chirpstack.io/docs/gateway-bridge/install/raspberry-pi.html)
- [ChirpStack: connecting a device](https://www.chirpstack.io/docs/guides/connect-device.html)

