# Tools 1. Prepare the Test Laptop and Measurement Utilities

Prepare these tools once before the counted experiments. They are test utilities, not new production technologies.

## 1. Test laptop

Use a separate Linux laptop on the isolated lab network.

Install only the required utilities:

```bash
sudo apt update
sudo apt install -y mosquitto-clients python3
mkdir -p "$HOME/lorawan-test-tools"
cd "$HOME/lorawan-test-tools"
```

Confirm:

```bash
mosquitto_pub --help >/dev/null
python3 --version
```

## 2. Create the MQTT invalid-connection generator

Create `connection_flood.py`:

```python
#!/usr/bin/env python3
import argparse
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument('--host', required=True)
ap.add_argument('--port', required=True, type=int)
ap.add_argument('--rate', required=True, type=float)
ap.add_argument('--seconds', required=True, type=float)
ap.add_argument('--user', required=True)
ap.add_argument('--password', required=True)
args = ap.parse_args()

if args.rate <= 0 or args.seconds <= 0:
    raise SystemExit('rate and seconds must be positive')

interval = 1.0 / args.rate
end_at = time.monotonic() + args.seconds
next_at = time.monotonic()
launched = 0
active = []
max_active = 200

while time.monotonic() < end_at:
    now = time.monotonic()
    if now < next_at:
        time.sleep(next_at - now)

    active = [p for p in active if p.poll() is None]
    if len(active) >= max_active:
        time.sleep(0.01)
        continue

    marker = f'connection-flood-{launched}'
    p = subprocess.Popen(
        [
            'mosquitto_pub',
            '-h', args.host,
            '-p', str(args.port),
            '-u', args.user,
            '-P', args.password,
            '-t', 'test/flood/connection-probe',
            '-m', marker,
            '-q', '0'
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    active.append(p)
    launched += 1
    next_at += interval

for p in active:
    try:
        p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        p.kill()

print(f'launched_attempts={launched}')
```

Make it executable:

```bash
chmod 750 connection_flood.py
```

This script creates new MQTT client processes at the requested rate. Use an intentionally wrong password only against the temporary test listener from [Execution 07 - DoS / Flooding](../../execution/07-dos-flooding.md).

Pilot examples:

```bash
./connection_flood.py \
  --host <LAB_SERVER_IP> --port 1885 \
  --rate 10 --seconds 10 \
  --user flood_publisher --password '<INTENTIONALLY_WRONG_PASSWORD>'
```

```bash
./connection_flood.py \
  --host <LAB_SERVER_IP> --port 1885 \
  --rate 50 --seconds 10 \
  --user flood_publisher --password '<INTENTIONALLY_WRONG_PASSWORD>'
```

The final five-minute runs use `--seconds 300`.

If `launched_attempts` is far below the target or the laptop itself saturates, the pilot is invalid. Fix the generator/test laptop before changing the server workload.

## 3. Create the invalid-message generator

Create `invalid_message_stream.py`:

```python
#!/usr/bin/env python3
import argparse
import json
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument('--rate', required=True, type=float)
ap.add_argument('--seconds', required=True, type=float)
args = ap.parse_args()

if args.rate <= 0 or args.seconds <= 0:
    raise SystemExit('rate and seconds must be positive')

fixtures = [
    {'missing': 'device identity'},
    {'dev_eui': 'not-a-valid-eui', 'value': 35},
    {'dev_eui': '0000000000000001', 'time': 'not-a-time', 'value': 35},
    {'dev_eui': '0000000000000001', 'time': '2000-01-01T00:00:00Z', 'value': 'wrong-type'}
]

interval = 1.0 / args.rate
end_at = time.monotonic() + args.seconds
next_at = time.monotonic()
sent = 0

while time.monotonic() < end_at:
    now = time.monotonic()
    if now < next_at:
        time.sleep(next_at - now)

    fixture = dict(fixtures[sent % len(fixtures)])
    fixture['test_sequence'] = sent
    print(json.dumps(fixture, separators=(',', ':')), flush=True)
    sent += 1
    next_at += interval

print(f'generated_messages={sent}', file=sys.stderr)
```

Make it executable:

```bash
chmod 750 invalid_message_stream.py
```

Pilot at 10 messages/s:

```bash
./invalid_message_stream.py --rate 10 --seconds 10 \
  2>pilot-message-count.txt \
  | mosquitto_pub -h <LAB_SERVER_IP> -p 1885 \
      -u flood_publisher -P '<FLOOD_PUBLISHER_PASSWORD>' \
      -t 'test/flood/invalid' -q 0 -l

cat pilot-message-count.txt
```

