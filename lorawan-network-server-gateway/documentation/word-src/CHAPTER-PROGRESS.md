# Comprehensive LoRaWAN Word Manual — Staged Progress

**One canonical editable file:** `../LoRaWAN-Operator-Manual-WIP.docx` (relative to this directory). Add later chapters to this same OfficeCLI Word document. The Word file is stored directly in the project workspace, not only in a ChatGPT download.

## Completed: Cover + Chapter 1 (21 September 2026)

- Chapter 1 starts **on page 2**, immediately after the cover, and continues through page 4.
- Sections **1.1–1.6**: system purpose and paths, technology explanations, equipment/ULC roles, prerequisites, exact project IDs, and numbered setup order.
- The updated original project-specific diagram `../assets/project-architecture-chapter1-v2.png` is embedded next to section 1.1. It explicitly shows Gateway-01's independent journal/mTLS ingest, both cloud MQTT broker witnesses, trusted verifier and only eligible Fabric anchoring. Its reproducible generator is `../assets/build_project_architecture_v2.py`.
- The distinction between **ChirpStack Gateway OS Base** on Gateway-01 and **cloud ChirpStack** is verified against the project's deployment notes and official Gateway OS documentation.
- 3 editable Word tables have repeating headers and non-splitting rows.
- Four A4 pages were rendered and visually inspected; OfficeCLI DOCX validation and ZIP integrity passed.
- The Grafana login screenshot and official ChirpStack/RAKwireless pictures are saved under `../assets/` for the technology chapters where the corresponding UI or hardware step is explained. They have **not** been inserted as unrelated Chapter 1 decoration.
- No production service or counted research run was changed.

## Completed: Chapter 2 — Gateway-01 / Gateway OS Base (21 September 2026)

- Added to the **same** `../LoRaWAN-Operator-Manual-WIP.docx`, starting page 5, through page 9 (nine pages total including the cover and Chapter 1) after the offline-visual refinement.
- Covers precise custom Gateway OS image basename, byte count and SHA-256, Windows PowerShell hash verification, protected backup boundary, safe flash workflow, management Ethernet/SSH access, safe OpenWrt status commands and quick fault isolation.
- The previously generic RAK5146 line drawing was replaced with the official RAKwireless **RAK5146 Pi HAT product photograph** at the assembly step, showing where the LoRa antenna port differs from GPS. The cropped photo is a vendor reference, not our disconnected Gateway-01/SIM7600 assembly. The project architecture diagram remains beside Chapter 1.
- The stock OS-selection screenshot that highlighted **Raspberry Pi OS** (the wrong user action) was replaced with a real Imager 2.0 screenshot showing **Use custom** selected. The stock Apple storage screenshot was replaced by a real **Windows Imager 2.0** microSD-selection screen with **Exclude system drives checked**. The official erase warning stays exactly by the destructive step and explicitly says the Apple example and Raspberry Pi OS background are not this project's media/settings. All third-party/manufacturer figure sources and limitations are in `../assets/VISUAL-SOURCES.md`. The commissioned `192.168.20.11` Gateway-01 administration screenshot remains pending physical power/network access; never replace it with a stock EU868 configuration and claim it was this gateway.
- Replaced manual 64-character checksum comparison with a copyable PowerShell file name/byte count/SHA-256 guard that prints `IMAGE_VERIFIED=PASS` or stops with `FAIL`; its syntax passed a read-only PowerShell AST check. OfficeCLI Word validation passed and all **nine** pages were rendered and inspected, including the three image pages and code block.
- The authoritative editable Word file is in the project `documentation/` workspace; scratch QA/backup files are only in `documentation/word-src/`.

## Final visual-refinement review of existing chapters — 22 September 2026

