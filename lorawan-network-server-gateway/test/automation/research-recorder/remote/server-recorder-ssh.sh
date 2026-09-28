#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
export LANG=C
export LANGUAGE=C

# Forced-command collector for the dedicated research-recorder SSH key.
# It deliberately exposes only read/capture operations needed by the dissertation recorder.

cmd=${SSH_ORIGINAL_COMMAND:-"$*"}
set -- $cmd
verb=${1:-}
shift || true

fail() { printf 'research-recorder: %s\n' "$*" >&2; exit 64; }
valid_iso() { printf '%s' "$1" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z$'; }
valid_eui() { printf '%s' "$1" | grep -Eq '^[0-9A-Fa-f]{16}$'; }
valid_key_hex() { printf '%s' "$1" | grep -Eq '^[0-9A-Fa-f]{32}$'; }
valid_interval() { printf '%s' "$1" | grep -Eq '^[1-9][0-9]*$' && [ "$1" -le 60 ]; }
valid_count() { printf '%s' "$1" | grep -Eq '^[1-9][0-9]*$' && [ "$1" -le 20 ]; }
valid_flood_rate() { [ "$1" = 10 ] || [ "$1" = 50 ]; }
valid_flood_seconds() { printf '%s' "$1" | grep -Eq '^[1-9][0-9]*$' && [ "$1" -le 300 ]; }

case "$verb" in
  version)
    [ "$#" -eq 0 ] || fail 'version takes no arguments'
    printf '%s\n' 'research-recorder-server-v10'
    ;;

  utc-now)
    [ "$#" -eq 0 ] || fail 'utc-now takes no arguments'
    date -u +%Y-%m-%dT%H:%M:%S.%3NZ
    ;;

  clock-probe)
    [ "$#" -eq 1 ] || fail 'clock-probe requires sample count'
    count=$1
    valid_count "$count" || fail 'invalid clock-probe sample count'
    printf '%s\n' '#CLOCK_PROBE_V1'
    i=0
    while [ "$i" -lt "$count" ]; do
      IFS= read -r request || fail 'clock-probe input ended early'
      request=$(printf '%s' "$request" | tr -d '\r')
      [ "$request" = probe ] || fail 'invalid clock-probe request'
      date -u +%Y-%m-%dT%H:%M:%S.%3NZ
      i=$((i + 1))
    done
    ;;

  evidence-ready)
    [ "$#" -eq 0 ] || fail 'evidence-ready takes no arguments'
    host=$(hostname)
    check_ready() {
      label=$1
      url=$2
      code=$(curl --silent --show-error --output /tmp/research-recorder-ready.$$ --write-out '%{http_code}' --connect-timeout 3 --max-time 5 "$url" 2>/dev/null || true)
      if [ "$code" != '200' ]; then
        body=$(tr '\r\n' '  ' </tmp/research-recorder-ready.$$ 2>/dev/null | head -c 300 || true)
        rm -f /tmp/research-recorder-ready.$$
        printf 'NOT_READY|%s|http=%s|%s\n' "$label" "${code:-000}" "$body" >&2
        return 1
      fi
      rm -f /tmp/research-recorder-ready.$$
      printf 'READY|%s|http=200\n' "$label"
    }
    case "$host" in
      ulc-01)
        check_ready collector-1 http://127.0.0.1:19101/readyz
        ;;
      ulc-02)
        check_ready verifier-1 http://127.0.0.1:19202/readyz
        ;;
      ulc-03)
        check_ready collector-2 http://127.0.0.1:19103/readyz
        check_ready verifier-2 http://127.0.0.1:19203/readyz
        ;;
      *) fail "unsupported evidence host: $host" ;;
    esac
    ;;

  flood-listener)
    [ "$#" -eq 1 ] || fail 'flood-listener requires start, status, smoke, or stop'
    [ "$(hostname)" = ulc-01 ] || fail 'flood-listener is allowed only on ulc-01'
    action=$1
    helper=/usr/local/sbin/lorawan-research-mqtt-test-listener
    [ -x "$helper" ] || fail 'flood listener helper is not installed'
    case "$action" in
      start)
        exec sudo -n "$helper" start flood 127.0.0.1 1885
        ;;
      status|smoke|stop)
        exec sudo -n "$helper" "$action" flood
        ;;
      *) fail 'unsupported flood-listener action' ;;
    esac
    ;;

  flood-branch)
    [ "$#" -eq 1 ] || fail 'flood-branch requires install, status, or remove'
    [ "$(hostname)" = ulc-03 ] || fail 'flood-branch is allowed only on ulc-03'
    action=$1
    helper=/home/opsadmin/.local/bin/lorawan-research-node-red-flood-branch
    [ -x "$helper" ] || fail 'flood branch helper is not installed'
    case "$action" in
      install|status|remove) exec "$helper" "$action" ;;
      *) fail 'unsupported flood-branch action' ;;
    esac
    ;;

  flood-db-guard)
    [ "$#" -eq 0 ] || fail 'flood-db-guard takes no arguments'
    [ "$(hostname)" = ulc-01 ] || fail 'flood-db-guard is allowed only on ulc-01'
    sql="SELECT 'FAKE_UPLINKS_TOTAL|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='0000000000000001';
