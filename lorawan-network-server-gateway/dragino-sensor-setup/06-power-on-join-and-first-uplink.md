# 6. Power On the Sensor, Join the Network, and Capture the First Uplink

Follow the exact power-on, reset, and button procedure for the Dragino model. The sequence differs between models, battery arrangements, and firmware versions.

## 6.1 Physical preparation

Before powering the sensor:

- install or charge the battery as specified by Dragino;
- connect the sensor probe or external input required by the model;
- place the gateway antenna correctly and keep it connected;
- keep the sensor within a reasonable first-test range of the gateway;
- avoid placing the sensor inside a metal cabinet during the first join; and
- confirm the device is configured for AS923-3.

Do not press random reset or function buttons repeatedly. Record what you do so a second attempt can be compared with the first.

## 6.2 Prepare the observation windows

Open the device page in ChirpStack and keep the event/frame view visible.

On the gateway, open a packet-forwarder log:

~~~bash
sudo journalctl -u ttn-gateway -f
~~~

In a second SSH session, open the Gateway Bridge log:

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose logs -f chirpstack-gateway-bridge
~~~

If you want to observe ChirpStack core events too:

~~~bash
docker compose logs -f chirpstack
~~~

Use one observation command at a time in its own terminal. Stop a live log with Ctrl+C; this does not stop the service.

## 6.3 Start the OTAA join

Power on or reset the sensor using its model-specific procedure. For many battery devices, the first join and first uplink are not immediate.

For the Dragino LSN50v2-S31/S31B, the vendor documentation describes OTAA Class A operation and a default periodic uplink interval around 20 minutes. Treat that interval as a default, not a guarantee: firmware settings and button actions can change it.

The expected flow is:

~~~text
Sensor sends JoinRequest
  -> gateway receives RF packet
  -> packet forwarder sends it to Gateway Bridge
  -> ChirpStack validates DevEUI / JoinEUI / AppKey
  -> ChirpStack schedules JoinAccept
  -> gateway transmits downlink in the sensor's receive window
  -> sensor becomes active and sends an uplink
~~~

## 6.4 Interpret the first result

| Observation | Meaning | Next action |
|---|---|---|
| Nothing appears anywhere | Sensor did not transmit or RF plan is wrong | Check battery, reset procedure, band, antenna, distance |
| JoinRequest appears, no JoinAccept | ChirpStack rejected or could not answer the join | Check DevEUI, JoinEUI, AppKey, profile, region, downlink path |
| JoinAccept appears, no data uplink | Sensor did not receive the downlink or is waiting for its schedule | Check downlink, RX parameters, battery, and model timing |
| Uplink appears and is decrypted | LoRaWAN network path works | Add or correct the codec |
| Uplink is decoded | End-to-end setup is working | Complete the acceptance test |

## 6.5 Do not confuse gateway statistics with sensor data

Gateway Bridge lines such as event=stats prove only that the gateway is reporting status. They do not prove that the Dragino sensor joined or transmitted.

Sensor confirmation requires a device-specific event in ChirpStack containing the sensor's DevEUI and an uplink or join event.

## 6.6 Allow for the sensor's reporting interval

If the sensor is configured to report every 20 minutes, do not declare it broken after watching for 30 seconds. Use the vendor's documented reset/join procedure to obtain a timely test uplink when supported, or wait for the next scheduled report.

Do not repeatedly power-cycle a battery sensor without reason. Frequent joins consume battery and can make frame-counter and session behavior harder to interpret.

Next: [07-acceptance-test-and-operations.md](07-acceptance-test-and-operations.md)