- Corrected Figure 1.1: exact EMU-01/Gateway-01/Local MQTT LTE/two cloud MQTT brokers/ChirpStack/one Node-RED SQL writer; independent journal → mTLS ingest → SeaweedFS + both MQTT witnesses → verifier → protected Fabric HRC. Project-owned image and generator are `../assets/project-architecture-chapter1-v2.png` and `../assets/build_project_architecture_v2.py`.
- Replaced Figure 2.1 line-art with an official RAK5146 PiHAT product photo, adjacent to the actual unpowered mounting and LoRa-vs-GPS connector step; the SIM7600 is separately identified as the real project's USB modem, **not** a pictured RAK2013 cellular HAT.
- Replaced wrong stock Raspberry Pi OS highlighted screenshot with Figure 2.2 showing **Use custom** selected; replaced Apple storage example with Figure 2.3 showing actual Windows removable microSD and **Exclude system drives**. Figure 2.4 shows only the real destructive-confirmation action and explicitly rejects its unrelated Apple/card/OS-customisation context.
- Chapter 2 now explicitly instructs **skip Raspberry Pi OS customisation** on the locally loaded approved OpenWrt image; do not copy stock OS settings. All images and third-party/manufacturer credits are mapped to exact steps in `../assets/VISUAL-SOURCES.md`.
- OfficeCLI validation and image-byte checks passed. **Nine pages, five embedded images**; latest Word file rendered to nine PNG pages and each reviewed, without broken figures or clipped paragraphs. No plugged-in Gateway-01/sensor screenshots were fabricated. Same canonical `../LoRaWAN-Operator-Manual-WIP.docx`, not a new independent manual.

## Completed: Chapter 3 — RAK5146 / SX1303 / plain AS923 (22 September 2026)

- Appended to the **same canonical editable Word file**, starting on page 10; 14 A4 pages total, no separate technology DOCX and no PDF.
- Project source is `03-rak5146-as923.md`, with one concise explanation, unpowered SPI/HAT/antenna identification, exact Gateway OS LuCI settings, recorded cloud AS923 frequencies and RX, safe BusyBox checks, local MQTT/forwarder acceptance and targeted troubleshooting. It clearly distinguishes tracked commissioning values from an unplugged gateway's unverified present configuration.
- Figure 3.1 is **RAKwireless's exact RAK2287/RAK5146 Pi HAT pinout** beside the 40-pin SPI seating step. Figure 3.2 is a project-owned **actual UCI-overlay settings worksheet**, labeled **NOT a live LuCI screenshot**, next to the corresponding configuration action. No EU868 stock screenshot was passed off as our AS923 setup.
- The two-page radio/MQTT BusyBox code section was reformatted into four **copyable, compact, shaded command blocks** instead of scattered oversized individual lines; all four passed read-only `bash -n` syntax checks. Their real running-service/RF acceptance remains **deferred** while the hardware is disconnected.
- The vetted cloud source uses uplink channels **923.2 / 923.4 MHz, 125 kHz, SF7–12** and RX2 **923.2 MHz / DR2**. The **historical** gateway multi-SF span 923.2–924.6 MHz is not represented as freshly measured individual live channels. Exact active frequencies require the powered Gateway-01.
- All 14 pages were rendered to PNG and visually reviewed; no empty orphan page, floating figure, cropped table or overflowing code line. OfficeCLI validates the DOCX.

## Completed: Chapter 4 — SIM7600 LTE field backhaul (22 September 2026)

- Appended to the **same** canonical Word document; 19 A4 pages total, Chapter 4 starts page 15 and runs through page 19. Three new, numbered visuals accompany their exact hardware, QMI and routing steps; ten embedded pictures across the book.
- Correct model: Waveshare SIM7600G-H **USB dongle**, not the SIM7600 Raspberry Pi HAT. Illustrations are one project-drawn model-specific hardware/port diagram and two project-specific settings/routing diagrams from the repository, all visibly identified as **not real photos/screenshots of unplugged Gateway-01**. Third-party manufacturer/retailer photo downloads returned HTTP 403; no wrong HAT photo substituted.
- Exact commissioned values: DITO `internet.dito.ph`, `/dev/cdc-wdm0` + `wwan0`, netifd `defaultroute=0` / `dhcp=0` / `peerdns=1`, independent `lte-route-health` metric-10 LTE Internet default, management-only br-lan, cloud MQTT `:8883` and two bridge sessions. All current-state verifications are explicitly deferred until gateway is physically powered.
- Four read-only Gateway-01 BusyBox blocks were syntax-checked with `bash -n`; four passed. The LTE repair/radio changing AT commands are not presented as ordinary preflight. No secrets, live service changes, PDF or counted RF run.
- OfficeCLI validate passed and every one of the 19 rendered pages was reviewed. Removed trailing orphan page and prevented the three-line MQTT diagnostic block splitting across pages.

