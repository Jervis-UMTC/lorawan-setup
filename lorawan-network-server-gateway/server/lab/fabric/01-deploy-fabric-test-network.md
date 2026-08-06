# Fabric 1. Deploy an Isolated Test Network

Run Fabric on a second Ubuntu Server VM on the same host computer. This simulates a separately operated blockchain environment and prevents Fabric dependencies from becoming part of the LoRaWAN application server.

## Step 1: Create the Fabric VM

Starting estimate for a small two-organization test network:

```text
CPU: 4 virtual CPUs
Memory: 8 GB
Disk: 60 GB dynamically allocated
Network: bridged or external virtual switch
Hostname: fabric-lab
IP: <FABRIC_VM_IP_ADDRESS>
```

These resource values are a planning estimate, not a Fabric requirement. Confirm the host has enough remaining CPU, memory, and disk, then record observed utilization during the test. Use an SSH key, apply operating-system updates, enable time synchronization, and restrict SSH to `<MANAGEMENT_SUBNET_CIDR>`.

## Step 2: Install prerequisites

Install Docker Engine using the maintained host procedure referenced by [Server 2. Deploy ChirpStack](../setup/02-deploy-chirpstack.md), then install the remaining tools:

```bash
sudo apt update
sudo apt install -y git curl jq build-essential ca-certificates openssl
sudo docker version
sudo docker compose version
git --version
jq --version
```

Use `sudo docker` unless Docker-group membership is explicitly approved.

## Step 3: Download Fabric with explicit versions

The official installer script is stored in the Fabric repository. Do not execute a moving `main` URL without recording the exact source revision. Resolve and review a repository commit first:

```bash
mkdir -p ~/fabric-lab
cd ~/fabric-lab

git ls-remote https://github.com/hyperledger/fabric.git refs/heads/main
export FABRIC_INSTALL_SCRIPT_COMMIT='<REVIEWED_40_CHARACTER_FABRIC_COMMIT>'
test "${#FABRIC_INSTALL_SCRIPT_COMMIT}" -eq 40

curl -fsSLo install-fabric.sh \
  "https://raw.githubusercontent.com/hyperledger/fabric/${FABRIC_INSTALL_SCRIPT_COMMIT}/scripts/install-fabric.sh"
chmod 700 install-fabric.sh
sha256sum install-fabric.sh
./install-fabric.sh -h
```

Keep the reviewed 40-character commit and calculated script checksum with the lab configuration so the installer source can be reproduced. Review the script before execution. Select compatible Fabric and Fabric CA releases from the official documentation, then use explicit versions:

```bash
./install-fabric.sh \
  --fabric-version <FABRIC_VERSION> \
  --ca-version <FABRIC_CA_VERSION> \
  docker binary samples
```

After installation, capture the actual sample revision, binary version, and image IDs used by this lab:

```bash
cd ~/fabric-lab/fabric-samples
git status --short --branch
git log -1 --oneline
bin/peer version
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep hyperledger
```

Do not use unrecorded `latest` images for repeatable testing.

## Step 4: Start the test network with certificate authorities

```bash
cd ~/fabric-lab/fabric-samples/test-network
./network.sh down
./network.sh up createChannel -ca -c lorawanlab
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Run `network.sh down` only when intentionally resetting the disposable lab. It removes generated identities, containers, and ledger volumes.

## Step 5: Deploy a known sample chaincode

Use the sample chaincode first to prove that the network itself works:

```bash
./network.sh deployCC \
  -c lorawanlab \
  -ccn basic \
  -ccp ../asset-transfer-basic/chaincode-go \
  -ccl go
```

Then run the official sample application or CLI query. A successful sample transaction proves the Fabric lab, not the telemetry contract.

## Step 6: Deploy the telemetry-attestation chaincode

The Fabric team must approve the contract in [`server/integrations/hyperledger-fabric/04-data-contract-and-chaincode.md`](../../integrations/hyperledger-fabric/04-data-contract-and-chaincode.md).

This repository does not currently contain the telemetry-attestation chaincode source. **Stop here if `<ATTESTATION_CHAINCODE_SOURCE_PATH>` does not resolve to reviewed source code.** The sample asset contract is not a substitute.

Deploy the approved source:

```bash
./network.sh deployCC \
  -c lorawanlab \
  -ccn <ATTESTATION_CHAINCODE_NAME> \
  -ccp <ATTESTATION_CHAINCODE_SOURCE_PATH> \
  -ccl <go|javascript|typescript|java>
