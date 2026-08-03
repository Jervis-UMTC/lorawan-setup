# Volume 08: Hyperledger Fabric Blockchain & Crop Traceability Engineering Handbook

## Executive Summary & Educational Purpose

This handbook covers permissioned enterprise blockchain architecture, distributed ledger technology, smart contract chaincode development, and cryptographic telemetry logging using **Hyperledger Fabric**. Designed for enterprise software architects, security engineers, and supply chain compliance auditors, this text details how to build an immutable digital ledger that records farm microclimate telemetry, fertilizer application logs, and irrigation events to provide verifiable proof of organic farming practices for distributors, retailers, and food auditors.

---

## 1. Public vs. Permissioned Enterprise Blockchain Architecture

Unlike public unpermissioned blockchains (e.g. Ethereum or Bitcoin) which require proof-of-work mining and charge expensive gas fees per transaction, **Hyperledger Fabric** is an open-source permissioned enterprise blockchain framework hosted by The Linux Foundation.

```text
+-----------------------------------------------------------------------------------+
|                        Hyperledger Fabric Architecture                            |
|                                                                                   |
|  • Permissioned Access: All participating nodes (Farms, Distributors, Auditors)   |
|    have verified identities issued by X.509 Certificate Authorities (CAs).        |
|  • Zero Gas Fees: Transactions are executed and endorsed without cryptocurrency.   |
|  • High Throughput: 2,000+ transactions per second (TPS) with sub-second finality.|
|  • Channel Isolation: Private channels keep farm business data confidential.      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Hyperledger Fabric Network Topology

A Hyperledger Fabric network for agricultural supply chains consists of Organizations (Orgs), Peer Nodes, Ordering Services, and Private Channels.

```text
                               +---------------------------------------+
                               |    Raft Ordering Service (Orderers)   |
                               | (Consensus & Block Batching Engine)   |
                               +---------------------------------------+
                                                   ^
                                                   | Block Ordering
                                                   v
+---------------------------------------------------------------------------------------------------+
|                            Private Channel: `agri-crop-traceability`                              |
|                                                                                                   |
|  +-----------------------------------+   +----------------------------------+   +--------------+  |
|  | Org 1: Smart Agri Farm Peer       |   | Org 2: Distributor / Retail Peer |   | Org 3:       |  |
|  | • Host: `peer0.farm.agri.com`     |   | • Host: `peer0.distributor.com`  |   | Organic      |  |
|  | • Ledger World State (CouchDB)    |   | • Ledger World State (CouchDB)   |   | Certification|  |
|  | • Chaincode: `crop-telemetry-cc`  |   | • Reads Immutable Ledger         |   | Auditor Peer |  |
|  +-----------------------------------+   +----------------------------------+   +--------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Endorsement Pipeline & Consensus Workflow

Hyperledger Fabric processes transactions in three distinct phases: **Execute/Endorse ➔ Order ➔ Validate & Commit**.

```text
[ Client (Node-RED) ] ──(1. Submit Tx)──> [ Endorsing Peers ]
        │                                         │
        │                               (2. Execute Chaincode & Sign)
        │ <───(3. Return Endorsement Signature)───┘
        │
        ├──(4. Send Signed Block)──> [ Raft Orderer ]
                                           │
                                 (5. Package Block)
                                           │
                                           v
                             [ Commit Block To Ledger ] ──> [ Update CouchDB World State ]
```

---

## 4. Production Smart Contract (Chaincode) in Go (`crop_telemetry.go`)

Chaincode defines the business logic and ledger state mutation functions. Below is a production Go smart contract for logging crop telemetry and verifying organic compliance.

