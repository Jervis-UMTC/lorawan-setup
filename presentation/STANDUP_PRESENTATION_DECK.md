# Weekly Standup Presentation Deck
**Project:** Local Setup Progress, Technical Discoveries & Real-World Agricultural Ideas  
**Presenter:** Jervis James Pedotim - Intern  
**Interactive Deck:** [presentation/index.html](file:///c:/Users/admin/Documents/lorawan-setup/presentation/index.html)

---

## User-Provided Technology Logos Used
- **LoRaWAN**: `LoRaWAN_Logo.svg.webp` (standalone logo badge, height: 28px)
- **ChirpStack**: `chirpstack.png` (standalone logo badge, height: 28px)
- **PostgreSQL**: `Postgresql_elephant.svg` (standalone logo badge, height: 28px)
- **Grafana**: `grafana.webp` (standalone logo badge, height: 28px)
- **Node-RED**: `node-red-icon.svg` (icon badge + Node-RED text)
- **Raspberry Pi 4**: `Raspberry-Pi-Logo-2012.png` (standalone logo badge, height: 28px)
- **Hyperledger Fabric**: `hyperledgerfabric.png` (standalone logo badge, height: 28px)

---

## Hardware Checklist Alignment (`hardware-checklist.pdf`)
- **RAKwireless WisBlock Platform**: Modular RAK4631 Nordic MCU + RAK19007 WisBlock Base Board with solar harvesting.
- **RAKwireless Soil NPK Sensor**: Industrial RS485 Modbus Soil NPK Sensor (measuring Nitrogen, Phosphorus, Potassium).
- **RAKwireless Base Station**: Raspberry Pi 4 + RAK5146 SPI LoRaWAN Concentrator Card with outdoor antenna.

---

## Slide Outline & Tech Badges

### Slide 1: Weekly Standup
* **Title:** Weekly Standup
* **Subtitle:** Local Setup Progress, Technical Discoveries & Real-World Agricultural Ideas
* **Presenter:** Jervis James Pedotim - Intern
* **Tech Badges:** LoRaWAN | ChirpStack | PostgreSQL | Grafana | Node-RED | Raspberry Pi 4 | Hyperledger Fabric

---

### Slide 2: Problem Statement
* **Title:** The Agricultural Field Data Gap
* **Subtitle:** Why traditional farm monitoring methods fail to deliver real-time field visibility.
* **Tech Badges:** Cellular SIM
* **The Limits of Standard Weather Stations:** Regional weather stations only measure ambient air on elevated towers miles away, completely missing localized canopy microclimates, greenhouse humidity pockets, and low-lying frost valleys where crops actually live and grow.
* **High Costs & Commercial Vendor Lock-In:** Proprietary commercial farm sensors require expensive per-device SIM subscriptions ($5–$10/month per node) and lock farm data behind proprietary cloud paywalls, making wide-scale deployment cost-prohibitive.

---

### Slide 3: Wireless Architecture
* **Title:** Long-Range, Zero-Subscription Field Coverage
* **Subtitle:** Establishing a private, low-cost LoRaWAN wireless network across farm terrain.
* **Tech Badges:** LoRaWAN (`LoRaWAN_Logo.svg.webp`)
* **Multi-Kilometer Canopy Penetration:** Long-range LoRaWAN radio signals travel 5 to 15 kilometers across farm terrain, easily passing through dense crop foliage, tree lines, and greenhouse structures where higher-frequency Wi-Fi drops within 50 meters.
* **Zero Monthly Data Fees & Complete Privacy:** One central base station gateway manages hundreds of field sensors for **$0 monthly data fees**, keeping operating expenses minimal while securing 100% data ownership.

---

### Slide 4: ChirpStack Core Server
* **Title:** Macro vs. Microclimate Intelligence
* **Subtitle:** Moving from general weather forecasts to canopy-level crop protection with ChirpStack.
* **Tech Badges:** ChirpStack v4 (`chirpstack.png`)
* **What I Explored in My Local Setup:** Configured our central ChirpStack network server locally in our lab environment to process multi-sensor data streams. As I set up the decoders, I realized how dense, ultra-low-power sensor arrays can capture micro-variations across different crop zones instead of relying on a single weather station.
* **Real-World Impact (Disease Prevention):** Fungal blights and crop diseases thrive in localized humidity pockets inside crop canopies long before regional humidity changes. Continuous canopy tracking lets agronomists predict disease risks days early and apply targeted crop protection only where needed.

---

### Slide 5: Offline Access Point Mode
* **Title:** Surviving Internet Dead Zones
* **Subtitle:** Ensuring farm operations never halt when cloud connections drop.
* **Tech Badges:** Gateway AP Mode (`LoRaWAN_Logo.svg.webp`)
* **What I Configured & Tested Locally:** Configured our gateway to broadcast its own local Wi-Fi Access Point and set up direct network routing on our server VM. Created simple one-click controls to toggle smoothly between local gateway mode and internet mode during local testing.
* **Real-World Impact (Remote Field Resilience):** Remote farmland frequently suffers from zero cellular coverage. Local edge processing ensures zero data loss during internet outages. Enables technicians walking into disconnected fields to connect their tablets directly to the gateway's local Wi-Fi to inspect live crop health on-site.

---

### Slide 6: PostgreSQL & Grafana
* **Title:** Data Sovereignty & Visual Farm Scoreboards
* **Subtitle:** Storing readings safely in PostgreSQL and turning data into clear Grafana scoreboards.
* **Tech Badges:** PostgreSQL (`Postgresql_elephant.svg`) | Grafana (`grafana.webp`)
* **What I Configured & Tested Locally:** Connected a local PostgreSQL database to record sensor uploads and built visual Grafana scoreboards with color-coded gauges and trend graphs. Storing data locally in a flexible format allows us to add new types of sensors in the future without changing our database setup.
* **Real-World Impact (Data Sovereignty):** All farm history remains stored on our own equipment—no third-party cloud vendors locking our farm data behind subscription paywalls. Replaces manual field check trips with clear visual screens (soil moisture, temperature, humidity) and lets managers compare trends across crop seasons.

---

### Slide 7: Node-RED Automation
* **Title:** An Automated 24/7 Digital Farm Watchman
* **Subtitle:** Bridging field data directly to automated physical hazard protection using Node-RED.
* **Tech Badges:** Node-RED (`node-red-icon.svg`)
* **What I Configured & Tested Locally:** Wired automated logic rules in Node-RED using our local test environment to monitor live sensor streams against safety limits. This showed me how raw sensor numbers can be processed in milliseconds to drive automated actions instead of waiting for a human operator to log into a dashboard.
* **Real-World Impact (Proactive Defense):** System acts like an automated 24/7 watchman—immediately sending an SMS alert to farm managers if temperatures drop toward freezing or if soil gets dangerously dry. Can directly activate automated irrigation valves during emergencies, protecting crops before damage occurs.

---

### Slide 8: Soil NPK Sensing
* **Title:** Real-Time Soil NPK Nutrient Intelligence
* **Subtitle:** Replacing slow off-site lab testing with live root-zone soil monitoring using RAKwireless sensors.
* **Tech Badges:** RAKwireless Soil NPK Sensor
* **The Traditional Soil Testing Problem:** Standard soil testing requires taking manual soil core samples, mailing them to off-site labs, and waiting 2–3 weeks for lab results—leading to blind over-fertilization, high fertilizer expenses, and chemical runoff.
* **Real-World Impact (RAKwireless Soil NPK Sensing & ROI):** Integrating the industrial **RAKwireless RS485 Soil NPK Sensor** allows measuring **Nitrogen (N), Phosphorus (P), and Potassium (K)** directly in root soil in real time—enabling precision fertilization that cuts fertilizer expenses, boosts crop yield, and protects soil quality.

---

### Slide 9: Hardware & Blockchain Roadmap
* **Title:** Next Phase: Prototyping & Blockchain Integrity
* **Subtitle:** Building RAKwireless WisBlock nodes and logging telemetry to a private Hyperledger Fabric blockchain.
* **Tech Badges:** Raspberry Pi 4 (`Raspberry-Pi-Logo-2012.png`) | Hyperledger (`hyperledgerfabric.png`)
* **What I Plan to Build & Experiment:** For our next phase, I will assemble modular **RAKwireless WisBlock** solar sensor nodes (RAK4631 MCU + RAK19007 baseboard) and build a custom base station gateway using a Raspberry Pi 4 with an outdoor antenna (RAK5146 card). Test the **RAKwireless Soil NPK Sensor** and explore uploading telemetry logs to a private **Hyperledger Fabric** blockchain network.
* **Real-World Impact (Hyperledger Traceability):** Uploading telemetry to a Hyperledger Fabric blockchain creates tamper-proof records of soil nutrients, microclimate history, and irrigation events. Provides food distributors and auditors with verifiable proof of sustainable farming for organic certification and supply chain transparency.

---

### Slide 10: Summary & Next Steps
* **Title:** Summary & My Internship Takeaways
* **Subtitle:** Reflecting on completed setup milestones and the roadmap ahead.
* **What We've Achieved So Far (Lab Setup):**
  * Configured & verified ChirpStack server decoders locally
  * Set up and tested gateway offline AP mode locally
  * Established local PostgreSQL database & Grafana scoreboards
  * Wired Node-RED rule engine for instant hazard alerts
* **My Next Steps (Prototyping Roadmap):**
  * Build Raspberry Pi 4 gateway base station (RAK5146 card)
  * Assemble RAKwireless WisBlock solar field node prototypes
  * Connect & calibrate RAKwireless Soil NPK sensor
  * Integrate Hyperledger Fabric blockchain for immutable data logging

---
*Maintained under project lorawan-setup/presentation*
