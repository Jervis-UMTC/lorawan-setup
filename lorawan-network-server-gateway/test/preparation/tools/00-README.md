# Test Tools Preparation

Use a separate Linux laptop on the isolated laboratory network for test traffic generation and EMU-01 serial evidence capture. Keep these utilities off the measured server VM so the traffic generator does not consume server vCPU or memory being measured.

## Manual

Complete [01-prepare-test-tools.md](01-prepare-test-tools.md).

The manual prepares only the utilities required by the research:

```text
mosquitto-clients
Python 3
MQTT invalid-connection generator
invalid application-message generator
RAK4631 SEC-02 raw-RF readiness checks
gateway CPU/memory CSV logger
```

No additional monitoring platform is required. Server resource data is collected with Docker/Linux tools and gateway resource data is collected from `/proc` at five-second intervals.

## Tool acceptance

```text
[ ] mosquitto_pub works from the isolated test laptop
[ ] connection generator reaches the pilot 10/s and 50/s rates
[ ] invalid-message generator reaches the pilot 10/s and 50/s rates
[ ] test listener is reachable only from the test laptop when enabled
[ ] SEC-02 raw-RF prerequisites are proven with RAK5146 reception
[ ] gateway resource CSV advances every five seconds
[ ] server resource CSV advances every five seconds
```

After all preparation folders pass, continue to [../../execution/00-README.md](../../execution/00-README.md).
