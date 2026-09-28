#!/bin/sh
set -eu

ACTION="${1:-verify}"
GATEWAY_EUI="${GATEWAY_EUI:-0016c001f139a1cb}"
LAN_IP="${LAN_IP:-192.168.20.11}"
LAN_NETMASK="${LAN_NETMASK:-255.255.255.0}"
MQTT_HOST="${MQTT_HOST:-smartagri-mqtt.duckdns.org}"
MQTT_PORT="${MQTT_PORT:-8883}"
EVIDENCE_URL="${EVIDENCE_URL:-https://smartagri-evidence.duckdns.org}"
EVIDENCE_HOST="${EVIDENCE_URL#https://}"
EVIDENCE_HOST="${EVIDENCE_HOST%%/*}"
EVIDENCE_HOST="${EVIDENCE_HOST%%:*}"
PUBLIC_IP="${PUBLIC_IP:-129.212.208.168}"
STAGING_DIR="${STAGING_DIR:-/tmp/gateway-provision}"

fail() {
    echo "FAIL|$*" >&2
    exit 1
}

pass() {
    echo "PASS|$*"
}

require_root() {
    [ "$(id -u)" = "0" ] || fail "run as root on Gateway OS"
}

require_radio_identity() {
    [ "$(uci -q get chirpstack-concentratord.@sx1302[0].model || true)" = "rak_5146" ] || fail "active SX1302 model is not rak_5146"
    [ "$(uci -q get chirpstack-concentratord.@sx1302[0].region || true)" = "AS923" ] || fail "active SX1302 region is not AS923"
    [ "$(uci -q get chirpstack-concentratord.@sx1302[0].channel_plan || true)" = "as923" ] || fail "active SX1302 channel plan is not as923"
    logread | grep 'Gateway ID retrieved' | tail -n 1 | grep -qi "$GATEWAY_EUI" || fail "live Concentratord Gateway EUI does not match $GATEWAY_EUI"
    pass "RAK5146 AS923 Gateway EUI $GATEWAY_EUI"
}

require_public_endpoint_sanity() {
    case "$EVIDENCE_URL" in
        https://*:18443|https://*:18443/*)
            fail "Evidence port 18443 is the internal object-store frontend, not the public gateway ingest endpoint"
            ;;
    esac
    [ -n "$EVIDENCE_HOST" ] || fail "Evidence hostname could not be derived from $EVIDENCE_URL"
}

require_no_commissioning_host_overrides() {
    if grep -Eq 'gateway-commissioning-relay|TEMP_(MQTT|EVIDENCE)_RELAY' /etc/hosts 2>/dev/null; then
        fail "temporary MQTT/Evidence commissioning relay entry is still present in /etc/hosts"
    fi

    for host in "$MQTT_HOST" "$EVIDENCE_HOST"; do
        if awk -v h="$host" '
            $1 ~ /^10\./ || $1 ~ /^192\.168\./ || $1 ~ /^172\.(1[6-9]|2[0-9]|3[01])\./ {
                for (i = 2; i <= NF; i++) if ($i == h) found = 1
            }
            END { exit found ? 0 : 1 }
        ' /etc/hosts 2>/dev/null; then
            fail "$host is pinned to a private address in /etc/hosts; remove the temporary relay and restart dnsmasq"
        fi
    done
}

preflight_clean_overlay() {
    require_radio_identity
    require_public_endpoint_sanity
    [ ! -f /etc/mosquitto/conf.d/bridge.conf ] || fail "MQTT bridge already exists; if this is meant to be a fresh flash, investigate stale writable overlay before provisioning"
    [ ! -e "/etc/mosquitto/certs/$GATEWAY_EUI.key" ] || fail "MQTT private key already exists; if this is meant to be a fresh flash, investigate stale writable overlay"
    [ ! -e /etc/gateway-evidence/tls/client.key ] || fail "Evidence private key already exists; if this is meant to be a fresh flash, investigate stale writable overlay"
    require_no_commissioning_host_overrides
    pass "factory secret paths and commissioning host overrides are absent"
}

require_secured_root() {
    ! grep -q '^root::' /etc/shadow || fail "factory-empty root password is still active; set a root password before apply"
    pass "factory-empty root password removed"
}

require_staging() {
    for file in \
        mqtt/ca.crt \
        mqtt/client.crt \
        mqtt/client.key \
        evidence/ca.crt \
        evidence/client.crt \
        evidence/client.key
    do
        [ -s "$STAGING_DIR/$file" ] || fail "missing staged identity file: $STAGING_DIR/$file"
    done
    pass "all six staged identity files present"
}

copy_checked() {
    src="$1"
    dst="$2"
    cp "$src" "$dst"
    src_hash="$(sha256sum "$src" | awk '{print $1}')"
    dst_hash="$(sha256sum "$dst" | awk '{print $1}')"
    [ "$src_hash" = "$dst_hash" ] || fail "hash mismatch after installing $dst"
}

