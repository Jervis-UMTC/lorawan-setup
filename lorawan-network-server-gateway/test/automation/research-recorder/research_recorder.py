#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import io
import json
import os
import re
import secrets
import stat
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from serial.tools import list_ports

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RESULTS_ROOT = PROJECT_ROOT / "chapter4-results"
STATE_PATH = RESULTS_ROOT / "_recorder-active.json"
LOCK_PATH = RESULTS_ROOT / "_recorder-active.lock"
SERIAL_SCRIPT = SCRIPT_DIR / "serial_capture.py"
SUMMARY_SCRIPT = SCRIPT_DIR / "summarize-run.py"
RECORDER_KEY = Path.home() / ".ssh" / "id_ed25519_research_recorder"
SSH_EXE = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
SERIAL_CONTROL_ROOT = Path(tempfile.gettempdir()) / "lorawan-research-recorder"

TARGETS = {
    "ulc01": "opsadmin@143.198.205.54",
    "ulc02": "opsadmin@165.22.253.127",
    "ulc03": "opsadmin@159.223.50.57",
    "gateway": "root@192.168.20.11",
}
EMU_PATTERN = re.compile(r"(VID:PID=239A:8029|VID_239A&PID_8029|239A.*8029)", re.I)
SEC_PATTERN = re.compile(r"(VID:PID=1915:521F|VID_1915&PID_521F|1915.*521F)", re.I)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DEV_EUI = re.compile(r"^[0-9A-Fa-f]{16}$")
SUPERVISOR_TRANSIENT_FAILURE_LIMIT = 3
CLOCK_PROBE_SAMPLES = 5
# EMU-01 source lines are timestamped by the workstation while the authoritative
# experiment window is server UTC. A workstation may have a large wall-clock
# offset (for example when its AD PDC is wrong) as long as that offset is measured
# independently at both run boundaries and remains stable. Cloud-node agreement
# and gateway-to-cloud agreement remain hard gates.
MAX_WORKSTATION_CLOCK_CALIBRATION_SECONDS = 300.0
MAX_WORKSTATION_CLOCK_DRIFT_SECONDS = 0.100
MAX_CLOUD_CLOCK_SPREAD_SECONDS = 0.250
MAX_GATEWAY_CLOUD_SKEW_SECONDS = 1.500
FINALIZATION_SSH_QUIET_SECONDS = 3.0
REMOTE_EXPORT_RETRY_DELAY_SECONDS = 2.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("UTC timestamp is missing timezone information")
    return dt.astimezone(timezone.utc)


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def ssh_argv(node: str, remote_command: str) -> list[str]:
    return [
        str(SSH_EXE),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "ConnectionAttempts=1",
        "-o", f"IdentityFile={RECORDER_KEY}",
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes",
        TARGETS[node],
        remote_command,
    ]


def run_remote(node: str, command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(ssh_argv(node, command), text=True, capture_output=True, timeout=30)
    if check and cp.returncode != 0:
        raise RuntimeError(f"{node} command failed ({cp.returncode}): {command}\n{cp.stderr.strip()}")
    return cp


def authoritative_utc_now() -> str:
    cp = run_remote("ulc01", "utc-now")
    value = cp.stdout.strip().splitlines()[-1] if cp.stdout.strip() else ""
    parse_utc(value)
    return value


def csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text))) if text.strip() else []


def settle_fabric_window(leader: str, start: str, end: str, dev_eui: str, timeout_seconds: int) -> dict[str, object]:
    """Wait for only the already-closed source window to reach Fabric confirmation.

    The counted experiment ends at ``end`` before this function is called. Polls
    therefore cannot add transmissions to the measurement window; they only let
    asynchronous evidence verification and Fabric commit state catch up before
    the immutable research bundle is exported and sealed.
    """
    result: dict[str, object] = {
        "enabled": timeout_seconds > 0,
        "timeout_seconds": timeout_seconds,
        "poll_interval_seconds": 5,
        "started_utc": authoritative_utc_now(),
        "window_start_utc": start,
        "window_end_utc": end,
        "status": "DISABLED" if timeout_seconds <= 0 else "WAITING",
        "uplink_rows": 0,
        "outbox_rows": 0,
        "confirmed_source_events": 0,
        "missing_source_events": [],
    }
    if timeout_seconds <= 0:
        result["finished_utc"] = result["started_utc"]
        return result

    deadline = time.monotonic() + timeout_seconds
    while True:
        uplinks_cp = run_remote(leader, f"db-export uplinks {start} {end} {dev_eui}")
        outbox_cp = run_remote(leader, f"db-export outbox {start} {end} {dev_eui}")
        uplinks = csv_rows(uplinks_cp.stdout)
        outbox = csv_rows(outbox_cp.stdout)
        source_keys = {row.get("event_key", "") for row in uplinks if row.get("event_key")}
        confirmed_keys = {
            row.get("source_event_key", "")
            for row in outbox
            if row.get("source_event_key")
            and (row.get("status") or "").lower() == "confirmed"
            and row.get("fabric_tx_id")
            and row.get("committed_at")
        }
        missing = sorted(source_keys - confirmed_keys)
        result.update({
            "uplink_rows": len(uplinks),
            "outbox_rows": len(outbox),
            "confirmed_source_events": len(source_keys & confirmed_keys),
            "missing_source_events": missing,
            "last_poll_utc": authoritative_utc_now(),
        })
        if source_keys and not missing:
            result["status"] = "CONFIRMED"
            break
        if time.monotonic() >= deadline:
            result["status"] = "TIMEOUT"
            break
        time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))

    result["finished_utc"] = authoritative_utc_now()
    result["elapsed_seconds"] = round(
        (parse_utc(str(result["finished_utc"])) - parse_utc(str(result["started_utc"]))).total_seconds(), 3
    )
    return result


