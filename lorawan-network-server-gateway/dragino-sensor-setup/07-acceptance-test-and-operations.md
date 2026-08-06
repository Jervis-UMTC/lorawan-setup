# 7. Acceptance Test and Normal Operations

Use this checklist to decide whether the Dragino sensor is genuinely working rather than merely visible in one log.

## 7.1 End-to-end acceptance test

| Test | Pass condition | Evidence to retain |
|---|---|---|
| Gateway health | Gateway is online and last-seen updates | ChirpStack gateway page |
| Concentrator health | Packet forwarder reports concentrator started | journalctl output |
| Bridge health | Gateway Bridge publishes stats using as923_3 | Gateway Bridge log |
| Device identity | DevEUI matches the physical sensor | Device record and label comparison |
| OTAA join | JoinRequest and JoinAccept are visible | ChirpStack device events |
| First uplink | Device sends an uplink after activation | Device event/frame view |
| Decryption | Frame is accepted without MIC/key error | ChirpStack event details |
| Codec | Measurements are plausible | Decoded JSON |
| Persistence | A later scheduled uplink arrives | Second event with increasing counter |
| Application path | MQTT/webhook/integration receives the event, if configured | Integration log or subscriber |

## 7.2 Check the important values

For an S31/S31B normal uplink, verify:

- battery voltage is plausible;
- temperature is plausible for the environment;
- humidity is between 0 and 100 percent unless the sensor documentation says otherwise;
- timestamp behavior is understood;
- the reported node type matches the physical sensor; and
- the frame counter increases between uplinks.

Do not reject a measurement solely because the local clock or sensor timestamp is initially wrong. First check the sensor's time-setting procedure and firmware behavior.

## 7.3 Class A downlink behavior

Most battery Dragino sensors are Class A. A downlink is normally received only after an uplink, during the device's receive windows.

Operational rules:

- queue a downlink before the next expected uplink;
- do not expect immediate downlink delivery after clicking send;
- avoid repeated retries while the sensor is asleep; and
- verify the sensor's downlink port and command format from its model manual.

Never send a command intended for a different Dragino model. A valid LoRaWAN downlink can still cause an unintended application action if the payload is wrong.

## 7.4 MQTT application integration

Gateway topics prove gateway health. Device uplinks are normally published under an application/device topic. The application ID is a ChirpStack application identifier; it is not the sensor's AppEUI/JoinEUI.

If the MQTT command-line client is available in the Mosquitto container, a topic pattern can be inspected with:

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose exec mosquitto mosquitto_sub -h localhost -t 'application/+/device/+/event/up' -v
~~~

Treat received data fields according to the integration format. Confirm whether the message contains decoded JSON, base64 data, or both before building application logic.

## 7.5 Multiple Dragino sensors

For each additional identical sensor:

1. reuse the proven device profile;
2. create a new device record;
3. enter that physical sensor's unique DevEUI and keys;
4. assign the correct application; and
5. verify one join and one decoded uplink before deploying it.

Do not duplicate a device record and leave the original DevEUI or AppKey in place.

## 7.6 Field installation checklist

Before moving a sensor away from the gateway:

- complete the acceptance test indoors or on a bench;
- record the exact installation location;
- record the antenna orientation and enclosure;
- record the battery type and installation date;
- confirm the first uplink after final placement;
- record the expected reporting interval; and
- retain only non-secret credentials metadata in the repository.

Next: [08-dragino-troubleshooting.md](08-dragino-troubleshooting.md)
