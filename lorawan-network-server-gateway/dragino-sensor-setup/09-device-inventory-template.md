# 9. Dragino Device Inventory Template

Copy this template for each physical sensor. It intentionally records where secrets are stored without putting the secrets in the repository.

## Device identity

~~~text
Device name in ChirpStack:
Manufacturer: Dragino
Exact model:
Hardware revision:
Serial number:
Physical label/photo location:
Installation site:
Installation date:
Owner/team:
~~~

## LoRaWAN configuration

~~~text
Frequency plan: AS923-3
Regional firmware marking:
Firmware version:
LoRaWAN MAC version:
Regional Parameters revision:
Activation: OTAA / ABP
Device class: A / B / C
Device profile name:
Application name:
DevEUI:
JoinEUI/AppEUI present: yes / no
Credential record location:
~~~

Do not write the AppKey or NwkKey in this file.

## Payload configuration

~~~text
Codec name:
Codec file/version:
Expected normal uplink port:
Expected status port:
Expected datalog port:
Reporting interval:
Known downlink ports/commands:
~~~

For LSN50v2-S31/S31B, the local decoder currently expects normal data on FPort 2, datalog data on FPort 3, and status on FPort 5. Confirm this against the installed firmware before production use.

## Acceptance evidence

~~~text
Gateway ID: 2ccf67fffe0abee3
Gateway last-seen verified: yes / no
JoinRequest observed: yes / no
JoinAccept observed: yes / no
First uplink timestamp:
First uplink fPort:
First uplink decoded: yes / no
Second uplink timestamp:
Frame counter advanced: yes / no
MQTT/application integration verified: yes / no / not configured
Observed RSSI/SNR:
Battery reading:
~~~

## Change history

| Date | Change | Operator | Result |
|---|---|---|---|
| YYYY-MM-DD | Initial enrollment | name | pass/fail |
| YYYY-MM-DD | Firmware or configuration change | name | pass/fail |

## Final review

- [ ] Exact model is recorded.
- [ ] AS923-3 compatibility is confirmed.
- [ ] DevEUI was checked against the physical device.
- [ ] Keys are stored outside this repository.
- [ ] Correct device profile is selected.
- [ ] Correct codec is selected or intentionally absent.
- [ ] Join and uplink events were observed.
- [ ] A later uplink was observed.
- [ ] The device was tested at its actual installation site.

Return to [00-README.md](00-README.md) for the complete guide.
