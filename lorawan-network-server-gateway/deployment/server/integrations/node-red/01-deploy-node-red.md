# 1. Deploy Node-RED and Enable Password Login

Node-RED needs access to MQTT and the Timescale-enabled `lorawan_telemetry` database. It does not need access to the LoRa concentrator or the ChirpStack core database.

## Deployment profile - choose before Step 1.1

### Single-host lab

Use the existing `/opt/lorawan-lab` Compose procedure below exactly as written.

### Three-Droplet cloud HA POC

Run Node-RED on `ha-03` as a **small standalone application container**. Do not add `mosquitto` or `telemetry-db` services to `ha-03`; those names belong to the single-host lab.

On `ha-03`:

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

Set only protected references/values required by the container:

~~~dotenv
NODE_RED_IMAGE=<PINNED_NODE_RED_IMAGE_OR_DIGEST>
NODE_RED_CREDENTIAL_SECRET=<REPLACE_WITH_64_HEX_CHAR_SECRET>
LORAWAN_REGION_ID=<CONFIRMED_REGION_ID>
~~~

Create `compose.yml`:

~~~yaml
services:
  node-red:
    image: ${NODE_RED_IMAGE}
    restart: unless-stopped
    ports:
      - "127.0.0.1:1880:1880"
    environment:
      TZ: Asia/Manila
      NODE_RED_CREDENTIAL_SECRET: ${NODE_RED_CREDENTIAL_SECRET}
      LORAWAN_REGION_ID: ${LORAWAN_REGION_ID}
    volumes:
      - /srv/node-red/data:/data
      - /etc/lorawan-pki/mqtt/ca.crt:/run/mqtt/ca.crt:ro
      - /etc/lorawan-pki/node-red-mqtt/client.crt:/run/mqtt/client.crt:ro
      - /etc/lorawan-pki/node-red-mqtt/client.key:/run/mqtt/client.key:ro
      - /etc/lorawan-pki/pgbouncer/ca.crt:/run/pgbouncer/ca.crt:ro
    extra_hosts:
      - "mqtt-ha.internal.<DOMAIN>:<HA03_PRIVATE_IP>"
      - "pgbouncer.internal.<DOMAIN>:<HA03_PRIVATE_IP>"
~~~

**Why these host mappings:** Node-RED talks to the local `ha-03` HAProxy/PgBouncer routes, which then follow Mosquitto and PostgreSQL failover. It must not contain a fixed `ha-01` or `ha-02` dependency.

Validate before start:

~~~bash
sudo docker compose --env-file node-red.env config --quiet
sudo docker compose --env-file node-red.env up -d
sudo docker compose --env-file node-red.env ps
sudo ss -lntp | grep ':1880'
~~~

Expected listener: `127.0.0.1:1880` only.

From this point onward, the authentication steps in Sections 1.4-1.9 apply to both profiles. In the cloud profile, run them from `/etc/lorawan-cloud/node-red` and include `--env-file node-red.env` where the Compose command needs environment interpolation.

**Stop here** if the editor binds publicly, either client-certificate file is missing, or the two logical service names do not resolve to `ha-03` from inside the container.

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
      LORAWAN_REGION_ID: ${LORAWAN_REGION_ID}
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
