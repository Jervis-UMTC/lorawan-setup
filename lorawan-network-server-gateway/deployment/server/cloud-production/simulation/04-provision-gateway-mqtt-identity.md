# Cloud Simulation 4. Provision the Gateway MQTT Identity

Use the same certificate Common Name, ACL, transfer bundle, and gateway bridge client IDs that will be used against the real cloud endpoint.

## Step 1: Run the canonical identity manual

Complete:

[Server 12. Provision a Gateway MQTT Identity](../../ha-cluster/12-provision-gateway-mqtt-identity.md)

Use the real `<GATEWAY_EUI>` reported by Concentratord. Do not issue a simulation-only fake EUI when the physical gateway is available.

## Step 2: Keep the gateway contract portable

The bundle remains:

```text
ca.crt
<GATEWAY_EUI>.crt
<GATEWAY_EUI>.key
```

The certificate Common Name remains:

```text
<GATEWAY_EUI>
```

The ACL remains:

```text
user <GATEWAY_EUI>
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#
```

The gateway bridge client IDs remain:

```text
gw-up-<GATEWAY_EUI>
gw-down-<GATEWAY_EUI>
```

Later migration to a real cloud broker should require only the delivery endpoint and appropriate MQTT CA/server certificate chain to change. Do not change the Gateway EUI topic contract during migration.

When v2 evidence upload is later implemented, provision its identity separately from this MQTT bundle unless a reviewed PKI policy explicitly chooses key reuse. Changing the evidence endpoint must never reset the local journal sequence/hash chain.

## Step 3: Verify allowed and denied access

Before importing the bundle into Gateway OS, test:

1. allowed subscribe to this gateway's command topic;
2. allowed publish to this gateway's event test subtopic on the disposable simulation broker;
3. denied publish to another Gateway EUI;
4. denied subscribe to another Gateway EUI;
5. rejected connection when the client certificate is omitted.

Do not weaken the ACL to make a negative test pass.

## Completion check

- certificate and private-key public hashes match;
- certificate Common Name equals the exact Gateway EUI;
- the gateway can access only its own event, state, and command topics;
- the transfer bundle contains no CA private key;
- certificate serial, fingerprint, expiry, and encrypted recovery location are retained;
- the gateway is ready for [persistent local MQTT buffer configuration](../../../gateway/setup/04-configure-local-mqtt-buffer.md) and then the [software-only integrity journal](../../../gateway/setup/04a-configure-gateway-integrity-journal.md).