configure_network() {
    : "${WIFI_SSID:?set WIFI_SSID for apply}"
    : "${WIFI_PSK:?set WIFI_PSK for apply}"

    uci set network.lan.proto='static'
    uci set network.lan.ipaddr="$LAN_IP"
    uci set network.lan.netmask="$LAN_NETMASK"
    uci -q delete network.lan.gateway || true
    uci -q delete network.lan.dns || true
    uci set network.wwan='interface'
    uci set network.wwan.proto='dhcp'

    uci set wireless.radio0.channel='auto'
    uci set wireless.default_radio0.network='wwan'
    uci set wireless.default_radio0.mode='sta'
    uci set wireless.default_radio0.ssid="$WIFI_SSID"
    uci set wireless.default_radio0.encryption='psk2'
    uci set wireless.default_radio0.key="$WIFI_PSK"

    uci commit network
    uci commit wireless
    /etc/init.d/network reload

    i=0
    while [ "$i" -lt 30 ]; do
        if ifstatus wwan 2>/dev/null | grep -q '"up": true'; then
            pass "Wi-Fi WWAN is up"
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done
    fail "Wi-Fi WWAN did not become ready"
}

configure_forwarder() {
    uci set chirpstack-mqtt-forwarder.@global[0].enabled='1'
    uci set chirpstack-mqtt-forwarder.@mqtt[0].topic_prefix='as923'
    uci set chirpstack-mqtt-forwarder.@mqtt[0].server='tcp://127.0.0.1:1883'
    uci set chirpstack-mqtt-forwarder.@mqtt[0].qos='1'
    uci commit chirpstack-mqtt-forwarder
    /etc/init.d/chirpstack-mqtt-forwarder restart
}

install_mqtt_identity_and_bridge() {
    mkdir -p /etc/mosquitto/certs /etc/mosquitto/conf.d /etc/mosquitto/data
    copy_checked "$STAGING_DIR/mqtt/ca.crt" /etc/mosquitto/certs/ca.crt
    copy_checked "$STAGING_DIR/mqtt/client.crt" "/etc/mosquitto/certs/$GATEWAY_EUI.crt"
    copy_checked "$STAGING_DIR/mqtt/client.key" "/etc/mosquitto/certs/$GATEWAY_EUI.key"
    chown -R mosquitto:mosquitto /etc/mosquitto/certs /etc/mosquitto/data
    chmod 0750 /etc/mosquitto/certs /etc/mosquitto/data
    chmod 0644 /etc/mosquitto/certs/ca.crt "/etc/mosquitto/certs/$GATEWAY_EUI.crt"
    chmod 0600 "/etc/mosquitto/certs/$GATEWAY_EUI.key"

    cat > /etc/mosquitto/conf.d/bridge.conf <<EOF
connection cloud-uplink
address $MQTT_HOST:$MQTT_PORT
bridge_protocol_version mqttv311
remote_clientid gw-up-$GATEWAY_EUI
cleansession false
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/$GATEWAY_EUI.crt
bridge_keyfile /etc/mosquitto/certs/$GATEWAY_EUI.key
bridge_insecure false
topic as923/gateway/$GATEWAY_EUI/event/# out 1
topic as923/gateway/$GATEWAY_EUI/state/# out 1

connection cloud-downlink
address $MQTT_HOST:$MQTT_PORT
bridge_protocol_version mqttv311
remote_clientid gw-down-$GATEWAY_EUI
cleansession true
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/$GATEWAY_EUI.crt
bridge_keyfile /etc/mosquitto/certs/$GATEWAY_EUI.key
bridge_insecure false
topic as923/gateway/$GATEWAY_EUI/command/# in 0
EOF
    chown root:mosquitto /etc/mosquitto/conf.d/bridge.conf
    chmod 0640 /etc/mosquitto/conf.d/bridge.conf
}

install_evidence_identity() {
    mkdir -p /etc/gateway-evidence/tls
    copy_checked "$STAGING_DIR/evidence/ca.crt" /etc/gateway-evidence/tls/ca.crt
    copy_checked "$STAGING_DIR/evidence/client.crt" /etc/gateway-evidence/tls/client.crt
    copy_checked "$STAGING_DIR/evidence/client.key" /etc/gateway-evidence/tls/client.key
    chown -R gateway-evidence-upload:gateway-evidence /etc/gateway-evidence/tls
    chmod 0700 /etc/gateway-evidence/tls
    chmod 0644 /etc/gateway-evidence/tls/ca.crt /etc/gateway-evidence/tls/client.crt
    chmod 0600 /etc/gateway-evidence/tls/client.key

    uci set gateway-evidence.uploader.ingest_url="$EVIDENCE_URL"
    uci set gateway-evidence.uploader.enabled='1'
    uci commit gateway-evidence
    /etc/init.d/gateway-evidence-uploader enable
}

