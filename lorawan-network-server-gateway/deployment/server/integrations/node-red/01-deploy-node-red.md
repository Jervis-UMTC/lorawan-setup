# 1. Deploy Node-RED and Enable Password Login

Node-RED needs access to MQTT and the Timescale-enabled `lorawan_telemetry` database. It does not need access to the LoRa concentrator or the ChirpStack core database.

## Deployment profile - choose before Step 1.1

### Single-host lab

Use the existing `/opt/lorawan-lab` Compose procedure below exactly as written.

### Three-Droplet cloud HA POC - active/passive

Stage the same pinned Node-RED application on two hosts:

```text
ulc-03 / 10.104.0.8  = Node-RED A, ACTIVE initially
ulc-02 / 10.104.0.4  = Node-RED B, STANDBY initially
```

Do not add standalone `mosquitto` or `telemetry-db` containers to either host. Each candidate uses that host's already-commissioned PgBouncer/HAProxy stack plus a local Node-RED MQTT HAProxy `:18884`. The passive Node-RED container stays stopped until the active instance has been fenced/stopped. See `06-active-passive-ha.md`.

Perform the following file/directory preparation on **both** ulc-03 and ulc-02:

~~~bash
sudo install -d -m 750 /etc/lorawan-cloud/node-red
sudo install -d -m 750 /etc/lorawan-pki/node-red-mqtt
sudo install -d -m 700 /srv/node-red/data
cd /etc/lorawan-cloud/node-red
~~~

Create a protected environment file:

~~~bash
sudo install -m 600 /dev/null /etc/lorawan-cloud/node-red/node-red.env
sudoedit /etc/lorawan-cloud/node-red/node-red.env
~~~

Set only protected references/values required by the container. The repository template is `runtime/node-red.env.example`; the populated host file is never committed:

~~~dotenv
NODE_RED_IMAGE=nodered/node-red@sha256:10f40d0a83e7e5852b13d4d472b2006b05b1cca6d55e2f29a55a12c25a630cb6
NODE_RED_SECRET_GID=<HOST_NODE_RED_SECRETS_GID>
NODE_RED_LOCAL_IP=<THIS_NODE_PRIVATE_IP>
NODE_RED_CREDENTIAL_SECRET=<REPLACE_WITH_64_HEX_CHAR_SECRET>
NODE_RED_ADMIN_PASSWORD_HASH=<BCRYPT_HASH>
NODE_RED_MQTT_CLIENT_ID=<HOST_SPECIFIC_CLIENT_ID>
LORAWAN_REGION_ID=as923
TELEMETRY_DB_USER=telemetry_writer
TELEMETRY_DB_PASSWORD=<TELEMETRY_WRITER_PASSWORD>
~~~

Create `compose.yml`:

~~~yaml
services:
  node-red:
    image: ${NODE_RED_IMAGE}
    restart: unless-stopped
    ports:
      - "127.0.0.1:1880:1880"
    group_add:
      - "${NODE_RED_SECRET_GID}"
    environment:
      TZ: Asia/Manila
      NODE_RED_CREDENTIAL_SECRET: ${NODE_RED_CREDENTIAL_SECRET}
      NODE_RED_ADMIN_PASSWORD_HASH: ${NODE_RED_ADMIN_PASSWORD_HASH}
      NODE_RED_MQTT_CLIENT_ID: ${NODE_RED_MQTT_CLIENT_ID}
      LORAWAN_REGION_ID: ${LORAWAN_REGION_ID}
      TELEMETRY_DB_USER: ${TELEMETRY_DB_USER}
      TELEMETRY_DB_PASSWORD: ${TELEMETRY_DB_PASSWORD}
      NODE_EXTRA_CA_CERTS: /run/pgbouncer/ca.crt
    volumes:
      - /srv/node-red/data:/data
      - /etc/lorawan-pki/mqtt/ca.crt:/run/mqtt/ca.crt:ro
      - /etc/lorawan-pki/node-red-mqtt/client.crt:/run/mqtt/client.crt:ro
      - /etc/lorawan-pki/node-red-mqtt/client.key:/run/mqtt/client.key:ro
      - /etc/lorawan-pki/node-red-pgbouncer/ca.crt:/run/pgbouncer/ca.crt:ro
    extra_hosts:
      - "mqtt.internal.lorawan.com:${NODE_RED_LOCAL_IP}"
      - "pgbouncer.internal.lorawan.com:${NODE_RED_LOCAL_IP}"
~~~

Use `NODE_RED_LOCAL_IP=10.104.0.8` on ulc-03 and `NODE_RED_LOCAL_IP=10.104.0.4` on ulc-02. Set `NODE_RED_SECRET_GID` to the numeric GID of that host's dedicated `node-red-secrets` group. The GID may differ by host; keep it in the protected host environment, not in the shared flow bundle.

