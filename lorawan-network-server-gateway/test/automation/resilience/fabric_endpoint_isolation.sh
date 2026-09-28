#!/bin/sh
set -eu

# Scoped Chapter-IV resilience helper.
# It isolates only the active Fabric-adapter container from its commissioned
# Fabric Gateway endpoint. It never alters a host default route or gateway path.

ACTION="${1:-status}"
CONTAINER="${FABRIC_ADAPTER_CONTAINER:-lorawan-gateway-evidence-fabric-adapter-1}"
RULE_COMMENT="lorawan-fabric-research-isolation"
STATE_FILE="${FABRIC_ISOLATION_STATE_FILE:-/run/lorawan-fabric-research-isolation.state}"
IPTABLES="${IPTABLES:-iptables}"

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run with sudo/root" >&2
    exit 2
  fi
}

container_endpoint() {
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER" 2>/dev/null \
    | sed -n 's/^FABRIC_GATEWAY_ENDPOINT=//p' \
    | head -n1
}

container_ip() {
  docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{if $v.IPAddress}}{{$v.IPAddress}}{{println}}{{end}}{{end}}' "$CONTAINER" 2>/dev/null \
    | sed -n '1p'
}

resolve_live() {
  ENDPOINT="$(container_endpoint)"
  SRC_IP="$(container_ip)"
  if [ -z "$ENDPOINT" ] || [ -z "$SRC_IP" ]; then
    echo "ERROR: cannot discover live adapter endpoint/IP for $CONTAINER" >&2
    exit 2
  fi
  DEST_HOST="${ENDPOINT%:*}"
  DEST_PORT="${ENDPOINT##*:}"
  case "$DEST_PORT" in
    ''|*[!0-9]*) echo "ERROR: invalid Fabric endpoint port: $ENDPOINT" >&2; exit 2 ;;
  esac
  if [ "$DEST_HOST" = "$ENDPOINT" ]; then
    echo "ERROR: Fabric endpoint must be host:port, got $ENDPOINT" >&2
    exit 2
  fi
}

rule_exists() {
  "$IPTABLES" -C DOCKER-USER \
    -s "$SRC_IP/32" -d "$DEST_HOST/32" -p tcp --dport "$DEST_PORT" \
    -m comment --comment "$RULE_COMMENT" \
    -j REJECT --reject-with tcp-reset 2>/dev/null
}

print_scope() {
  printf 'container=%s\nsource_ip=%s\nfabric_endpoint=%s:%s\nchain=DOCKER-USER\ncomment=%s\n' \
    "$CONTAINER" "$SRC_IP" "$DEST_HOST" "$DEST_PORT" "$RULE_COMMENT"
}

case "$ACTION" in
  status)
    need_root
    resolve_live
    print_scope
    if rule_exists; then
      echo "isolation=ACTIVE"
      exit 0
    fi
    echo "isolation=INACTIVE"
    exit 0
    ;;
  apply)
    need_root
    resolve_live
    print_scope
    if rule_exists; then
      echo "isolation=ACTIVE"
      exit 0
    fi
    "$IPTABLES" -I DOCKER-USER 1 \
      -s "$SRC_IP/32" -d "$DEST_HOST/32" -p tcp --dport "$DEST_PORT" \
      -m comment --comment "$RULE_COMMENT" \
      -j REJECT --reject-with tcp-reset
    umask 077
    printf 'SRC_IP=%s\nDEST_HOST=%s\nDEST_PORT=%s\n' "$SRC_IP" "$DEST_HOST" "$DEST_PORT" > "$STATE_FILE"
    if ! rule_exists; then
      echo "ERROR: scoped isolation rule was not installed" >&2
      exit 1
    fi
    echo "isolation=ACTIVE"
    ;;
  remove)
    need_root
    # Prefer the exact values saved at apply-time so cleanup still works if the
    # container is recreated and gets a new bridge address during the outage.
    if [ -r "$STATE_FILE" ]; then
      SRC_IP="$(sed -n 's/^SRC_IP=//p' "$STATE_FILE" | head -n1)"
      DEST_HOST="$(sed -n 's/^DEST_HOST=//p' "$STATE_FILE" | head -n1)"
      DEST_PORT="$(sed -n 's/^DEST_PORT=//p' "$STATE_FILE" | head -n1)"
    else
      resolve_live
    fi
    while rule_exists; do
      "$IPTABLES" -D DOCKER-USER \
        -s "$SRC_IP/32" -d "$DEST_HOST/32" -p tcp --dport "$DEST_PORT" \
        -m comment --comment "$RULE_COMMENT" \
        -j REJECT --reject-with tcp-reset
    done
    rm -f "$STATE_FILE"
    echo "isolation=INACTIVE"
    ;;
  *)
    echo "usage: $0 {status|apply|remove}" >&2
    exit 2
    ;;
esac
