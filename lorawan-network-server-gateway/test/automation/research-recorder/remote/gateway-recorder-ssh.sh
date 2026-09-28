#!/bin/sh
set -eu

# Forced-command collector for Gateway-01 (OpenWrt / Dropbear).
cmd=${SSH_ORIGINAL_COMMAND:-"$*"}
set -- $cmd
verb=${1:-}
shift || true

fail() { echo "research-recorder: $*" >&2; exit 64; }
valid_interval() { echo "$1" | grep -Eq '^[1-9][0-9]*$' && [ "$1" -le 60 ]; }
valid_count() { echo "$1" | grep -Eq '^[1-9][0-9]*$' && [ "$1" -le 500 ]; }
run_uqmi_bounded() {
  seconds=$1
  shift
  uqmi "$@" &
  qpid=$!
  (
    sleep "$seconds"
    kill "$qpid" 2>/dev/null || exit 0
    sleep 1
    kill -9 "$qpid" 2>/dev/null || :
  ) &
  tpid=$!
  wait "$qpid" 2>/dev/null || :
  kill "$tpid" 2>/dev/null || :
  wait "$tpid" 2>/dev/null || :
}

case "$verb" in
  version)
    [ "$#" -eq 0 ] || fail 'version takes no arguments'
    echo 'research-recorder-gateway-v3'
    ;;

  clock-probe)
    [ "$#" -eq 1 ] || fail 'clock-probe requires sample count'
    count=$1
    valid_count "$count" || fail 'invalid clock-probe sample count'
    [ "$count" -le 20 ] || fail 'clock-probe sample count too large'
    echo '#CLOCK_PROBE_V1'
    i=0
    while [ "$i" -lt "$count" ]; do
      IFS= read -r request || fail 'clock-probe input ended early'
      request=$(printf '%s' "$request" | tr -d '\r')
      [ "$request" = probe ] || fail 'invalid clock-probe request'
      date -u +%Y-%m-%dT%H:%M:%SZ
      i=$((i + 1))
    done
    ;;

  snapshot)
    [ "$#" -eq 0 ] || fail 'snapshot takes no arguments'
    echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "hostname=$(cat /proc/sys/kernel/hostname 2>/dev/null || echo gateway-01)"
    echo '--- uptime ---'; cat /proc/uptime
    echo '--- lte ---'; ubus call network.interface.lte status 2>/dev/null || true
    echo '--- lte_4 ---'; ubus call network.interface.lte_4 status 2>/dev/null || true
    echo '--- wwan0 ---'; ip addr show dev wwan0 2>/dev/null || true
    echo '--- routes ---'; ip route show
    echo '--- cloud-route ---'; ip route get 129.212.208.168 2>/dev/null || true
    echo '--- cloud-probe ---'
    if command -v nc >/dev/null 2>&1; then
      if nc -z -w 3 129.212.208.168 8883 >/dev/null 2>&1; then echo 'tcp_8883=REACHABLE'; else echo 'tcp_8883=UNREACHABLE'; fi
    else
      echo 'tcp_8883=PROBE_TOOL_MISSING'
    fi
    echo '--- mqtt-sockets ---'; netstat -nt 2>/dev/null | grep ':8883' || true
    echo '--- serving-system ---'; command -v uqmi >/dev/null 2>&1 && run_uqmi_bounded 4 -d /dev/cdc-wdm0 --get-serving-system 2>/dev/null || true
    echo '--- signal ---'; command -v uqmi >/dev/null 2>&1 && run_uqmi_bounded 4 -d /dev/cdc-wdm0 --get-signal-info 2>/dev/null || true
    ;;

  resource)
    [ "$#" -eq 1 ] || fail 'resource requires interval seconds'
    interval=$1
    valid_interval "$interval" || fail 'invalid interval'
    echo 'timestamp_utc,cpu_percent,memory_used_bytes,memory_total_bytes,memory_percent,load1,network_rx_bytes,network_tx_bytes'
    read_cpu() {
      set -- $(head -n 1 /proc/stat)
      user=$2; nice=$3; system=$4; idle=$5; iowait=${6:-0}; irq=${7:-0}; softirq=${8:-0}; steal=${9:-0}
      idle_all=$((idle + iowait)); non_idle=$((user + nice + system + irq + softirq + steal)); total=$((idle_all + non_idle))
      echo "$total $idle_all"
    }
    read_net() {
      awk -F'[: ]+' 'NR>2 && $1!="lo" {rx+=$2; tx+=$10} END {printf "%.0f %.0f\n",rx,tx}' /proc/net/dev
    }
    set -- $(read_cpu); prev_total=$1; prev_idle=$2
    while :; do
      sleep "$interval"
      set -- $(read_cpu); total=$1; idle_all=$2
      dt=$((total-prev_total)); di=$((idle_all-prev_idle))
      cpu=$(awk -v dt="$dt" -v di="$di" 'BEGIN{if(dt>0)printf "%.3f",100*(dt-di)/dt;else print 0}')
      prev_total=$total; prev_idle=$idle_all
      mem_total_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
      mem_avail_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
      [ -n "$mem_avail_kib" ] || mem_avail_kib=$(awk '/^MemFree:/ {print $2}' /proc/meminfo)
      mem_used=$(((mem_total_kib-mem_avail_kib)*1024)); mem_total=$((mem_total_kib*1024))
      mem_pct=$(awk -v u="$mem_used" -v t="$mem_total" 'BEGIN{if(t>0)printf "%.3f",100*u/t;else print 0}')
      load1=$(awk '{print $1}' /proc/loadavg)
      set -- $(read_net); rx=$1; tx=$2
      printf '%s,%s,%s,%s,%s,%s,%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$cpu" "$mem_used" "$mem_total" "$mem_pct" "$load1" "$rx" "$tx"
    done
    ;;

  journal-recent)
    [ "$#" -eq 1 ] || fail 'journal-recent requires record count'
    count=$1
    valid_count "$count" || fail 'invalid record count'
    files=$(ls /etc/gateway-evidence/journal/closed/segment-*.jsonl /etc/gateway-evidence/journal/open/segment-*.jsonl 2>/dev/null | sort | tail -n 8 || true)
    [ -n "$files" ] || exit 0
    for f in $files; do
      grep '"kind":"record"' "$f" 2>/dev/null || true
    done | tail -n "$count"
    ;;

  radio-recent)
    [ "$#" -eq 1 ] || fail 'radio-recent requires frame count'
    count=$1
    valid_count "$count" || fail 'invalid frame count'
    logread 2>/dev/null | grep 'Frame received, uplink_id:' | tail -n "$count"
    ;;

  logstream)
    [ "$#" -eq 0 ] || fail 'logstream takes no arguments'
    logread -f
    ;;

  *) fail 'command not allowed' ;;
esac
