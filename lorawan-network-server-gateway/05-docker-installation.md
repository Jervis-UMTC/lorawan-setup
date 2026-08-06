# 5. Installing Docker

ChirpStack's own images and the standard `postgres`, `redis`, and `eclipse-mosquitto` images all publish multi-architecture builds that include `arm64`, so Docker on 64-bit Raspberry Pi OS works the same way it does anywhere else. This is exactly why we insisted on the 64-bit image back in [02](02-flash-raspberry-pi-os.md) — 32-bit (armhf) would leave you hunting for compatible images.

## Step 1: Install Docker Engine via the official apt repository

Raspberry Pi OS is a Debian derivative. For this guide's supported 64-bit Bookworm and Trixie systems, use Docker's **Debian** repository. Do not construct a `linux/raspbian` repository URL with the `trixie` codename: Docker does not publish a `trixie` suite there, so APT will return `404 Not Found`. Docker's Debian repository publishes arm64 packages for Trixie.

```bash
# Remove any old/conflicting packages first
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Set up Docker's apt repository
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

> The Debian repository is intentional even though the operating system is Raspberry Pi OS. Docker's own documentation directs Debian derivatives to use the corresponding Debian installation instructions. `$VERSION_CODENAME` resolves to `bookworm` or `trixie` automatically.

## Step 2: Let your user run Docker without `sudo`

```bash
sudo usermod -aG docker $USER
```

Log out and back in (or run `newgrp docker`) for the group change to take effect.

## Step 3: Verify

```bash
docker run hello-world
docker info | grep -i architecture
```

The architecture line should read `aarch64` — if it says `armv7l` or similar, you're on a 32-bit OS install and should go back to [02](02-flash-raspberry-pi-os.md) to reflash with the 64-bit image.

## Step 4: Enable Docker at boot

```bash
sudo systemctl enable docker
sudo systemctl enable containerd
```

(Compose's `restart: unless-stopped` policy, which the ChirpStack stack uses, handles bringing the containers themselves back up once the Docker daemon is running — more on this in [09](09-autostart-persistence-hardening.md).)

---
Next: [06-chirpstack-server-deployment.md](06-chirpstack-server-deployment.md)
