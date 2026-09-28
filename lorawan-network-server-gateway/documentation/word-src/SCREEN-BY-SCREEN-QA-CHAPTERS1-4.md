# Screen-by-screen visual QA — Chapters 1–4 (22 September 2026)

Scope: one canonical editable Word file `documentation/LoRaWAN-Operator-Manual-WIP.docx`. Work chapter-by-chapter; do not create separate technology manuals or a PDF.

| Chapter / operator action | Visual currently in Word | Verified provenance / next action |
|---|---|---|
| 1 — identify project routes | Exact project architecture diagram | Source configuration schematic, **not a live screenshot**. |
| 2 — seat RAK5146 and check LoRa antenna | RAKwireless exact Pi HAT photo | Real vendor photo; actual Gateway-01 photo when powered/accessible. |
| 2 — identify correct Pi before flashing | **Screen 2A: Pi4 selected in Imager v2** | Real third-party Imager v2 screen, image includes source's video-player strip outside app. |
| 2 — select image type | **Use custom** selected | Real Imager v2 image; this is NOT choosing Raspberry Pi OS. |
| 2 — select destination | Windows storage screen with removable SD and Exclude system drives | Real Imager v2 reference, example reader differs from operator hardware. |
| 2 — confirm correct image and destination | **Screen 2B: official Writing Summary as explicit WRONG EXAMPLE** | Real official screen shows Pi5, stock PiOS and Apple SDXC; instruct **BACK, NOT WRITE**, until the operator's actual summary shows Pi4, exact verified custom file and their SD card. Cannot show a genuine accepted project-specific Writing Summary without loading the actual accepted image and card. |
| 2 — irrevocable erase dialog | Official erase-warning screenshot | Identify actual target name before action. |
| 2 — first real gateway LuCI/SSH/backup | **No live screenshot**, hardware disconnected | Capture actual `192.168.20.11` login (empty fields), System → Backup/Flash Firmware screen, first OpenWrt shell and OS identity when powered. Redact secrets/token/other desktops. |
| 3 — SPI HAT seating | RAKwireless 40-pin HAT pinout | Real official technical drawing. |
| 3 — Global/Active SX1302 settings | Project UCI-overlay worksheet, clearly **not a screenshot** | Capture actual Gateway-01 LuCI **ChirpStack → Concentratord → Global**, then **SX1302/SX1303** AS923/Rak5146/SPI/antenna fields after hardware available. Never show official EU868/USB example as this setup. |
| 4 — identify USB dongle | Project drawing derived from correct Waveshare dongle | Replace with actual unit photo or exact official model photograph when accessible; never use similar Waveshare HAT. |
| 4 — LTE interface/QMI | Actual UCI-derived worksheet, not live screen | Capture **Network → Interfaces → lte → General/Advanced** including QMI, APN, device, DNS/default-route controls when powered. |
| 4 — traffic route | Commissioned production-versus-management diagram | Capture current `wwan0` IP/route and two existing :8883 sockets (no private keys) when powered. |

**Web/UI source verification:** Raspberry Pi's official Imager manual documents Device → OS/Use Custom → Storage → Writing Summary → erase confirmation → writing/verification → Done. The project does not have Raspberry Pi Imager installed on its remote workstation, so screenshots are sourced from actual matching UI captures and marked as reference; it has NOT flashed a card for pictures. [Official workflow](https://www.raspberrypi.com/documentation/computers/getting-started.html).

**Do not fabricate:** powered Gateway-01 management pages, live SX1303 multi-SF channels, LTE radio signal readings, sensors and ChirpStack uplinks while the physical hardware is disconnected. No secrets or unsupported PASS claims in images.

**Quality gate:** export canonical to a uniquely named DOCX for user (avoid stale filename cache), render all pages, inspect each newly affected page at native resolution, ensure screenshots and their captions do not split and a screenshot of wrong values is explicitly labeled before pressing an irreversible Write.
