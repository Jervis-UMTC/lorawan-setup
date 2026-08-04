# Troubleshooting Manual 05: Offline Gateway Backhaul & Buffer Overflow

## 1. Executive Problem Summary

* **Symptom**: Cellular/Wi-Fi backhaul drops at remote field sites; the Milesight UG65 gateway loses connection to the ChirpStack Network Server; sensor telemetry collected during internet outages is lost or discarded upon reconnection.
* **Impact**: Critical farm telemetry recorded during severe weather storms is permanently lost; historical time-series graphs display large blank gaps.
* **Primary Root Cause**: **Gateway Packet Forwarder Buffer Overflow** and misconfigured Gateway Bridge offline queuing during network outages.

---

## 2. Root Cause Analysis & Architecture

In remote farm deployments, gateways rely on cellular 4G SIMs or Wi-Fi point-to-point links. When an outage occurs:
1. **Semtech UDP Packet Forwarder Default Behavior**: By default, the Semtech UDP packet forwarder attempts to send UDP packets to port 1700. If the IP endpoint is unreachable, UDP packets are silently dropped—UDP has no built-in retransmission mechanism.
2. **Buffer Limits**: If the gateway lacks a persistent local packet queue, incoming RF packets received during the outage overflow the small RAM buffer within minutes.
3. **Routing Failures**: In offline Direct AP Mode (`192.168.23.0/24`), if static Netplan routes fail on the Ubuntu VM, UDP 1700 traffic is routed to a non-existent WAN default gateway (`192.168.23.1`).

---

## 3. Diagnostic & Inspection Commands

### Step 1: Verify Gateway Packet Forwarder Status & Log Errors
Log into the Milesight UG65 gateway via SSH or Web UI (`192.168.23.150`):
~~~bash
ssh admin@192.168.23.150
cat /var/log/messages | grep -i -E "packet-forwarder|push_data|ack"
~~~
*Expected Error*: `PUSH_DATA ack not received`, `sendto error: Network is unreachable`.

### Step 2: Test Semtech UDP Port 1700 Reachability
From the gateway shell, verify UDP socket connectivity to the Ubuntu VM (`192.168.23.137`):
~~~bash
nc -z -v -u 192.168.23.137 1700
~~~

### Step 3: Check Netplan Routing Table on Ubuntu VM Host
~~~bash
ip route show
ping -c 3 192.168.23.150
~~~

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Enable Local Flash Memory Queuing on Gateway
Configure the Milesight UG65 Gateway Packet Forwarder to queue packets to internal flash storage during backhaul disconnects:

1. Log into Milesight Gateway Web UI (`http://192.168.23.150`).
2. Navigate to **LoRaWAN** $\rightarrow$ **Packet Forwarder** $\rightarrow$ **General**.
3. Enable **Enable Packet Buffer / Offline Buffer**.
4. Set parameters:
   * **Buffer Size**: `100 MB` (stores up to ~500,000 sensor uplinks).
   * **Resend Interval**: `5 seconds` (upon backhaul restoration).
5. Click **Save & Apply**.

### Action 2: Configure Offline Direct AP Static Routing (Doc 02 Baseline)
Ensure the Ubuntu VM maintains static routing over the gateway Wi-Fi AP (`Gateway_F94C0B`):

1. Edit `/etc/netplan/01-netcfg.yaml` on the Ubuntu VM:
   ~~~yaml
   network:
     version: 2
     ethernets:
       eth0:
         dhcp4: no
         addresses:
           - 192.168.23.137/24
         routes:
           - to: default
             via: 192.168.23.150
         nameservers:
           addresses: [8.8.8.8, 1.1.1.1]
   ~~~
2. Apply netplan configuration:
   ~~~bash
   sudo netplan apply
   ~~~

### Action 3: Enable ChirpStack Gateway Bridge Local MQTT Buffer
If running `chirpstack-gateway-bridge` directly on the gateway or edge Pi, configure MQTT offline storage in `chirpstack-gateway-bridge.toml`:
~~~toml
[integration.mqtt]
event_topic_template="eu868/gateway/{{ .GatewayID }}/event/{{ .EventType }}"
command_topic_template="eu868/gateway/{{ .GatewayID }}/command/{{ .CommandType }}"
clean_session=false
qos=1
max_reconnect_interval="1m0s"
~~~

---

## 5. Verification & Acceptance Criteria

1. **Outage Simulation Test**: Disconnect the gateway WAN cable for 30 minutes while sensors uplink.
2. **Buffer Flush Verification**: Upon reconnecting WAN, the gateway flushes stored historical packets; ChirpStack receives all buffered uplinks without sequence loss.
3. **Database Integrity**: PostgreSQL `event_up` table contains complete continuous time-series data without timestamp gaps.
