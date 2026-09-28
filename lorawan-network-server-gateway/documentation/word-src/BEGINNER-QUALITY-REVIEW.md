# Word manual beginner-readability audit — 21 September 2026

**Canonical editable file:** `../LoRaWAN-Operator-Manual-WIP.docx` (relative to this directory). The Word document is not one page. The current version has **eight A4 pages**: cover p1, Chapter 1 pp2–4, Chapter 2 pp5–8. The first Word copy previously shared in the conversation was **95,070 bytes and four pages** (cover + Chapter 1 only); the workspace file was **460,868 bytes and eight pages** before the cover-label correction. The most recent review used the canonical workspace file and rendered all eight pages.

## What passed

- The Chapter 1 heading is visible on page 2 and an original two-lane project architecture image appears immediately under the explanation.
- Chapter 2 starts on page 5, includes eight numbered sections, the project's commissioned custom Gateway OS image basename/size/SHA-256, exact Windows PowerShell and gateway OpenWrt shell labels, mounting reference credited to RAKwireless, verified boot/management checks and a brief fault-isolation table.
- Actual DOCX XML contains editable Word text, three editable tables and two embedded images. It is not a flattened one-page picture.
- OfficeCLI validation passed; project images display in rendered pages.
- The cover now identifies **Chapters 1–2 / eight pages** to distinguish a one-page attachment preview from the document itself.

## Not yet fully beginner-proof — release blockers to address chapter by chapter

1. **Incomplete book**: only Gateway OS and system overview are written. The concentrator radio, LTE, MQTT, HA database, ChirpStack, sensor assembly, evidence/Fabric, Grafana and research procedures are not yet in the Word file. Do not call it the finished deployment/recovery manual.
2. **Custom image retrieval**: Chapter 2 describes the approved image/hash but does not provide a one-click exact location/approved retrieval path for a new operator who lacks the current protected build artifact. Resolve from the real image manifest/protected custody before commissioning a new card.
3. **PowerShell hash command**: prints size and SHA-256, but a novice must visually compare a 64-character digest. Replace with one self-checking block that prints PASS or stops with a clear mismatch.
4. **Screenshots**: the manufacturer RAK5146 image is clearly identified as a reference. The real commissioned Gateway-01 web login and its actual AS923 configuration screen were not reachable to capture during this session. Do not misrepresent the stock vendor example (which may display EU868) as this system.
5. **Readability**: the actual code is copyable, but its Consolas font is 8.5 pt in the first draft; use at least comfortably readable text and wrap/split long pipelines before calling this accessible to a beginner. Render every page after changes.
6. **Protected recovery**: Chapter 2 tells the operator which queue/cert/journal sets to preserve but does not yet give every complete protected export and restore command. Include those in the eventual recovery chapter and put an explicit pointer within the Word book.
7. **First-boot administration**: distinguish commissioned protected root access at `192.168.20.11` from official generic Gateway OS first-boot instructions. The stock public image and Raspberry Pi OS are NOT equivalent to the project's commissioned custom image.

## Displaying the actual document

Open/download the **latest** canonical `LoRaWAN-Operator-Manual-WIP.docx`, not the previously downloaded 95 KB Chapter 1 snapshot. Open in Microsoft Word and choose **Print Layout** to view page boundaries; a chat file-card preview may show only a first-page thumbnail and does not establish page count. The cover says Chapters 1–2 and eight pages. An eight-page renderer check is the evidence for page count.

## External documentation cross-check

- ChirpStack Gateway OS official [Raspberry Pi installation](https://www.chirpstack.io/docs/chirpstack-gateway-os/install/raspberry-pi.html) and [Getting started](https://www.chirpstack.io/docs/chirpstack-gateway-os/getting-started.html): Base forwards to an external server; stock first-boot network and credentials do not override commissioned private configuration.
- RAKwireless official [RPi DIY Gateway assembly](https://docs.rakwireless.com/product-categories/accessories/rak-rpi-diy-gateway-kit/installation-guide/): reference for RAK5146 mounting and LoRa/GNSS connectors, not evidence that the project's SIM7600 assembly matches the manufacturer's cellular variant.
- Microsoft [Word print layout and mobile view](https://support.microsoft.com/en-us/word/use-word-views-to-read-or-edit-your-document): the app can show differently paginated reading and print layouts. Use Print Layout to verify the eight-page document.
