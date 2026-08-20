# Cloud Simulation 3. Secure MQTT with the Shared mTLS Procedure

The simulated cloud uses the same CA layout, dual-listener broker model, per-gateway client certificates, and ACL model as the lab. ChirpStack stays on authenticated Docker-internal `1883`; physical gateways use mTLS on published `8883`.

Gateway journal checkpoints/segments are **not** transported through MQTT. When the reviewed v2 evidence-ingest implementation is later added, it uses its separate HTTPS/mTLS endpoint and identity. Until then, do not open a placeholder TCP 443 listener and do not claim the simulation verifies cloud anchoring.

## Step 1: Run the canonical MQTT security manual

Complete:

[Server 11. Secure Gateway MQTT with Mutual TLS](../../ha-cluster/11-secure-gateway-mqtt.md)

Use the cloud-simulation values below. Do not create a second, weaker simulation-only broker configuration.

## Step 2: Apply the simulation values

```text
<MQTT_BROKER_FQDN> = <CLOUD_SIM_MQTT_FQDN>
<BROKER_BIND_ADDRESS> = <CLOUD_SIM_VM_IP_ADDRESS>
<CONFIRMED_REGION_TOPIC_PREFIX> = the same prefix used by Gateway OS
PKI workspace = /root/lorawan-lab-pki
Runtime project = /opt/lorawan-lab
```

Keeping the same PKI paths makes the simulation and lab commands identical. Store the simulation backup separately and label the certificate subject and expiry clearly.

The broker certificate SAN must contain `<CLOUD_SIM_MQTT_FQDN>`. Add the VM IP only when clients intentionally connect by IP; the gateway should normally use the DNS name.

## Step 3: Verify the simulated public boundary

Run on the VM:

```bash
sudo ss -lntup | grep -E ':8883|:1883|:1700'
sudo ufw status verbose
```

Required result:

```text
8883/TCP -> bound only to the intended gateway-facing address
1883/TCP -> not published by Docker to the host
1700/UDP -> no listener
```

From the gateway network, verify the certificate name and chain:

```bash
openssl s_client \
  -connect <CLOUD_SIM_MQTT_FQDN>:8883 \
  -servername <CLOUD_SIM_MQTT_FQDN> \
  -CAfile mqtt-ca.crt \
  -verify_return_error </dev/null
```

The unauthenticated connection must not become an authorized MQTT session because client certificates are required.

## Completion check

- the broker certificate validates the simulated cloud DNS name;
- only TCP `8883` is gateway-facing;
- the gateway-facing Mosquitto listener requires a client certificate and maps its Common Name to the ACL username;
- ChirpStack remains authenticated on Docker-internal `mosquitto:1883`;
- plaintext MQTT and Semtech UDP are not exposed to the gateway network;
- no unauthenticated or placeholder gateway-evidence upload endpoint is exposed.

## Next step

Continue with [04-provision-gateway-mqtt-identity.md](04-provision-gateway-mqtt-identity.md).
