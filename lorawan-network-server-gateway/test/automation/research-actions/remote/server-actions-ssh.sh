#!/bin/sh
set -eu

VERSION="research-actions-v2"
ORIGINAL="${SSH_ORIGINAL_COMMAND:-}"
HOST="$(hostname)"

fail() { echo "ERROR: $*" >&2; exit 2; }
valid_iso() {
  printf '%s' "$1" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$'
}

case "$ORIGINAL" in
  version)
    printf '%s|%s\n' "$VERSION" "$HOST"
    ;;

  auth-listener-start)
    [ "$HOST" = "ulc-01" ] || fail 'auth listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener start auth 127.0.0.1 1884
    ;;
  auth-listener-stop)
    [ "$HOST" = "ulc-01" ] || fail 'auth listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener stop auth
    ;;
  auth-listener-status)
    [ "$HOST" = "ulc-01" ] || fail 'auth listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener status auth
    ;;
  auth-listener-smoke)
    [ "$HOST" = "ulc-01" ] || fail 'auth listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener smoke auth
    ;;
  auth-listener-run)
    [ "$HOST" = "ulc-01" ] || fail 'auth listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener run auth
    ;;
  flood-listener-start)
    [ "$HOST" = "ulc-01" ] || fail 'flood listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener start flood 127.0.0.1 1885
    ;;
  flood-listener-stop)
    [ "$HOST" = "ulc-01" ] || fail 'flood listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener stop flood
    ;;
  flood-listener-status)
    [ "$HOST" = "ulc-01" ] || fail 'flood listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener status flood
    ;;
  flood-listener-smoke)
    [ "$HOST" = "ulc-01" ] || fail 'flood listener action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-research-mqtt-test-listener smoke flood
    ;;
  fabric-isolation-status)
    [ "$HOST" = "ulc-01" ] || fail 'Fabric isolation action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-fabric-endpoint-isolation status
    ;;
  fabric-isolation-apply)
    [ "$HOST" = "ulc-01" ] || fail 'Fabric isolation action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-fabric-endpoint-isolation apply
    ;;
  fabric-isolation-remove)
    [ "$HOST" = "ulc-01" ] || fail 'Fabric isolation action allowed only on ulc-01'
    sudo -n /usr/local/sbin/lorawan-fabric-endpoint-isolation remove
    ;;

  flood-db-guard)
    [ "$HOST" = "ulc-01" ] || fail 'flood DB guard allowed only on ulc-01'
    sql="SELECT 'FAKE_UPLINKS_TOTAL|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='0000000000000001';
SELECT 'FAKE_OUTBOX_TOTAL|' || count(*)::text FROM telemetry.fabric_outbox o JOIN telemetry.uplinks u ON u.event_key=o.source_event_key AND u.time=o.observed_at WHERE u.dev_eui='0000000000000001';
SELECT 'EMU_LAST_2M|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='ac1f09fffe296d29' AND time >= now() - interval '2 minutes';"
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -c "$sql"
    ;;

  flood-window\ *)
    [ "$HOST" = "ulc-01" ] || fail 'flood window allowed only on ulc-01'
    set -- $ORIGINAL
    [ "$#" -eq 3 ] || fail 'flood-window requires startUTC endUTC'
    [ "$1" = "flood-window" ] || fail 'invalid command'
    start=$2; end=$3
    valid_iso "$start" || fail 'invalid flood-window start timestamp'
    valid_iso "$end" || fail 'invalid flood-window end timestamp'
    sql="SELECT 'VALID_DELIVERED|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='ac1f09fffe296d29' AND time >= '${start}'::timestamptz AND time < '${end}'::timestamptz;
SELECT 'MEAN_LATENCY_MS|' || COALESCE(round(avg(extract(epoch FROM (received_at-time))*1000)::numeric,3)::text,'') FROM telemetry.uplinks WHERE dev_eui='ac1f09fffe296d29' AND time >= '${start}'::timestamptz AND time < '${end}'::timestamptz;
SELECT 'UNAUTHORIZED_UPLINKS|' || count(*)::text FROM telemetry.uplinks WHERE dev_eui='0000000000000001' AND received_at >= '${start}'::timestamptz AND received_at < '${end}'::timestamptz;
SELECT 'UNAUTHORIZED_OUTBOX|' || count(*)::text FROM telemetry.fabric_outbox o JOIN telemetry.uplinks u ON u.event_key=o.source_event_key AND u.time=o.observed_at WHERE u.dev_eui='0000000000000001' AND o.created_at >= '${start}'::timestamptz AND o.created_at < '${end}'::timestamptz;"
    docker exec spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry -c "$sql"
    ;;

  flood-branch-install)
    [ "$HOST" = "ulc-03" ] || fail 'Node-RED flood branch action allowed only on ulc-03'
    python3 /home/opsadmin/.local/bin/lorawan-node-red-flood-branch install
    ;;
  flood-branch-remove)
    [ "$HOST" = "ulc-03" ] || fail 'Node-RED flood branch action allowed only on ulc-03'
    python3 /home/opsadmin/.local/bin/lorawan-node-red-flood-branch remove
    ;;
  flood-branch-status)
    [ "$HOST" = "ulc-03" ] || fail 'Node-RED flood branch action allowed only on ulc-03'
    python3 /home/opsadmin/.local/bin/lorawan-node-red-flood-branch status
    ;;
  flood-summary)
    [ "$HOST" = "ulc-03" ] || fail 'Node-RED flood summary allowed only on ulc-03'
    docker exec node-red-node-red-1 sh -lc 'test -r /data/research-flood-validation.jsonl && tail -n 20 /data/research-flood-validation.jsonl || true'
    ;;
  *)
    fail 'command not allowed'
    ;;
esac
