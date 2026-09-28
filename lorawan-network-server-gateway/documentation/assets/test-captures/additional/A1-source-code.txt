#!/usr/bin/env python3
"""A1 LoRaWAN authentication commissioning/formal harness.

Three conditions:
  * legitimate EMU-01 OTAA join -> ALLOW
  * registered DevEUI with deliberately wrong AppKey on SEC -> REJECT
  * unregistered SEC DevEUI -> REJECT

The legitimate root key never enters this process.  Invalid attempts count only
when Gateway-01's retained raw PHYPayload proves the exact JoinRequest DevEUI.
ChirpStack state is read through the restricted recorder wrapper before/after.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "test" / "automation" / "research_contract.py"
RESULTS = ROOT / "chapter4-results" / "authentication" / "lorawan"
RECORDER_KEY = Path.home() / ".ssh" / "id_ed25519_research_recorder"
SSH = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
SERVER = "opsadmin@143.198.205.54"
GATEWAY = "root@192.168.20.11"

LEGIT_DEV_EUI = "ac1f09fffe296d29"
LEGIT_JOIN_EUI = "0000000000000000"
UNREGISTERED_DEV_EUI = "000000000000a102"
UNREGISTERED_JOIN_EUI = "000000000000a102"

# Dedicated non-production fixtures.  They are not legitimate device secrets.
WRONG_APP_KEY = "00112233445566778899aabbccddeeff"
UNREGISTERED_APP_KEY = "11223344556677889900aabbccddeeff"

EMU_USB_SERIAL = "69D8B0D3239621F1"
EMU_APP_PID = 0x8029
EMU_DFU_PID = 0x002A
SEC_PATTERN = re.compile(r"(VID:PID=1915:521F|VID_1915&PID_521F|1915.*521F)", re.I)

CFG = ROOT / "chapter4-results" / "_configuration" / "emu01-counted-test-15s"
BUILD_RECORD = CFG / "build-record.json"
NRFUTIL = (
    Path.home() / "AppData" / "Local" / "Arduino15" / "packages" / "RAKwireless"
    / "hardware" / "nrf52" / "1.3.3" / "tools" / "adafruit-nrfutil"
    / "win32" / "adafruit-nrfutil.exe"
)


def load_contract():
    spec = importlib.util.spec_from_file_location("research_contract", CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import research contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RC = load_contract()
RC.validate_static_contract()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def remote(host: str, command: str, timeout: float = 25.0) -> str:
    cp = subprocess.run(
        [
            str(SSH), "-i", str(RECORDER_KEY),
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8",
            host, command,
        ],
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
        raise RuntimeError(f"restricted recorder action failed: {host} {command.split()[0]}: {detail[-500:]}")
    return cp.stdout


def emu_port(pid: int) -> str | None:
    for port in list_ports.comports():
        if (port.serial_number or "").upper() == EMU_USB_SERIAL and port.pid == pid:
            return port.device
    return None


def wait_emu(pid: int, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = emu_port(pid)
        if found:
            return found
        time.sleep(0.25)
    raise RuntimeError(f"EMU-01 USB PID {pid:04X} not found")


def sec_port() -> str:
    for port in list_ports.comports():
        hay = " ".join(str(x or "") for x in (port.device, port.description, port.hwid))
        if SEC_PATTERN.search(hay):
            return port.device
    raise RuntimeError("SEC RUI3 USB identity VID_1915/PID_521F is not present")


def sec_command(command: str, timeout: float = 4.0, retries: int = 4) -> list[str]:
    """One AT command per fresh USB handle.

    RUI3 can re-enumerate after configuration commands. Reopening the endpoint
    makes this deterministic and avoids writes to a stale Windows handle.
    """
    last: Exception | None = None
    for _ in range(retries):
        try:
            port = sec_port()
            with serial.Serial(port, 115200, timeout=0.20, write_timeout=2) as ser:
                time.sleep(0.15)
                ser.reset_input_buffer()
                ser.write((command + "\r\n").encode("ascii"))
                ser.flush()
                deadline = time.monotonic() + timeout
                lines: list[str] = []
                while time.monotonic() < deadline:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    lines.append(line)
                    if line in {"OK", "AT_ERROR", "AT_PARAM_ERROR", "AT_BUSY_ERROR"}:
                        break
                if "OK" not in lines:
                    raise RuntimeError(f"no OK for {command.split('=')[0]}: {lines[-5:]}")
                return lines
        except Exception as exc:
            last = exc
            time.sleep(1)
    assert last is not None
    raise last


def query_value(command: str, prefix: str) -> str:
    lines = sec_command(command)
    for line in lines:
        # RUI3 echoes the query (e.g. AT+VER=?) before the actual AT+VER=...
        # value; the echo must never be mistaken for the configured value.
        if line.strip() == command or line.strip() == prefix + "?":
            continue
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            if value and value != "?":
                return value
    raise RuntimeError(f"SEC query {command} did not return a value for {prefix}")


def sec_baseline() -> dict[str, str]:
    baseline = {
        "version": query_value("AT+VER=?", "AT+VER="),
        "nwm": query_value("AT+NWM=?", "AT+NWM="),
        "band": query_value("AT+BAND=?", "AT+BAND="),
        "njm": query_value("AT+NJM=?", "AT+NJM="),
        "class": query_value("AT+CLASS=?", "AT+CLASS="),
        "njs": query_value("AT+NJS=?", "AT+NJS="),
        "deveui": query_value("AT+DEVEUI=?", "AT+DEVEUI=").lower(),
    }
    expected = {
        "version": "RUI_4.2.4_RAK4631",
        "nwm": "1", "band": "8", "njm": "1", "class": "A", "njs": "0",
        "deveui": "0000000000000000",
    }
    if baseline != expected:
        raise RuntimeError(f"SEC parked-state drift: {baseline}")
    return baseline


def park_sec() -> None:
    # No NWM/BAND rewrite here: those settings are already proven and NWM=1
    # deliberately re-enumerates the RUI3 USB endpoint.
    for command in (
        "AT+APPKEY=00000000000000000000000000000000",
        "AT+APPEUI=0000000000000000",
        "AT+DEVEUI=0000000000000000",
    ):
        sec_command(command)
    if query_value("AT+NJS=?", "AT+NJS=") != "0":
        raise RuntimeError("SEC remained joined after parking")
    if query_value("AT+DEVEUI=?", "AT+DEVEUI=").lower() != "0000000000000000":
        raise RuntimeError("SEC DevEUI did not return to parked value")


def set_sec_identity(dev_eui: str, join_eui: str, app_key: str) -> None:
    sec_command(f"AT+DEVEUI={dev_eui}")
    sec_command(f"AT+APPEUI={join_eui}")
    sec_command(f"AT+APPKEY={app_key}")
    if query_value("AT+DEVEUI=?", "AT+DEVEUI=").lower() != dev_eui.lower():
        raise RuntimeError("SEC DevEUI verification failed")


def sec_join_attempt() -> tuple[list[str], bool]:
    port = sec_port()
    transcript: list[str] = []
    with serial.Serial(port, 115200, timeout=0.20, write_timeout=2) as ser:
        time.sleep(0.15)
        ser.reset_input_buffer()
        ser.write(b"AT+JOIN=1:0:10:1\r\n")
        ser.flush()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                transcript.append(line)
            upper = line.upper()
            if "JOIN" in upper and ("FAILED" in upper or "JOINED" in upper):
                # Keep a short tail in case a final status line follows.
                tail = time.monotonic() + 1
                while time.monotonic() < tail:
                    raw2 = ser.readline()
                    if raw2:
                        text = raw2.decode("utf-8", errors="replace").strip()
                        if text:
                            transcript.append(text)
                break
    njs = query_value("AT+NJS=?", "AT+NJS=")
    joined = njs == "1" or any("JOINED" in line.upper() and "FAIL" not in line.upper() for line in transcript)
    return transcript, joined


def gateway_records(count: int = 220) -> list[dict]:
    text = remote(GATEWAY, f"journal-recent {count}", timeout=20)
    records: list[dict] = []
    for line in text.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        body = obj.get("record_body") if isinstance(obj, dict) else None
        if not isinstance(body, dict):
            continue
        try:
            payload = base64.b64decode(body.get("phy_payload_base64", ""), validate=True)
        except Exception:
            continue
        seq = body.get("sequence")
        if not payload or not isinstance(seq, int):
            continue
        records.append({"sequence": seq, "body": body, "payload": payload, "raw": obj})
    return records


def max_gateway_sequence(records: list[dict]) -> int:
    if not records:
        raise RuntimeError("gateway journal pre-attempt watermark missing; cannot prove a fresh JoinRequest")
    return max(int(r["sequence"]) for r in records)


def matching_join_requests(
    records: list[dict], after_sequence: int, dev_eui: str, join_eui: str,
) -> list[dict]:
    matches: list[dict] = []
    wanted = dev_eui.lower()
    wanted_join = join_eui.lower()
    for rec in records:
        if int(rec["sequence"]) <= after_sequence:
            continue
        payload = rec["payload"]
        # JoinRequest = MHDR MType 0; 1 + JoinEUI(8 LE) + DevEUI(8 LE) + DevNonce(2) + MIC(4)
        if len(payload) != 23 or ((payload[0] >> 5) & 0x07) != 0:
            continue
        parsed_join = payload[1:9][::-1].hex()
        parsed_dev = payload[9:17][::-1].hex()
        if parsed_dev == wanted and parsed_join == wanted_join:
            matches.append({
                "sequence": int(rec["sequence"]),
                "join_eui": parsed_join,
                "dev_eui": parsed_dev,
                "phy_sha256": hashlib.sha256(payload).hexdigest(),
            })
    return matches


def chirp_state(dev_eui: str) -> dict[str, str]:
    text = remote(SERVER, f"a1-lorawan-state {dev_eui}")
    out: dict[str, str] = {"raw": text.strip()}
    for line in text.splitlines():
        parts = line.split("|")
        if parts[0] == "REGISTERED" and len(parts) == 2:
            out["registered"] = parts[1]
        elif parts[0] == "STATE" and len(parts) >= 6:
            out.update({
                "dev_eui": parts[1], "last_seen_at": parts[2],
                "dev_addr": parts[3], "session_fingerprint": parts[4],
                "f_cnt_up": parts[5],
            })
    return out


def state_identity(state: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        state.get("registered", ""), state.get("last_seen_at", ""),
        state.get("dev_addr", ""), state.get("session_fingerprint", ""),
        state.get("f_cnt_up", ""),
    )


def identity_guard() -> str:
    text = remote(
        SERVER,
        f"a1-lorawan-guard {LEGIT_DEV_EUI} {UNREGISTERED_DEV_EUI} {WRONG_APP_KEY}",
    )
    if "A1_LORAWAN_GUARD=PASS" not in text:
        raise RuntimeError("A1 LoRaWAN identity guard failed")
    return text


def build_material() -> tuple[dict, Path]:
    record = json.loads(BUILD_RECORD.read_text(encoding="utf-8-sig"))
    package = ROOT / record["upload_package_path"]
    if record.get("profile") != "COUNTED_TEST_15S" or record.get("compile_define") != "EMU01_COUNTED_TEST_PROFILE=1":
        raise RuntimeError("counted firmware build-record profile drift")
    if sha256_file(package) != record.get("upload_package_sha256"):
        raise RuntimeError("counted firmware upload-package SHA-256 mismatch")
    if not NRFUTIL.is_file():
        raise RuntimeError(f"DFU utility missing: {NRFUTIL}")
    return record, package


def enter_emu_dfu() -> str:
    app = wait_emu(EMU_APP_PID, 8)
    with serial.Serial(app, 1200, timeout=0.20):
        pass
    return wait_emu(EMU_DFU_PID, 12)


def flash_emu(package: Path, output_dir: Path, label: str) -> str:
    dfu = emu_port(EMU_DFU_PID)
    if not dfu:
        dfu = enter_emu_dfu()
    cp = subprocess.run(
        [str(NRFUTIL), "dfu", "serial", "--package", str(package), "--port", dfu, "--baudrate", "115200"],
        text=True, capture_output=True, timeout=90, check=False,
    )
    (output_dir / f"{label}.dfu.stdout.txt").write_text(cp.stdout, encoding="utf-8")
    (output_dir / f"{label}.dfu.stderr.txt").write_text(cp.stderr, encoding="utf-8")
    if cp.returncode != 0 or "Device programmed" not in cp.stdout + cp.stderr:
        raise RuntimeError(f"EMU-01 same-image DFU failed rc={cp.returncode}")
    return wait_emu(EMU_APP_PID, 15)


def observe_emu_join(app_port: str, output_dir: Path, label: str, timeout: float = 45) -> tuple[list[str], bool, bool]:
    lines: list[str] = []
    joined = False
    uplink = False
    with serial.Serial(app_port, 115200, timeout=0.20) as ser:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not (joined and uplink):
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            lines.append(line)
            joined |= line.startswith("EMU01_OTAA_JOIN=PASS")
            uplink |= line.startswith("SENSOR_TX,") and "join=1" in line and "send_status=0" in line
    (output_dir / f"{label}.serial.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines, joined, uplink


def invalid_trial(
    condition: str, trial: int, dev_eui: str, join_eui: str, app_key: str,
    output_dir: Path,
) -> dict[str, object]:
    label = f"{condition}-{trial:02d}"
    pre_state = chirp_state(LEGIT_DEV_EUI if condition == "LORAWAN_WRONG_APPKEY" else dev_eui)
    before = gateway_records()
    watermark = max_gateway_sequence(before)
    set_sec_identity(dev_eui, join_eui, app_key)
    started = utc_now()
    observation_started = time.perf_counter()
    transcript, joined = sec_join_attempt()
    join_observation_ms = round((time.perf_counter() - observation_started) * 1000, 3)
    ended = utc_now()
    after = gateway_records()
    joins = matching_join_requests(after, watermark, dev_eui, join_eui)
    post_state = chirp_state(LEGIT_DEV_EUI if condition == "LORAWAN_WRONG_APPKEY" else dev_eui)
    if condition == "LORAWAN_WRONG_APPKEY":
        state_verified = all(
            state.get("registered") == "1"
            and state.get("dev_eui", "").lower() == LEGIT_DEV_EUI
            and all(field in state for field in (
                "last_seen_at", "dev_addr", "session_fingerprint", "f_cnt_up"
            ))
            for state in (pre_state, post_state)
        )
        state_unchanged = state_verified and state_identity(pre_state) == state_identity(post_state)
    else:
        state_verified = all(
            state.get("registered") in {"0", "1"}
            for state in (pre_state, post_state)
        )
        state_unchanged = (
            state_verified
            and pre_state.get("registered") == "0"
            and post_state.get("registered") == "0"
        )
    gateway_received = bool(joins)
    if joined:
        actual = "ALLOW"
    elif not gateway_received:
        actual = "INVALID"
    elif not state_verified:
        actual = "INVALID_STATE_UNVERIFIED"
    elif not state_unchanged:
        actual = "FAIL_STATE_CHANGED"
    else:
        actual = "REJECT"
    row: dict[str, object] = {
        "condition": condition, "trial": trial, "expected_decision": "REJECT",
        "actual_decision": actual, "correct_decision": actual == "REJECT",
        "false_acceptance": actual == "ALLOW", "gateway_join_request_observed": gateway_received,
        "join_request_count": len(joins), "chirpstack_state_verified": state_verified,
        "chirpstack_state_unchanged": state_unchanged,
        "started_at_utc": started, "ended_at_utc": ended,
        "join_observation_ms": join_observation_ms,
        "join_requests": joins, "pre_state": pre_state, "post_state": post_state,
    }
    safe_transcript = [line for line in transcript if "APPKEY" not in line.upper()]
    (output_dir / f"{label}.serial.txt").write_text("\n".join(safe_transcript) + "\n", encoding="utf-8")
    (output_dir / f"{label}.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    park_sec()
    return row


def valid_trial(trial: int, package: Path, output_dir: Path) -> dict[str, object]:
    label = f"LORAWAN_VALID_OTAA-{trial:02d}"
    pre_state = chirp_state(LEGIT_DEV_EUI)
    before = gateway_records()
    watermark = max_gateway_sequence(before)
    app = flash_emu(package, output_dir, label)
    started = utc_now()
    observation_started = time.perf_counter()
    _, joined, uplink = observe_emu_join(app, output_dir, label)
    join_observation_ms = round((time.perf_counter() - observation_started) * 1000, 3)
    ended = utc_now()
    after = gateway_records()
    joins = matching_join_requests(after, watermark, LEGIT_DEV_EUI, LEGIT_JOIN_EUI)
    post_state = chirp_state(LEGIT_DEV_EUI)
    state_verified = all(
        state.get("registered") == "1"
        and state.get("dev_eui", "").lower() == LEGIT_DEV_EUI
        and "session_fingerprint" in state
        for state in (pre_state, post_state)
    )
    session_changed = (
        state_verified
        and bool(post_state.get("session_fingerprint"))
        and pre_state["session_fingerprint"] != post_state["session_fingerprint"]
    )
    gateway_received = bool(joins)
    allow = joined and uplink and gateway_received and state_verified and session_changed
    row: dict[str, object] = {
        "condition": "LORAWAN_VALID_OTAA", "trial": trial, "expected_decision": "ALLOW",
        "actual_decision": "ALLOW" if allow else "REJECT",
        "correct_decision": allow, "false_rejection": not allow,
        "gateway_join_request_observed": gateway_received, "join_request_count": len(joins),
        "otaa_join_pass": joined, "accepted_uplink_observed_at_source": uplink,
        "chirpstack_state_verified": state_verified,
        "chirpstack_session_changed": session_changed,
        "started_at_utc": started, "ended_at_utc": ended,
        "join_observation_ms": join_observation_ms,
        "join_requests": joins, "pre_state": pre_state, "post_state": post_state,
    }
    (output_dir / f"{label}.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return row


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = [
        "condition", "trial", "expected_decision", "actual_decision", "correct_decision",
        "false_acceptance", "false_rejection", "gateway_join_request_observed",
        "join_request_count", "chirpstack_state_verified", "chirpstack_state_unchanged",
        "chirpstack_session_changed",
        "otaa_join_pass", "accepted_uplink_observed_at_source", "started_at_utc", "ended_at_utc",
        "join_observation_ms",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rehearsal", action="store_true", help="one non-counted attempt per condition")
    args = ap.parse_args()

    if not RECORDER_KEY.is_file():
        raise RuntimeError("research-recorder SSH key missing")
    formal_attempts = int(RC.FORMAL["A1"]["attempts_per_condition"])
    if formal_attempts != 10 or RC.FORMAL["A1"]["total_attempts"] != 90:
        raise RuntimeError("A1 authoritative contract drift")
    attempts = 1 if args.rehearsal else formal_attempts
    inter_trial = 3 if args.rehearsal else 30

    if remote(SERVER, "version").strip() != "research-recorder-server-v10":
        raise RuntimeError("ULC-01 research recorder wrapper version drift")
    if remote(GATEWAY, "version").strip() != "research-recorder-gateway-v3":
        raise RuntimeError("Gateway research recorder wrapper version drift")

    build_record, package = build_material()
    sec_pre = sec_baseline()
    guard = identity_guard()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = RESULTS / f"A1-LORAWAN-{'rehearsal' if args.rehearsal else 'formal'}-{stamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "identity-guard.txt").write_text(guard, encoding="utf-8")
    (output_dir / "sec-precondition.json").write_text(json.dumps(sec_pre, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary: dict[str, object] = {
        "test": "A1", "layer": "LoRaWAN", "formal": not args.rehearsal,
        "attempts_per_condition": attempts, "counted_research": not args.rehearsal,
        "started_at_utc": utc_now(), "status": "FAIL", "trials": [],
        "emu_isolation": "DFU_BOOTLOADER_RADIO_INACTIVE",
        "build_record": str(BUILD_RECORD.relative_to(ROOT)),
        "upload_package_sha256": build_record["upload_package_sha256"],
    }
    rows: list[dict[str, object]] = []
    emu_in_dfu = False
    try:
        # Invalid conditions first. The legitimate application is held in the
        # bootloader so its registered identity cannot transmit concurrently.
        dfu_port = enter_emu_dfu()
        emu_in_dfu = True
        summary["emu_dfu_port"] = dfu_port

        for condition, dev, join, key in (
            ("LORAWAN_WRONG_APPKEY", LEGIT_DEV_EUI, LEGIT_JOIN_EUI, WRONG_APP_KEY),
            ("LORAWAN_UNREGISTERED_DEVEUI", UNREGISTERED_DEV_EUI, UNREGISTERED_JOIN_EUI, UNREGISTERED_APP_KEY),
        ):
            for trial in range(1, attempts + 1):
                row = invalid_trial(condition, trial, dev, join, key, output_dir)
                rows.append(row)
                if not row["correct_decision"]:
                    raise RuntimeError(f"{condition} trial {trial} did not produce a proven rejection: {row['actual_decision']}")
                if trial < attempts:
                    time.sleep(inter_trial)

        park_sec()

        # The first same-image flash both restores EMU-01 and starts legitimate
        # trial 1. Every subsequent flash gives another clean OTAA boot.
        for trial in range(1, attempts + 1):
            row = valid_trial(trial, package, output_dir)
            emu_in_dfu = False
            rows.append(row)
            if not row["correct_decision"]:
                raise RuntimeError(f"legitimate trial {trial} was not fully proven")
            if trial < attempts:
                time.sleep(inter_trial)
                # valid_trial will enter DFU again on its next same-image flash.

        summary["trials"] = rows
        expected_rows = 3 * attempts
        if len(rows) != expected_rows:
            raise RuntimeError(f"trial count {len(rows)} != {expected_rows}")
        summary["status"] = "PASS"
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
        summary["trials"] = rows
        summary["status"] = "FAIL"
    finally:
        try:
            park_sec()
            summary["sec_cleanup"] = "PASS"
        except Exception as exc:
            summary["sec_cleanup"] = f"FAIL:{type(exc).__name__}:{exc}"
            summary["status"] = "FAIL"
        # Never leave the legitimate node stranded in DFU. If the normal trial
        # path did not restore it, restore the same hash-verified image now.
        try:
            if emu_port(EMU_DFU_PID):
                app = flash_emu(package, output_dir, "cleanup-restore")
                _, joined, uplink = observe_emu_join(app, output_dir, "cleanup-restore", timeout=45)
                summary["emu_cleanup"] = "PASS" if joined and uplink else "FAIL:post-restore proof incomplete"
                if not (joined and uplink):
                    summary["status"] = "FAIL"
            else:
                summary["emu_cleanup"] = "PASS"
        except Exception as exc:
            summary["emu_cleanup"] = f"FAIL:{type(exc).__name__}:{exc}"
            summary["status"] = "FAIL"
        summary["finished_at_utc"] = utc_now()
        write_csv(output_dir / "a1-lorawan-trials.csv", rows)
        (output_dir / "a1-lorawan-summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    print(f"A1_LORAWAN_HARNESS={summary['status']} formal={not args.rehearsal} trials={len(rows)}")
    print(f"SESSION_DIR={output_dir}")
    if summary["status"] != "PASS":
        print(f"ERROR={summary.get('error', 'validation failed')}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, subprocess.TimeoutExpired, serial.SerialException) as exc:
        print(f"ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(1)
