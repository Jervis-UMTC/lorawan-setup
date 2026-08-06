# 1. Deploy Node-RED and Enable Password Login

Node-RED needs access to MQTT and TimescaleDB. It does not need access to the LoRa concentrator or the ChirpStack core database.

## 1.1 Go to the Compose directory

~~~bash
cd ~/chirpstack-docker
~~~

## 1.2 Add Node-RED to Docker Compose

Back up the Compose file:

~~~bash
cp docker-compose.yml docker-compose.yml.before-node-red
~~~

Open the Compose file:

~~~bash
nano docker-compose.yml
~~~

Add this service under services:

~~~yaml
  node-red:
    image: nodered/node-red:latest-22
    restart: unless-stopped
    ports:
      - "1880:1880"
    environment:
      TZ: Asia/Manila
    volumes:
      - node-red-data:/data
    depends_on:
      - mosquitto
      - telemetry-db
~~~

Add this under the top-level volumes section:

~~~yaml
volumes:
  node-red-data:
~~~

## 1.3 Start Node-RED

~~~bash
docker compose config
~~~

~~~bash
docker compose up -d node-red
~~~

~~~bash
docker compose ps node-red
~~~

Open:

~~~text
http://<raspberry-pi-ip>:1880
~~~

## 1.4 Generate a password hash

~~~bash
docker compose exec node-red node-red admin hash-pw
~~~

Copy the complete bcrypt hash.

## 1.5 Copy the settings file to the host

~~~bash
docker compose cp node-red:/data/settings.js ./settings.js.node-red
~~~

Create a backup:

~~~bash
cp settings.js.node-red settings.js.node-red.backup
~~~

## 1.6 Edit the settings file

~~~bash
nano settings.js.node-red
~~~

Inside the existing module.exports object, add this block. Replace the placeholder with the hash from Section 1.4:

~~~javascript
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

## 1.7 CRITICAL: copy the edited file back

This is the step that activates the password configuration. Editing the host copy alone does not change the file inside the Node-RED container.

~~~bash
docker compose cp ./settings.js.node-red node-red:/data/settings.js
~~~

If this command is skipped, restarting Node-RED will keep using the old unauthenticated settings.

## 1.8 Check and restart

~~~bash
docker compose exec node-red node --check /data/settings.js
~~~

~~~bash
docker compose restart node-red
~~~

## 1.9 Verify authentication

~~~bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:1880/flows
~~~

Expected result:

~~~text
401
~~~

Then open the editor in a private browser window:

~~~text
http://<raspberry-pi-ip>:1880
~~~

Log in with username admin and the original password used to generate the hash.

If the browser still opens without asking, use a private window because an old browser session may still be active.

Reference: [Node-RED editor security](https://nodered.org/docs/user-guide/runtime/securing-node-red)

Next: [02-configure-mqtt-and-postgresql.md](02-configure-mqtt-and-postgresql.md)