The `group_add` entry gives the container's `uid=1000(node-red)` process supplementary read access to files owned `root:node-red-secrets` without making those files readable through host GID `1000`. Keep the MQTT private key `0640 root:node-red-secrets` and the PKI directory `0750 root:node-red-secrets`.

PgBouncer keeps its commissioned CA under `/etc/lorawan-pki/pgbouncer` as `root:postgres` and intentionally does not grant Node-RED access to the PostgreSQL host group. Before starting a candidate, copy only the public CA certificate to `/etc/lorawan-pki/node-red-pgbouncer/ca.crt`, with directory `0750 root:node-red-secrets` and file `0640 root:node-red-secrets`, and verify that its SHA-256 matches the commissioned PgBouncer CA. The container then reads the dedicated copy at `/run/pgbouncer/ca.crt`; do not loosen the original PgBouncer PKI permissions.

**Why these host mappings:** each Node-RED candidate uses its own local MQTT HAProxy `:18884` and PgBouncer `:6432`. This removes ulc-03 as a dependency of the standby. The logical TLS names stay unchanged while the local IP differs per host.

The canonical shared cloud files are maintained under `deployment/server/integrations/node-red/runtime/` (`compose.yml`, `settings.js`, `package.json`, `package-lock.json`, `flows.json`, and the environment template). The current A/B staging uses the same reviewed bytes, including `flows.json` SHA-256 `02be61d7fafdaa8877b9b6f5cf5ef32f7685730e300d4af55b49aadd76518718`. Copy/review that bundle rather than independently recreating A and B by hand; host-specific secrets and client private keys remain outside it.

Validate the Compose artifacts on **both** hosts, but start only Node-RED A on ulc-03:

~~~bash
sudo docker compose --env-file node-red.env config --quiet
~~~

On ulc-03 only:

~~~bash
sudo docker compose --env-file node-red.env up -d
sudo docker compose --env-file node-red.env ps
sudo ss -lntp | grep ':1880'
~~~

On ulc-02, confirm the standby remains stopped:

~~~bash
sudo docker compose --env-file node-red.env ps
sudo ss -lntp | grep ':1880' && echo 'STOP: standby is listening unexpectedly' || true
~~~

Expected normal state: ulc-03 has `127.0.0.1:1880`; ulc-02 has no Node-RED listener.

From this point onward, the authentication steps in Sections 1.4-1.9 apply to both profiles. In the cloud profile, run them from `/etc/lorawan-cloud/node-red` and include `--env-file node-red.env` where the Compose command needs environment interpolation.

**Stop here** if either editor would bind publicly, a host-specific MQTT client certificate/key is missing, the candidate host's private `:18884` MQTT frontend is not commissioned, either logical service name does not resolve to that candidate's own private IP, or both Node-RED containers are running simultaneously.

## 1.1 Go to the Compose directory

~~~bash
cd /opt/lorawan-lab
~~~

## 1.2 Add Node-RED to Docker Compose - single-host lab only

Back up the Compose file:

~~~bash
cp compose.yml compose.yml.before-node-red
~~~

Open the Compose file:

~~~bash
nano compose.yml
~~~

If you selected the cloud HA POC profile above, **skip this lab-only section and continue at 1.4**. Otherwise add this service under services:

~~~yaml
  node-red:
    image: ${NODE_RED_IMAGE}
    restart: unless-stopped
    ports:
      - "127.0.0.1:1880:1880"
    environment:
      TZ: Asia/Manila
      NODE_RED_CREDENTIAL_SECRET: ${NODE_RED_CREDENTIAL_SECRET}
      NODE_RED_ADMIN_PASSWORD_HASH: ${NODE_RED_ADMIN_PASSWORD_HASH}
      NODE_RED_MQTT_CLIENT_ID: ${NODE_RED_MQTT_CLIENT_ID}
      LORAWAN_REGION_ID: ${LORAWAN_REGION_ID}
      TELEMETRY_DB_USER: ${TELEMETRY_DB_USER}
      TELEMETRY_DB_PASSWORD: ${TELEMETRY_DB_PASSWORD}
      NODE_EXTRA_CA_CERTS: /run/pgbouncer/ca.crt
    volumes:
      - node-red-data:/data
    depends_on:
      - mosquitto
      - telemetry-db
    networks: [application, telemetry]
~~~

Set `NODE_RED_IMAGE` in `/opt/lorawan-lab/.env` to a tested version tag or immutable digest. Add the following to the protected `.env` file:

~~~dotenv
NODE_RED_CREDENTIAL_SECRET=<REPLACE_WITH_64_HEX_CHAR_SECRET>
LORAWAN_REGION_ID=<CONFIRMED_REGION_ID>
~~~

