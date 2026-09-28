# Fabric synchronization tooling

`fabric_sync.py` is LoRaWAN-side coordination tooling. It does not replace the production Fabric adapter.

Key commands:
- `prepare-run`: create a sealed run manifest. Default is rehearsal; add `--formal` only from a qualified harness.
- `register-record`: bind an exact payload to trial/source IDs.
- `seal-records`: freeze the post-capture record manifest.
- `marker`: create sealed phase markers.
- `prepare-p2`: formal defaults are locked to 300 seconds x 3 repetitions. Any shortened/custom commissioning matrix requires `--rehearsal`.
- `verify-fabric-export`: fail-closed correlation of Fabric NDJSON to our record manifest.

The JSON schemas in this directory are the interchange contract for the Fabric team.
