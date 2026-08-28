# Node-RED Runtime Bundle

This directory is the reviewed, versioned shared runtime bundle for the cloud active/passive Node-RED candidates. Host-specific secrets, MQTT private keys, local IP mappings, and numeric `node-red-secrets` GIDs do not belong here.

Current immutable inputs:

- Node-RED image: `nodered/node-red@sha256:10f40d0a83e7e5852b13d4d472b2006b05b1cca6d55e2f29a55a12c25a630cb6`
- Node-RED: `5.0.4`
- Node.js: `24.18.1`
- PostgreSQL palette: `node-red-contrib-postgresql@0.16.2`
- Region: `as923` supplied through the protected host environment

`package-lock.json` is intentionally not hand-written. Generate it with the pinned image from this exact `package.json`, verify that the top-level dependency remains exactly `0.16.2`, then add the generated lock file before installing runtime dependencies on either HA candidate.

Node-RED A and B must receive the same files from this directory. Keep each candidate's certificate/private key and environment file outside the shared bundle. Keep B stopped until the active candidate is fenced during an approved promotion.

## Shared runtime files

The shared A/B runtime layer now contains:

- `package.json` and `package-lock.json`: exact `node-red-contrib-postgresql@0.16.2` dependency lock.
- `compose.yml`: common container topology; host-specific IP, secret-group GID, MQTT client ID, and protected secrets arrive through `node-red.env`.
- `settings.js`: fails closed when required protected values are absent or placeholders and enables authenticated editor access.
- `node-red.env.example`: variable names only; never populate or commit real secrets here.
- `flows.json`: reviewed ChirpStack application-uplink ingestion flow using mTLS MQTT, the EMU-01 payload-v2 normalization contract, and one parameterized PostgreSQL statement.

The generated lock file SHA-256 is `89289e301cab799ac7e85e2fbe2fc40b34ff195e799313a4f720c642397ba85e`.

`NODE_EXTRA_CA_CERTS=/run/pgbouncer/ca.crt` extends the Node.js trust store with the commissioned internal CA while the PostgreSQL client connects by the verified logical hostname. The later PostgreSQL config node must keep SSL enabled and must use `pgbouncer.internal.lorawan.com`, not a raw backend IP.

Do not start either candidate merely because these files exist. `flows.json` is now part of the reviewed shared bundle, but the single-active rule remains mandatory. Validate dependencies and the flow runtime before activating A; keep B stopped except during an approved fenced promotion.