SELECT 'FAKE_OUTBOX_TOTAL|' || count(*)::text FROM telemetry.fabric_outbox o JOIN telemetry.uplinks u ON u.event_key=o.source_event_key AND u.time=o.observed_at WHERE u.dev_eui='0000000000000001';
SELECT 'EMU_LAST_2M|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='ac1f09fffe296d29' AND time >= now() - interval '2 minutes';"
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -c "$sql"
    ;;

  flood-window)
    [ "$#" -eq 2 ] || fail 'flood-window requires startUTC endUTC'
    [ "$(hostname)" = ulc-01 ] || fail 'flood-window is allowed only on ulc-01'
    start=$1; end=$2
    valid_iso "$start" || fail 'invalid flood-window start timestamp'
    valid_iso "$end" || fail 'invalid flood-window end timestamp'
    sql="SELECT 'VALID_DELIVERED|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='ac1f09fffe296d29' AND time >= '${start}'::timestamptz AND time < '${end}'::timestamptz;
SELECT 'MEAN_LATENCY_MS|' || COALESCE(round(avg(extract(epoch FROM (received_at-time))*1000)::numeric,3)::text,'') FROM telemetry.uplinks WHERE dev_eui='ac1f09fffe296d29' AND time >= '${start}'::timestamptz AND time < '${end}'::timestamptz;
SELECT 'UNAUTHORIZED_UPLINKS|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='0000000000000001' AND received_at >= '${start}'::timestamptz AND received_at < '${end}'::timestamptz;
SELECT 'UNAUTHORIZED_OUTBOX|' || count(*)::text FROM telemetry.fabric_outbox o JOIN telemetry.uplinks u ON u.event_key=o.source_event_key AND u.time=o.observed_at WHERE u.dev_eui='0000000000000001' AND o.created_at >= '${start}'::timestamptz AND o.created_at < '${end}'::timestamptz;"
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -c "$sql"
    ;;

  snapshot)
    [ "$#" -eq 0 ] || fail 'snapshot takes no arguments'
    printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'hostname=%s\n' "$(hostname)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'uptime_seconds=%s\n' "$(cut -d. -f1 /proc/uptime)"
    printf '%s\n' '--- memory ---'
    free -b
    printf '%s\n' '--- load ---'
    cat /proc/loadavg
    printf '%s\n' '--- docker ---'
    docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}'
    printf '%s\n' '--- listeners ---'
    ss -lnt
    ;;

  db-role)
    [ "$#" -eq 0 ] || fail 'db-role takes no arguments'
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d postgres \
      -c "select case when pg_is_in_recovery() then 'replica' else 'leader' end"
    ;;

  a1-lorawan-guard)
    [ "$#" -eq 3 ] || fail 'a1-lorawan-guard requires legitimate DevEUI, unregistered DevEUI, and test wrong AppKey'
    [ "$(hostname)" = ulc-01 ] || fail 'a1-lorawan-guard is allowed only on ulc-01'
    legit=$1; unregistered=$2; wrong_key=$3
    valid_eui "$legit" || fail 'invalid legitimate DevEUI'
    valid_eui "$unregistered" || fail 'invalid unregistered DevEUI'
    valid_key_hex "$wrong_key" || fail 'invalid wrong AppKey fixture'
    [ "$(printf '%s' "$legit" | tr 'A-F' 'a-f')" != "$(printf '%s' "$unregistered" | tr 'A-F' 'a-f')" ] || fail 'test DevEUI must differ from legitimate DevEUI'
    sql="SELECT 'LEGIT_REGISTERED|' || count(*)::text FROM public.device WHERE dev_eui=decode(lower('${legit}'),'hex');
