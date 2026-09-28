#!/bin/sh
set -eu

ULC01="opsadmin@143.198.205.54"
ULC03="opsadmin@159.223.50.57"
ADMIN_KEY="${ADMIN_KEY:-$HOME/.ssh/id_ed25519_home_ops}"
ACTION_PUB_WIN="${ACTION_PUB_WIN:-/mnt/c/Users/smartagriintern/.ssh/id_ed25519_lorawan_research_actions.pub}"
SSH="ssh -i $ADMIN_KEY -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
SCP="scp -q -i $ADMIN_KEY -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)"
WRAPPER="$ROOT/test/automation/research-actions/remote/server-actions-ssh.sh"
SUDOERS="$ROOT/test/automation/research-actions/remote/lorawan-research-actions.sudoers"
LISTENER="$ROOT/test/automation/mqtt-test-listener/mqtt_test_listener.sh"
NODERED="$ROOT/test/automation/node-red-flood-test/node_red_flood_branch.py"
FABRIC_ISOLATION="$ROOT/test/automation/resilience/fabric_endpoint_isolation.sh"

for f in "$ADMIN_KEY" "$ACTION_PUB_WIN" "$WRAPPER" "$SUDOERS" "$LISTENER" "$NODERED" "$FABRIC_ISOLATION"; do
  [ -r "$f" ] || { echo "ERROR: required file missing: $f" >&2; exit 2; }
done
ssh-add -l >/dev/null 2>&1 || { echo "ERROR: administrator key must already be loaded in ssh-agent" >&2; exit 2; }

$SCP "$WRAPPER" "$LISTENER" "$FABRIC_ISOLATION" "$SUDOERS" "$ACTION_PUB_WIN" "$ULC01:/tmp/"
$SCP "$WRAPPER" "$NODERED" "$ACTION_PUB_WIN" "$ULC03:/tmp/"

# ULC-03 needs no root privilege for this helper: opsadmin already owns the
# Node-RED Docker access used by the reviewed temporary branch manager.
$SSH "$ULC03" 'set -eu
  mkdir -p "$HOME/.local/bin" "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  install -m 0755 /tmp/server-actions-ssh.sh "$HOME/.local/bin/lorawan-research-actions-ssh"
  install -m 0755 /tmp/node_red_flood_branch.py "$HOME/.local/bin/lorawan-node-red-flood-branch"
  pub=$(cat /tmp/id_ed25519_lorawan_research_actions.pub)
  grep -v " lorawan-research-actions$" "$HOME/.ssh/authorized_keys" > "$HOME/.ssh/authorized_keys.new" || true
  printf "%s %s\n" "restrict,command=\"/home/opsadmin/.local/bin/lorawan-research-actions-ssh\"" "$pub" >> "$HOME/.ssh/authorized_keys.new"
  mv "$HOME/.ssh/authorized_keys.new" "$HOME/.ssh/authorized_keys"
  chmod 600 "$HOME/.ssh/authorized_keys"
  rm -f /tmp/server-actions-ssh.sh /tmp/node_red_flood_branch.py /tmp/id_ed25519_lorawan_research_actions.pub
  echo ULC03_RESEARCH_ACTIONS=INSTALLED'

# ULC-01 requires root only to install the isolated listener helper and its
# exact-command sudoers allowlist. sudo -v prompts once in this interactive
# commissioning session; the final research-actions key itself remains NOPASSWD
# only for the four explicitly listed listener commands.
$SSH -tt "$ULC01" 'set -eu
  sudo -v
  sudo install -m 0755 /tmp/mqtt_test_listener.sh /usr/local/sbin/lorawan-research-mqtt-test-listener
  sudo install -m 0755 /tmp/fabric_endpoint_isolation.sh /usr/local/sbin/lorawan-fabric-endpoint-isolation
  sudo install -m 0440 /tmp/lorawan-research-actions.sudoers /etc/sudoers.d/lorawan-research-actions
  sudo visudo -cf /etc/sudoers.d/lorawan-research-actions
  mkdir -p "$HOME/.local/bin" "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  install -m 0755 /tmp/server-actions-ssh.sh "$HOME/.local/bin/lorawan-research-actions-ssh"
  pub=$(cat /tmp/id_ed25519_lorawan_research_actions.pub)
  grep -v " lorawan-research-actions$" "$HOME/.ssh/authorized_keys" > "$HOME/.ssh/authorized_keys.new" || true
  printf "%s %s\n" "restrict,command=\"/home/opsadmin/.local/bin/lorawan-research-actions-ssh\"" "$pub" >> "$HOME/.ssh/authorized_keys.new"
  mv "$HOME/.ssh/authorized_keys.new" "$HOME/.ssh/authorized_keys"
  chmod 600 "$HOME/.ssh/authorized_keys"
  rm -f /tmp/server-actions-ssh.sh /tmp/mqtt_test_listener.sh /tmp/fabric_endpoint_isolation.sh /tmp/lorawan-research-actions.sudoers /tmp/id_ed25519_lorawan_research_actions.pub
  echo ULC01_RESEARCH_ACTIONS=INSTALLED'

echo RESEARCH_ACTIONS_DEPLOYMENT=PASS