```

Project contract functions required by this lab:

```text
CreateAttestation
ReadAttestation
VerifyAttestation
GetContractVersion
```

These names are defined by this project contract; they are not built-in Fabric functions. Do not repurpose the sample asset contract and call it telemetry integration.

## Step 7: Restrict the peer Gateway endpoint

The current official test-network sample publishes the Org1 peer on host port 7051, but verify the active binding instead of assuming it:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
docker inspect peer0.org1.example.com --format '{{json .NetworkSettings.Ports}}'
```

When the observed binding is 7051, allow it only from `<LAB_SERVER_IP_ADDRESS>` using the hypervisor firewall or a Docker-aware host firewall.

Inspect the current chain before changing it:

```bash
sudo iptables -S DOCKER-USER
```

When this host uses iptables and the peer is actually published on 7051, add idempotent example rules:

```bash
sudo iptables -C DOCKER-USER -p tcp -s <LAB_SERVER_IP_ADDRESS> --dport 7051 -j ACCEPT 2>/dev/null \
  || sudo iptables -I DOCKER-USER 1 -p tcp -s <LAB_SERVER_IP_ADDRESS> --dport 7051 -j ACCEPT

sudo iptables -C DOCKER-USER -p tcp --dport 7051 -j DROP 2>/dev/null \
  || sudo iptables -A DOCKER-USER -p tcp --dport 7051 -j DROP

sudo iptables -S DOCKER-USER
```

These are examples, not a universal firewall policy. Verify rule order, existing nftables or hypervisor controls, SSH reachability, and persistence before applying them. Block peer 9051, orderer ports, CA ports, and operations ports from the general LAN unless a specific test requires them.

## Step 8: Export a disposable Org1 application identity

For this test network only, use the generated Org1 `User1` identity. It is a non-admin sample identity, but it is still sensitive and must never be reused outside the lab.

Run on the Fabric VM from `~/fabric-lab/fabric-samples/test-network`:

```bash
EXPORT_DIR=~/fabric-adapter-export
rm -rf "$EXPORT_DIR"
install -d -m 700 "$EXPORT_DIR/identity" "$EXPORT_DIR/tls"

cp organizations/peerOrganizations/org1.example.com/users/User1@org1.example.com/msp/signcerts/cert.pem \
  "$EXPORT_DIR/identity/cert.pem"

KEY_DIR=organizations/peerOrganizations/org1.example.com/users/User1@org1.example.com/msp/keystore
KEY_COUNT=$(find "$KEY_DIR" -maxdepth 1 -type f | wc -l)
test "$KEY_COUNT" -eq 1
KEY_FILE=$(find "$KEY_DIR" -maxdepth 1 -type f | head -1)
cp "$KEY_FILE" "$EXPORT_DIR/identity/key.pem"

cp organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt \
  "$EXPORT_DIR/tls/ca.crt"

chmod 600 "$EXPORT_DIR/identity/key.pem"
chmod 644 "$EXPORT_DIR/identity/cert.pem" "$EXPORT_DIR/tls/ca.crt"
tar -C "$EXPORT_DIR" -czf ~/fabric-adapter-org1-test.tgz identity tls
chmod 600 ~/fabric-adapter-org1-test.tgz
```

Copy the archive to the application VM through the protected management path:

```bash
scp ~/fabric-adapter-org1-test.tgz \
  <SERVER_USER>@<LAB_SERVER_IP_ADDRESS>:~/
```

On the application VM:

```bash
sudo install -d -m 700 /opt/fabric-adapter/crypto
sudo tar -xzf ~/fabric-adapter-org1-test.tgz -C /opt/fabric-adapter/crypto
sudo chown -R root:root /opt/fabric-adapter/crypto
sudo chmod 700 /opt/fabric-adapter/crypto /opt/fabric-adapter/crypto/identity /opt/fabric-adapter/crypto/tls
sudo chmod 600 /opt/fabric-adapter/crypto/identity/key.pem
sudo chmod 644 /opt/fabric-adapter/crypto/identity/cert.pem /opt/fabric-adapter/crypto/tls/ca.crt
rm -f ~/fabric-adapter-org1-test.tgz
```

Keep these connection values for the adapter deployment because they determine TLS routing and contract selection:

```text
MSP ID: Org1MSP
Fabric Gateway endpoint: <FABRIC_VM_IP_ADDRESS>:7051
TLS server name: peer0.org1.example.com
channel: lorawanlab
chaincode name: <ATTESTATION_CHAINCODE_NAME>
contract name and version: <ATTESTATION_CONTRACT_NAME> / telemetry-attestation-v1
```

Delete the temporary export archive from the Fabric VM after the application VM copy and backup are verified.