## Screen-by-screen audit of Chapters 1–4 — 22 September 2026

- Audited each chapter's figures against numbered steps in `SCREEN-BY-SCREEN-QA-CHAPTERS1-4.md`. With Gateway-01 and sensors disconnected, Chapters 3 and 4 contain project-verified configuration worksheets and authentic manufacturer hardware references, but **no fake live Gateway-01 LuCI screenshots**. Screens requiring actual gateway/sensor state are enumerated for future real capture.
- Chapter 2 gained two **genuine GUI screenshots**: Raspberry Pi Imager v2 with the **correct Raspberry Pi 4 selected**, and the official **Writing Summary** used explicitly as a STOP example because its Pi5/stock PiOS/Apple SDXC values are wrong for this project. Source steps now call these Screen 2A and 2B and require the approved custom `.img.gz` and actual SD target before Write.
- Repaired figure/caption pagination so the wrong-example Writing Summary and its **STOP** caption remain on the same page. All 20 A4 pages rendered and checked. The Word file now has **12 embedded visuals**. OfficeCLI validate and original Chapter 1–4 preservation PASS. No hardware flashed, no actual device/UI status fabricated.

## Completed: Chapters 5–6 and actual Gateway-01 screens (22 September 2026)

- The canonical editable Word file now contains **Chapters 1–6**. Chapter 5 documents the persistent local Mosquitto buffer and two separately authenticated cloud bridges. Chapter 6 documents cloud ChirpStack v4.19.1 operator navigation and the registered Gateway-01 / EMU-01 path.
- Through jervis-hijo and an actual powered Gateway-01, authenticated LuCI screens were saved under `../assets/live-gateway-20260922/` (no gateway changes). Nine step-matched screenshot placements were added across Chapters 2–5 using OfficeCLI. Chapter 6 retains its actual project login and operator overview screens; additional gateway/device profile/event screens remain to insert.
- Verified and corrected the Word instructions for current ChirpStack **LoRaWAN frames** tab, tenant-level Device Profiles, **Applications → dissertation-sensors → Devices**, and OpenWrt Network → Interfaces → **Edit lte**. SEC-01 is not claimed registered merely because EMU-01 is registered.
- Complete visual gaps are documented in `SCREEN-BY-SCREEN-AUDIT-CHAPTERS1-6-20260922.md`; do not label the full book 100% screenshot-compliant yet. In particular, actual cloud device frames/events and sanitized Mosquitto buffer/TLS terminal captures remain to insert; accepted Raspberry Pi Imager writing summary requires the approved image/card at a real workstation.
- OfficeCLI validation passed. Native Word pagination reported **33 pages**; independent A4 rendering produced **34 pages** inspected for meaningful layout issues. The canonical WIP file was backed up before publication as `.canonical-before-screen-by-screen-20260922.docx`.

## Screen 6B correction and full ChirpStack visual run (22 September 2026)

- Rejected the blank/loading Screen 6B that exposed unrelated browser tabs; used a dedicated single-tab Firefox window authenticated to the real ChirpStack v4.19.1 tenant and waited until the dashboard had visibly rendered. Replaced the published screen and shortened both 6A/6B captions. Cropped the genuine login source for readable fields.
- Captured and inserted Screens 6C–6J beside the appropriate steps: gateway list, Gateway-01 dashboard and LoRaWAN frames, tenant device profiles, applications, EMU-01 list/overview and real Events. No credentials or OTAA keys were captured. The authentic dashboard screenshot was cropped only to exclude a blank map panel not relevant to the check.
- Corrected all nine earlier Gateway-01 UI screenshots from forced 14.7×10 cm to undistorted 14.7×8.56 cm. Preserved original source captures, the previous Word state and reproducible OfficeCLI insertion/capture scripts.
- The updated reviewed DOCX passed OfficeCLI validation; independent A4 rendering produced 37 pages with captions alongside their pictures. Remaining genuine-screen gaps are recorded in `SCREEN-BY-SCREEN-AUDIT-CHAPTERS1-6-20260922.md`.