def _clock_exchange_probe(node: str, samples: int) -> dict[str, object]:
    if samples < 1 or samples > 20:
        raise ValueError("clock probe sample count must be between 1 and 20")
    proc = subprocess.Popen(
        ssh_argv(node, f"clock-probe {samples}"),
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    if proc.stdin is None or proc.stdout is None or proc.stderr is None:
        proc.kill()
        raise RuntimeError(f"{node} clock probe could not open SSH pipes")

    offsets: list[float] = []
    rtts_ms: list[float] = []
    server_times: list[str] = []
    try:
        marker = proc.stdout.readline().strip()
        if marker != "#CLOCK_PROBE_V1":
            detail = proc.stderr.read().strip().replace("\n", " ")
            raise RuntimeError(f"{node} clock-probe handshake failed: {marker or detail or 'no response'}")

        # The SSH handshake is completed before this exchange begins. Each
        # request therefore measures only the live command-channel round trip,
        # making midpoint correction valid instead of charging SSH setup time
        # to the workstation clock.
        for index in range(samples):
            local_before = datetime.now(timezone.utc)
            proc.stdin.write("probe\n")
            proc.stdin.flush()
            text = proc.stdout.readline().strip()
            local_after = datetime.now(timezone.utc)
            if not text:
                detail = proc.stderr.read().strip().replace("\n", " ")
                raise RuntimeError(f"{node} clock-probe returned no timestamp: {detail[:160]}")
            server_time = parse_utc(text)
            midpoint = local_before + (local_after - local_before) / 2
            offsets.append((server_time - midpoint).total_seconds())
            rtts_ms.append((local_after - local_before).total_seconds() * 1000.0)
            server_times.append(text)
            if index + 1 < samples:
                time.sleep(0.05)

        proc.stdin.close()
        returncode = proc.wait(timeout=5)
        detail = proc.stderr.read().strip().replace("\n", " ")
        if returncode != 0:
            raise RuntimeError(f"{node} clock-probe failed ({returncode}): {detail[:160]}")
    except Exception:
        if proc.poll() is None:
            proc.kill()
        raise
    finally:
        if proc.poll() is None:
            proc.kill()

    return {
        "node": node,
        "samples": samples,
        "server_timestamp_utc": server_times[-1],
        "server_minus_workstation_seconds": statistics.median(offsets),
        "offset_min_seconds": min(offsets),
        "offset_max_seconds": max(offsets),
        "rtt_median_ms": statistics.median(rtts_ms),
        "rtt_max_ms": max(rtts_ms),
        "measurement": "established SSH command-channel request/response midpoint",
    }


def clock_probe(node: str, samples: int = CLOCK_PROBE_SAMPLES) -> dict[str, object]:
    if node not in ("ulc01", "ulc02", "ulc03"):
        raise ValueError(f"clock probe is supported only on cloud nodes: {node}")
    return _clock_exchange_probe(node, samples)


def gateway_clock_probe(samples: int = CLOCK_PROBE_SAMPLES) -> dict[str, object]:
    result = _clock_exchange_probe("gateway", samples)
    result["resolution_note"] = "Gateway clock probe has whole-second timestamp resolution"
    return result


def clock_readiness() -> tuple[bool, dict[str, object]]:
    probes: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for node in ("ulc01", "ulc02", "ulc03"):
        try:
            probes[node] = clock_probe(node)
        except Exception as exc:
            errors.append(f"{node}: {exc}")

    cluster_offset = None
    cloud_spread = None
    gateway_minus_cloud = None
    gateway_probe = None
    ready = not errors and len(probes) == 3
    if ready:
        offsets = [float(probes[node]["server_minus_workstation_seconds"]) for node in ("ulc01", "ulc02", "ulc03")]
        cluster_offset = statistics.median(offsets)
        cloud_spread = max(offsets) - min(offsets)
        if abs(cluster_offset) > MAX_WORKSTATION_CLOCK_CALIBRATION_SECONDS:
            ready = False
            errors.append(
                f"workstation clock calibration offset is {cluster_offset:+.6f}s; "
                f"maximum calibratable magnitude is {MAX_WORKSTATION_CLOCK_CALIBRATION_SECONDS:.3f}s"
            )
        if cloud_spread > MAX_CLOUD_CLOCK_SPREAD_SECONDS:
            ready = False
            errors.append(
                f"cloud clock spread is {cloud_spread:.6f}s; "
                f"limit is {MAX_CLOUD_CLOCK_SPREAD_SECONDS:.3f}s"
            )

    try:
        gateway_probe = gateway_clock_probe()
        probes["gateway"] = gateway_probe
    except Exception as exc:
        ready = False
        errors.append(f"gateway: {exc}")

    if cluster_offset is not None and gateway_probe is not None:
        gateway_minus_cloud = float(gateway_probe["server_minus_workstation_seconds"]) - cluster_offset
        if abs(gateway_minus_cloud) > MAX_GATEWAY_CLOUD_SKEW_SECONDS:
            ready = False
            errors.append(
                f"gateway clock differs from cloud UTC by {gateway_minus_cloud:+.6f}s; "
                f"limit is +/-{MAX_GATEWAY_CLOUD_SKEW_SECONDS:.3f}s"
            )

    return ready, {
        "ready": ready,
        "reference": "median of midpoint-corrected ulc01/ulc02/ulc03 utc-now probes",
        "workstation_calibration_limit_seconds": MAX_WORKSTATION_CLOCK_CALIBRATION_SECONDS,
        "workstation_drift_limit_seconds": MAX_WORKSTATION_CLOCK_DRIFT_SECONDS,
        "cloud_spread_limit_seconds": MAX_CLOUD_CLOCK_SPREAD_SECONDS,
        "gateway_cloud_skew_limit_seconds": MAX_GATEWAY_CLOUD_SKEW_SECONDS,
        "server_minus_workstation_seconds": cluster_offset,
        "cloud_spread_seconds": cloud_spread,
        "gateway_minus_cloud_seconds": gateway_minus_cloud,
        "probes": probes,
        "errors": errors,
    }


def database_roles() -> dict[str, str]:
    roles: dict[str, str] = {}
    for node in ("ulc01", "ulc02", "ulc03"):
        try:
            cp = run_remote(node, "db-role", check=False)
        except (subprocess.TimeoutExpired, OSError):
            roles[node] = "ERROR"
            continue
        roles[node] = cp.stdout.strip() if cp.returncode == 0 else "ERROR"
    return roles


def current_database_leader() -> tuple[str, dict[str, str]]:
    roles = database_roles()
    leaders = [node for node, role in roles.items() if role == "leader"]
    if len(leaders) != 1:
        raise RuntimeError(f"expected exactly one database leader; roles={roles}")
    return leaders[0], roles


def try_live_evidence_status() -> tuple[str, str, bool]:
    leader, _roles = current_database_leader()
    cp = run_remote(leader, "evidence-status", check=False)
    detail = cp.stderr.strip().replace("\r", " ").replace("\n", "; ")
    if cp.returncode == 64 and "command not allowed" in detail.lower():
        return leader, "UNAVAILABLE_WRAPPER_UPGRADE_REQUIRED", False
    if cp.returncode != 0:
        raise RuntimeError(f"{leader} evidence-status failed ({cp.returncode}): {detail or 'no detail'}")
    text = cp.stdout.strip()
    if "VERIFICATION|" not in text or "LATEST_VERIFIED_AT|" not in text:
        raise RuntimeError(f"{leader} evidence-status returned an incomplete summary")
    return leader, text, True


def live_evidence_status() -> tuple[str, str]:
    leader, text, supported = try_live_evidence_status()
    if not supported:
        raise RuntimeError(f"{leader} evidence-status unavailable: server recorder wrapper upgrade required")
    return leader, text


def write_evidence_status_snapshot(path: Path) -> bool:
    leader, text, supported = try_live_evidence_status()
    path.write_text(f"EVIDENCE_STATUS_NODE={leader}\n{text}\n", encoding="utf-8")
    return supported


EVIDENCE_SNAPSHOT_CONTAINERS = {
    "ulc01": ("lorawan-gateway-evidence-collector-1",),
    "ulc02": ("lorawan-gateway-evidence-verifier-1",),
    "ulc03": (
        "lorawan-gateway-evidence-collector-1",
        "lorawan-gateway-evidence-verifier-1",
    ),
}


def _snapshot_evidence_readiness(node: str, snapshot: str) -> tuple[bool, str]:
    expected = EVIDENCE_SNAPSHOT_CONTAINERS[node]
    docker_rows: dict[str, str] = {}
    in_docker = False
    for raw_line in snapshot.splitlines():
        line = raw_line.strip()
        if line == "--- docker ---":
            in_docker = True
            continue
        if line.startswith("--- ") and in_docker:
            break
        if not in_docker or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            docker_rows[parts[0]] = parts[2]

    missing = [name for name in expected if name not in docker_rows]
    not_up = [name for name in expected if name in docker_rows and not docker_rows[name].startswith("Up")]
    if missing or not_up:
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if not_up:
            detail.append("not_up=" + ",".join(not_up))
        return False, "NOT_READY|fallback-snapshot|" + "|".join(detail)
    return True, "READY|fallback-snapshot|containers=" + ",".join(expected)


def evidence_readiness() -> tuple[bool, dict[str, str]]:
    details: dict[str, str] = {}
    ok = True
    for node in ("ulc01", "ulc02", "ulc03"):
        try:
            cp = run_remote(node, "evidence-ready", check=False)
        except subprocess.TimeoutExpired:
            details[node] = "TIMEOUT|evidence-ready|after=30s"
            ok = False
            continue
        except OSError as exc:
            details[node] = f"ERROR|evidence-ready|{exc}"
            ok = False
            continue
        if cp.returncode == 0:
            text = cp.stdout.strip().replace("\r", " ").replace("\n", "; ")
            details[node] = text[:500] or "READY|evidence-ready"
            continue

        error_text = cp.stderr.strip().replace("\r", " ").replace("\n", "; ")
        if cp.returncode == 64 and "command not allowed" in error_text.lower():
            try:
                snapshot = run_remote(node, "snapshot", check=False)
            except subprocess.TimeoutExpired:
                details[node] = "TIMEOUT|fallback-snapshot|after=30s"
                ok = False
                continue
            except OSError as exc:
                details[node] = f"ERROR|fallback-snapshot|{exc}"
                ok = False
                continue
            if snapshot.returncode == 0:
                fallback_ok, fallback_detail = _snapshot_evidence_readiness(node, snapshot.stdout)
                details[node] = fallback_detail[:500]
                ok &= fallback_ok
                continue

        details[node] = error_text[:500] or f"exit={cp.returncode}"
        ok = False
    return ok, details


def remote_to_file(
    node: str,
    command: str,
    out: Path,
    check: bool = True,
    timeout_seconds: float = 90,
) -> tuple[int, str]:
    """Export read-only evidence with one bounded retry for SSH teardown races."""
    out.parent.mkdir(parents=True, exist_ok=True)
    err = Path(str(out) + ".stderr")
    attempts = 2
    last_timeout: subprocess.TimeoutExpired | None = None
    for attempt in range(1, attempts + 1):
        proc: subprocess.Popen | None = None
        try:
            with out.open("wb") as fo, err.open("wb") as fe:
                proc = subprocess.Popen(ssh_argv(node, command), stdout=fo, stderr=fe)
                returncode = proc.wait(timeout=timeout_seconds)
            if check and returncode != 0:
                raise RuntimeError(f"{node} export failed ({returncode}): {command}; see {err}")
            return returncode, str(err)
        except subprocess.TimeoutExpired as exc:
            last_timeout = exc
            if proc is not None and proc.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=8,
                        check=False,
                    )
                finally:
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
            if attempt >= attempts:
                break
            time.sleep(REMOTE_EXPORT_RETRY_DELAY_SECONDS)
    assert last_timeout is not None
    raise last_timeout