SELECT 'UNREGISTERED_COUNT|' || count(*)::text FROM public.device WHERE dev_eui=decode(lower('${unregistered}'),'hex');
SELECT 'WRONG_KEY_COLLISION|' || count(*)::text FROM public.device_keys WHERE dev_eui=decode(lower('${legit}'),'hex') AND (nwk_key=decode(lower('${wrong_key}'),'hex') OR app_key=decode(lower('${wrong_key}'),'hex'));"
    result=$(docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d chirpstack -c "$sql") || fail 'ChirpStack identity guard query failed'
    printf '%s\n' "$result"
    legit_count=$(printf '%s\n' "$result" | awk -F'|' '$1=="LEGIT_REGISTERED"{print $2}')
    unreg_count=$(printf '%s\n' "$result" | awk -F'|' '$1=="UNREGISTERED_COUNT"{print $2}')
    collision=$(printf '%s\n' "$result" | awk -F'|' '$1=="WRONG_KEY_COLLISION"{print $2}')
    [ "$legit_count" = 1 ] || fail 'legitimate DevEUI registration guard failed'
    [ "$unreg_count" = 0 ] || fail 'unregistered DevEUI is already registered'
    [ "$collision" = 0 ] || fail 'wrong AppKey fixture collides with a legitimate stored key'
    printf '%s\n' 'A1_LORAWAN_GUARD=PASS'
    ;;

  a1-lorawan-state)
    [ "$#" -eq 1 ] || fail 'a1-lorawan-state requires DevEUI'
    [ "$(hostname)" = ulc-01 ] || fail 'a1-lorawan-state is allowed only on ulc-01'
    dev=$1
    valid_eui "$dev" || fail 'invalid DevEUI'
    sql="SELECT 'REGISTERED|' || count(*)::text FROM public.device WHERE dev_eui=decode(lower('${dev}'),'hex');