```go
package main

import (
	"encoding/json"
	"fmt"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// CropTelemetryRecord defines the structure of stored telemetry
type CropTelemetryRecord struct {
	ID             string  `json:"id"`             // Unique Tx ID or Batch ID
	Timestamp      string  `json:"timestamp"`      // UTC Timestamp
	DevEUI         string  `json:"dev_eui"`        // LoRaWAN Sensor ID
	FarmZone       string  `json:"farm_zone"`      // Farm Location / Zone
	SoilMoisture   float64 `json:"soil_moisture"`  // Volumetric Water Content %
	NitrogenPPM    float64 `json:"nitrogen_ppm"`   // N Level
	PhosphorusPPM  float64 `json:"phosphorus_ppm"` // P Level
	PotassiumPPM   float64 `json:"potassium_ppm"`  // K Level
	OrganicStatus  bool    `json:"organic_status"` // Compliance Status
}

// SmartContract provides functions for managing crop records
type SmartContract struct {
	contractapi.Contract
}

// RecordTelemetry logs a new sensor uplink to the immutable blockchain ledger
func (s *SmartContract) RecordTelemetry(ctx contractapi.TransactionContextInterface, 
	id string, timestamp string, devEUI string, farmZone string, 
	moisture float64, n float64, p float64, k float64) error {

	// Verify if record already exists
	exists, err := s.RecordExists(ctx, id)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("the record %s already exists on the ledger", id)
	}

	// Determine organic compliance (e.g. Nitrogen must not exceed 60 ppm threshold)
	isOrganic := n <= 60.0

	record := CropTelemetryRecord{
		ID:            id,
		Timestamp:     timestamp,
		DevEUI:        devEUI,
		FarmZone:      farmZone,
		SoilMoisture:  moisture,
		NitrogenPPM:   n,
		PhosphorusPPM: p,
		PotassiumPPM:  k,
		OrganicStatus: isOrganic,
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	// Write immutable state to ledger key-value world state
	return ctx.GetStub().PutState(id, recordJSON)
}

// RecordExists returns true when asset with given ID exists in world state
func (s *SmartContract) RecordExists(ctx contractapi.TransactionContextInterface, id string) (bool, error) {
	recordBytes, err := ctx.GetStub().GetState(id)
	if err != nil {
		return false, err
	}
	return recordBytes != nil, nil
}

// QueryTelemetryHistory retrieves complete tamper-proof audit trail for a crop batch
func (s *SmartContract) QueryTelemetryHistory(ctx contractapi.TransactionContextInterface, id string) ([]CropTelemetryRecord, error) {
	resultsIterator, err := ctx.GetStub().GetHistoryForKey(id)
	if err != nil {
		return nil, err
	}
	defer resultsIterator.Close()

	var records []CropTelemetryRecord
	for resultsIterator.HasNext() {
		response, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		var record CropTelemetryRecord
		err = json.Unmarshal(response.Value, &record)
		if err != nil {
			return nil, err
		}
		records = append(records, record)
	}

	return records, nil
}

func main() {
	cc, err := contractapi.NewChaincode(&SmartContract{})
	if err != nil {
		panic(fmt.Sprintf("Error creating crop-telemetry chaincode: %s", err))
	}
	if err := cc.Start(); err != nil {
		panic(fmt.Sprintf("Error starting crop-telemetry chaincode: %s", err))
	}
}
```

---

## 5. Consumer Organic Certification Audit Flow

```text
[ LoRaWAN Field Sensor ] ──> [ Node-RED ] ──> [ Hyperledger Fabric Ledger ]
                                                      │
                                           (Cryptographic Block Hash)
                                                      │
                                                      v
[ Consumer QR Code Scan ] <── [ Distributor Audit Portal ] <── [ Organic Certification ]
```

### Key Benefits

1. **Unalterable Audit Trails**: Neither farm managers nor cloud operators can alter historical NPK nutrient levels or chemical application logs after block commitment.
2. **Organic Certification Premium**: Enables organic compliance auditors to query `GetHistoryForKey()` to verify zero synthetic chemical over-application across the entire growing season.
3. **Consumer Trust & QR Verification**: Food packaging can print QR codes linked to the Hyperledger transaction hash, allowing retail consumers to verify farm-to-table sustainability.

---
*Maintained under project `lorawan-setup/technology-docs`.*
