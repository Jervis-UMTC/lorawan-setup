#!/usr/bin/env python3
"""Guarded temporary Node-RED branch for Chapter-IV invalid-message flooding.

The branch runs inside the active production Node-RED container so resource impact
is representative, but it is deliberately disconnected from SQL and Fabric.
It subscribes only to the isolated private research broker and writes aggregate
validation counters to /data/research-flood-validation.jsonl.

Install/remove are fail-closed: the exact original flows are backed up, only
fixed tagged research nodes are appended, and removal refuses to overwrite any
concurrent non-research flow edit.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

DEFAULT_CONTAINER = os.environ.get("NODE_RED_CONTAINER", "node-red-node-red-1")
FLOW_PATH = "/data/flows.json"
STATE_PATH = "/data/.research-flood-test-state.json"
SUMMARY_PATH = "/data/research-flood-validation.jsonl"
TAG = "chapter4-research-flood"

IDS = {
    "tab": "f10d000000000001",
    "broker": "f10d000000000002",
    "input": "f10d000000000003",
    "validator": "f10d000000000004",
    "file": "f10d000000000005",
}
INSERTED_IDS = set(IDS.values())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic_hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(raw)


def run(
    cmd: list[str], *, capture: bool = True, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def container_exec(
    container: str, *argv: str, capture: bool = True, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", container, *argv], capture=capture, check=check)


def copy_from_container(container: str, remote: str, local: Path) -> None:
    run(["docker", "cp", f"{container}:{remote}", str(local)])


def copy_to_container(container: str, local: Path, remote: str) -> None:
    run(["docker", "cp", str(local), f"{container}:{remote}"])


def container_health(container: str) -> str:
    result = run(
        [
            "docker",
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
            container,
        ]
    )
    return result.stdout.strip()


def wait_healthy(container: str, timeout: float = 75.0) -> None:
    deadline = time.monotonic() + timeout
    last = "unknown"
    while time.monotonic() < deadline:
        last = container_health(container)
        if last == "healthy":
            return
        if last in {"exited", "dead", "unhealthy"}:
            break
        time.sleep(2)
    raise RuntimeError(f"Node-RED did not become healthy (last={last})")


def parse_flows(raw: bytes) -> list[dict[str, Any]]:
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, list) or not all(isinstance(n, dict) for n in value):
        raise RuntimeError("flows.json must be an array of node objects")
    return value


def find_unique(flows: list[dict[str, Any]], predicate, label: str) -> dict[str, Any]:
    found = [n for n in flows if predicate(n)]
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one {label}; found {len(found)}")
    return found[0]


def discover_production(flows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if any(n.get("id") in INSERTED_IDS for n in flows):
        raise RuntimeError("research flood node IDs already exist")

    tab = find_unique(
        flows,
        lambda n: n.get("type") == "tab"
        and "lorawan" in str(n.get("label", "")).lower()
        and "telemetry" in str(n.get("label", "")).lower(),
        "production LoRaWAN telemetry tab",
    )
    validator = find_unique(
        flows,
        lambda n: n.get("type") == "function"
        and n.get("name") == "Validate + normalize + parameterize",
        "production validation function",
    )
    mqtt_in = find_unique(
        flows,
        lambda n: n.get("type") == "mqtt in"
        and n.get("topic") == "application/+/device/+/event/up",
        "production ChirpStack MQTT input",
    )
    broker_id = mqtt_in.get("broker")
    broker = find_unique(
        flows,
        lambda n: n.get("id") == broker_id and n.get("type") == "mqtt-broker",
        "production MQTT broker",
    )
    tls_id = broker.get("tls")
    tls = find_unique(
        flows,
        lambda n: n.get("id") == tls_id and n.get("type") == "tls-config",
        "production MQTT TLS config",
    )

    if validator.get("z") != tab.get("id") or mqtt_in.get("z") != tab.get("id"):
        raise RuntimeError("production input/validator are not on the telemetry tab")
    if not broker.get("usetls") or not tls_id:
        raise RuntimeError("production MQTT broker is not using TLS")
    if (
        tls.get("servername") != "mqtt.internal.lorawan.com"
        or tls.get("verifyservercert") is not True
    ):
        raise RuntimeError("production MQTT TLS contract differs from commissioned state")

    return {
        "tab": tab,
        "validator": validator,
        "mqtt_in": mqtt_in,
        "broker": broker,
        "tls": tls,
    }


def build_validation_function(production_func: str) -> str:
    helper_start = production_func.find("function numberOrNull(value) {")
    gate_start = production_func.find("const topicParts =", helper_start)
    gate_end = production_func.find("\n\nconst receivedAt =", gate_start)
    if min(helper_start, gate_start, gate_end) < 0:
        raise RuntimeError("could not locate production validation-gate boundaries")

    setup = production_func[:helper_start].strip()
    setup_required = [
        "const p = msg.payload || {};",
        "const deviceInfo = p.deviceInfo || {};",
        "const decoded = p.object || {};",
    ]
    setup_missing = [token for token in setup_required if token not in setup]
    if setup_missing:
        raise RuntimeError(
            "production validation setup changed; missing: " + ", ".join(setup_missing)
        )

    helper = production_func[helper_start:gate_start].rstrip()
    gate = production_func[gate_start:gate_end].strip()
    required = [
        "/^[0-9a-f]{16}$/",
        "Date.parse(eventTime)",
        "LORAWAN_REGION_ID",
        "decoded.payload_version",
        "decoded.test_sequence",
        "decoded.sensor_validity_bitmap",
        "payloadVersion !== 2",
        "Number.isInteger(testSequence)",
        "Number.isInteger(validity)",
    ]
    missing = [token for token in required if token not in gate]
    if missing:
        raise RuntimeError(
            "production validation gate changed; missing: " + ", ".join(missing)
        )

    transformed: list[str] = []
    for line in gate.splitlines():
        stripped = line.strip()
        if stripped.startswith("node.warn(") or stripped.startswith("node.error("):
            continue
        if stripped == "return null;":
            indent = line[: len(line) - len(line.lstrip())]
            transformed.append(indent + "return reject();")
        else:
            transformed.append(line)
    gate = "\n".join(transformed)

    prelude = r'''// Managed Chapter-IV research branch. No SQL/Fabric output exists here.
let state = context.get('researchFloodCounters') || {
    received: 0,
    rejected: 0,
    accepted: 0,
    last_emit_ms: 0
};

function emitSummary(force) {
    const now = Date.now();
    const due = force || state.received === 1 || (state.received % 100) === 0 || (now - state.last_emit_ms) >= 5000;
    if (!due) {
        context.set('researchFloodCounters', state);
        return null;
    }
    state.last_emit_ms = now;
    context.set('researchFloodCounters', state);
    return {
        topic: 'research/flood/validation',
        payload: JSON.stringify({
            timestamp_utc: new Date(now).toISOString(),
            received: state.received,
            rejected: state.rejected,
            accepted: state.accepted
        }) + '\n'
    };
}

function reject() {
    state.rejected += 1;
    return emitSummary(false);
}

function accept() {
    state.accepted += 1;
    return emitSummary(false);
}

// Isolated research-only control marker: report counters without counting it.
if (msg.payload && msg.payload.__research_flush === true) {
    return emitSummary(true);
}

state.received += 1;
'''
    return (
        prelude
        + "\n"
        + setup
        + "\n\n"
        + helper
        + "\n\n"
        + gate
        + "\n\nreturn accept();\n"
    )


def build_research_nodes(prod: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    validator_code = build_validation_function(str(prod["validator"].get("func", "")))

    tab = {
        "id": IDS["tab"],
        "type": "tab",
        "label": "Research Flood Validation (temporary)",
        "disabled": False,
        "info": f"Managed by {TAG}. Isolated topic only; no SQL or Fabric outputs.",
    }

    broker = copy.deepcopy(prod["broker"])
    broker.update(
        {
            "id": IDS["broker"],
            "name": "Research flood private mTLS",
            "broker": "10.104.0.2",
            "port": "1887",
            "clientid": "node-red-flood-validation",
            "autoConnect": True,
            "usetls": True,
            "verifyservercert": True,
            "cleansession": True,
        }
    )

    mqtt_in = {
        "id": IDS["input"],
        "type": "mqtt in",
        "z": IDS["tab"],
        "name": "Research invalid-message input",
        "topic": "test/flood/invalid",
        "qos": "0",
        "datatype": "json",
        "broker": IDS["broker"],
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 190,
        "y": 120,
        "wires": [[IDS["validator"]]],
    }

    validator = {
        "id": IDS["validator"],
        "type": "function",
        "z": IDS["tab"],
        "name": "Research production-gate validation + counters",
        "func": validator_code,
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 510,
        "y": 120,
        "wires": [[IDS["file"]]],
    }

    file_node = {
        "id": IDS["file"],
        "type": "file",
        "z": IDS["tab"],
        "name": "Write aggregate validation counters",
        "filename": SUMMARY_PATH,
        "filenameType": "str",
        "appendNewline": False,
        "createDir": False,
        "overwriteFile": "false",
        "encoding": "none",
        "x": 850,
        "y": 120,
        "wires": [[]],
    }
    return [tab, broker, mqtt_in, validator, file_node]


def plan_flows(raw: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    flows = parse_flows(raw)
    prod = discover_production(flows)
    research = build_research_nodes(prod)
    candidate = flows + research
    return candidate, {
        "original_sha256": sha256_bytes(raw),
        "original_semantic_sha256": semantic_hash(flows),
        "production_validator_sha256": sha256_bytes(
            str(prod["validator"].get("func", "")).encode("utf-8")
        ),
        "production_broker": f"{prod['broker'].get('broker')}:{prod['broker'].get('port')}",
        "production_topic": prod["mqtt_in"].get("topic"),
        "research_broker": "10.104.0.2:1887",
        "research_topic": "test/flood/invalid",
        "inserted_ids": sorted(INSERTED_IDS),
        "candidate_semantic_sha256": semantic_hash(candidate),
    }


def state_exists(container: str) -> bool:
    return container_exec(container, "test", "-e", STATE_PATH, check=False).returncode == 0


def load_container_json(container: str, remote: str) -> Any:
    with tempfile.TemporaryDirectory(prefix="nr-flood-read-") as tmp:
        local = Path(tmp) / "item.json"
        copy_from_container(container, remote, local)
        return json.loads(local.read_text(encoding="utf-8-sig"))


def pull_flow_bytes(container: str, remote: str = FLOW_PATH) -> bytes:
    with tempfile.TemporaryDirectory(prefix="nr-flood-flow-") as tmp:
        local = Path(tmp) / "flows.json"
        copy_from_container(container, remote, local)
        return local.read_bytes()


def command_plan(args: argparse.Namespace) -> int:
    _, info = plan_flows(Path(args.flows).read_bytes())
    print(json.dumps(info, indent=2, sort_keys=True))
    return 0


def command_install(args: argparse.Namespace) -> int:
    container = args.container
    health = container_health(container)
    if health != "healthy":
        raise RuntimeError(f"Node-RED must be healthy before install (health={health})")
    if state_exists(container):
        raise RuntimeError("research flood state already exists")

    original_raw = pull_flow_bytes(container)
    candidate, info = plan_flows(original_raw)
    original_flows = parse_flows(original_raw)
    research_nodes = [n for n in candidate if n.get("id") in INSERTED_IDS]
    original_sha = info["original_sha256"]
    backup_path = f"/data/flows.json.research-flood-backup-{original_sha[:12]}"

    state = {
        "manager": TAG,
        "installed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "original_sha256": original_sha,
        "original_semantic_sha256": semantic_hash(original_flows),
        "backup_path": backup_path,
        "production_validator_sha256": info["production_validator_sha256"],
        "inserted_ids": sorted(INSERTED_IDS),
        "inserted_node_hashes": {
            str(n["id"]): semantic_hash(n) for n in research_nodes
        },
        "summary_path": SUMMARY_PATH,
        "research_endpoint": "10.104.0.2:1887",
        "research_topic": "test/flood/invalid",
    }

    backup_exists = container_exec(container, "test", "-e", backup_path, check=False).returncode == 0
    if not backup_exists:
        container_exec(container, "cp", FLOW_PATH, backup_path)
    backup_raw = pull_flow_bytes(container, backup_path)
    if sha256_bytes(backup_raw) != original_sha:
        raise RuntimeError("backup hash mismatch; refusing mutation")

    with tempfile.TemporaryDirectory(prefix="nr-flood-install-") as tmp:
        td = Path(tmp)
        candidate_file = td / "flows.candidate.json"
        state_file = td / "state.json"
        candidate_file.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        state_file.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        # docker cp maps files to the SSH operator UID on this bind mount.
        # Never chown from inside the container (the mount rejects that). Instead,
        # let the configured node-red user create fresh files and atomically rename them.
        container_exec(
            container,
            "rm",
            "-f",
            "/data/flows.json.research-flood-candidate",
            "/data/.research-flood-test-state.candidate",
            "/data/flows.json.research-flood-new",
            "/data/.research-flood-test-state.new",
        )
        copy_to_container(
            container, candidate_file, "/data/flows.json.research-flood-candidate"
        )
        copy_to_container(
            container, state_file, "/data/.research-flood-test-state.candidate"
        )
        container_exec(
            container,
            "sh",
            "-lc",
            "cat /data/flows.json.research-flood-candidate > /data/flows.json.research-flood-new && "
            "chmod 0644 /data/flows.json.research-flood-new && "
            "cat /data/.research-flood-test-state.candidate > /data/.research-flood-test-state.new && "
            "chmod 0600 /data/.research-flood-test-state.new && "
            "mv /data/flows.json.research-flood-new /data/flows.json && "
            "mv /data/.research-flood-test-state.new /data/.research-flood-test-state.json && "
            "rm -f /data/flows.json.research-flood-candidate /data/.research-flood-test-state.candidate && "
            f"rm -f '{SUMMARY_PATH}'",
        )

    run(["docker", "restart", container])
    wait_healthy(container)
    live_flows = parse_flows(pull_flow_bytes(container))
    live_ids = {n.get("id") for n in live_flows}
    missing = sorted(INSERTED_IDS - live_ids)
    if missing:
        raise RuntimeError("research nodes missing after restart: " + ", ".join(missing))

    print(
        json.dumps(
            {"status": "INSTALLED", "container_health": container_health(container), **info},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_status(args: argparse.Namespace) -> int:
    container = args.container
    raw = pull_flow_bytes(container)
    flows = parse_flows(raw)
    ids = {n.get("id") for n in flows}
    status: dict[str, Any] = {
        "container": container,
        "container_health": container_health(container),
        "branch_installed": INSERTED_IDS.issubset(ids),
        "research_nodes_present": sorted(str(i) for i in INSERTED_IDS & ids),
        "flow_sha256": sha256_bytes(raw),
        "state_present": state_exists(container),
    }
    if status["state_present"]:
        status["state"] = load_container_json(container, STATE_PATH)
    summary = container_exec(
        container,
        "sh",
        "-lc",
        f"test -r '{SUMMARY_PATH}' && tail -n 5 '{SUMMARY_PATH}' || true",
        check=False,
    )
    status["summary_tail"] = [line for line in summary.stdout.splitlines() if line.strip()]
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


def command_remove(args: argparse.Namespace) -> int:
    container = args.container
    if not state_exists(container):
        raise RuntimeError("research flood state is absent; safe restore unavailable")
    state = load_container_json(container, STATE_PATH)
    if state.get("manager") != TAG:
        raise RuntimeError("state is not owned by this helper")

    current = parse_flows(pull_flow_bytes(container))
    current_by_id = {str(n.get("id")): n for n in current}
    expected_ids = set(state.get("inserted_ids", []))
    if expected_ids != INSERTED_IDS:
        raise RuntimeError("state inserted-ID set differs from this helper version")

    for node_id, expected_hash in state.get("inserted_node_hashes", {}).items():
        node = current_by_id.get(node_id)
        if node is None or semantic_hash(node) != expected_hash:
            raise RuntimeError(f"research node {node_id} changed; refusing overwrite")

    without_research = [n for n in current if str(n.get("id")) not in INSERTED_IDS]
    if semantic_hash(without_research) != state.get("original_semantic_sha256"):
        raise RuntimeError(
            "non-research flows changed while branch was installed; refusing overwrite"
        )

    backup_path = str(state.get("backup_path", ""))
    if not backup_path.startswith("/data/flows.json.research-flood-backup-"):
        raise RuntimeError("invalid backup path in state")
    backup_raw = pull_flow_bytes(container, backup_path)
    if sha256_bytes(backup_raw) != state.get("original_sha256"):
        raise RuntimeError("exact backup hash mismatch; refusing restore")

    container_exec(
        container,
        "sh",
        "-lc",
        f"cat '{backup_path}' > '{FLOW_PATH}.research-flood-restore' && "
        f"chmod 0644 '{FLOW_PATH}.research-flood-restore' && "
        f"mv '{FLOW_PATH}.research-flood-restore' '{FLOW_PATH}'",
    )
    run(["docker", "restart", container])
    wait_healthy(container)
    restored = pull_flow_bytes(container)
    if sha256_bytes(restored) != state.get("original_sha256"):
        raise RuntimeError("restored flows do not match exact pre-test bytes")

    container_exec(container, "rm", "-f", STATE_PATH, backup_path)
    print(
        json.dumps(
            {
                "status": "REMOVED",
                "container_health": container_health(container),
                "restored_sha256": sha256_bytes(restored),
                "summary_preserved": SUMMARY_PATH,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="validate a flows.json without mutation")
    p_plan.add_argument("--flows", required=True)
    p_plan.set_defaults(func=command_plan)

    p_install = sub.add_parser("install", help="install temporary flood branch")
    p_install.set_defaults(func=command_install)

    p_status = sub.add_parser("status", help="show branch and counter state")
    p_status.set_defaults(func=command_status)

    p_remove = sub.add_parser("remove", help="restore exact pre-test flows")
    p_remove.set_defaults(func=command_remove)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except subprocess.CalledProcessError as exc:
        print(
            f"ERROR: command failed ({exc.returncode}): {' '.join(exc.cmd)}",
            file=sys.stderr,
        )
        if exc.stderr:
            print(exc.stderr.strip(), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