SELECT 'STATE|' || encode(dev_eui,'hex') || '|' || COALESCE(to_char(last_seen_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'),'') || '|' || COALESCE(encode(dev_addr,'hex'),'') || '|' || COALESCE(md5(device_session),'') || '|' || COALESCE(f_cnt_up::text,'') FROM public.device WHERE dev_eui=decode(lower('${dev}'),'hex');"
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d chirpstack -c "$sql"
    ;;

  evidence-status)
    [ "$#" -eq 0 ] || fail 'evidence-status takes no arguments'
    sql="SELECT 'VERIFICATION|pending|' || count(*)::text FROM gateway_evidence.verification_status WHERE status='pending';
SELECT 'VERIFICATION|verified|' || count(*)::text FROM gateway_evidence.verification_status WHERE status='verified';
SELECT 'VERIFICATION|evidence_gap|' || count(*)::text FROM gateway_evidence.verification_status WHERE status='evidence_gap';
SELECT 'VERIFICATION|integrity_failure|' || count(*)::text FROM gateway_evidence.verification_status WHERE status='integrity_failure';
SELECT 'VERIFICATION|not_required|' || count(*)::text FROM gateway_evidence.verification_status WHERE status='not_required';
SELECT 'LATEST_VERIFIED_AT|' || COALESCE(to_char(max(verified_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'),'') FROM gateway_evidence.verification_status WHERE status='verified';
SELECT 'CHECKPOINT|' || gateway_id || '|' || checkpoint_id::text || '|' || segment_id::text || '|' || last_sequence::text || '|' || to_char(server_received_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"') || '|' || round(extract(epoch from checkpoint_age))::bigint::text FROM gateway_evidence.checkpoint_status ORDER BY gateway_id;"
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -c "$sql"
    ;;

  monitor-stream)
    [ "$#" -eq 1 ] || fail 'monitor-stream requires interval seconds'
    interval=$1
    valid_interval "$interval" || fail 'invalid interval'
    printf '%s\n' '#LORAWAN_MONITOR_STREAM_V1'
    read_cpu() {
      read -r _ user nice system idle iowait irq softirq steal _rest < /proc/stat
      idle_all=$((idle + iowait))
      non_idle=$((user + nice + system + irq + softirq + steal))
      total=$((idle_all + non_idle))
      printf '%s %s\n' "$total" "$idle_all"
    }
    read_net() {
      awk -F'[: ]+' 'NR>2 && $1!="lo" {rx+=$2; tx+=$10} END {printf "%.0f %.0f\n",rx,tx}' /proc/net/dev
    }
    emit_snapshot() {
      ts=$1
      host=$(hostname)
      printf 'HOST|%s|%s|%s\n' "$ts" "$host" "$(cut -d. -f1 /proc/uptime)"
      docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null |
        while IFS='|' read -r name image status; do
          state=not-running
          case "$status" in Up\ *) state=running ;; esac
          printf 'SERVICE|%s|%s|%s|%s|%s\n' "$ts" "$name" "$state" "$image" "$status"
        done
      for unit in mosquitto haproxy pgbouncer fail2ban ufw; do
        state=$(systemctl is-active "$unit" 2>/dev/null || true)
        [ -n "$state" ] || state=unknown
        printf 'UNIT|%s|%s|%s\n' "$ts" "$unit" "$state"
      done
      role=$(docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d postgres -c "select case when pg_is_in_recovery() then 'replica' else 'leader' end" 2>/dev/null || true)
      [ -n "$role" ] || role=unavailable
      printf 'DBROLE|%s|%s\n' "$ts" "$role"
      if [ "$role" = leader ]; then
        docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -F '|' -c "
          select 'telemetry.uplinks',count(*) from telemetry.uplinks
          union all select 'telemetry.measurements',count(*) from telemetry.measurements
          union all select 'evidence.mqtt_events',count(*) from gateway_evidence.mqtt_gateway_events
          union all select 'evidence.segments',count(*) from gateway_evidence.segments
          union all select 'evidence.checkpoints',count(*) from gateway_evidence.checkpoints
          union all select 'evidence.verifications',count(*) from gateway_evidence.event_verification
          union all select 'fabric.outbox',count(*) from telemetry.fabric_outbox;" 2>/dev/null |
          while IFS='|' read -r metric value; do
            printf 'DBMETRIC|%s|%s|%s\n' "$ts" "$metric" "$value"
          done
        docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -F '|' -c "select 'fabric.status.'||status,count(*) from telemetry.fabric_outbox group by status order by status" 2>/dev/null |
          while IFS='|' read -r metric value; do printf 'DBMETRIC|%s|%s|%s\n' "$ts" "$metric" "$value"; done
        docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -F '|' -c "select 'evidence.verification_status.'||status,count(*) from gateway_evidence.event_verification group by status order by status" 2>/dev/null |
          while IFS='|' read -r metric value; do printf 'DBMETRIC|%s|%s|%s\n' "$ts" "$metric" "$value"; done
      fi
      check_stream_ready() {
        label=$1; url=$2
        tmp=/tmp/research-monitor-ready.$$
        code=$(curl --silent --show-error --output "$tmp" --write-out '%{http_code}' --connect-timeout 2 --max-time 4 "$url" 2>/dev/null || true)
        body=$(tr '\r\n|' '   ' <"$tmp" 2>/dev/null | head -c 300 || true)
        rm -f "$tmp"
        state=not-ready; [ "$code" = 200 ] && state=ready
        printf 'READY|%s|%s|%s|%s|%s\n' "$ts" "$label" "$state" "${code:-000}" "$body"
      }
      case "$host" in
        ulc-01)
          check_stream_ready collector-1 http://127.0.0.1:19101/readyz
          check_stream_ready fabric-adapter-1 http://127.0.0.1:19301/readyz
          ;;
        ulc-02)
          check_stream_ready verifier-1 http://127.0.0.1:19202/readyz
          check_stream_ready fabric-adapter-2 http://127.0.0.1:19302/readyz
          ;;
        ulc-03)
          check_stream_ready collector-2 http://127.0.0.1:19103/readyz
          check_stream_ready verifier-2 http://127.0.0.1:19203/readyz
          ;;
      esac
    }
    emit_recent_errors() {
      ts=$1; host=$(hostname)
      case "$host" in
        ulc-01) targets='chirpstack lorawan-gateway-evidence-fabric-adapter-1' ;;
        ulc-02) targets='chirpstack lorawan-gateway-evidence-verifier-1' ;;
        ulc-03) targets='node-red-node-red-1 lorawan-gateway-evidence-verifier-1' ;;
        *) targets='' ;;
      esac
      for name in $targets; do
        docker logs --since 70s "$name" 2>&1 | grep -Ei 'error|failed|fatal|panic|denied|reject|mismatch|unhealthy|timeout|dead.?letter' | tail -n 8 |
          while IFS= read -r line; do
            msg=$(printf '%s' "$line" | base64 -w0)
            printf 'LOG|%s|%s|warning|%s\n' "$ts" "$name" "$msg"
          done
      done
      for unit in mosquitto haproxy; do
        journalctl --no-pager -o short-iso-precise -u "$unit" --since '70 seconds ago' 2>/dev/null |
          grep -Ei 'error|failed|fatal|panic|denied|reject|mismatch|unhealthy|timeout' | tail -n 8 |
          while IFS= read -r line; do
            msg=$(printf '%s' "$line" | base64 -w0)
            printf 'LOG|%s|%s|warning|%s\n' "$ts" "$unit" "$msg"
          done
      done
    }
    set -- $(read_cpu); prev_total=$1; prev_idle=$2
    tick=0
    while :; do
      sleep "$interval"
      set -- $(read_cpu); total=$1; idle_all=$2
      dt=$((total - prev_total)); di=$((idle_all - prev_idle))
      if [ "$dt" -gt 0 ]; then cpu=$(awk -v dt="$dt" -v di="$di" 'BEGIN{printf "%.3f",100*(dt-di)/dt}'); else cpu=0; fi
      prev_total=$total; prev_idle=$idle_all
      mem_total_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
      mem_avail_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
      mem_used=$(((mem_total_kib - mem_avail_kib) * 1024))
      mem_total=$((mem_total_kib * 1024))
      mem_pct=$(awk -v u="$mem_used" -v t="$mem_total" 'BEGIN{if(t>0)printf "%.3f",100*u/t;else print 0}')
      load1=$(awk '{print $1}' /proc/loadavg)
      set -- $(read_net); rx=$1; tx=$2
      ts=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)
      printf 'RESOURCE|%s|%s|%s|%s|%s|%s|%s|%s\n' "$ts" "$cpu" "$mem_used" "$mem_total" "$mem_pct" "$load1" "$rx" "$tx"
      tick=$((tick + interval))
      # Snapshot/log observations are optional side channels. A single failed
      # probe (including grep finding no errors) must never terminate the live
      # resource stream used by the research cockpit.
      if [ "$tick" -eq "$interval" ] || [ $((tick % 30)) -lt "$interval" ]; then emit_snapshot "$ts" || true; fi
      if [ "$tick" -ge 60 ] && [ $((tick % 60)) -lt "$interval" ]; then emit_recent_errors "$ts" || true; fi
    done
    ;;

  resource-host)
    [ "$#" -eq 1 ] || fail 'resource-host requires interval seconds'
    interval=$1
    valid_interval "$interval" || fail 'invalid interval'
    printf 'timestamp_utc,cpu_percent,memory_used_bytes,memory_total_bytes,memory_percent,load1,network_rx_bytes,network_tx_bytes\n'
    read_cpu() {
      read -r _ user nice system idle iowait irq softirq steal _rest < /proc/stat
      idle_all=$((idle + iowait))
      non_idle=$((user + nice + system + irq + softirq + steal))
      total=$((idle_all + non_idle))
      printf '%s %s\n' "$total" "$idle_all"
    }
    read_net() {
      awk -F'[: ]+' 'NR>2 && $1!="lo" {rx+=$2; tx+=$10} END {printf "%.0f %.0f\n",rx,tx}' /proc/net/dev
    }
    set -- $(read_cpu); prev_total=$1; prev_idle=$2
    while :; do
      sleep "$interval"
      set -- $(read_cpu); total=$1; idle_all=$2
      dt=$((total - prev_total)); di=$((idle_all - prev_idle))
      if [ "$dt" -gt 0 ]; then cpu=$(awk -v dt="$dt" -v di="$di" 'BEGIN{printf "%.3f",100*(dt-di)/dt}'); else cpu=0; fi
      prev_total=$total; prev_idle=$idle_all
      mem_total_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
      mem_avail_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
      mem_used=$(((mem_total_kib - mem_avail_kib) * 1024))
      mem_total=$((mem_total_kib * 1024))
      mem_pct=$(awk -v u="$mem_used" -v t="$mem_total" 'BEGIN{if(t>0)printf "%.3f",100*u/t;else print 0}')
      load1=$(awk '{print $1}' /proc/loadavg)
      set -- $(read_net); rx=$1; tx=$2
      printf '%s,%s,%s,%s,%s,%s,%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" "$cpu" "$mem_used" "$mem_total" "$mem_pct" "$load1" "$rx" "$tx"
    done
    ;;

  resource-docker)
    [ "$#" -eq 1 ] || fail 'resource-docker requires interval seconds'
    interval=$1
    valid_interval "$interval" || fail 'invalid interval'
    printf 'timestamp_utc,container,cpu_percent,memory_usage,memory_percent\n'
    while :; do
      ts=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)
      docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' |
        while IFS='|' read -r name cpu mem mempct; do
          cpu=${cpu%%%}; mempct=${mempct%%%}
          printf '%s,%s,%s,"%s",%s\n' "$ts" "$name" "$cpu" "$mem" "$mempct"
        done
      sleep "$interval"
    done
    ;;

  db-export)
    [ "$#" -eq 4 ] || fail 'db-export requires table startUTC endUTC identityEUI'
    table=$1; start=$2; end=$3; identity=$4
    valid_iso "$start" || fail 'invalid start timestamp'
    valid_iso "$end" || fail 'invalid end timestamp'
    valid_eui "$identity" || fail 'identity EUI must be exactly 16 hexadecimal characters'
    case "$table" in
      uplinks)
        sql="SELECT event_key,time,received_at,dev_eui,gateway_id,f_cnt,payload_json->>'test_sequence' AS test_sequence,rssi_dbm,snr_db,gateway_uplink_id,gateway_frequency_hz,raw_data,mqtt_topic,decoder_version,region,f_port,confirmed FROM telemetry.uplinks WHERE dev_eui='${identity}' AND time >= '${start}'::timestamptz AND time < '${end}'::timestamptz ORDER BY time,event_key"
        ;;
      measurements)
        sql="SELECT measurement_id,time,event_key,dev_eui,metric_name,metric_value,metric_text,metric_bool,unit,quality,source_field FROM telemetry.measurements WHERE dev_eui='${identity}' AND time >= '${start}'::timestamptz AND time < '${end}'::timestamptz ORDER BY time,event_key,measurement_id"
        ;;
      outbox)
        sql="SELECT o.event_key,o.source_event_key,o.observed_at,o.event_type,o.schema_version,o.status,o.attempts,o.digest_sha256,o.fabric_tx_id,o.submitted_at,o.committed_at,o.last_error_category,o.created_at,o.updated_at FROM telemetry.fabric_outbox o WHERE o.source_event_key IN (SELECT u.event_key FROM telemetry.uplinks u WHERE u.dev_eui='${identity}' AND u.time >= '${start}'::timestamptz AND u.time < '${end}'::timestamptz) ORDER BY o.created_at,o.outbox_id"
        ;;
      gatewaymqtt)
        sql="SELECT gateway_event_id,gateway_id,mqtt_topic,broker_received_at,capture_key_sha256,serialized_event_sha256,phy_payload_sha256,uplink_id,frequency_hz,rssi_dbm,snr_db,gateway_context_base64,correlation_digest_sha256,collector_version,object_ref FROM gateway_evidence.mqtt_gateway_events WHERE gateway_id='${identity}' AND broker_received_at >= '${start}'::timestamptz AND broker_received_at < '${end}'::timestamptz ORDER BY broker_received_at,gateway_event_id"
        ;;
      packetflow)
        sql="SELECT g.gateway_event_id,g.gateway_id,g.mqtt_topic,g.broker_received_at,g.phy_payload_sha256,g.uplink_id,g.frequency_hz,g.rssi_dbm,g.snr_db,u.event_key,u.time AS application_time,u.received_at AS database_received_at,u.dev_eui,u.f_cnt,u.payload_json->>'test_sequence' AS test_sequence,COALESCE(v.status,'') AS verification_status,COALESCE(v.reason_code,'') AS verification_reason,COALESCE(o.status,'') AS outbox_status,COALESCE(o.fabric_tx_id,'') AS fabric_tx_id,o.submitted_at,o.committed_at FROM gateway_evidence.mqtt_gateway_events g LEFT JOIN telemetry.uplinks u ON u.gateway_id=g.gateway_id AND u.gateway_uplink_id::text=g.uplink_id LEFT JOIN gateway_evidence.event_verification v ON v.source_event_key=u.event_key AND v.observed_at=u.time LEFT JOIN telemetry.fabric_outbox o ON o.source_event_key=u.event_key AND o.observed_at=u.time WHERE g.gateway_id='${identity}' AND g.broker_received_at >= '${start}'::timestamptz AND g.broker_received_at < '${end}'::timestamptz AND g.mqtt_topic LIKE '%/event/up' ORDER BY g.broker_received_at,g.gateway_event_id"
        ;;
      *) fail 'unsupported export table' ;;
    esac
    timeout --signal=TERM --kill-after=5s 35s docker exec spilo psql -X -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry \
      -c "COPY (${sql}) TO STDOUT WITH (FORMAT CSV, HEADER TRUE)"
    ;;

  docker-logstream)
    [ "$#" -eq 1 ] || fail 'docker-logstream requires container'
    container=$1
    case "$container" in
      chirpstack) ;;
      *) fail 'stream container not allowed' ;;
    esac
    exec docker logs --timestamps --tail 0 --follow "$container" 2>&1
    ;;

  docker-log)
    [ "$#" -eq 3 ] || fail 'docker-log requires container startUTC endUTC'
    container=$1; start=$2; end=$3
    valid_iso "$start" || fail 'invalid start timestamp'
    valid_iso "$end" || fail 'invalid end timestamp'
    case "$container" in
      chirpstack|node-red-node-red-1|lorawan-gateway-evidence-ingest-1|lorawan-gateway-evidence-verifier-1|lorawan-gateway-evidence-collector-1|lorawan-gateway-evidence-fabric-adapter-1|grafana|openbao|spilo|etcd|seaweedfs) ;;
      *) fail 'container not allowed' ;;
    esac
    timeout --signal=TERM --kill-after=5s 25s docker logs --timestamps --since "$start" --until "$end" "$container" 2>&1
    ;;

  unit-log)
    [ "$#" -eq 3 ] || fail 'unit-log requires unit startUTC endUTC'
    unit=$1; start=$2; end=$3
    valid_iso "$start" || fail 'invalid start timestamp'
    valid_iso "$end" || fail 'invalid end timestamp'
    case "$unit" in
      mosquitto|haproxy|pgbouncer|fail2ban|ufw) ;;
      *) fail 'unit not allowed' ;;
    esac
    timeout --signal=TERM --kill-after=5s 25s journalctl --no-pager -o short-iso-precise -u "$unit" --since "$start" --until "$end" 2>&1
    ;;

  kernel-log)
    [ "$#" -eq 2 ] || fail 'kernel-log requires startUTC endUTC'
    start=$1; end=$2
    valid_iso "$start" || fail 'invalid start timestamp'
    valid_iso "$end" || fail 'invalid end timestamp'
    timeout --signal=TERM --kill-after=5s 25s journalctl --no-pager -o short-iso-precise -k --since "$start" --until "$end" 2>&1
    ;;

  *) fail 'command not allowed' ;;
esac