verify_commissioned() {
    require_radio_identity
    require_secured_root

    [ "$(uci -q get network.lan.proto || true)" = "static" ] || fail "maintenance LAN is not static"
    [ "$(uci -q get network.lan.ipaddr || true)" = "$LAN_IP" ] || fail "maintenance LAN address is not $LAN_IP"
    if ip route | grep -q '^default .* dev wwan0 .*metric 10'; then
        pass "LTE is the active production default route"
    elif ifstatus wwan 2>/dev/null | grep -q '"up": true' && ip route | grep -q '^default .* phy0-sta0'; then
        pass "Wi-Fi is the active commissioning/fallback default route"
    else
        fail "neither the metric-10 LTE production route nor the Wi-Fi commissioning/fallback route is active"
    fi

    [ "$(uci -q get chirpstack-mqtt-forwarder.@mqtt[0].topic_prefix || true)" = "as923" ] || fail "MQTT Forwarder topic prefix is not as923"
    [ "$(uci -q get chirpstack-mqtt-forwarder.@mqtt[0].server || true)" = "tcp://127.0.0.1:1883" ] || fail "MQTT Forwarder is not using loopback Mosquitto"
    [ "$(uci -q get chirpstack-mqtt-forwarder.@mqtt[0].qos || true)" = "1" ] || fail "MQTT Forwarder QoS is not 1"

    [ -s /etc/mosquitto/conf.d/bridge.conf ] || fail "MQTT bridge configuration missing"
    [ "$(ls -l "/etc/mosquitto/certs/$GATEWAY_EUI.key" | awk '{print $1}')" = "-rw-------" ] || fail "MQTT private key permissions are not 0600"
    [ "$(ls -l /etc/gateway-evidence/tls/client.key | awk '{print $1}')" = "-rw-------" ] || fail "Evidence private key permissions are not 0600"
    require_public_endpoint_sanity
    require_no_commissioning_host_overrides
    [ "$(uci -q get gateway-evidence.uploader.ingest_url || true)" = "$EVIDENCE_URL" ] || fail "Evidence uploader endpoint drifted from $EVIDENCE_URL"

    nslookup "$MQTT_HOST" 2>/dev/null | grep -q "$PUBLIC_IP" || fail "$MQTT_HOST does not resolve to expected public ingress $PUBLIC_IP"
    nslookup "$EVIDENCE_HOST" 2>/dev/null | grep -q "$PUBLIC_IP" || fail "Evidence hostname does not resolve to expected public ingress $PUBLIC_IP"

    openssl s_client \
        -connect "$MQTT_HOST:$MQTT_PORT" \
        -servername "$MQTT_HOST" \
        -CAfile /etc/mosquitto/certs/ca.crt \
        -cert "/etc/mosquitto/certs/$GATEWAY_EUI.crt" \
        -key "/etc/mosquitto/certs/$GATEWAY_EUI.key" \
        -verify_return_error -brief </dev/null 2>&1 | grep -q 'Verification: OK' || fail "MQTT mTLS verification failed"

    curl --fail --silent --show-error \
        --cacert /etc/gateway-evidence/tls/ca.crt \
        --cert /etc/gateway-evidence/tls/client.crt \
        --key /etc/gateway-evidence/tls/client.key \
        "$EVIDENCE_URL/readyz" | grep -q '"status":"ready"' || fail "Evidence mTLS readiness failed"

    ps w | grep -q '[m]osquitto -c' || fail "Mosquitto is not running"
    ps w | grep -q '[g]ateway-evidence-writer' || fail "Evidence writer is not running"
    ps w | grep -q '[g]ateway-evidence-uploader' || fail "Evidence uploader is not running"
    bridge_count="$(netstat -nt 2>/dev/null | grep "$PUBLIC_IP:$MQTT_PORT" | grep -c ESTABLISHED || true)"
    [ "$bridge_count" -ge 2 ] || fail "expected two established MQTT bridge sockets, found $bridge_count"

    pass "commissioned gateway runtime verified"
}

apply_commissioning() {
    preflight_clean_overlay
    require_secured_root
    require_staging
    configure_network
    configure_forwarder
    install_mqtt_identity_and_bridge
    install_evidence_identity

    /etc/init.d/mosquitto restart
    /etc/init.d/gateway-evidence-uploader restart >/dev/null 2>&1 || true
    sleep 5
    verify_commissioned

    rm -rf "$STAGING_DIR"
    pass "temporary staging removed"
}

require_root
case "$ACTION" in
    preflight)
        preflight_clean_overlay
        ;;
    apply)
        apply_commissioning
        ;;
    verify)
        verify_commissioned
        ;;
    *)
        fail "usage: $0 {preflight|apply|verify}"
        ;;
esac