def run_remote_file_jobs(
    jobs: list[tuple[str, str, Path]],
    *,
    timeout_seconds: float = 45,
    max_workers: int = 6,
) -> list[str]:
    """Run evidence exports in parallel across nodes, serializing each node's SSH jobs."""
    if not jobs:
        return []

    grouped: dict[str, list[tuple[int, tuple[str, str, Path]]]] = {}
    for index, job in enumerate(jobs):
        grouped.setdefault(job[0], []).append((index, job))

    def run_node(node_jobs: list[tuple[int, tuple[str, str, Path]]]) -> list[tuple[int, str | None]]:
        node_results: list[tuple[int, str | None]] = []
        for index, job in node_jobs:
            node, command, out = job
            try:
                remote_to_file(node, command, out, timeout_seconds=timeout_seconds)
                node_results.append((index, None))
            except Exception as exc:
                node_results.append((index, f"{out.name}: {exc}"))
        return node_results

    results: list[tuple[int, str | None]] = []
    workers = max(1, min(max_workers, len(grouped)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="recorder-finalize") as pool:
        futures = [pool.submit(run_node, node_jobs) for node_jobs in grouped.values()]
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as exc:
                results.append((len(jobs), f"remote evidence worker failed unexpectedly: {exc}"))
    return [message for _, message in sorted(results, key=lambda item: item[0]) if message]

def start_capture(node: str, command: str, out: Path, label: str) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    err = Path(str(out) + ".stderr")
    fo = out.open("wb")
    fe = err.open("wb")
    try:
        p = subprocess.Popen(
            ssh_argv(node, command),
            stdin=subprocess.DEVNULL,
            stdout=fo,
            stderr=fe,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    finally:
        fo.close()
        fe.close()
    return {"label": label, "pid": p.pid, "stdout": str(out), "stderr": str(err)}


def start_serial(label: str, pattern: str, out: Path, run_id: str) -> dict:
    SERIAL_CONTROL_ROOT.mkdir(parents=True, exist_ok=True)
    pause_file = SERIAL_CONTROL_ROOT / f"{run_id}-{label.lower()}.pause"
    pause_file.unlink(missing_ok=True)
    # serial_capture.py writes the research stream directly to --output. Do not
    # let this long-lived child inherit the recorder CLI's stdout/stderr handles:
    # callers such as flood_harness.py capture those handles and would otherwise
    # wait forever for EOF after `recorder start` exits.
    err = Path(str(out) + ".stderr")
    fe = err.open("wb")
    try:
        p = subprocess.Popen(
            [
                sys.executable,
                str(SERIAL_SCRIPT),
                "--label", label,
                "--vidpid-regex", pattern,
                "--output", str(out),
                "--pause-file", str(pause_file),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=fe,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    finally:
        fe.close()
    return {
        "label": f"{label.lower()}-serial",
        "pid": p.pid,
        "stdout": str(out),
        "stderr": str(err),
        "pause_file": str(pause_file),
    }


def stop_tree(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timed out stopping recorder child PID {pid}") from exc


def process_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_uint32()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def ports_snapshot() -> list[dict]:
    return [{"device": p.device, "description": p.description, "hwid": p.hwid} for p in list_ports.comports()]


def find_port(pattern: re.Pattern[str]):
    for p in list_ports.comports():
        hay = " ".join(str(x or "") for x in (p.device, p.description, p.hwid))
        if pattern.search(hay):
            return p
    return None


def wait_for_new_marker(path: Path, marker: str, start_size: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    needle = marker.encode("utf-8")
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > start_size:
            with path.open("rb") as f:
                f.seek(start_size)
                if needle in f.read():
                    return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for serial recorder marker {marker!r} in {path}")


def capture_health(state: dict, require_ports: bool = True, check_remote: bool = True) -> list[str]:
    errors: list[str] = []
    for child in state.get("children", []):
        label = str(child.get("label", "unknown"))
        pid = int(child.get("pid", 0))
        if pid <= 0 or not process_alive(pid):
            errors.append(f"collector process not alive: {label} pid={pid}")
        pause_file = child.get("pause_file")
        if pause_file and Path(pause_file).exists():
            errors.append(f"serial collector still paused: {label}")
    if require_ports:
        labels = {str(c.get("label")) for c in state.get("children", [])}
        if "emu01-serial" in labels and find_port(EMU_PATTERN) is None:
            errors.append("EMU-01 USB serial device is absent")
        if "sec-serial" in labels and find_port(SEC_PATTERN) is None:
            errors.append("SEC USB serial device is absent")
    if check_remote:
        ready, details = evidence_readiness()
        if not ready:
            for node, detail in details.items():
                if not detail.startswith("READY|"):
                    errors.append(f"{node} evidence not ready: {detail}")
    return errors


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def load_state() -> dict:
    if not STATE_PATH.exists():
        raise RuntimeError("No active research-recorder run.")
    return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))


def save_state(state: dict) -> None:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_PATH.with_name(f".{STATE_PATH.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, STATE_PATH)
    finally:
        temp_path.unlink(missing_ok=True)


def load_run_lock() -> dict:
    if not LOCK_PATH.exists():
        raise RuntimeError("Recorder ownership lock is missing while an active run state exists")
    return json.loads(LOCK_PATH.read_text(encoding="utf-8-sig"))


def acquire_run_lock(run_id: str) -> str:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    owner_token = secrets.token_hex(24)
    lock = {
        "run_id": run_id,
        "owner_token": owner_token,
        "owner_pid": os.getpid(),
        "created_utc": utc_now(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(LOCK_PATH, flags)
    except FileExistsError as exc:
        try:
            current = json.loads(LOCK_PATH.read_text(encoding="utf-8-sig"))
            detail = f"run_id={current.get('run_id')} owner_pid={current.get('owner_pid')}"
        except Exception:
            detail = "lock metadata unreadable"
        raise RuntimeError(
            "A recorder run is already active/locked; concurrent research capture is prohibited "
            f"({detail}). Use status, then stop/recover it before starting another."
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lock, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        LOCK_PATH.unlink(missing_ok=True)
        raise
    return owner_token


def assert_state_ownership(state: dict) -> None:
    token = str(state.get("owner_token") or "")
    if not token:
        raise RuntimeError("Active recorder state has no ownership token; recover it with the compatible tooling before continuing")
    lock = load_run_lock()
    if lock.get("owner_token") != token or lock.get("run_id") != state.get("run_id"):
        raise RuntimeError(
            "Recorder ownership mismatch: refusing to operate on collectors that may belong to another run "
            f"(state_run={state.get('run_id')} lock_run={lock.get('run_id')})"
        )


def release_run_lock(owner_token: str) -> None:
    lock = load_run_lock()
    if lock.get("owner_token") != owner_token:
        raise RuntimeError("Recorder ownership changed; refusing to remove another run's lock")
    LOCK_PATH.unlink()


def load_owned_state() -> dict:
    state = load_state()
    assert_state_ownership(state)
    return state


def validate_common() -> None:
    if not SSH_EXE.exists():
        raise RuntimeError(f"OpenSSH client missing: {SSH_EXE}")
    if not RECORDER_KEY.exists():
        raise RuntimeError(f"Recorder key missing: {RECORDER_KEY}")


def preflight(require_emu: bool = False, require_sec: bool = False) -> int:
    validate_common()
    ok = True
    print("NODE\tREACHABLE\tDETAIL")
    for node in TARGETS:
        cp = run_remote(node, "snapshot", check=False)
        detail = cp.stdout.splitlines()[0] if cp.stdout else cp.stderr.strip().replace("\n", " ")[:120]
        good = cp.returncode == 0
        ok &= good
        print(f"{node}\t{str(good).lower()}\t{detail}")

    roles = database_roles()
    print("DB_ROLES=" + json.dumps(roles, sort_keys=True))
    if list(roles.values()).count("leader") != 1:
        ok = False

    try:
        evidence_status_node, evidence_status_text, evidence_status_supported = try_live_evidence_status()
        print(f"EVIDENCE_STATUS_NODE={evidence_status_node}")
        if evidence_status_supported:
            for line in evidence_status_text.splitlines():
                print(f"EVIDENCE_STATUS={line}")
        else:
            print(f"EVIDENCE_STATUS={evidence_status_text}")
    except Exception as exc:
        print(f"EVIDENCE_STATUS_ERROR={exc}")
        ok = False

    evidence_ok, evidence = evidence_readiness()
    for node, detail in evidence.items():
        print(f"EVIDENCE_READY_{node.upper()}={detail}")
    if not evidence_ok:
        ok = False

    try:
        print(f"AUTHORITATIVE_UTC={authoritative_utc_now()}")
    except Exception as exc:
        print(f"AUTHORITATIVE_UTC_ERROR={exc}")
        ok = False

    try:
        clock_ok, clock = clock_readiness()
        print(f"CLOCK_GATE={'PASS' if clock_ok else 'FAIL'}")
        print(f"CLOCK_WORKSTATION_CALIBRATION_LIMIT_SECONDS={clock['workstation_calibration_limit_seconds']:.3f}")
        print(f"CLOCK_WORKSTATION_DRIFT_LIMIT_SECONDS={clock['workstation_drift_limit_seconds']:.3f}")
        print(f"CLOCK_CLOUD_SPREAD_LIMIT_SECONDS={clock['cloud_spread_limit_seconds']:.3f}")
        print(f"CLOCK_GATEWAY_CLOUD_SKEW_LIMIT_SECONDS={clock['gateway_cloud_skew_limit_seconds']:.3f}")
        if clock.get("server_minus_workstation_seconds") is not None:
            print(f"CLOCK_SERVER_MINUS_WORKSTATION_SECONDS={float(clock['server_minus_workstation_seconds']):+.6f}")
        if clock.get("cloud_spread_seconds") is not None:
            print(f"CLOCK_CLOUD_SPREAD_SECONDS={float(clock['cloud_spread_seconds']):.6f}")
        if clock.get("gateway_minus_cloud_seconds") is not None:
            print(f"CLOCK_GATEWAY_MINUS_CLOUD_SECONDS={float(clock['gateway_minus_cloud_seconds']):+.6f}")
        for node, probe in clock.get("probes", {}).items():
            print(
                f"CLOCK_{node.upper()}="
                f"offset={float(probe['server_minus_workstation_seconds']):+.6f}s|"
                f"rtt_median={float(probe['rtt_median_ms']):.3f}ms|samples={probe['samples']}"
            )
        for error in clock.get("errors", []):
            print(f"CLOCK_ERROR={error}")
        if not clock_ok:
            ok = False
    except Exception as exc:
        print(f"CLOCK_GATE=FAIL")
        print(f"CLOCK_ERROR={exc}")
        ok = False

    emu = find_port(EMU_PATTERN)
    sec = find_port(SEC_PATTERN)
    print(f"EMU_PORT={emu.device if emu else 'ABSENT'}")
    print(f"SEC_PORT={sec.device if sec else 'ABSENT'}")
    if require_emu and emu is None:
        ok = False
    if require_sec and sec is None:
        ok = False
    return 0 if ok else 2


def assert_id(value: str, name: str) -> None:
    if not SAFE_ID.fullmatch(value or ""):
        raise ValueError(f"invalid {name}: {value!r}")


def _cmd_start_locked(args, owner_token: str) -> int:
    validate_common()
    assert_id(args.group, "group")
    assert_id(args.run_id, "run-id")
    if not DEV_EUI.fullmatch(args.dev_eui):
        raise ValueError("DevEUI must be exactly 16 hexadecimal characters")
    if not 1 <= args.interval <= 60:
        raise ValueError("interval must be 1..60 seconds")
    if not 0 <= args.fabric_settle_seconds <= 900:
        raise ValueError("fabric-settle-seconds must be 0..900 seconds")
    if STATE_PATH.exists():
        raise RuntimeError("A recorder run is already active. Use status, then stop/recover it before starting another; research evidence is never overwritten.")
    preflight_rc = preflight(require_emu=not args.skip_serial, require_sec=args.capture_sec)
    if preflight_rc != 0:
        raise RuntimeError("Recorder preflight failed; no research run directory was created")

    run_dir = RESULTS_ROOT / args.group / args.run_id
    if run_dir.exists():
        raise RuntimeError(f"Run directory already exists; research evidence is never overwritten: {run_dir}")
    raw, derived, meta = run_dir / "raw", run_dir / "derived", run_dir / "metadata"
    for p in (raw, derived, meta):
        p.mkdir(parents=True, exist_ok=False)

    build_dir = RESULTS_ROOT / "_configuration" / "emu01-counted-test-15s"
    source = PROJECT_ROOT / "firmware" / "EMU01_Agriculture_Node" / "EMU01_Agriculture_Node.ino"
    hexfile = build_dir / "EMU01_Agriculture_Node.ino.hex"
    run_meta = {
        "run_id": args.run_id,
        "group": args.group,
        "scope": args.scope,
        "condition": args.condition,
        "expected_result": args.expected,
        "start_utc": None,
        "dev_eui": args.dev_eui.lower(),
        "gateway_eui": args.gateway_eui.lower(),
        "payload_version": 2,
        "payload_bytes": 46,
        "serial_capture_enabled": not args.skip_serial,
        "emu_source_capture_enabled": not args.skip_serial,
        "sec_source_capture_enabled": bool(args.capture_sec and not args.skip_serial),
        "emu_profile": "COUNTED_TEST_15S" if not args.skip_serial else "NOT_CAPTURED_UNCOUNTED",
        "sample_interval_seconds": 15 if not args.skip_serial else None,
        "normal_tx_interval_seconds": 15 if not args.skip_serial else None,
        "jitter_seconds": 0 if not args.skip_serial else None,
        "source_sha256": sha256(source) if not args.skip_serial else "",
        "counted_hex_sha256": sha256(hexfile) if not args.skip_serial else "",
        "recorder_key_fingerprint": "SHA256:LcXNMbqJN63QmQwQmjDe0RcjQ+r+hXOy69LZTawDjbs",
        "recorder_version": 9,
        "measurement_window_semantics": "collectors-ready authoritative start; fixed-duration runs close at exact planned UTC end; workstation source clock is independently calibrated to cloud UTC at start and end",
        "fabric_settle_seconds": args.fabric_settle_seconds,
        "recorder_owner_token_recorded": True,
    }
    save_json(meta / "usb-start.json", ports_snapshot())

    for node in TARGETS:
        remote_to_file(node, "snapshot", meta / f"{node}-snapshot-start.txt")
    write_evidence_status_snapshot(meta / "evidence-status-start.txt")

    children: list[dict] = []
    try:
        if not args.skip_serial:
            children.append(start_serial("EMU01", r"VID:PID=239A:8029|VID_239A&PID_8029|239A.*8029", raw / "emu-01-source.log", args.run_id))
            if args.capture_sec:
                children.append(start_serial("SEC", r"VID:PID=1915:521F|VID_1915&PID_521F|1915.*521F", raw / "sec-source.log", args.run_id))
        children.append(start_capture("gateway", f"resource {args.interval}", raw / "gateway-resource.csv", "gateway-resource"))
        children.append(start_capture("gateway", "logstream", raw / "gateway.log", "gateway-log"))
        for node in ("ulc01", "ulc02", "ulc03"):
            children.append(start_capture(node, f"resource-host {args.interval}", raw / f"{node}-host-resource.csv", f"{node}-host-resource"))
            children.append(start_capture(node, f"resource-docker {args.interval}", raw / f"{node}-docker-resource.csv", f"{node}-docker-resource"))
        # Capture the true ChirpStack acceptance boundary live. Using follow
        # streams avoids expensive post-run Docker log scraping and preserves
        # both HA nodes; summarize-run filters these files to the exact window.
        children.append(start_capture("ulc01", "docker-logstream chirpstack", raw / "ulc01-chirpstack.log", "ulc01-chirpstack-stream"))
        children.append(start_capture("ulc02", "docker-logstream chirpstack", raw / "ulc02-chirpstack.log", "ulc02-chirpstack-stream"))

        # Open the formal window only after each observation process is live.
        # Serial capture must explicitly prove that it owns the USB port first.
        if not args.skip_serial:
            wait_for_new_marker(raw / "emu-01-source.log", "RECORDER_SERIAL_OPEN", 0, 15.0)
            # Do not open a counted/rehearsal window merely because the USB port
            # exists. Require one real scheduled source transmission first; it is
            # warm-up evidence and is excluded because start_utc is captured only
            # after this gate passes.
            wait_for_new_marker(raw / "emu-01-source.log", "SENSOR_TX", 0, 35.0)
            if args.capture_sec:
                wait_for_new_marker(raw / "sec-source.log", "RECORDER_SERIAL_OPEN", 0, 15.0)
        provisional_state = {"children": children, "run_dir": str(run_dir)}
        startup_errors = capture_health(
            provisional_state,
            require_ports=not args.skip_serial,
            check_remote=False,
        )
        if startup_errors:
            raise RuntimeError("Collector startup gate failed: " + "; ".join(startup_errors))

        # Source lines use workstation UTC while the formal boundary uses ULC-01
        # UTC. Record a fresh mapping immediately before the authoritative start
        # so warm-up source lines can be excluded without depending on DB delivery.
        measurement_clock = clock_probe("ulc01")
        start = authoritative_utc_now()
        measurement_start_monotonic = time.monotonic()
    except Exception:
        for c in children:
            stop_tree(int(c["pid"]))
        raise

    run_meta["start_utc"] = start
    run_meta["measurement_clock_reference"] = "ulc01 midpoint-corrected command-channel probe immediately before formal start"
    run_meta["measurement_clock_server_minus_workstation_seconds"] = float(
        measurement_clock["server_minus_workstation_seconds"]
    )
    save_json(meta / "run-meta.json", run_meta)
    (meta / "start-utc.txt").write_text(start + "\n", encoding="ascii")

    with (raw / "markers.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp_utc", "type", "message"])
    with (derived / "trial-results.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "trial_id", "test_condition", "expected_result", "actual_result", "status",
            "start_utc", "end_utc", "duration_seconds", "gateway_received",
            "chirpstack_accepted", "chirpstack_rejected", "application_reached",
            "database_created", "outbox_created", "decision_time_seconds",
            "observations_json", "evidence_reference", "notes",
        ])

    state = {
        "run_id": args.run_id,
        "group": args.group,
        "scope": args.scope,
        "run_dir": str(run_dir),
        "start_utc": start,
        "measurement_start_monotonic": measurement_start_monotonic,
        "dev_eui": args.dev_eui.lower(),
        "gateway_eui": args.gateway_eui.lower(),
        "fabric_settle_seconds": args.fabric_settle_seconds,
        "owner_token": owner_token,
        "children": children,
        "active_trial": None,
    }
    save_state(state)
    print(f"RECORDER_STARTED={args.run_id}")
    print(f"RUN_DIR={run_dir}")
    print(f"START_UTC={start}")
    return 0


def cmd_start(args) -> int:
    # The lock is acquired atomically before the old shared-state check. This
    # makes concurrent starts fail before either invocation can create evidence
    # directories or collectors, and the token binds later stop/finalization to
    # the run that actually owns the active state.
    assert_id(args.group, "group")
    assert_id(args.run_id, "run-id")
    owner_token = acquire_run_lock(args.run_id)
    try:
        return _cmd_start_locked(args, owner_token)
    except Exception:
        try:
            release_run_lock(owner_token)
        except Exception:
            pass
        raise


def latest_server_capture_utc(state: dict) -> str:
    """Use an already-open server resource stream as the in-run clock witness."""
    for child in state.get("children", []):
        if child.get("label") != "ulc01-host-resource":
            continue
        path = Path(str(child.get("stdout", "")))
        if not path.exists() or path.stat().st_size == 0:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-20:]):
            value = line.split(",", 1)[0].strip()
            if value and value != "timestamp_utc":
                try:
                    parse_utc(value)
                    return value
                except Exception:
                    pass
    return ""


def append_supervisor_health(path: Path, status: str, details: list[str], state: dict | None = None) -> str:
    local_before = datetime.now(timezone.utc)
    authoritative = latest_server_capture_utc(state or {})
    clock_error = "" if authoritative else "live server timestamp not yet available from open resource stream"
    local_after = datetime.now(timezone.utc)
    midpoint = local_before + (local_after - local_before) / 2
    midpoint_text = midpoint.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    server_minus_workstation = ""
    if authoritative:
        server_minus_workstation = f"{(parse_utc(authoritative) - midpoint).total_seconds():.6f}"
    round_trip_ms = (local_after - local_before).total_seconds() * 1000.0
    effective_status = "WARN" if clock_error and status == "PASS" else status
    effective_details = list(details)
    if clock_error:
        effective_details.append(clock_error)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow([
                "authoritative_timestamp_utc", "workstation_midpoint_utc",
                "server_minus_workstation_seconds", "clock_probe_round_trip_ms",
                "status", "detail",
            ])
        w.writerow([
            authoritative, midpoint_text, server_minus_workstation, f"{round_trip_ms:.3f}",
            effective_status, "; ".join(effective_details) if effective_details else "all collectors and evidence services healthy",
        ])
    return authoritative or midpoint_text


def cmd_run(args) -> int:
    """Run the recorder under a foreground supervisor and always finalize it.

    This is the preferred operator path for research runs. The supervisor keeps
    the workstation process alive, verifies collector/evidence health at a
    bounded interval, records its own control-plane health evidence, and invokes
    the normal stop/export/hash path on completion or Ctrl+C.
    """
    if not 5 <= args.health_interval <= 300:
        raise ValueError("health-interval must be 5..300 seconds")
    if args.duration_seconds < 0:
        raise ValueError("duration-seconds must be >= 0")

    cmd_start(args)
    state = load_owned_state()
    run_dir = Path(state["run_dir"])
    health_path = run_dir / "raw" / "control-plane-health.csv"
    supervisor_errors: list[str] = []
    consecutive_transient_failures = 0
    planned_end_utc = ""
    if args.duration_seconds:
        measurement_start_monotonic = float(state.get("measurement_start_monotonic") or time.monotonic())
        deadline = measurement_start_monotonic + args.duration_seconds
        planned_end = parse_utc(str(state["start_utc"])) + timedelta(seconds=args.duration_seconds)
        planned_end_utc = planned_end.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    else:
        deadline = None
    print("SUPERVISOR_ACTIVE=true")
    print(f"HEALTH_INTERVAL_SECONDS={args.health_interval}")
    if deadline is None:
        print("SUPERVISOR_DURATION=until-interrupt")
    else:
        print(f"SUPERVISOR_DURATION_SECONDS={args.duration_seconds}")

    try:
        while True:
            try:
                errors = capture_health(state, check_remote=False)
            except Exception as exc:
                errors = [f"health probe failed: {exc}"]

            hard_errors = [error for error in errors if error.startswith("collector process not alive:")]
            if hard_errors:
                health_timestamp = append_supervisor_health(health_path, "FAIL", hard_errors, state)
                supervisor_errors.extend(hard_errors)
                print(f"SUPERVISOR_HEALTH=FAIL|{health_timestamp}", file=sys.stderr)
                for error in hard_errors:
                    print(f"SUPERVISOR_ERROR={error}", file=sys.stderr)
                break

            if errors:
                consecutive_transient_failures += 1
                terminal = consecutive_transient_failures >= SUPERVISOR_TRANSIENT_FAILURE_LIMIT
                health_timestamp = append_supervisor_health(health_path, "FAIL" if terminal else "WARN", errors, state)
                if terminal:
                    supervisor_errors.extend(errors)
                    print(f"SUPERVISOR_HEALTH=FAIL|consecutive={consecutive_transient_failures}/{SUPERVISOR_TRANSIENT_FAILURE_LIMIT}|{health_timestamp}", file=sys.stderr)
                    for error in errors:
                        print(f"SUPERVISOR_ERROR={error}", file=sys.stderr)
                    break
                print(f"SUPERVISOR_HEALTH=WARN|consecutive={consecutive_transient_failures}/{SUPERVISOR_TRANSIENT_FAILURE_LIMIT}|{health_timestamp}", file=sys.stderr)
                for error in errors:
                    print(f"SUPERVISOR_WARNING={error}", file=sys.stderr)
            else:
                consecutive_transient_failures = 0
                health_timestamp = append_supervisor_health(health_path, "PASS", [], state)
                print(f"SUPERVISOR_HEALTH=PASS|{health_timestamp}")

            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # The counted window ends exactly at start + requested
                    # duration. Settling/export may continue after this point
                    # but can never extend the measurement boundary.
                    state["measurement_end_utc"] = planned_end_utc
                    save_state(state)
                    print(f"MEASUREMENT_WINDOW_CLOSED={planned_end_utc}")
                    break
                time.sleep(min(float(args.health_interval), remaining))
            else:
                time.sleep(float(args.health_interval))
    except KeyboardInterrupt:
        print("SUPERVISOR_INTERRUPT=operator")
    finally:
        if supervisor_errors:
            meta = run_dir / "metadata" / "supervisor-errors.txt"
            meta.write_text("\n".join(supervisor_errors) + "\n", encoding="utf-8")
        stop_rc = cmd_stop(args) if STATE_PATH.exists() else 2

    if supervisor_errors:
        return 2
    return stop_rc


def cmd_mark(args) -> int:
    state = load_owned_state()
    if not args.message:
        raise ValueError("mark requires --message")
    path = Path(state["run_dir"]) / "raw" / "markers.csv"
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([utc_now(), "MARK", args.message])
    print(f"MARK_RECORDED={args.message}")
    return 0


def write_trial_row(run_dir: Path, row: list[object]) -> None:
    path = run_dir / "derived" / "trial-results.csv"
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def parse_trial_metrics(items: list[str] | None) -> dict[str, object]:
    """Parse repeatable KEY=VALUE observations without inventing test semantics."""
    out: dict[str, object] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"trial metric must be KEY=VALUE: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key):
            raise ValueError(f"invalid trial metric key: {key!r}")
        if key in out:
            raise ValueError(f"duplicate trial metric key: {key}")
        lowered = value.lower()
        if lowered in ("true", "false"):
            parsed: object = lowered == "true"
        elif lowered in ("yes", "no", "unknown", "match", "mismatch"):
            parsed = lowered
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        out[key] = parsed
    return out


def cmd_trial(args) -> int:
    """Legacy one-shot classification retained for compatibility.

    New counted runs should use trial-begin/trial-end so each attempt has a
    server-authoritative observation window and a pre-attempt health gate.
    """
    state = load_owned_state()
    assert_id(args.trial_id, "trial-id")
    health = capture_health(state)
    if health:
        raise RuntimeError("Recorder health gate failed: " + "; ".join(health))
    now = utc_now()
    write_trial_row(Path(state["run_dir"]), [
        args.trial_id, args.condition, args.expected, args.actual, args.status,
        now, now, "0.000", "unknown", "unknown", "unknown", "unknown",
        "unknown", "unknown", "", "{}", "", args.notes,
    ])
    print(f"TRIAL_RECORDED={args.trial_id}|{args.status}")
    return 0


def cmd_trial_begin(args) -> int:
    state = load_owned_state()
    assert_id(args.trial_id, "trial-id")
    if state.get("active_trial"):
        raise RuntimeError(f"Trial already active: {state['active_trial'].get('trial_id')}")
    health = capture_health(state)
    if health:
        raise RuntimeError("Recorder health gate failed before trial: " + "; ".join(health))
    start = utc_now()
    state["active_trial"] = {
        "trial_id": args.trial_id,
        "condition": args.condition,
        "expected": args.expected,
        "start_utc": start,
    }
    save_state(state)
    marker = Path(state["run_dir"]) / "raw" / "markers.csv"
    with marker.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([start, "TRIAL_BEGIN", args.trial_id])
    print(f"TRIAL_STARTED={args.trial_id}|{start}")
    return 0


def cmd_trial_end(args) -> int:
    state = load_owned_state()
    assert_id(args.trial_id, "trial-id")
    active = state.get("active_trial")
    if not active:
        raise RuntimeError("No trial is active")
    if active.get("trial_id") != args.trial_id:
        raise RuntimeError(f"Active trial is {active.get('trial_id')}, not {args.trial_id}")

    health = capture_health(state)
    if health and args.status not in ("INVALID", "BLOCKED"):
        raise RuntimeError(
            "Recorder health gate failed during trial; classify this attempt INVALID or BLOCKED before continuing: "
            + "; ".join(health)
        )

    end = utc_now()
    start_dt = parse_utc(active["start_utc"])
    end_dt = parse_utc(end)
    duration = max(0.0, (end_dt - start_dt).total_seconds())
    notes = args.notes
    if health:
        suffix = "recorder_health=" + "; ".join(health)
        notes = f"{notes}; {suffix}" if notes else suffix

    observations = parse_trial_metrics(args.metric)
    write_trial_row(Path(state["run_dir"]), [
        args.trial_id, active.get("condition", ""), active.get("expected", ""),
        args.actual, args.status, active["start_utc"], end, f"{duration:.3f}",
        args.gateway_received, args.chirpstack_accepted, args.chirpstack_rejected,
        args.application_reached, args.database_created, args.outbox_created,
        "" if args.decision_time is None else f"{args.decision_time:.6f}",
        json.dumps(observations, sort_keys=True, separators=(",", ":")),
        args.evidence_reference, notes,
    ])
    marker = Path(state["run_dir"]) / "raw" / "markers.csv"
    with marker.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([end, "TRIAL_END", f"{args.trial_id}|{args.status}"])
    state["active_trial"] = None
    save_state(state)
    print(f"TRIAL_RECORDED={args.trial_id}|{args.status}|duration_seconds={duration:.3f}")
    return 0


def serial_child(state: dict, device: str) -> dict:
    wanted = "emu01-serial" if device == "emu" else "sec-serial"
    for child in state.get("children", []):
        if child.get("label") == wanted:
            return child
    raise RuntimeError(f"No active {device.upper()} serial collector in this run")


def cmd_serial_pause(args) -> int:
    state = load_owned_state()
    if state.get("active_trial"):
        raise RuntimeError("Cannot pause serial capture while a counted trial is active")
    child = serial_child(state, args.device)
    pid = int(child["pid"])
    if not process_alive(pid):
        raise RuntimeError(f"{child['label']} collector is not alive")
    out = Path(child["stdout"])
    start_size = out.stat().st_size if out.exists() else 0
    pause_file = Path(child["pause_file"])
    pause_file.parent.mkdir(parents=True, exist_ok=True)
    pause_file.write_text(f"requested_utc={utc_now()}\n", encoding="ascii")
    wait_for_new_marker(out, "RECORDER_SERIAL_RELEASED", start_size, 6.0)
    if not process_alive(pid):
        raise RuntimeError(f"{child['label']} exited while yielding the serial port")
    print(f"SERIAL_PAUSED={args.device}|released=true|pause_file={pause_file}")
    return 0


def cmd_serial_resume(args) -> int:
    state = load_owned_state()
    if state.get("active_trial"):
        raise RuntimeError("Cannot resume/re-enumerate serial capture while a counted trial is active")
    child = serial_child(state, args.device)
    pid = int(child["pid"])
    if not process_alive(pid):
        raise RuntimeError(f"{child['label']} collector is not alive")
    out = Path(child["stdout"])
    start_size = out.stat().st_size if out.exists() else 0
    pause_file = Path(child["pause_file"])
    pause_file.unlink(missing_ok=True)
    wait_for_new_marker(out, "RECORDER_SERIAL_RESUMED", start_size, 6.0)
    wait_for_new_marker(out, "RECORDER_SERIAL_OPEN", start_size, 15.0)
    pattern = EMU_PATTERN if args.device == "emu" else SEC_PATTERN
    if find_port(pattern) is None:
        raise RuntimeError(f"{args.device.upper()} USB device did not re-enumerate after serial resume")
    if not process_alive(pid):
        raise RuntimeError(f"{child['label']} exited while resuming serial capture")
    print(f"SERIAL_RESUMED={args.device}|open=true")
    return 0


def cmd_evidence_status(_args) -> int:
    leader, text = live_evidence_status()
    print(f"EVIDENCE_STATUS_NODE={leader}")
    print(text)
    return 0


def cmd_status(_args) -> int:
    state = load_owned_state()
    print(json.dumps(state, indent=2, sort_keys=True))
    for c in state.get("children", []):
        print(f"{c['label']}|pid={c['pid']}|alive={str(process_alive(int(c['pid']))).lower()}")
    try:
        errors = capture_health(state)
    except Exception as exc:
        errors = [f"health probe failed: {exc}"]
    if errors:
        print("RECORDER_HEALTH=FAIL")
        for error in errors:
            print(f"HEALTH_ERROR={error}")
        return 2
    print("RECORDER_HEALTH=PASS")
    return 0


def cmd_stop(_args) -> int:
    state = load_owned_state()
    lock = load_run_lock()
    owner_pid = int(lock.get("owner_pid") or 0)
    action = str(getattr(_args, "action", "stop") or "stop")
    # A foreground `run` owns its collectors and must be the only process that
    # finalizes them while it is alive. External stop/recover racing the live
    # owner can otherwise kill collectors between the final supervisor health
    # sample and sealing. Recovery is specifically for a dead/interrupted owner.
    if owner_pid and owner_pid != os.getpid() and process_alive(owner_pid):
        raise RuntimeError(
            f"Recorder owner PID {owner_pid} is still alive; refusing external {action} while the supervised run owns finalization"
        )
    run_dir = Path(state["run_dir"])
    raw, derived, meta = run_dir / "raw", run_dir / "derived", run_dir / "metadata"

    # Recovery is idempotent for already-sealed runs. Never reopen read-only raw
    # evidence or rewrite the manifest. Because old state stores only PIDs (not
    # immutable process identities), refuse to kill any PID that is still alive:
    # it could have been reused after the original recorder died.
    if getattr(_args, "action", "") == "recover" and (meta / "SHA256SUMS.csv").is_file() and (derived / "run-status.txt").is_file():
        still_present = [
            f"{child.get('label')}:{child.get('pid')}"
            for child in state.get("children", [])
            if process_alive(int(child["pid"]))
        ]
        if still_present:
            print("RECOVERY_REFUSED_LIVE_OR_REUSED_PIDS=" + ",".join(still_present), file=sys.stderr)
            return 2
        STATE_PATH.unlink(missing_ok=True)
        release_run_lock(str(state["owner_token"]))
        print(f"RECOVERY_SEALED_STALE_OWNERSHIP_CLEARED={state.get('run_id')}")
        return 0

    errors: list[str] = []
    fatal_finalization_error: str | None = None
    end = str(state.get("measurement_end_utc") or "").strip()
    if end:
        parse_utc(end)
    else:
        try:
            end = authoritative_utc_now()
        except Exception as exc:
            end = utc_now()
            errors.append(f"authoritative end UTC unavailable; workstation UTC fallback used: {exc}")

    if state.get("active_trial"):
        errors.append(f"run stopped with active trial {state['active_trial'].get('trial_id')}")

    # During a run, the long-lived SSH resource collectors are themselves the
    # remote liveness evidence. Do not open another set of SSH readiness probes
    # while those streams are active.
    try:
        pre_stop_errors = capture_health(state, check_remote=False)
    except Exception as exc:
        pre_stop_errors = [f"health probe failed: {exc}"]
    for error in pre_stop_errors:
        errors.append("pre-stop recorder check: " + error)

    for child in state.get("children", []):
        try:
            stop_tree(int(child["pid"]))
        except Exception as exc:
            errors.append(f"failed to stop recorder child {child.get('label')} PID {child.get('pid')}: {exc}")
        if child.get("pause_file"):
            Path(child["pause_file"]).unlink(missing_ok=True)
    stop_deadline = time.monotonic() + 5.0
    while time.monotonic() < stop_deadline:
        if not any(process_alive(int(child["pid"])) for child in state.get("children", [])):
            break
        time.sleep(0.2)

    alive_children = [
        f"{child.get('label')}:{child.get('pid')}"
        for child in state.get("children", [])
        if process_alive(int(child["pid"]))
    ]
    if alive_children:
        errors.append("recorder children still alive after stop: " + ", ".join(alive_children))
    else:
        # Give sshd/client sockets from the eight long-lived collectors a brief
        # chance to close before opening the finalization probe/export burst.
        time.sleep(FINALIZATION_SSH_QUIET_SECONDS)

    # Re-measure the workstation-to-cloud mapping only after long-lived SSH
    # collectors are stopped. This proves the source-clock calibration stayed
    # stable across the formal window and also re-checks cloud/gateway agreement.
    try:
        end_clock_ok, end_clock = clock_readiness()
        save_json(meta / "clock-calibration-end.json", end_clock)
        run_meta_path = meta / "run-meta.json"
        run_meta = json.loads(run_meta_path.read_text(encoding="utf-8-sig"))
        start_offset = float(run_meta["measurement_clock_server_minus_workstation_seconds"])
        end_offset = float(end_clock["probes"]["ulc01"]["server_minus_workstation_seconds"])
        drift = end_offset - start_offset
        calibration_ok = end_clock_ok and abs(drift) <= MAX_WORKSTATION_CLOCK_DRIFT_SECONDS
        run_meta["measurement_clock_end_server_minus_workstation_seconds"] = end_offset
        run_meta["measurement_clock_drift_seconds"] = drift
        run_meta["measurement_clock_drift_limit_seconds"] = MAX_WORKSTATION_CLOCK_DRIFT_SECONDS
        run_meta["measurement_clock_calibration_status"] = "PASS" if calibration_ok else "FAIL"
        save_json(run_meta_path, run_meta)
        if not end_clock_ok:
            errors.append("end clock readiness failed: " + "; ".join(str(x) for x in end_clock.get("errors", [])))
        if abs(drift) > MAX_WORKSTATION_CLOCK_DRIFT_SECONDS:
            errors.append(
                f"workstation/cloud calibration drifted by {drift:+.6f}s; "
                f"limit is +/-{MAX_WORKSTATION_CLOCK_DRIFT_SECONDS:.3f}s"
            )
    except Exception as exc:
        errors.append(f"end clock calibration failed: {exc}")

    try:
        (meta / "end-utc.txt").write_text(end + "\n", encoding="ascii")
        save_json(meta / "usb-end.json", ports_snapshot())

        snapshot_jobs = [
            (node, "snapshot", meta / f"{node}-snapshot-end.txt")
            for node in TARGETS
        ]
        errors.extend(run_remote_file_jobs(snapshot_jobs, timeout_seconds=30, max_workers=len(snapshot_jobs)))

        roles = database_roles()
        save_json(meta / "database-roles-end.json", roles)
        leaders = [node for node, role in roles.items() if role == "leader"]
        if len(leaders) != 1:
            errors.append(f"expected exactly one database leader; roles={roles}")
        else:
            leader = leaders[0]
            start, dev, gateway = state["start_utc"], state["dev_eui"], state["gateway_eui"]
            settle_seconds = int(state.get("fabric_settle_seconds") or 0)
            try:
                settle = settle_fabric_window(leader, start, end, dev, settle_seconds)
                save_json(meta / "fabric-settle.json", settle)
                if settle_seconds and settle.get("status") != "CONFIRMED":
                    errors.append(
                        "Fabric settle did not reach confirmation for every in-window uplink: "
                        f"status={settle.get('status')} uplinks={settle.get('uplink_rows')} "
                        f"confirmed={settle.get('confirmed_source_events')} missing={len(settle.get('missing_source_events') or [])}"
                    )
            except Exception as exc:
                errors.append(f"Fabric settle probe failed: {exc}")
            try:
                write_evidence_status_snapshot(meta / "evidence-status-end.txt")
            except Exception as exc:
                errors.append(str(exc))
            export_specs = (
                ("uplinks", "uplinks.csv", dev),
                ("measurements", "measurements.csv", dev),
                ("outbox", "fabric-outbox.csv", dev),
                ("gatewaymqtt", "gateway-mqtt-events.csv", gateway),
            )
            export_jobs = [
                (leader, f"db-export {table} {start} {end} {identity}", raw / filename)
                for table, filename, identity in export_specs
            ]
            errors.extend(run_remote_file_jobs(export_jobs, timeout_seconds=45, max_workers=4))

        start = state["start_utc"]
        # Keep mandatory finalization evidence minimal and directly tied to the
        # Chapter 3 calculations. ChirpStack acceptance logs are required for
        # formal PDR. Database/outbox/evidence/resource data above carry the
        # remaining formal metrics. Large service/kernel logs are diagnostic and
        # opt-in because opening many fresh SSH sessions immediately after the
        # long-lived collectors close can itself destabilize finalization.
        log_jobs: list[tuple[str, str, Path]] = []
        if os.environ.get("RESEARCH_RECORDER_DIAGNOSTIC_LOGS", "0").strip() == "1":
            log_jobs.extend([
                ("ulc03", f"docker-log node-red-node-red-1 {start} {end}", raw / "ulc03-node-red.log"),
                ("ulc01", f"docker-log lorawan-gateway-evidence-collector-1 {start} {end}", raw / "ulc01-evidence-collector.log"),
                ("ulc03", f"docker-log lorawan-gateway-evidence-collector-1 {start} {end}", raw / "ulc03-evidence-collector.log"),
                ("ulc02", f"docker-log lorawan-gateway-evidence-verifier-1 {start} {end}", raw / "ulc02-evidence-verifier.log"),
                ("ulc03", f"docker-log lorawan-gateway-evidence-verifier-1 {start} {end}", raw / "ulc03-evidence-verifier.log"),
                ("ulc01", f"unit-log mosquitto {start} {end}", raw / "ulc01-mosquitto.log"),
                ("ulc02", f"unit-log mosquitto {start} {end}", raw / "ulc02-mosquitto.log"),
                ("ulc01", f"kernel-log {start} {end}", raw / "ulc01-kernel.log"),
                ("ulc02", f"kernel-log {start} {end}", raw / "ulc02-kernel.log"),
                ("ulc03", f"kernel-log {start} {end}", raw / "ulc03-kernel.log"),
            ])
            if state.get("scope") == "full":
                log_jobs.extend([
                    ("ulc01", f"docker-log lorawan-gateway-evidence-fabric-adapter-1 {start} {end}", raw / "ulc01-fabric-adapter.log"),
                    ("ulc02", f"docker-log lorawan-gateway-evidence-fabric-adapter-1 {start} {end}", raw / "ulc02-fabric-adapter.log"),
                ])
        diagnostic_log_errors = run_remote_file_jobs(log_jobs, timeout_seconds=45, max_workers=2)
        if diagnostic_log_errors:
            (meta / "diagnostic-log-export-errors.txt").write_text(
                "\n".join(diagnostic_log_errors) + "\n", encoding="utf-8"
            )

        try:
            cp = subprocess.run(
                [sys.executable, str(SUMMARY_SCRIPT), str(run_dir)],
                text=True,
                capture_output=True,
                timeout=60,
            )
            if cp.returncode != 0:
                errors.append(f"summarizer failed: {cp.stderr.strip()}")
        except Exception as exc:
            errors.append(f"summarizer failed: {exc}")
    except Exception as exc:
        fatal_finalization_error = f"unexpected finalization error: {type(exc).__name__}: {exc}"
        errors.append(fatal_finalization_error)

    # Only the run that owns the atomic lock may clear active state. Keep the
    # lock in place until after state removal so no new start can interleave with
    # this finalizer. A lock-release failure is evidence/tooling failure and
    # intentionally leaves the lock visible for operator recovery.
    if not alive_children:
        STATE_PATH.unlink(missing_ok=True)
        try:
            # After state removal, an already-missing lock is harmless: no old
            # run remains addressable. If a new run acquired a different lock in
            # this tiny interval, release_run_lock will detect the token mismatch
            # and preserve it.
            if LOCK_PATH.exists():
                release_run_lock(str(state["owner_token"]))
        except Exception as exc:
            errors.append(f"failed to release recorder ownership lock: {exc}")

    if alive_children:
        status_text = "INVALID_RECORDER_CHILDREN_STILL_RUNNING"
    elif fatal_finalization_error:
        status_text = "INVALID_TOOLING_FINALIZATION"
    else:
        status_text = "RECORDED_WITH_ERRORS" if errors else "RECORDED_UNCLASSIFIED"

    derived.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)
    (derived / "run-status.txt").write_text(status_text + "\n", encoding="ascii")
    if errors:
        (meta / "stop-errors.txt").write_text("\n".join(errors) + "\n", encoding="utf-8")
    if fatal_finalization_error:
        (meta / "finalization-error.txt").write_text(fatal_finalization_error + "\n", encoding="utf-8")

    manifest = meta / "SHA256SUMS.csv"
    try:
        files = sorted(
            (path for path in run_dir.rglob("*") if path.is_file() and path != manifest),
            key=lambda path: str(path).lower(),
        )
        with manifest.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["relative_path", "sha256", "bytes"])
            for path in files:
                writer.writerow([path.relative_to(run_dir).as_posix(), sha256(path), path.stat().st_size])
    except Exception as exc:
        status_text = "INVALID_TOOLING_FINALIZATION"
        (derived / "run-status.txt").write_text(status_text + "\n", encoding="ascii")
        with (meta / "finalization-error.txt").open("a", encoding="utf-8") as handle:
            handle.write(f"manifest generation failed: {type(exc).__name__}: {exc}\n")
        errors.append(f"manifest generation failed: {exc}")

    for path in raw.glob("*"):
        if path.is_file():
            try:
                os.chmod(path, stat.S_IREAD)
            except OSError:
                pass

    print(f"RECORDER_STOPPED={state['run_id']}")
    print(f"END_UTC={end}")
    print(f"RUN_STATUS={status_text}")
    print(f"SUMMARY={derived / 'run-summary.json'}")
    print(f"HASH_MANIFEST={manifest}")
    if errors:
        print(f"STOP_ERRORS={len(errors)}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Automated dissertation research evidence recorder")
    sub = p.add_subparsers(dest="action", required=True)

    q = sub.add_parser("preflight")
    q.add_argument("--require-emu", action="store_true")
    q.add_argument("--require-sec", action="store_true")

    def add_start_args(q):
        q.add_argument("--group", required=True)
        q.add_argument("--run-id", required=True)
        q.add_argument("--condition", default="")
        q.add_argument("--expected", default="")
        q.add_argument("--scope", choices=("lorawan", "full"), default="lorawan")
        q.add_argument("--interval", type=int, default=5)
        q.add_argument("--dev-eui", default="ac1f09fffe296d29")
        q.add_argument("--gateway-eui", default="0016c001f139a1cb")
        q.add_argument("--capture-sec", action="store_true")
        q.add_argument("--skip-serial", action="store_true", help="uncounted recorder smoke tests only")
        q.add_argument("--fabric-settle-seconds", type=int, default=0,
                       help="after closing the counted window, wait up to this many seconds for all in-window uplinks to reach Fabric confirmation")

    q = sub.add_parser("start", help="advanced detached mode; prefer run for counted research")
    add_start_args(q)

    q = sub.add_parser("run", help="preferred supervised foreground capture with automatic finalization")
    add_start_args(q)
    q.add_argument("--health-interval", type=int, default=15, help="collector/evidence health gate interval in seconds")
    q.add_argument("--duration-seconds", type=int, default=0, help="0 runs until Ctrl+C; nonzero is useful for uncounted smoke tests")

    q = sub.add_parser("mark")
    q.add_argument("--message", required=True)

    q = sub.add_parser("trial")
    q.add_argument("--trial-id", required=True)
    q.add_argument("--condition", default="")
    q.add_argument("--expected", default="")
    q.add_argument("--actual", default="")
    q.add_argument("--status", choices=("PASS", "FAIL", "INVALID", "BLOCKED", "UNCLASSIFIED"), default="UNCLASSIFIED")
    q.add_argument("--notes", default="")

    q = sub.add_parser("trial-begin", help="Open one counted attempt after a fail-closed recorder health gate")
    q.add_argument("--trial-id", required=True)
    q.add_argument("--condition", required=True)
    q.add_argument("--expected", required=True)

    q = sub.add_parser("trial-end", help="Close the active attempt and retain structured Chapter-IV result fields")
    q.add_argument("--trial-id", required=True)
    q.add_argument("--actual", required=True)
    q.add_argument("--status", choices=("PASS", "FAIL", "INVALID", "BLOCKED"), required=True)
    evidence_choices = ("yes", "no", "unknown")
    q.add_argument("--gateway-received", choices=evidence_choices, default="unknown")
    q.add_argument("--chirpstack-accepted", choices=evidence_choices, default="unknown")
    q.add_argument("--chirpstack-rejected", choices=evidence_choices, default="unknown")
    q.add_argument("--application-reached", choices=evidence_choices, default="unknown")
    q.add_argument("--database-created", choices=evidence_choices, default="unknown")
    q.add_argument("--outbox-created", choices=evidence_choices, default="unknown")
    q.add_argument("--decision-time", type=float, default=None, help="decision time in seconds when a trustworthy boundary exists")
    q.add_argument("--metric", action="append", default=[], metavar="KEY=VALUE", help="repeatable structured observation for Chapter-IV metrics")
    q.add_argument("--evidence-reference", default="")
    q.add_argument("--notes", default="")

    q = sub.add_parser("serial-pause", help="Keep the recorder alive while temporarily releasing one USB serial port")
    q.add_argument("--device", choices=("emu", "sec"), required=True)

    q = sub.add_parser("serial-resume", help="Resume a previously paused USB serial collector")
    q.add_argument("--device", choices=("emu", "sec"), required=True)

    sub.add_parser("evidence-status", help="read aggregate verifier and latest gateway checkpoint state from the current database leader")
    sub.add_parser("status")
    sub.add_parser("stop")
    sub.add_parser("recover", help="finalize and seal a stale/interrupted active run using the normal stop path")
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.action == "preflight":
            return preflight(args.require_emu, args.require_sec)
        if args.action == "start":
            return cmd_start(args)
        if args.action == "run":
            return cmd_run(args)
        if args.action == "mark":
            return cmd_mark(args)
        if args.action == "trial":
            return cmd_trial(args)
        if args.action == "trial-begin":
            return cmd_trial_begin(args)
        if args.action == "trial-end":
            return cmd_trial_end(args)
        if args.action == "serial-pause":
            return cmd_serial_pause(args)
        if args.action == "serial-resume":
            return cmd_serial_resume(args)
        if args.action == "evidence-status":
            return cmd_evidence_status(args)
        if args.action == "status":
            return cmd_status(args)
        if args.action in ("stop", "recover"):
            return cmd_stop(args)
        raise RuntimeError("unsupported action")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