## Expanded full-screen and first-time cloud setup (22 September 2026)

- The cropped Screen 6G Applications listing was replaced with a genuine Firefox full-page capture preserving the entire page, from tenant navigation through the application listing and footer. Do not reuse the former 900px viewport image as the full page.
- Added section 6.1A **before** the existing Chapter 6 gateway checks: a first-time and duplicate-aware Add gateway → compatible AS923 profile → Add application → Add device → securely configure OTAA key → join/uplink verification process. Five actual **full-page screenshots** (Add gateway, Add profile, commissioned EMU-01 profile, Add application, Add device) are embedded beside the numbered steps. Existing keys are not shown, and nothing was submitted or duplicated just for photographs.
- Updated Chapter 6 name to include setup and registration; removed stale Chapter 3 claim that gateway/sensor are unplugged. The previously commissioned EUI, real registered EMU-01 and AS923 version are preserved.
- OfficeCLI validation passed and independently rendered **41 A4 pages** were checked after the insertion. All five onboarding placeholders were resolved and the book has **36 embedded visual assets**. The canonical Word was backed up before publication as `.before-first-time-cloud-setup-20260922.docx`.
- This is **not yet a complete full-infrastructure setup book**: see `FULL-SETUP-SCREEN-COVERAGE-AUDIT.md` for each chapter's remaining first-build screens. Chapter 2 approved SD writing summary, Chapter 3 full channel/hardware photos, Chapter 4 complete LTE and live route readout, Chapter 5 provisioning and sanitized live broker/bridge evidence, and the EMU/SEC physical firmware chapter remain.

## Expanded full-page Gateway OS, radio, LTE and MQTT coverage (22 September 2026)

- Isolated headless Chromium captured Gateway-01 LuCI without activating or typing into the user's desktop browser. Nine previous truncated operator screens in Chapters 2–5 were replaced with project-authentic complete views where the UI allowed full capture. Concentratord SX1302/SX1303 and Global, backup, Interfaces and LTE General controls are legible; MQTT Forwarder's 1936px full form is embedded as two overlapping segments covering `as923`, the loopback broker, QoS 1, session settings and Save.
- The nested scrolling **LTE Advanced** modal remained clipped at the lower controls even with a taller isolated capture. Word captions acknowledge this limitation and direct operators to the effective CLI/UCI check rather than claim false full-page coverage.
- A bounded password-authenticated, read-only Gateway-01 inspection captured actual persistence/queue, loopback listener, two distinct mTLS bridges and current LTE/TCP details. Screens 4D and 5C/5D are faithful command-output panels sourced from `assets/live-gateway-fullpage-headless-20260922/read-only-gateway-operator-output.json`; not counted-study results or invented terminal UIs. The LTE sample displayed no default route at that instant, so the caption specifically requires retesting before LTE PASS.
- Fixed OpenWrt BusyBox's missing `hostname` command to `uname -n` and clarified effective LTE UCI `pdptype=IP` versus the live LuCI label. Removed orphan figure-credits/transition pages and retained source credits in `assets/VISUAL-SOURCES.md`.
- The canonical Word now renders to **43 A4 pages**, contains **41 embedded images**, has clean ZIP structure and passed OfficeCLI validation. An identical reviewed candidate and the pre-revision canonical backup remain in `word-src/`. No production configuration, gateway radio settings or user-facing desktop browser session was changed.

## Next: Finish the genuine screen-by-screen captures, then continue downstream technology chapters

Continue one chapter at a time and keep the same canonical DOCX. Capture the authorized project screens next to their exact user action. The comprehensive Word book is still a working draft; methodology, recovery and remaining technologies will be added after checking their live source and commands. No PDF deliverable.
