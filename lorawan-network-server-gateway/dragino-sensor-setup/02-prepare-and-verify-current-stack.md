# 2. Prepare and Verify the Existing Gateway and ChirpStack Stack

Do not troubleshoot the sensor until the gateway path is known to be healthy. These checks are read-only and should be performed before every new sensor enrollment.

## 2.1 Check the Docker services

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps
~~~

The ChirpStack core, Gateway Bridge, MQTT broker, PostgreSQL, and Redis services should be running or healthy according to the Compose file. If the stack is restarting, stop here and follow [08-dragino-troubleshooting.md](08-dragino-troubleshooting.md#the-gateway-or-chirpstack-is-not-healthy).

## 2.2 Check the native packet forwarder

~~~bash
sudo systemctl status ttn-gateway --no-pager -l
~~~

Healthy output should show the service as active and the packet-forwarder process underneath start.sh. The gateway log should include the RAK5146 board detection, reset completion, and concentrator startup.

~~~bash
sudo journalctl -u ttn-gateway -n 100 --no-pager
~~~

Look for:

- Detected board: Raspberry Pi 4 Model B;
- Using GPIO 17 on gpiochip0;
- Reset sequence completed;
- Starting packet forwarder;
- chip version is 0x12; and
- concentrator started, packet can now be received.

Do not consider a wrapper process alone proof that the concentrator is running. The service can be active while the packet forwarder has exited or is being restarted.

## 2.3 Confirm the packet forwarder uses the local bridge

~~~bash
cd /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd
~~~

~~~bash
sudo grep -nE 'gateway_ID|server_address|serv_port_up|serv_port_down' local_conf.json
~~~

The current installation should contain these values under gateway_conf:

~~~json
{
    "gateway_conf": {
        "gateway_ID": "2CCF67FFFE0ABEE3",
        "server_address": "127.0.0.1",
        "serv_port_up": 1700,
        "serv_port_down": 1700
    }
}
~~~

The gateway ID in ChirpStack is normally entered as lowercase hexadecimal without separators:

~~~text
2ccf67fffe0abee3
~~~

## 2.4 Check the Gateway Bridge traffic

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose logs --since=5m --tail=100 chirpstack-gateway-bridge
~~~

The current bridge should periodically publish state and statistics using the as923_3 topic prefix and gateway ID. Lines resembling these prove the UDP-to-MQTT side is active:

~~~text
publishing state ... gateway_id=2ccf67fffe0abee3 ...
publishing event ... event=stats ... topic=as923_3/gateway/2ccf67fffe0abee3/event/stats
~~~

These are gateway statistics, not sensor data. A sensor will appear only after it transmits RF frames and is registered in ChirpStack.

## 2.5 Check the gateway in the ChirpStack UI

Open:

~~~text
http://<raspberry-pi-ip>:8080
~~~

Confirm that:

1. the correct tenant is selected;
2. the gateway exists with ID 2ccf67fffe0abee3;
3. its region is AS923-3 or the equivalent AS923-3 configuration; and
4. its last-seen time and statistics are updating.

If the gateway is offline, fix that first using [10-troubleshooting.md](../10-troubleshooting.md). The Dragino setup cannot compensate for a broken gateway-to-server path.

## 2.6 Verify the bridge topic region before adding a sensor

The Gateway Bridge and ChirpStack region configuration must use the same region identifier. In this deployment the expected topic prefix is:

~~~text
as923_3
~~~

If the bridge logs show eu868, as923, or another prefix, do not proceed. Correct the deployment configuration and restart the affected service using the existing gateway guide.

Next: [03-create-chirpstack-device-profile.md](03-create-chirpstack-device-profile.md)
