#!/usr/bin/env python3
"""Authorized SEC-01/SEC-02 exact-PHYPayload replay fixture helper.

The security node never receives EMU-01 AppKey/session keys.  Capture reads the
ciphertext LoRaWAN PHYPayload already preserved by Gateway-01's evidence journal
and the actual RF parameters observed by RAK5146.  Send transmits those exact
bytes through the commissioned RUI3 P2P fixture, then returns SEC to its parked
AS923 OTAA state.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import serial
from serial.tools import list_ports

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RESULTS_ROOT = (PROJECT_ROOT / "chapter4-results").resolve()
RECORDER_KEY = Path.home() / ".ssh" / "id_ed25519_research_recorder"
SSH_EXE = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
TARGETS = {
    "gateway": "root@192.168.20.11",
    "ulc01": "opsadmin@143.198.205.54",
    "ulc02": "opsadmin@165.22.253.127",
    "ulc03": "opsadmin@159.223.50.57",
}
GATEWAY_EUI = "0016c001f139a1cb"
EMU_DEV_EUI = "ac1f09fffe296d29"
SEC_PATTERN = re.compile(r"(VID:PID=1915:521F|VID_1915&PID_521F|1915.*521F)", re.I)
RADIO_RE = re.compile(
    r"Frame received, uplink_id: (?P<uplink>\d+), count_us: \d+, freq: (?P<freq>\d+), "
    r"bw: (?P<bw>\d+), mod: (?P<mod>[^,]+), dr: (?P<dr>SF\d+)"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ssh_argv(node: str, command: str) -> list[str]:
    return [
        str(SSH_EXE), "-o", "BatchMode=yes", "-o", f"IdentityFile={RECORDER_KEY}",
        "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
        TARGETS[node], command,
    ]


def remote(node: str, command: str, timeout: int = 12) -> str:
    cp = subprocess.run(ssh_argv(node, command), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, check=False)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
        raise RuntimeError(f"{node} {command.split()[0]} failed: {detail.splitlines()[-1][:180] if detail else 'unknown error'}")
    return cp.stdout


def query_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_result_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(RESULTS_ROOT)
    except ValueError as exc:
        raise ValueError(f"fixture/result path must be inside {RESULTS_ROOT}") from exc
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def parse_journal_records(text: str) -> list[dict]:
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
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
        if not payload:
            continue
        records.append({"envelope": obj, "body": body, "payload": payload})
    return records


def valid_data_up(payload: bytes) -> bool:
    # MHDR(1) + FHDR minimum(7) + MIC(4) = 12 bytes.
    return len(payload) >= 12 and (payload[0] >> 5) in (2, 4)


def data_up_record(records: list[dict]) -> dict:
    # LoRaWAN MHDR MType values 2 and 4 are UnconfirmedDataUp/ConfirmedDataUp.
    candidates = [r for r in records if valid_data_up(r["payload"])]
    if not candidates:
        raise RuntimeError("no LoRaWAN data-uplink PHYPayload is present in the retained recent gateway journal")
    return max(candidates, key=lambda r: int(r["body"].get("sequence", 0)))


def packetflow_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=2)
    end = now + timedelta(minutes=5)
    last_error = None
    for node in ("ulc03", "ulc01", "ulc02"):
        try:
            text = remote(node, f"db-export packetflow {query_time(start)} {query_time(end)} {GATEWAY_EUI}")
            return list(csv.DictReader(io.StringIO(text)))
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"packetflow export unavailable: {last_error}")


def parse_radio_rows(text: str) -> dict[str, dict]:
    out = {}
    for line in text.splitlines():
        m = RADIO_RE.search(line)
        if not m:
            continue
        out[m.group("uplink")] = {
            "uplink_id": m.group("uplink"), "frequency_hz": int(m.group("freq")),
            "bandwidth_hz": int(m.group("bw")), "data_rate": m.group("dr"), "raw_log": line,
        }
    return out


def cmd_capture(args) -> int:
    output = ensure_result_path(Path(args.output))
    journal = parse_journal_records(remote("gateway", f"journal-recent {args.scan_records}"))
    data_records = [r for r in journal if valid_data_up(r["payload"])]
    if not data_records:
        raise RuntimeError("no LoRaWAN data-uplink PHYPayload is present in the retained recent gateway journal")

    flow = packetflow_rows()
    emu_rows = []
    for row in flow:
        if (row.get("dev_eui") or "").lower() != EMU_DEV_EUI or not row.get("event_key"):
            continue
        if args.test_sequence is not None:
            try:
                if int(row.get("test_sequence") or "") != args.test_sequence:
                    continue
            except (TypeError, ValueError):
                continue
        try:
            row["_fcnt"] = int(row.get("f_cnt") or "")
        except (TypeError, ValueError):
            continue
        emu_rows.append(row)
    if not emu_rows:
        suffix = f" for test_sequence={args.test_sequence}" if args.test_sequence is not None else ""
        raise RuntimeError(f"no accepted EMU-01 packetflow rows are available for replay selection{suffix}")
    latest_fcnt = max(row["_fcnt"] for row in emu_rows)

    flow_by_sha: dict[str, list[dict]] = {}
    for row in emu_rows:
        digest = (row.get("phy_payload_sha256") or "").lower()
        if digest:
            flow_by_sha.setdefault(digest, []).append(row)

    eligible = []
    for record in data_records:
        digest = hashlib.sha256(record["payload"]).hexdigest()
        for row in flow_by_sha.get(digest, []):
            age = latest_fcnt - row["_fcnt"]
            if age >= args.minimum_fcnt_age:
                eligible.append((row["_fcnt"], int(record["body"].get("sequence", 0)), age, record, row, digest))
    if not eligible:
        raise RuntimeError(
            f"no accepted EMU-01 gateway journal packet is at least {args.minimum_fcnt_age} FCnt values old; "
            f"latest accepted FCnt is {latest_fcnt}"
        )

    _fcnt, _journal_seq, fcnt_age, chosen, cloud, phy_sha = max(eligible, key=lambda item: (item[0], item[1]))
    body = chosen["body"]
    payload: bytes = chosen["payload"]
    uplink_id = str(cloud.get("uplink_id") or "")
    if not uplink_id:
        raise RuntimeError("selected PHYPayload has no gateway uplink ID")
    radio = parse_radio_rows(remote("gateway", f"radio-recent {args.scan_radio}")).get(uplink_id)
    if not radio:
        raise RuntimeError(f"RAK5146 Frame received evidence for gateway uplink ID {uplink_id} is no longer in the live log buffer")
    if int(body.get("frequency_hz") or 0) != radio["frequency_hz"]:
        raise RuntimeError("journal/radio frequency mismatch; refusing to build replay fixture")
    sf = int(radio["data_rate"].removeprefix("SF"))
    bw_hz = radio["bandwidth_hz"]
    if bw_hz not in (125000, 250000, 500000):
        raise RuntimeError(f"captured bandwidth {bw_hz} Hz is not supported by the reviewed SEC replay profile")

    mtype = payload[0] >> 5
    fixture = {
        "fixture_version": "sec02-exact-lorawan-replay-v1",
        "created_at": utc_now(),
        "source": "Gateway-01 immutable journal + gateway MQTT evidence + RAK5146 Frame received log",
        "gateway_eui": GATEWAY_EUI,
        "gateway_journal_sequence": int(body["sequence"]),
        "gateway_record_hash": chosen["envelope"].get("record_hash", ""),
        "captured_at": body.get("captured_at"),
        "gateway_uplink_id": uplink_id,
        "phy_payload_hex": payload.hex().upper(),
        "phy_payload_sha256": phy_sha,
        "lorawan_mtype": mtype,
        "lorawan_mtype_name": "UnconfirmedDataUp" if mtype == 2 else "ConfirmedDataUp",
        "devaddr_hex": payload[1:5][::-1].hex().upper() if len(payload) >= 8 else "",
        "fcnt16": int.from_bytes(payload[6:8], "little") if len(payload) >= 8 else None,
        "accepted_fcnt": int(cloud["_fcnt"]),
        "latest_accepted_fcnt_at_capture": latest_fcnt,
        "fcnt_age_at_capture": fcnt_age,
        "minimum_required_fcnt_age": args.minimum_fcnt_age,
        "frequency_hz": radio["frequency_hz"],
        "spreading_factor": sf,
        "bandwidth_hz": bw_hz,
        "coding_rate": "4/5",
        "rui3_coding_rate_parameter": 0,
        "preamble_symbols": 8,
        "tx_power_dbm": 14,
        "syncword_hex": "3444",
        "iq_inversion": 0,
        "gateway_rssi_dbm": float(cloud["rssi_dbm"]) if cloud.get("rssi_dbm") else None,
        "gateway_snr_db": float(cloud["snr_db"]) if cloud.get("snr_db") else None,
        "security_boundary": "ciphertext PHYPayload only; no EMU-01 AppKey or session key is present",
    }
    output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"REPLAY_FIXTURE={output}")
    print(f"PHYPAYLOAD_SHA256={phy_sha}")
    print(f"GATEWAY_UPLINK_ID={uplink_id}")
    print(f"FCNT={cloud['_fcnt']}|LATEST_FCNT={latest_fcnt}|AGE={fcnt_age}")
    print(f"RF={radio['frequency_hz']}Hz|SF{sf}|BW{bw_hz}")
    return 0


def find_sec_port() -> str:
    for p in list_ports.comports():
        hay = " ".join(str(x or "") for x in (p.device, p.description, p.hwid))
        if SEC_PATTERN.search(hay):
            return p.device
    raise RuntimeError("SEC-01/SEC-02 RUI3 USB identity VID_1915/PID_521F is not present")


def read_until(ser: serial.Serial, required: tuple[str, ...], timeout: float) -> list[str]:
    deadline = time.monotonic() + timeout
    lines: list[str] = []
    while time.monotonic() < deadline:
        raw = ser.readline()
        if raw:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                lines.append(line)
                if any(token in line for token in required):
                    return lines
    raise RuntimeError(f"SEC response timeout waiting for {required}; last={lines[-5:]}")


def at(ser: serial.Serial, command: str, timeout: float = 4.0, async_token: str | None = None) -> list[str]:
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()
    lines = read_until(ser, ("OK", "AT_ERROR", "AT_PARAM_ERROR", "AT_BUSY_ERROR",
                             "AT_COMMAND_NOT_FOUND"), timeout)
    if not any(line == "OK" for line in lines):
        raise RuntimeError(f"SEC command failed: {command}: {lines[-3:]}")
    if async_token:
        lines.extend(read_until(ser, (async_token,), 20.0))
    return lines


def at_fresh(command: str, *, timeout: float = 4.0,
             async_token: str | None = None, retries: int = 4) -> list[str]:
    """One RUI3 command per fresh USB handle; NWM=0/1 can re-enumerate COM."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with serial.Serial(find_sec_port(), 115200, timeout=0.20,
                               write_timeout=2) as ser:
                # Preserve default DTR/RTS: forcing both low makes RUI3 mute.
                time.sleep(0.15)
                ser.reset_input_buffer()
                return at(ser, command, timeout=timeout, async_token=async_token)
        except (serial.SerialException, OSError, RuntimeError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(0.8)
    assert last is not None
    raise last


def query_parked(command: str, prefix: str) -> str:
    for line in at_fresh(command):
        line = line.strip()
        if line == command or line == prefix + "?":
            continue
        if line.startswith(prefix) and line[len(prefix):].strip() not in ("", "?"):
            return line[len(prefix):].strip()
    raise RuntimeError(f"SEC parked query did not return {prefix}")


def park_sec() -> list[str]:
    transcript: list[str] = []
    for command in ("AT+NWM=1", "AT+BAND=8", "AT+NJM=1", "AT+CLASS=A",
                    "AT+DEVEUI=0000000000000000"):
        transcript.append(f"> {command}")
        try:
            transcript.extend(at_fresh(command, timeout=6))
        except Exception as exc:
            transcript.append(f"PARK_ERROR {command}: {type(exc).__name__}: {str(exc)[:100]}")
    for command, prefix, expected in (
        ("AT+NWM=?", "AT+NWM=", "1"),
        ("AT+BAND=?", "AT+BAND=", "8"),
        ("AT+NJM=?", "AT+NJM=", "1"),
        ("AT+CLASS=?", "AT+CLASS=", "A"),
        ("AT+NJS=?", "AT+NJS=", "0"),
        ("AT+DEVEUI=?", "AT+DEVEUI=", "0000000000000000"),
    ):
        try:
            actual = query_parked(command, prefix)
            transcript.append(f"VERIFY {prefix}{actual}")
            if actual.lower() != expected.lower():
                transcript.append(f"PARK_ERROR {prefix} expected {expected}")
        except Exception as exc:
            transcript.append(f"PARK_ERROR {prefix}: {type(exc).__name__}: {str(exc)[:100]}")
    return transcript


def cmd_forge_invalid_mic(args) -> int:
    """Build an address-level spoof fixture without any session key or valid MIC."""
    src = ensure_result_path(Path(args.fixture))
    out = ensure_result_path(Path(args.output))
    if src == out or out.exists():
        raise RuntimeError("spoof fixture output must be new and distinct from the genuine control")
    genuine = json.loads(src.read_text(encoding="utf-8-sig"))
    raw = bytes.fromhex(genuine.get("phy_payload_hex", ""))
    source_digest = hashlib.sha256(raw).hexdigest()
    if genuine.get("fixture_version") != "sec02-exact-lorawan-replay-v1" or not valid_data_up(raw):
        raise RuntimeError("invalid source LoRaWAN control fixture")
    if source_digest != genuine.get("phy_payload_sha256"):
        raise RuntimeError("source fixture SHA-256 mismatch")

    rows = packetflow_rows()
    legit = [row for row in rows if (row.get("dev_eui") or "").lower() == EMU_DEV_EUI
             and row.get("event_key") and row.get("f_cnt")]
    control = [row for row in legit if row.get("uplink_id") == genuine.get("gateway_uplink_id")
               and (row.get("phy_payload_sha256") or "").lower() == source_digest]
    if len(control) != 1 or not legit:
        raise RuntimeError("source ciphertext not uniquely bound to an accepted EMU-01 control")
    latest_fcnt = max(int(row["f_cnt"]) for row in legit)
    new_fcnt = latest_fcnt + 32
    if not (latest_fcnt < new_fcnt <= 65535) or new_fcnt <= int(genuine["accepted_fcnt"]):
        raise RuntimeError("no valid unaccepted 16-bit frame-counter value for spoof fixture")
    forged = bytearray(raw)
    forged[6:8] = new_fcnt.to_bytes(2, "little")
    forged[-1] ^= 0x01
    if forged[1:5] != raw[1:5] or forged[-4:] == raw[-4:]:
        raise RuntimeError("address/MIC spoof invariant failed")
    fixture = dict(genuine)
    fixture.update({
        "fixture_variant": "S1_INVALID_MIC_SPOOF_NON_COUNTED",
        "created_at": utc_now(), "phy_payload_hex": forged.hex().upper(),
        "phy_payload_sha256": hashlib.sha256(forged).hexdigest(),
        "source_control_phy_payload_sha256": source_digest,
        "source_control_event_key": control[0]["event_key"],
        "latest_accepted_fcnt_at_forge": latest_fcnt,
        "spoof_unaccepted_fcnt": new_fcnt,
        "fcnt16": new_fcnt,
        "forgery": "unchanged DevAddr and MType; fresh FCnt16; last MIC byte XOR 01; no MIC recomputation",
        "security_boundary": "ciphertext and intentionally invalid MIC only; no EMU key material",
    })
    out.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SPOOF_FIXTURE={out}")
    print(f"SOURCE_SHA256={source_digest}")
    print(f"FORGED_SHA256={fixture['phy_payload_sha256']}")
    print(f"LATEST_ACCEPTED_FCNT={latest_fcnt} SPOOF_FCNT={new_fcnt}")
    return 0


def cmd_send(args) -> int:
    fixture_path = ensure_result_path(Path(args.fixture))
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("fixture_version") != "sec02-exact-lorawan-replay-v1":
        raise ValueError("unsupported replay fixture version")
    payload_hex = str(fixture.get("phy_payload_hex") or "").strip().upper()
    if not re.fullmatch(r"[0-9A-F]{2,500}", payload_hex) or len(payload_hex) % 2:
        raise ValueError("fixture PHYPayload hex is invalid")
    payload = bytes.fromhex(payload_hex)
    if hashlib.sha256(payload).hexdigest() != fixture.get("phy_payload_sha256"):
        raise ValueError("fixture PHYPayload SHA-256 mismatch")
    if not valid_data_up(payload):
        raise ValueError("fixture is not a complete LoRaWAN data-uplink PHYPayload")
    sf = int(fixture["spreading_factor"])
    bw_hz = int(fixture["bandwidth_hz"])
    bw_param = bw_hz // 1000
    freq = int(fixture["frequency_hz"])
    cr = int(fixture.get("rui3_coding_rate_parameter", 0))
    preamble = int(fixture.get("preamble_symbols", 8))
    power = int(fixture.get("tx_power_dbm", 14))
    if not (150_000_000 <= freq <= 960_000_000 and 6 <= sf <= 12 and bw_param in (125, 250, 500) and cr in range(4) and 2 <= preamble <= 65535 and 5 <= power <= 22):
        raise ValueError("fixture RF values are outside the reviewed RUI3 P2P boundary")
    commands = [
        "AT", "AT+VER=?", "AT+NWM=0",
        f"AT+P2P={freq}:{sf}:{bw_param}:{cr}:{preamble}:{power}",
        f"AT+SYNCWORD={fixture.get('syncword_hex','3444')}",
        f"AT+IQINVER={int(fixture.get('iq_inversion',0))}",
        # RUI_4.2.4_RAK4631 reports AT_COMMAND_NOT_FOUND for AT+PCRYPT.
        # After NWM=0, P2P TX does not require entering receive mode.
        f"AT+PSEND={payload_hex}",
    ]
    if args.dry_run:
        for command in commands[:-1]:
            print(command)
        print(f"AT+PSEND=<PHYPAYLOAD sha256={fixture['phy_payload_sha256']} bytes={len(payload_hex)//2}>")
        return 0

    port = find_sec_port()
    transcript: list[str] = [f"timestamp_utc={utc_now()}", f"port={port}", f"fixture={fixture_path.name}", f"phy_payload_sha256={fixture['phy_payload_sha256']}"]
    success = False
    restored_ok = False
    error: str | None = None
    result_path = ensure_result_path(Path(args.result)) if args.result else fixture_path.with_name(fixture_path.stem + "-send.json")
    try:
        for command in commands:
            transmitting = command.startswith("AT+PSEND=")
            transcript.append(f"> {'AT+PSEND=<exact fixture bytes>' if transmitting else command}")
            # Never automatically retry a possible RF send. One write can be
            # transmitted even if the asynchronous USB acknowledgement is lost.
            reply = at_fresh(command, timeout=6 if command.startswith("AT+NWM=") else 4,
                             async_token="+EVT:TXP2P DONE" if transmitting else None,
                             retries=1 if transmitting else 4)
            transcript.extend(reply)
        success = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:200]}"
        transcript.append(f"SEND_ERROR {error}")
    finally:
        transcript.append("-- restore and independently verify parked security-node state --")
        park_lines = park_sec()
        transcript.extend(park_lines)
        restored_ok = not any(line.startswith("PARK_ERROR ") for line in park_lines)

    result = {
        "fixture": str(fixture_path), "phy_payload_sha256": fixture["phy_payload_sha256"],
        "sent_at": utc_now(), "sec_port": port, "txp2p_done": success,
        "restored_state": "VERIFIED" if restored_ok else "FAILED",
        "expected_parked_state": "NWM=1,BAND=8,NJM=1,CLASS=A,NJS=0,DEVEUI=0000000000000000",
        "error": error, "transcript": transcript,
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    completed = success and restored_ok
    print(f"SEC_REPLAY_SENT={'PASS' if completed else 'FAIL'}")
    print(f"RESULT={result_path}")
    return 0 if completed else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Authorized SEC-01/SEC-02 exact LoRaWAN PHYPayload replay helper")
    sub = ap.add_subparsers(dest="action", required=True)
    q = sub.add_parser("capture", help="build a replay fixture from a real accepted gateway journal packet")
    q.add_argument("--output", required=True, help="fixture JSON path under chapter4-results")
    q.add_argument("--scan-records", type=int, default=200)
    q.add_argument("--scan-radio", type=int, default=300)
    q.add_argument("--minimum-fcnt-age", type=int, default=3, help="require the captured accepted FCnt to trail the latest EMU-01 FCnt by at least this amount")
    q.add_argument("--test-sequence", type=int, default=None, help="select the exact accepted EMU-01 test_sequence used as this trial's legitimate control")
    q = sub.add_parser("forge-invalid-mic", help="derive one uncounted spoof without real session keys")
    q.add_argument("--fixture", required=True, help="captured, accepted genuine control fixture")
    q.add_argument("--output", required=True, help="new spoof fixture under chapter4-results")
    q = sub.add_parser("send", help="transmit one exact captured PHYPayload with SEC-01/SEC-02 RUI3 P2P")
    q.add_argument("--fixture", required=True)
    q.add_argument("--result", default="")
    q.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not SSH_EXE.exists() or not RECORDER_KEY.exists():
        raise RuntimeError("research recorder SSH client/key is unavailable")
    if args.action == "forge-invalid-mic":
        return cmd_forge_invalid_mic(args)
    if args.action == "capture":
        if not 1 <= args.scan_records <= 500 or not 1 <= args.scan_radio <= 500:
            raise ValueError("scan counts must be 1..500")
        if not 1 <= args.minimum_fcnt_age <= 100000:
            raise ValueError("minimum-fcnt-age must be 1..100000")
        if args.test_sequence is not None and args.test_sequence < 0:
            raise ValueError("test-sequence must be >= 0")
        return cmd_capture(args)
    return cmd_send(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