Generate a new secret only for a new Node-RED credential store:

~~~bash
openssl rand -hex 32
chmod 600 .env
~~~

Do not rotate `NODE_RED_CREDENTIAL_SECRET` independently after encrypted credentials exist; Node-RED will no longer be able to decrypt the existing `flows_cred.json`. Back up the Node-RED data volume before an approved rotation and re-enter credentials afterward. Do not continue while a placeholder remains.

The canonical lab topology already declares `node-red-data:` under the top-level `volumes:` block. If you are adapting this guide elsewhere, add that one volume entry without replacing existing volumes.

## 1.3 Start Node-RED

~~~bash
docker compose config --quiet
~~~

~~~bash
docker compose up -d node-red
~~~

~~~bash
docker compose ps node-red
~~~

Confirm the host listener is loopback-only:

~~~bash
sudo ss -lntp | grep ':1880'
~~~

From the workstation used to administer the application server, create an SSH tunnel:

~~~bash
ssh -L 1880:127.0.0.1:1880 <SERVER_USER>@<SERVER_IP_ADDRESS>
~~~

`<SERVER_USER>` is the SSH account created on the application VM, and `<SERVER_IP_ADDRESS>` is that VM's management address. The command runs on the workstation, not inside the container.

Open:

~~~text
http://127.0.0.1:1880
~~~

A successful check shows `127.0.0.1:1880` and the tunnel opens the editor locally. If no listener exists, inspect the Node-RED container logs; if it binds to `0.0.0.0`, correct Compose before continuing.

If direct LAN access is explicitly required, bind the port to the specific management address and apply Docker-aware filtering. Do not publish `1880` broadly as a troubleshooting shortcut.

## 1.4 Generate a password hash

~~~bash
docker compose exec node-red node-red admin hash-pw
~~~

Copy the complete bcrypt hash.

## 1.5 Copy the settings file to the host

~~~bash
docker compose cp node-red:/data/settings.js ./settings.js.node-red
~~~

Create a protected backup:

~~~bash
umask 077
cp -p settings.js.node-red settings.js.node-red.backup
chmod 600 settings.js.node-red settings.js.node-red.backup
~~~

## 1.6 Edit the settings file

~~~bash
nano settings.js.node-red
~~~

Inside the existing `module.exports` object, add this block. Replace the password placeholder with the hash from Section 1.4:

~~~javascript
credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET,

adminAuth: {
    type: "credentials",
    users: [{
        username: "admin",
        password: "PASTE_BCRYPT_HASH_HERE",
        permissions: "*"
    }]
},
~~~

Save in Nano with Ctrl+O, press Enter, then exit with Ctrl+X.

## 1.7 Copy the edited file back

This is the step that activates the password configuration. Editing the host copy alone does not change the file inside the Node-RED container.

~~~bash
docker compose cp ./settings.js.node-red node-red:/data/settings.js
~~~

If this command is skipped, restarting Node-RED will keep using the old unauthenticated settings.

## 1.8 Check and restart

~~~bash
docker compose exec node-red node --check /data/settings.js
docker compose exec node-red sh -c \
  'test -n "$NODE_RED_CREDENTIAL_SECRET" && test "$NODE_RED_CREDENTIAL_SECRET" != "<REPLACE_WITH_64_HEX_CHAR_SECRET>"'
~~~

Run the environment check only when the selected image contains a POSIX shell. Otherwise use the image's documented command-execution method.

~~~bash
docker compose restart node-red
~~~

## 1.9 Verify authentication

~~~bash
AUTH_SCHEME=$(curl -fsS http://127.0.0.1:1880/auth/login)
printf '%s\n' "$AUTH_SCHEME" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"credentials"'
FLOW_STATUS=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:1880/flows)
printf 'Unauthenticated /flows status: %s\n' "$FLOW_STATUS"
test "$FLOW_STATUS" -ne 200
~~~

The first command must confirm credential authentication. The second check must not return HTTP 200 without a session or access token. A current Node-RED release normally returns an authorization error, but the security decision is that unauthenticated flow access is denied rather than relying on one hard-coded status code.

Then open the editor through the approved tunnel in a private browser window:

~~~text
http://127.0.0.1:1880
~~~

Log in with username admin and the original password used to generate the hash.

If the browser still opens without asking, use a private window because an old browser session may still be active. Re-run both authentication checks, inspect `/data/settings.js`, and confirm no second Node-RED service or port binding is serving an unauthenticated editor.

Reference: [Node-RED editor security](https://nodered.org/docs/user-guide/runtime/securing-node-red)

Next: [02-configure-mqtt-and-postgresql.md](02-configure-mqtt-and-postgresql.md)