Pilot at 50 messages/s by changing `--rate 50`.

The final five-minute runs use `--seconds 300`.

## 4. Prepare the RAK4631 security test node

The Agriculture Kit's second RAK4631 is first used to verify every second-copy sensor and then becomes the project's security node (`SEC-02`). Configure it using [Sensor 01 - Configure the RAK4631 Physical Sensor Node and Security Node](../sensor/01-configure-rak4631-emulators.md).

The replay/spoofing experiment requires SEC-02 to transmit a **specified raw LoRaWAN PHYPayload** with the captured/approved AS923 radio parameters. Before the counted replay/spoofing test, prove all of the following:

```text
SEC-02 hardware identity and pinned RUI3 version are recorded
SEC-02 can switch between LoRaWAN and LoRa P2P modes
raw PHYPayload hex can be supplied unchanged
frequency can be matched to the captured uplink
spreading factor / data rate can be matched
bandwidth and coding rate can be matched
required sync-word/IQ settings can be matched
transmit power stays within the approved test limit
RAK5146 can be proven to receive a SEC-02 raw transmission
```

RUI3 provides P2P raw transmission through `AT+PSEND=<hex>` / `api.lora.psend(...)` on current firmware. Do not count the experiment merely because SEC-02 reports TX success; the RAK5146 gateway log must prove reception.

SEC-02 must not contain EMU-01's legitimate AppKey or legitimate LoRaWAN session keys for the invalid-MIC spoofing test.

## 5. Prepare Raspberry Pi resource logging

Chapter III asks for Raspberry Pi CPU and memory measurements. The current architecture also needs server-VM/container measurements. Collect both separately.

On the gateway create `/tmp/resource-log.sh`:

```sh
#!/bin/sh
OUT="${1:-/tmp/gateway-resource.csv}"
printf 'timestamp,cpu_percent,memory_used_kib,memory_total_kib,memory_percent\n' > "$OUT"

read_cpu() {
    set -- $(head -n 1 /proc/stat)
    user=$2; nice=$3; system=$4; idle=$5; iowait=$6; irq=$7; softirq=$8; steal=$9
    total=$((user + nice + system + idle + iowait + irq + softirq + steal))
    idle_all=$((idle + iowait))
}

read_cpu
prev_total=$total
prev_idle=$idle_all

while true; do
    sleep 5
    read_cpu
    delta_total=$((total - prev_total))
    delta_idle=$((idle_all - prev_idle))

    cpu_pct="$(awk -v t="$delta_total" -v i="$delta_idle" 'BEGIN { if (t <= 0) print "0.00"; else printf "%.2f", 100 * (t-i) / t }')"
    mem_total="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
    mem_avail="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
    [ -n "$mem_avail" ] || mem_avail="$(awk '/^MemFree:/ {print $2}' /proc/meminfo)"
    mem_used=$((mem_total - mem_avail))
    mem_pct="$(awk -v u="$mem_used" -v t="$mem_total" 'BEGIN { if (t <= 0) print "0.00"; else printf "%.2f", 100*u/t }')"

    printf '%s,%s,%s,%s,%s\n' "$(date -Iseconds)" "$cpu_pct" "$mem_used" "$mem_total" "$mem_pct" >> "$OUT"

    prev_total=$total
    prev_idle=$idle_all
 done
```

Make it executable:

```sh
chmod 700 /tmp/resource-log.sh
```

Before a measured run:

```sh
/tmp/resource-log.sh /tmp/<RUN_ID>-gateway-resource.csv &
echo $! > /tmp/gateway-resource.pid
```

After the run:

```sh
kill "$(cat /tmp/gateway-resource.pid)"
rm -f /tmp/gateway-resource.pid
```

Copy the CSV to the matching server result directory with `scp` over the management LAN.

The script uses `/proc/stat` and `/proc/meminfo`, so it does not require another monitoring package on the gateway.

## 6. Test-tool acceptance

Before counted tests confirm:

```text
[ ] mosquitto_pub works from the test laptop
[ ] connection generator hits the pilot rate
[ ] invalid-message generator hits the pilot rate
[ ] temporary test listener is reachable only from the test laptop
[ ] RAK4631 SEC-02 passes the Sensor Preparation invalid-OTAA and raw-RF acceptance checks
[ ] gateway resource CSV advances every 5 seconds
[ ] server resource CSV advances every 5 seconds
```

If a tool cannot create or observe the intended condition, fix the tool before counting experiments.
