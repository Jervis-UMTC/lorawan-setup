#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from testing_monitor import TestingMonitor
from packet_monitor import PacketMonitor

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RESULTS_ROOT = PROJECT_ROOT / "chapter4-results"
ACTIVE_STATE = RESULTS_ROOT / "_recorder-active.json"
TX_RE = re.compile(r"SENSOR_TX,seq=(\d+).*?send_status=(-?\d+)")
RECORDER_KEY = Path.home() / ".ssh" / "id_ed25519_research_recorder"
SSH_EXE = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
TARGETS = {
    "gateway": "root@192.168.20.11",
    "ulc01": "opsadmin@143.198.205.54",
    "ulc02": "opsadmin@165.22.253.127",
    "ulc03": "opsadmin@159.223.50.57",
}
DISPLAY_NAMES = {
    "gateway": "Gateway",
    "ulc01": "Server 1",
    "ulc02": "Server 2",
    "ulc03": "Server 3",
}
NETWORK_CAPACITY = {
    # SIM7600G-H is LTE Cat 4: the modem's theoretical radio ceiling is
    # 150 Mbps down / 50 Mbps up. Actual DITO throughput varies with signal,
    # congestion and carrier policy, so these values are never presented as
    # guaranteed available bandwidth.
    "gateway": {
        "receive_capacity_mbps": 150.0,
        "send_capacity_mbps": 50.0,
        "capacity_label": "LTE modem theoretical maximum",
    },
    # DigitalOcean provides the cloud network; a fixed guaranteed Internet
    # Mbps ceiling is not exposed by this recorder. Do not invent one from a
    # virtual NIC link rate.
    "ulc01": {"receive_capacity_mbps": None, "send_capacity_mbps": None, "capacity_label": "Cloud network · fixed Mbps ceiling not exposed"},
    "ulc02": {"receive_capacity_mbps": None, "send_capacity_mbps": None, "capacity_label": "Cloud network · fixed Mbps ceiling not exposed"},
    "ulc03": {"receive_capacity_mbps": None, "send_capacity_mbps": None, "capacity_label": "Cloud network · fixed Mbps ceiling not exposed"},
}

LIVE_LOCK = threading.Lock()
LIVE_STOP = threading.Event()
LIVE_PROCESSES: dict[str, subprocess.Popen[str]] = {}
HISTORY_POINTS = 300  # five minutes at the one-second live sampling rate
LIVE_HISTORY = {name: deque(maxlen=HISTORY_POINTS) for name in TARGETS}
LIVE_SYSTEMS = {
    name: {
        "name": DISPLAY_NAMES[name],
        "status": "connecting",
        "cpu_percent": None,
        "memory_used_bytes": None,
        "memory_total_bytes": None,
        "ram_percent": None,
        "receive_mbps": None,
        "send_mbps": None,
        "receive_capacity_mbps": NETWORK_CAPACITY[name]["receive_capacity_mbps"],
        "send_capacity_mbps": NETWORK_CAPACITY[name]["send_capacity_mbps"],
        "capacity_label": NETWORK_CAPACITY[name]["capacity_label"],
        "updated_at": None,
        "error": "",
    }
    for name in TARGETS
}

GATEWAY_EUI = "0016c001f139a1cb"

TELEMETRY_DEVICES = {
    "ac1f09fffe296d29": {"name": "EMU-01", "role": "Agriculture sensor"},
    "ac1f09fffe296aeb": {"name": "SEC-02", "role": "Security / verification node"},
}
TELEMETRY_POLL_SECONDS = 5
TELEMETRY_UPLINK_LIMIT_PER_DEVICE = 24
# Live presence only needs a short recent window. Keeping this small avoids
# expensive repeated exports during counted research runs while still retaining
# enough EMU-01 arrivals for useful live history at its 15-second cadence.
TELEMETRY_WINDOW_MINUTES = 3
TELEMETRY_QUERY_TIMEOUT_SECONDS = 5
TELEMETRY_MEASUREMENT_TIMEOUT_SECONDS = 3
TELEMETRY_CACHE_MAX_AGE_SECONDS = 30
TELEMETRY_CACHE = Path(os.environ.get("TEMP", str(SCRIPT_DIR))) / "lorawan-research-cockpit-telemetry.json"
TELEMETRY_WORKER_PROCESS: subprocess.Popen | None = None
TELEMETRY_LOCK = threading.Lock()
TESTING_MONITOR = TestingMonitor(SSH_EXE, RECORDER_KEY, RESULTS_ROOT)
PACKET_MONITOR = PacketMonitor(SSH_EXE, RECORDER_KEY, TARGETS, GATEWAY_EUI, tuple(TELEMETRY_DEVICES))

TELEMETRY_STATE = {
    "status": "connecting",
    "updated_at": None,
    "source_server": None,
    "window_minutes": TELEMETRY_WINDOW_MINUTES,
    "packet_count": 0,
    "sender_count": 0,
    "latest_packet_at": None,
    "devices": [
        {
            "device_eui": eui,
            "sender_name": meta["name"],
            "sender_role": meta["role"],
            "packet_count": 0,
            "latest_packet_at": None,
        }
        for eui, meta in TELEMETRY_DEVICES.items()
    ],
    "uplinks": [],
    "error": "",
}


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def read_csv(path: Path):
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def num(value):
    try:
        return float(value)
    except Exception:
        return None


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def find_latest_run() -> Path | None:
    if ACTIVE_STATE.exists():
        state = read_json(ACTIVE_STATE, {})
        p = Path(state.get("run_dir", ""))
        if p.exists():
            return p
    candidates = []
    if RESULTS_ROOT.exists():
        for p in RESULTS_ROOT.glob("*/*"):
            if not p.is_dir() or p.parent.name.startswith("_") or p.parent.name == "summaries":
                continue
            marker = p / "metadata" / "run-meta.json"
            if marker.exists():
                candidates.append((marker.stat().st_mtime, p))
    return max(candidates, default=(0, None), key=lambda x: x[0])[1]


def source_state(path: Path):
    if not path.exists():
        return {"attempts": 0, "send_ok": 0, "send_fail": 0, "last_seq": None, "last_timestamp": None}
    rows = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = TX_RE.search(line)
            if not m:
                continue
            ts = line.split("|", 1)[0]
            rows.append({"timestamp": ts, "seq": int(m.group(1)), "send_status": int(m.group(2))})
    except Exception:
        pass
    return {
        "attempts": len(rows),
        "send_ok": sum(1 for r in rows if r["send_status"] == 0),
        "send_fail": sum(1 for r in rows if r["send_status"] != 0),
        "last_seq": rows[-1]["seq"] if rows else None,
        "last_timestamp": rows[-1]["timestamp"] if rows else None,
    }


def summary_metrics(run_dir: Path):
    s = read_json(run_dir / "derived" / "run-summary.json", {})
    telemetry = s.get("telemetry") or {}
    correlation = s.get("correlation") or {}
    fabric = s.get("fabric_outbox") or {}
    latency = telemetry.get("application_event_to_db_ms") or {}
    return {
        "sealed": (run_dir / "metadata" / "SHA256SUMS.csv").exists(),
        "formal_pdr": telemetry.get("formal_chapter3_pdr_percent"),
        "formal_pdr_status": telemetry.get("formal_chapter3_pdr_status"),
        "database_delivery": telemetry.get("database_delivery_percent_exact_payload_clock_aligned"),
        "latency_mean_ms": latency.get("mean"),
        "rssi_mean_dbm": (telemetry.get("rssi_dbm") or {}).get("mean"),
        "snr_mean_db": (telemetry.get("snr_db") or {}).get("mean"),
        "exact_matches": correlation.get("eligible_exact_payload_matches"),
        "eligible_source_attempts": correlation.get("eligible_source_attempts_in_db_export_window"),
        "fabric_status": fabric.get("status_counts", {}),
        "fabric_committed_with_txid": fabric.get("committed_with_tx_id"),
    }


def ssh_argv(node: str, remote_command: str | None = None) -> list[str]:
    if remote_command is None:
        remote_command = "resource 1" if node == "gateway" else "monitor-stream 1"
    return [
        str(SSH_EXE),
        "-o", "BatchMode=yes",
        "-o", f"IdentityFile={RECORDER_KEY}",
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=5",
        TARGETS[node],
        remote_command,
    ]


def _query_remote_csv(node: str, command: str, timeout_seconds: int | None = None) -> list[dict]:
    try:
        completed = subprocess.run(
            ssh_argv(node, command),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds or TELEMETRY_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("telemetry query timed out") from exc
    except OSError as exc:
        raise RuntimeError("telemetry SSH query could not start") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or f"exit {completed.returncode}").strip()
        raise RuntimeError(detail.splitlines()[-1][:180] if detail else "remote query failed")
    return list(csv.DictReader(io.StringIO(completed.stdout)))


def _parse_db_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _query_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _telemetry_poll_once() -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=TELEMETRY_WINDOW_MINUTES)
    last_error = ""

    # ULC-03 is the preferred read path for the live cockpit because its
    # recorder export is proven responsive. The other HA members remain safe
    # failover readers if that path is unavailable.
    for node in ("ulc03", "ulc01", "ulc02"):
        try:
            all_uplinks: list[dict] = []
            device_states: list[dict] = []
            total_packets = 0
            successful_device_queries = 0

            for device_eui, meta in TELEMETRY_DEVICES.items():
                query_status = "available"
                try:
                    uplink_rows = _query_remote_csv(
                        node,
                        f"db-export uplinks {_query_time(start)} {_query_time(now)} {device_eui}",
                    )
                    successful_device_queries += 1
                except Exception:
                    # One silent or temporarily slow sensor must never erase a
                    # different sensor's confirmed live arrivals.
                    uplink_rows = []
                    query_status = "unavailable"
                total_packets += len(uplink_rows)
                selected = uplink_rows[-TELEMETRY_UPLINK_LIMIT_PER_DEVICE:]
                by_event: dict[str, list[dict]] = {}
                measurement_status = "not needed"

                # Packet arrival must remain visible even if the decoded-value
                # export is temporarily slow. Measurement enrichment therefore
                # fails independently from the uplink feed.
                if selected:
                    oldest = _parse_db_time(selected[0].get("time")) or start
                    measurement_start = oldest - timedelta(seconds=2)
                    try:
                        measurement_rows = _query_remote_csv(
                            node,
                            f"db-export measurements {_query_time(measurement_start)} {_query_time(now)} {device_eui}",
                            TELEMETRY_MEASUREMENT_TIMEOUT_SECONDS,
                        )
                        measurement_status = "available"
                        for row in measurement_rows:
                            by_event.setdefault(row.get("event_key", ""), []).append(
                                {
                                    "metric_name": row.get("metric_name"),
                                    "metric_value": num(row.get("metric_value")),
                                    "metric_text": row.get("metric_text") or None,
                                    "metric_bool": (
                                        None
                                        if row.get("metric_bool") in (None, "")
                                        else str(row.get("metric_bool")).strip().lower() in ("t", "true", "1", "yes")
                                    ),
                                    "unit": row.get("unit") or "",
                                    "quality": row.get("quality") or "",
                                }
                            )
                    except Exception:
                        measurement_status = "delayed"

                device_uplinks = []
                for row in selected:
                    topic = row.get("mqtt_topic") or ""
                    topic_match = re.match(r"^application/([^/]+)/device/", topic)
                    device_uplinks.append(
                        {
                            "event_key": row.get("event_key"),
                            "time": row.get("time"),
                            "received_at": row.get("received_at"),
                            "device_eui": (row.get("dev_eui") or device_eui).lower(),
                            "sender_name": meta["name"],
                            "sender_role": meta["role"],
                            "application_id": topic_match.group(1) if topic_match else None,
                            "f_cnt": num(row.get("f_cnt")),
                            "test_sequence": num(row.get("test_sequence")),
                            "rssi_dbm": num(row.get("rssi_dbm")),
                            "snr_db": num(row.get("snr_db")),
                            "gateway_frequency_hz": num(row.get("gateway_frequency_hz")),
                            "region": row.get("region") or "",
                            "gateway_id": row.get("gateway_id") or "",
                            "f_port": num(row.get("f_port")),
                            "confirmed": str(row.get("confirmed") or "").strip().lower() in ("t", "true", "1", "yes"),
                            "decoder_version": row.get("decoder_version") or "",
                            "measurements": by_event.get(row.get("event_key", ""), []),
                        }
                    )
                all_uplinks.extend(device_uplinks)
                latest_for_device = None
                if device_uplinks:
                    latest_row = device_uplinks[-1]
                    latest_for_device = latest_row.get("received_at") or latest_row.get("time")
                device_states.append(
                    {
                        "device_eui": device_eui,
                        "sender_name": meta["name"],
                        "sender_role": meta["role"],
                        "packet_count": len(uplink_rows),
                        "shown_packets": len(device_uplinks),
                        "latest_packet_at": latest_for_device,
                        "measurement_status": measurement_status,
                        "query_status": query_status,
                    }
                )

            if successful_device_queries == 0:
                raise RuntimeError("all live sensor read queries failed")

            all_uplinks.sort(
                key=lambda row: _parse_db_time(row.get("received_at") or row.get("time"))
                or datetime.min.replace(tzinfo=timezone.utc)
            )
            latest_packet_at = None
            if all_uplinks:
                latest_packet_at = all_uplinks[-1].get("received_at") or all_uplinks[-1].get("time")
            sender_count = sum(1 for item in device_states if item["packet_count"] > 0)
            return {
                "status": "online" if all_uplinks else "stale",
                "updated_at": iso_now(),
                "source_server": node,
                "window_minutes": TELEMETRY_WINDOW_MINUTES,
                "packet_count": total_packets,
                "sender_count": sender_count,
                "latest_packet_at": latest_packet_at,
                "devices": device_states,
                "uplinks": all_uplinks,
                "error": "" if all_uplinks else f"No sensor packets received in the last {TELEMETRY_WINDOW_MINUTES} minutes",
            }
        except Exception as exc:
            # Keep raw command details out of the browser. The failing HA member
            # is still remembered internally while the next read path is tried.
            last_error = f"{node}: {type(exc).__name__}: {str(exc)[:120]}"

    return {
        "status": "error",
        "updated_at": iso_now(),
        "source_server": None,
        "window_minutes": TELEMETRY_WINDOW_MINUTES,
        "packet_count": 0,
        "sender_count": 0,
        "latest_packet_at": None,
        "devices": [
            {
                "device_eui": eui,
                "sender_name": meta["name"],
                "sender_role": meta["role"],
                "packet_count": 0,
                "shown_packets": 0,
                "latest_packet_at": None,
                "measurement_status": "unavailable",
                "query_status": "unavailable",
            }
            for eui, meta in TELEMETRY_DEVICES.items()
        ],
        "uplinks": [],
        "error": "Live sensor database query is temporarily unavailable; retrying automatically.",
        "internal_error": last_error,
    }


def _write_telemetry_cache(state: dict):
    tmp = TELEMETRY_CACHE.with_suffix(TELEMETRY_CACHE.suffix + ".tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, TELEMETRY_CACHE)


def _presence_device(node: str, device_eui: str, meta: dict, now: datetime) -> tuple[dict, list[dict]]:
    start = now - timedelta(minutes=TELEMETRY_WINDOW_MINUTES)
    rows = _query_remote_csv(
        node,
        f"db-export uplinks {_query_time(start)} {_query_time(now)} {device_eui}",
        TELEMETRY_QUERY_TIMEOUT_SECONDS,
    )
    selected = rows[-TELEMETRY_UPLINK_LIMIT_PER_DEVICE:]
    uplinks: list[dict] = []
    for row in selected:
        topic = row.get("mqtt_topic") or ""
        topic_match = re.match(r"^application/([^/]+)/device/", topic)
        uplinks.append(
            {
                "event_key": row.get("event_key"),
                "time": row.get("time"),
                "received_at": row.get("received_at"),
                "device_eui": (row.get("dev_eui") or device_eui).lower(),
                "sender_name": meta["name"],
                "sender_role": meta["role"],
                "application_id": topic_match.group(1) if topic_match else None,
                "f_cnt": num(row.get("f_cnt")),
                "test_sequence": num(row.get("test_sequence")),
                "rssi_dbm": num(row.get("rssi_dbm")),
                "snr_db": num(row.get("snr_db")),
                "gateway_frequency_hz": num(row.get("gateway_frequency_hz")),
                "region": row.get("region") or "",
                "gateway_id": row.get("gateway_id") or "",
                "f_port": num(row.get("f_port")),
                "confirmed": str(row.get("confirmed") or "").strip().lower() in ("t", "true", "1", "yes"),
                "decoder_version": row.get("decoder_version") or "",
                "measurements": [],
            }
        )
    latest = None
    if uplinks:
        latest = uplinks[-1].get("received_at") or uplinks[-1].get("time")
    return (
        {
            "device_eui": device_eui,
            "sender_name": meta["name"],
            "sender_role": meta["role"],
            "packet_count": len(rows),
            "shown_packets": len(uplinks),
            "latest_packet_at": latest,
            "measurement_status": "delayed" if uplinks else "not needed",
            "query_status": "available",
        },
        uplinks,
    )


def _measurement_payload(row: dict) -> dict:
    return {
        "metric_name": row.get("metric_name"),
        "metric_value": num(row.get("metric_value")),
        "metric_text": row.get("metric_text") or None,
        "metric_bool": (
            None
            if row.get("metric_bool") in (None, "")
            else str(row.get("metric_bool")).strip().lower() in ("t", "true", "1", "yes")
        ),
        "unit": row.get("unit") or "",
        "quality": row.get("quality") or "",
    }


def _enrich_device_measurements(node: str, device_eui: str, uplinks: list[dict], now: datetime) -> list[dict]:
    if not uplinks:
        return uplinks
    oldest = _parse_db_time(uplinks[0].get("time")) or now
    start = oldest - timedelta(seconds=2)
    rows = _query_remote_csv(
        node,
        f"db-export measurements {_query_time(start)} {_query_time(now)} {device_eui}",
        TELEMETRY_MEASUREMENT_TIMEOUT_SECONDS,
    )
    by_event: dict[str, list[dict]] = {}
    for row in rows:
        by_event.setdefault(row.get("event_key", ""), []).append(_measurement_payload(row))
    enriched = []
    for uplink in uplinks:
        item = dict(uplink)
        item["measurements"] = by_event.get(item.get("event_key", ""), [])
        enriched.append(item)
    return enriched


def _latest_known_device(node: str, device_eui: str, meta: dict, now: datetime) -> dict | None:
    latest_row = None
    for lookback_hours in (24, 24 * 7):
        start = now - timedelta(hours=lookback_hours)
        rows = _query_remote_csv(
            node,
            f"db-export uplinks {_query_time(start)} {_query_time(now)} {device_eui}",
            TELEMETRY_QUERY_TIMEOUT_SECONDS,
        )
        if rows:
            latest_row = rows[-1]
            break
    if latest_row is None:
        return None

    event_time = _parse_db_time(latest_row.get("time") or latest_row.get("received_at")) or now
    start = event_time - timedelta(seconds=2)
    end = min(now, event_time + timedelta(seconds=3))
    measurements = []
    try:
        measurement_rows = _query_remote_csv(
            node,
            f"db-export measurements {_query_time(start)} {_query_time(end)} {device_eui}",
            TELEMETRY_MEASUREMENT_TIMEOUT_SECONDS,
        )
        event_key = latest_row.get("event_key", "")
        measurements = [
            _measurement_payload(row)
            for row in measurement_rows
            if row.get("event_key", "") == event_key
        ]
    except Exception:
        pass

    return {
        "event_key": latest_row.get("event_key"),
        "time": latest_row.get("time"),
        "received_at": latest_row.get("received_at"),
        "device_eui": (latest_row.get("dev_eui") or device_eui).lower(),
        "sender_name": meta["name"],
        "sender_role": meta["role"],
        "f_cnt": num(latest_row.get("f_cnt")),
        "test_sequence": num(latest_row.get("test_sequence")),
        "rssi_dbm": num(latest_row.get("rssi_dbm")),
        "snr_db": num(latest_row.get("snr_db")),
        "gateway_frequency_hz": num(latest_row.get("gateway_frequency_hz")),
        "measurements": measurements,
    }


def _presence_state(
    device_cache: dict[str, tuple[dict, list[dict]]],
    error: str = "",
    latest_known: dict | None = None,
) -> dict:
    devices: list[dict] = []
    uplinks: list[dict] = []
    for eui, meta in TELEMETRY_DEVICES.items():
        cached = device_cache.get(eui)
        if cached:
            devices.append(cached[0])
            uplinks.extend(cached[1])
        else:
            devices.append(
                {
                    "device_eui": eui,
                    "sender_name": meta["name"],
                    "sender_role": meta["role"],
                    "packet_count": 0,
                    "shown_packets": 0,
                    "latest_packet_at": None,
                    "measurement_status": "unavailable",
                    "query_status": "unavailable",
                }
            )
    uplinks.sort(
        key=lambda row: _parse_db_time(row.get("received_at") or row.get("time"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )
    latest = uplinks[-1].get("received_at") or uplinks[-1].get("time") if uplinks else None
    packet_count = sum(int(d.get("packet_count") or 0) for d in devices)
    sender_count = sum(1 for d in devices if int(d.get("packet_count") or 0) > 0)
    return {
        "status": "online" if uplinks else ("stale" if error and device_cache else "error" if error else "idle"),
        "updated_at": iso_now(),
        "source_server": "ulc03" if device_cache else None,
        "window_minutes": TELEMETRY_WINDOW_MINUTES,
        "packet_count": packet_count,
        "sender_count": sender_count,
        "latest_packet_at": latest,
        "devices": devices,
        "uplinks": uplinks,
        "latest_known": latest_known,
        "error": "" if uplinks else (error or f"No sensor packets received in the last {TELEMETRY_WINDOW_MINUTES} minutes"),
    }


def telemetry_worker_main():
    # Presence is the priority for the live screen. Query EMU-01 first and write
    # the cache immediately, then check the quieter SEC-02 less frequently.
    # This prevents a silent/slow second device from making an actively sending
    # first device appear as "Not seen".
    device_cache: dict[str, tuple[dict, list[dict]]] = {}
    sec_last_query = 0.0
    latest_known = None
    latest_known_query = 0.0
    while True:
        now = datetime.now(timezone.utc)
        error = ""
        emu_eui = "ac1f09fffe296d29"
        try:
            device_cache[emu_eui] = _presence_device("ulc03", emu_eui, TELEMETRY_DEVICES[emu_eui], now)
            _write_telemetry_cache(_presence_state(device_cache, latest_known=latest_known))
            emu_state, emu_uplinks = device_cache[emu_eui]
            if emu_uplinks:
                try:
                    enriched = _enrich_device_measurements("ulc03", emu_eui, emu_uplinks, now)
                    enriched_state = dict(emu_state)
                    enriched_state["measurement_status"] = "available"
                    device_cache[emu_eui] = (enriched_state, enriched)
                    latest_known = enriched[-1]
                    _write_telemetry_cache(_presence_state(device_cache, latest_known=latest_known))
                except Exception:
                    pass
            elif time.monotonic() - latest_known_query >= 300 or latest_known is None:
                latest_known_query = time.monotonic()
                try:
                    latest_known = _latest_known_device("ulc03", emu_eui, TELEMETRY_DEVICES[emu_eui], now)
                except Exception:
                    pass
                _write_telemetry_cache(_presence_state(device_cache, latest_known=latest_known))
        except Exception as exc:
            detail = " ".join(str(exc).split())[:160]
            error = f"EMU-01 live read retrying: {type(exc).__name__}"
            if detail:
                error += f": {detail}"
            if device_cache:
                _write_telemetry_cache(_presence_state(device_cache, error, latest_known))

        sec_eui = "ac1f09fffe296aeb"
        if time.monotonic() - sec_last_query >= 30:
            sec_last_query = time.monotonic()
            try:
                device_cache[sec_eui] = _presence_device("ulc03", sec_eui, TELEMETRY_DEVICES[sec_eui], now)
            except Exception:
                pass
            _write_telemetry_cache(_presence_state(device_cache, error, latest_known))

        time.sleep(TELEMETRY_POLL_SECONDS)


def start_telemetry_collector():
    global TELEMETRY_WORKER_PROCESS
    try:
        TELEMETRY_CACHE.unlink(missing_ok=True)
    except Exception:
        pass
    TELEMETRY_WORKER_PROCESS = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--telemetry-worker"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_telemetry_collector():
    global TELEMETRY_WORKER_PROCESS
    process = TELEMETRY_WORKER_PROCESS
    TELEMETRY_WORKER_PROCESS = None
    if process is not None and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def telemetry_snapshot():
    try:
        cached = json.loads(TELEMETRY_CACHE.read_text(encoding="utf-8"))
        updated = _parse_db_time(cached.get("updated_at"))
        if updated is not None and (datetime.now(timezone.utc) - updated).total_seconds() <= TELEMETRY_CACHE_MAX_AGE_SECONDS:
            return cached
    except Exception:
        pass
    with TELEMETRY_LOCK:
        return json.loads(json.dumps(TELEMETRY_STATE))


def _set_live(node: str, **values):
    with LIVE_LOCK:
        LIVE_SYSTEMS[node].update(values)


def _stream_live_node(node: str):
    while not LIVE_STOP.is_set():
        process = None
        try:
            # Preserve the last verified state while reconnecting. Resetting an
            # already-unavailable node to "connecting" on every retry makes an
            # unreachable management path look like transient startup forever.
            process = subprocess.Popen(
                ssh_argv(node),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            with LIVE_LOCK:
                LIVE_PROCESSES[node] = process
            assert process.stdout is not None
            header = process.stdout.readline().strip()
            multiplexed = node != "gateway"
            if multiplexed:
                if header != "#LORAWAN_MONITOR_STREAM_V1":
                    raise RuntimeError("monitor stream did not start")
                TESTING_MONITOR.set_node_status(node, "online")
            elif not header.startswith("timestamp_utc,cpu_percent"):
                raise RuntimeError("live metric stream did not start")

            previous_rx = None
            previous_tx = None
            previous_monotonic = None
            for line in process.stdout:
                if LIVE_STOP.is_set():
                    break
                raw = line.strip()
                if not raw:
                    continue
                if multiplexed and not raw.startswith("RESOURCE|"):
                    TESTING_MONITOR.ingest_stream_line(node, raw)
                    continue
                fields = raw.split("|") if multiplexed else raw.split(",")
                if len(fields) < 9 if multiplexed else len(fields) < 8:
                    continue
                server_timestamp = fields[1] if multiplexed else fields[0]
                TESTING_MONITOR.ingest_clock_sample(node, server_timestamp)
                now_mono = time.monotonic()
                offset = 1 if multiplexed else 0
                cpu = num(fields[1 + offset])
                memory_used = num(fields[2 + offset])
                memory_total = num(fields[3 + offset])
                ram = num(fields[4 + offset])
                rx = num(fields[6 + offset])
                tx = num(fields[7 + offset])
                receive_mbps = None
                send_mbps = None
                if (
                    previous_rx is not None
                    and previous_tx is not None
                    and previous_monotonic is not None
                    and rx is not None
                    and tx is not None
                ):
                    elapsed = max(now_mono - previous_monotonic, 0.001)
                    receive_mbps = max(0.0, (rx - previous_rx) * 8.0 / elapsed / 1_000_000.0)
                    send_mbps = max(0.0, (tx - previous_tx) * 8.0 / elapsed / 1_000_000.0)
                previous_rx, previous_tx, previous_monotonic = rx, tx, now_mono
                updated_at = iso_now()
                with LIVE_LOCK:
                    LIVE_SYSTEMS[node].update(
                        status="online",
                        cpu_percent=cpu,
                        memory_used_bytes=memory_used,
                        memory_total_bytes=memory_total,
                        ram_percent=ram,
                        receive_mbps=receive_mbps,
                        send_mbps=send_mbps,
                        updated_at=updated_at,
                        error="",
                    )
                    LIVE_HISTORY[node].append(
                        {
                            "timestamp_utc": updated_at,
                            "cpu_percent": cpu,
                            "ram_percent": ram,
                            "memory_used_bytes": memory_used,
                            "memory_total_bytes": memory_total,
                            "receive_mbps": receive_mbps,
                            "send_mbps": send_mbps,
                        }
                    )
            if LIVE_STOP.is_set():
                break
            detail = ""
            if process.stderr is not None:
                detail = process.stderr.read().strip().splitlines()[-1:] or []
                detail = detail[0] if detail else ""
            _set_live(node, status="unavailable", error=detail[:120])
            TESTING_MONITOR.set_node_status(node, "unavailable", detail[:120])
        except Exception as exc:
            _set_live(node, status="unavailable", error=str(exc)[:120])
            TESTING_MONITOR.set_node_status(node, "unavailable", str(exc)[:120])
        finally:
            with LIVE_LOCK:
                LIVE_PROCESSES.pop(node, None)
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
        LIVE_STOP.wait(2.0)


def start_live_collectors():
    if not SSH_EXE.exists() or not RECORDER_KEY.exists():
        detail = "SSH client or research-recorder key is unavailable"
        for node in TARGETS:
            _set_live(node, status="unavailable", error=detail)
        return
    for node in TARGETS:
        threading.Thread(target=_stream_live_node, args=(node,), daemon=True, name=f"live-{node}").start()


def stop_live_collectors():
    LIVE_STOP.set()
    with LIVE_LOCK:
        processes = list(LIVE_PROCESSES.values())
    for process in processes:
        try:
            process.terminate()
        except Exception:
            pass


def live_systems_snapshot():
    now = datetime.now(timezone.utc)
    result = {}
    with LIVE_LOCK:
        for node, raw in LIVE_SYSTEMS.items():
            item = dict(raw)
            age = None
            if item.get("updated_at"):
                try:
                    dt = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
                    age = max(0.0, (now - dt).total_seconds())
                except Exception:
                    age = None
            if age is not None and age > 4.0:
                item["status"] = "stale"
            item["age_seconds"] = age
            item["history"] = list(LIVE_HISTORY[node])
            result[node] = item
    return result


def build_state():
    run_dir = find_latest_run()
    active = ACTIVE_STATE.exists()
    state = {
        "generated_at": iso_now(),
        "active": active,
        "systems": live_systems_snapshot(),
        "telemetry": telemetry_snapshot(),
        "packets": PACKET_MONITOR.snapshot(),
        "monitor": TESTING_MONITOR.snapshot(),
        "run": None,
        "links": {
            "grafana": "http://127.0.0.1:3000/d/lorawan-research-cockpit/lorawan-research-test-cockpit?orgId=1&refresh=15s&from=now-6h&to=now",
            "chirpstack": "https://smartagri-chirpstack.duckdns.org",
        },
    }
    if not run_dir:
        return state
    meta = read_json(run_dir / "metadata" / "run-meta.json", {})
    state["run"] = {
        "id": meta.get("run_id", run_dir.name),
        "group": meta.get("group", run_dir.parent.name),
        "condition": meta.get("condition", ""),
        "source": source_state(run_dir / "raw" / "emu-01-source.log"),
        "metrics": summary_metrics(run_dir),
    }
    return state


INDEX = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LoRaWAN Live Monitor</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;background:#09111d;color:#edf4fb;--panel:#0f1c2c;--line:#22364b;--muted:#86a0b8;--soft:#718aa2;--good:#6ee7a8;--warn:#ffd37b;--bad:#ff9c9c}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1440px;margin:auto;padding:20px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.title{font-size:25px;font-weight:800;letter-spacing:-.02em}.subtitle{margin-top:4px;color:var(--muted);font-size:13px}.live{display:inline-flex;align-items:center;gap:7px;margin-left:8px;padding:4px 8px;border-radius:999px;border:1px solid #245b45;background:#102a21;color:#8af0bc;font-size:11px;font-weight:800}.dot{width:7px;height:7px;border-radius:50%;background:#58e39f}.links{display:flex;gap:7px}.btn{background:#132a43;color:#8dd0ff;text-decoration:none;padding:7px 10px;border-radius:7px;font-size:12px}.section{margin-top:13px;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}.sectionTitle{padding:10px 13px;border-bottom:1px solid #203247;color:#9ab0c5;font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:700}.tableWrap{overflow-x:auto}.systems{display:grid;grid-template-columns:1.05fr .9fr 1.2fr 1.15fr 1.15fr;min-width:920px}.cell{padding:11px 12px;border-bottom:1px solid #1d2e40;min-width:0}.head{font-size:10px;color:var(--soft);text-transform:uppercase;letter-spacing:.05em}.name{font-weight:800}.value{font-size:17px;font-weight:800;letter-spacing:-.015em}.status{font-size:11px;font-weight:800}.online{color:var(--good)}.offline,.error{color:var(--bad)}.stale,.unavailable,.idle,.connecting{color:var(--warn)}.sub{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.35}.historyGrid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#203247}.historyPanel{background:var(--panel);padding:12px;min-width:0}.historyHead{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:7px}.historyName{font-size:13px;font-weight:800}.historyMeta{font-size:10px;color:var(--soft)}.chartSvg{display:block;width:100%;height:154px}.legend{display:flex;gap:12px;flex-wrap:wrap;margin-top:5px;color:#91a9bf;font-size:10px}.legend i{width:9px;height:2px;display:inline-block;vertical-align:middle;margin-right:4px}.networkGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#203247;border-top:1px solid #203247}.networkPanel{background:var(--panel);padding:11px;min-width:0}.sensorSummary{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid #203247}.deviceStrip{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1px;background:#203247;border-bottom:1px solid #203247}.deviceCard{background:var(--panel);padding:11px 12px;min-width:0}.deviceName{font-size:14px;font-weight:800}.deviceEui{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px;color:#a8bfd3;margin-top:3px}.senderBlock{border-top:1px solid #203247}.senderHead{padding:9px 12px;display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}.senderTitle{font-size:12px;font-weight:800}.senderMeta{font-size:10px;color:var(--soft)}.summaryItem{padding:11px 12px;border-right:1px solid #203247;min-width:0}.summaryLabel{font-size:10px;color:var(--soft);text-transform:uppercase;letter-spacing:.05em}.summaryValue{font-size:15px;font-weight:800;margin-top:4px;overflow-wrap:anywhere}.metricGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:1px;background:#203247}.sensorMetric{background:var(--panel);padding:12px;min-height:176px;min-width:0}.metricName{font-size:11px;color:#9bb0c4}.metricValue{font-size:22px;font-weight:800;margin-top:4px;letter-spacing:-.02em}.metricQuality{font-size:10px;color:var(--muted);margin-top:2px}.miniChart{margin-top:7px}.packetTable{width:100%;border-collapse:collapse;min-width:1100px;font-size:11px}.packetTable th,.packetTable td{text-align:left;padding:9px 10px;border-bottom:1px solid #1d2e40;vertical-align:top}.packetTable th{color:var(--soft);font-size:10px;text-transform:uppercase;letter-spacing:.04em}.readingCell{min-width:410px;line-height:1.45;color:#b8c9d8}.cards{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:#203247}.card{background:var(--panel);padding:11px;min-height:86px}.label{font-size:10px;color:#7e9ab5;text-transform:uppercase;letter-spacing:.05em}.metric{font-size:21px;font-weight:800;margin-top:4px}.runbar{padding:9px 12px;border-bottom:1px solid #203247;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.runname{font-weight:800}.muted{color:var(--muted);font-size:11px}.waiting{padding:16px;color:#8da5bb}.footer{margin-top:11px;color:#71869b;font-size:10px;line-height:1.5}details{border-top:1px solid #203247}summary{cursor:pointer;padding:10px 12px;color:#8fa8bf;font-size:11px;font-weight:700;user-select:none}summary:hover{color:#c0d2e1}.advancedWrap{margin-top:13px}.advancedWrap>summary{background:var(--panel);border:1px solid var(--line);border-radius:10px;text-transform:uppercase;letter-spacing:.06em}@media(max-width:1050px){.networkGrid{grid-template-columns:1fr 1fr}.sensorSummary{grid-template-columns:repeat(3,1fr)}.cards{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.wrap{padding:11px}.historyGrid,.networkGrid{grid-template-columns:1fr}.sensorSummary{grid-template-columns:1fr 1fr}.cards{grid-template-columns:1fr 1fr}.title{font-size:21px}.links{display:none}.chartSvg{height:140px}}@media(max-width:430px){.sensorSummary{grid-template-columns:1fr}.metricGrid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="top"><div><div class="title">LoRaWAN Live Monitor <span class="live"><span class="dot"></span><span id="liveText">LIVE</span></span></div><div class="subtitle" id="stamp">Connecting to gateway, servers and telemetry…</div></div><div class="links"><a class="btn" id="grafana" target="_blank">Grafana</a><a class="btn" id="chirp" target="_blank">ChirpStack</a></div></div>
<div id="app"></div><div class="footer"><strong>Evidence rule:</strong> formal test conclusions come only from the sealed evidence for that trial. Chapter PDFs and old dissertation prose are requirements/provenance references, not runtime or result truth. Live monitor values describe only what was actually observed at that time. System usage refreshes every second. RAM is shown as actual used memory / total memory. CPU is current host utilization / 100%. Gateway network capacity uses the SIM7600G-H modem theoretical 150 Mbps receive / 50 Mbps send ceiling, not guaranteed carrier throughput; cloud traffic has no invented fixed Internet ceiling. Sensor history is read-only from TimescaleDB. Sealed research results remain unchanged.</div></div><script>
const REFRESH_MS=1000;let lastRefresh=0;const KEYS=['gateway','ulc01','ulc02','ulc03'];const COLORS=['#75b7ff','#7ce0b7','#d8a8ff','#ffd27c'];
const n=(v,d=1)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function bytes(v){if(v==null)return '—';let x=Number(v);if(x>=1073741824)return `${(x/1073741824).toFixed(2)} GiB`;return `${(x/1048576).toFixed(0)} MiB`}
function cpu(x){if(x.cpu_percent==null)return `<div class="value">${x.status==='unavailable'?'Not observed':'warming up'}</div>`;let used=Number(x.cpu_percent),free=Math.max(0,100-used);return `<div class="value">${n(used,1)}% / 100%</div><div class="sub">${n(free,1)}% available</div>`}
function ram(x){if(x.memory_used_bytes==null||x.memory_total_bytes==null)return `<div class="value">${x.status==='unavailable'?'Not observed':(x.ram_percent==null?'warming up':n(x.ram_percent,1)+'% used')}</div>`;let avail=Math.max(0,Number(x.memory_total_bytes)-Number(x.memory_used_bytes));return `<div class="value">${bytes(x.memory_used_bytes)} / ${bytes(x.memory_total_bytes)}</div><div class="sub">${n(x.ram_percent,1)}% used · ${bytes(avail)} available</div>`}
function traffic(v,cap,label){if(v==null)return `<div class="value">${label&&String(label).includes('LTE')?'Not observed':'warming up'}</div>`;let main=cap==null?`${n(v,2)} Mbps`:`${n(v,2)} / ${n(cap,0)} Mbps`;let sub=cap==null?label:`${n((Number(v)/Number(cap))*100,3)}% of modem theoretical maximum`;return `<div class="value">${main}</div><div class="sub">${esc(sub)}</div>`}
function statusText(s){if(s==='online')return 'Online';if(s==='connecting')return 'Connecting';if(s==='idle')return 'No fresh packets';if(s==='stale')return 'Last observation stale';if(s==='unavailable')return 'Management observation unavailable';if(s==='error')return 'Read error';if(s==='offline')return 'Offline';return 'Observation unavailable'}
function lineChart(series,opt={}){const W=640,H=170,p={l:42,r:12,t:11,b:25};let vals=[];for(const s of series)for(const q of s.values||[])if(Number.isFinite(Number(q.v)))vals.push(Number(q.v));if(!vals.length)return '<div class="waiting">History is filling…</div>';let lo=opt.min!=null?Number(opt.min):Math.min(...vals),hi=opt.max!=null?Number(opt.max):Math.max(...vals);if(!(hi>lo)){let pad=Math.max(Math.abs(hi)*.08,1);lo-=pad;hi+=pad}if(opt.pad&&opt.min==null&&opt.max==null){let pad=(hi-lo)*.12;lo-=pad;hi+=pad}const x=(i,len)=>p.l+(W-p.l-p.r)*(len<=1?1:i/(len-1));const y=v=>p.t+(H-p.t-p.b)*(1-(v-lo)/(hi-lo));let grid='';for(const f of [0,.5,1]){let v=lo+(hi-lo)*(1-f),yy=p.t+(H-p.t-p.b)*f;grid+=`<line x1="${p.l}" y1="${yy}" x2="${W-p.r}" y2="${yy}" stroke="#23384b" stroke-width="1"/><text x="${p.l-6}" y="${yy+3}" fill="#718aa2" font-size="10" text-anchor="end">${esc(opt.formatY?opt.formatY(v):n(v,opt.decimals??1)+(opt.suffix||''))}</text>`}let paths='';series.forEach((s,si)=>{let pts=(s.values||[]).filter(q=>Number.isFinite(Number(q.v)));if(!pts.length)return;let d=pts.map((q,i)=>`${i?'L':'M'}${x(i,pts.length).toFixed(1)},${y(Number(q.v)).toFixed(1)}`).join(' ');paths+=`<path d="${d}" fill="none" stroke="${s.color||COLORS[si%COLORS.length]}" stroke-width="2" vector-effect="non-scaling-stroke"/>`});let legend=series.map((s,i)=>`<span><i style="background:${s.color||COLORS[i%COLORS.length]}"></i>${esc(s.name)}</span>`).join('');return `<svg class="chartSvg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opt.aria||'history chart')}">${grid}${paths}<text x="${p.l}" y="${H-6}" fill="#718aa2" font-size="10">${esc(opt.leftLabel||'5 min ago')}</text><text x="${W-p.r}" y="${H-6}" fill="#718aa2" font-size="10" text-anchor="end">now</text></svg><div class="legend">${legend}</div>`}
function historySeries(systems,field){return KEYS.map((k,i)=>({name:systems?.[k]?.name||k,color:COLORS[i],values:(systems?.[k]?.history||[]).map(q=>({v:q[field]}))}))}
function resourceHistory(systems){let cpuChart=lineChart(historySeries(systems,'cpu_percent'),{min:0,max:100,suffix:'%',decimals:0,aria:'CPU utilization history'});let ramChart=lineChart(historySeries(systems,'ram_percent'),{min:0,max:100,suffix:'%',decimals:0,aria:'RAM utilization history'});let net=KEYS.map((k)=>{let x=systems?.[k]||{},h=x.history||[];return `<div class="networkPanel"><div class="historyHead"><div class="historyName">${esc(x.name||k)}</div><div class="historyMeta">Mbps · auto-scaled</div></div>${lineChart([{name:'Receive',color:'#75b7ff',values:h.map(q=>({v:q.receive_mbps}))},{name:'Send',color:'#7ce0b7',values:h.map(q=>({v:q.send_mbps}))}],{min:0,pad:true,decimals:2,aria:`${x.name||k} network history`})}</div>`}).join('');return `<div class="section"><div class="sectionTitle">Resource history · last 5 minutes</div><div class="historyGrid"><div class="historyPanel"><div class="historyHead"><div class="historyName">CPU utilization</div><div class="historyMeta">0–100%</div></div>${cpuChart}</div><div class="historyPanel"><div class="historyHead"><div class="historyName">RAM utilization</div><div class="historyMeta">0–100%</div></div>${ramChart}</div></div><div class="networkGrid">${net}</div></div>`}
const METRIC_ORDER=['environment_temperature_c','environment_humidity_percent','environment_pressure_pa','environment_gas_resistance_ohm','barometer_temperature_c','barometer_pressure_pa','soil_moisture_percent','soil_temperature_c','light_opt3001_lux','light_veml7700_lux','uv_index','rain_wet','battery_v'];
const METRIC_NAMES={environment_temperature_c:'Air temperature',environment_humidity_percent:'Air humidity',environment_pressure_pa:'Air pressure',environment_gas_resistance_ohm:'Gas resistance',barometer_temperature_c:'Barometer temperature',barometer_pressure_pa:'Barometer pressure',soil_moisture_percent:'Soil moisture',soil_temperature_c:'Soil temperature',light_opt3001_lux:'Light · OPT3001',light_veml7700_lux:'Light · VEML7700',uv_index:'UV index',rain_wet:'Rain / wet',battery_v:'Battery voltage'};
function metricDisplay(m){if(!m)return {text:'—',numeric:null,unit:''};if((m.quality||'').toLowerCase()==='invalid')return {text:'Invalid / no reading',numeric:null,unit:''};if(m.metric_name==='rain_wet'&&m.metric_bool!=null)return {text:m.metric_bool?'Wet':'Dry',numeric:m.metric_bool?1:0,unit:''};let v=m.metric_value;if(v==null)return {text:m.metric_text||'—',numeric:null,unit:m.unit||''};v=Number(v);if(m.unit==='Pa')return {text:`${n(v/1000,2)} kPa`,numeric:v/1000,unit:'kPa'};if(m.unit==='Cel')return {text:`${n(v,1)} °C`,numeric:v,unit:'°C'};if((m.unit||'').toLowerCase()==='ohm')return {text:`${n(v/1000,2)} kΩ`,numeric:v/1000,unit:'kΩ'};if(m.unit==='lx')return {text:`${n(v,1)} lux`,numeric:v,unit:'lux'};if(m.unit==='%')return {text:`${n(v,1)}%`,numeric:v,unit:'%'};if(m.unit==='V')return {text:`${n(v,2)} V`,numeric:v,unit:'V'};if(m.metric_name==='uv_index'||m.unit==='1')return {text:`${n(v,1)} index`,numeric:v,unit:'index'};return {text:`${n(v,2)}${m.unit?' '+m.unit:''}`,numeric:v,unit:m.unit||''}}
function humanTime(v){if(!v)return '—';let d=new Date(v);return Number.isNaN(d.getTime())?String(v):d.toLocaleString()}
function ageText(v){if(!v)return '—';let sec=Math.max(0,(Date.now()-new Date(v).getTime())/1000);if(sec<60)return `${Math.round(sec)} sec ago`;if(sec<3600)return `${Math.round(sec/60)} min ago`;if(sec<86400)return `${(sec/3600).toFixed(1)} h ago`;return `${(sec/86400).toFixed(1)} d ago`}
function senderName(eui){let k=(eui||'').toLowerCase();if(k==='ac1f09fffe296d29')return 'EMU-01 · Agriculture';if(k==='ac1f09fffe296aeb')return 'SEC-02 · Security';return eui||'Unknown sender'}
function fabricLabel(raw){let s=String(raw||'').toLowerCase();if(s==='confirmed'||s==='committed')return 'Committed';if(['pending','claimed','retry','retrying'].includes(s))return 'Waiting';if(!s)return '—';return 'Needs attention'}
function packetSection(p){
  p=p||{};let c=p.counts||{},rows=p.packets||[],history=p.packet_history||[];
  let card=(label,value,sub,cls='')=>`<div class="card"><div class="label">${esc(label)}</div><div class="metric ${cls}">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`;
  let latency=v=>v==null?'—':`${n(v,1)} ms`;
  let anomalyCount=(c.fcnt_repeats||0)+(c.fcnt_gap_missing||0)+(c.fcnt_regressions||0)+(c.sequence_repeats||0)+(c.sequence_gap_missing||0)+(c.sequence_regressions||0);
  let cards='';
  cards+=card('Gateway packets',c.gateway_uplink_events??0,'uplinks seen by Gateway-01');
  cards+=card('Application accepted',c.application_accepted??0,'packets accepted into the application');
  cards+=card('Counter anomalies',anomalyCount,anomalyCount?'review FCnt / sequence behavior':'no FCnt or sequence anomaly observed',anomalyCount?'stale':'online');
  cards+=card('App → DB delay',latency(c.mqtt_to_db_avg_ms),`average · max ${latency(c.mqtt_to_db_max_ms)}`);
  cards+=card('Fabric delivery',`${c.fabric_committed??0} committed`,`${c.fabric_pending??0} waiting`);
  cards+=p.per_packet_verification_available?card('Evidence verified',c.verification_verified??0,'accepted packets with verified evidence'):card('Evidence','Aggregate health','see integrity summary below');
  let body='';
  if(!rows.length){body=`<div class="waiting">${p.status==='unavailable'?'Packet observation is unavailable; retrying automatically.':'No LoRaWAN packets in the current live window.'}</div>`}
  else body=`<div class="tableWrap"><table class="packetTable"><thead><tr><th>Arrived</th><th>Sender</th><th>FCnt / sequence</th><th>Radio</th><th>Application / DB</th><th>Fabric</th></tr></thead><tbody>${rows.slice().reverse().map(x=>{
    let freq=x.frequency_hz==null?'—':`${n(Number(x.frequency_hz)/1000000,3)} MHz`;
    let radio=`RSSI ${n(x.rssi_dbm,1)} dBm · SNR ${n(x.snr_db,1)} dB<div class="sub">${freq} · ${esc(x.data_rate||'DR —')}</div>`;
    let fcnt=x.f_cnt??'—',seq=x.test_sequence??'—';
    let anomaly=[x.fcnt_anomaly,x.sequence_anomaly].filter(v=>v&&v!=='normal'&&v!=='first').join(' · ');
    let accepted=x.application_state==='accepted_application';
    let app=`<span class="status ${accepted?'online':'stale'}">${accepted?'Accepted':'Not yet accepted'}</span><div class="sub">DB ${latency(x.mqtt_to_db_ms)}</div>`;
    let fab=fabricLabel(x.outbox_status),fabCls=fab==='Committed'?'online':fab==='Waiting'?'stale':fab==='—'?'':'error';
    return `<tr><td>${esc(humanTime(x.broker_received_at))}<div class="sub">${esc(ageText(x.broker_received_at))}</div></td><td><strong>${esc(senderName(x.dev_eui))}</strong></td><td>${esc(fcnt)} / ${esc(seq)}${anomaly?`<div class="sub status stale">${esc(anomaly)}</div>`:''}</td><td>${radio}</td><td>${app}</td><td><span class="status ${fabCls}">${esc(fab)}</span><div class="sub">commit ${latency(x.mqtt_to_fabric_commit_ms)}</div></td></tr>`;
  }).join('')}</tbody></table></div>`;
  let historyRows=history.slice(0,60).map(x=>{let anomaly=[x.fcnt_anomaly,x.sequence_anomaly].filter(v=>v&&v!=='normal'&&v!=='first').join(' · ')||'none';return `<tr><td>${esc(humanTime(x.broker_received_at))}</td><td>${esc(senderName(x.dev_eui))}</td><td>${x.f_cnt??'—'} / ${x.test_sequence??'—'}</td><td>${esc(anomaly)}</td><td>${latency(x.mqtt_to_db_ms)}</td><td>${esc(fabricLabel(x.outbox_status))}</td></tr>`}).join('');
  let advanced=`<details><summary>Recent diagnostic history</summary><div class="tableWrap"><table class="packetTable"><thead><tr><th>Observed</th><th>Sender</th><th>FCnt / sequence</th><th>Anomaly</th><th>DB delay</th><th>Fabric</th></tr></thead><tbody>${historyRows||'<tr><td colspan="6">History is filling.</td></tr>'}</tbody></table></div></details>`;
  return `<div class="section"><div class="sectionTitle">Recent LoRaWAN packet flow</div><div class="cards">${cards}</div>${body}${advanced}</div>`;
}
function sensorHistory(t){
  let ups=t?.uplinks||[],devices=t?.devices||[],latest=ups.length?ups[ups.length-1]:null,windowMin=t?.window_minutes||10;
  if(!ups.length){
    let feedError=t?.status==='error',feedStale=t?.status==='stale',msg=feedError?'Live sensor database observation is unavailable after retries. Retrying automatically.':feedStale?'Last valid sensor observation is being retained while the live database read retries.':`No sensor packets received in the last ${windowMin} minutes. Database read is healthy; waiting for the next uplink…`;
    let known=devices.map(d=>{let unavailable=feedError||d.query_status==='unavailable',label=unavailable?'Telemetry observation unavailable':'No fresh packets',cls=unavailable?'error':'stale';return `<div class="deviceCard"><div class="deviceName">${esc(d.sender_name||'Unknown sensor')} <span class="status ${cls}">${label}</span></div><div class="sub">${esc(d.sender_role||'LoRaWAN device')}${unavailable?' · live read retrying':''}</div></div>`}).join('');
    let lk=t?.latest_known||null,latestBlock='';
    if(lk){let ms=lk.measurements||[],observed=lk.received_at||lk.time,cards=METRIC_ORDER.map(name=>{let m=ms.find(x=>x.metric_name===name),md=metricDisplay(m);return `<div class="sensorMetric"><div class="metricName">${esc(METRIC_NAMES[name]||name)}</div><div class="metricValue">${esc(md.text)}</div><div class="metricQuality">${esc(m?.quality||'last known value')}</div></div>`}).join('');let radio=lk.rssi_dbm==null&&lk.snr_db==null?'':` · RSSI ${n(lk.rssi_dbm,1)} dBm · SNR ${n(lk.snr_db,1)} dB`;latestBlock=`<div class="senderBlock"><div class="senderHead"><div><div class="senderTitle">Last known EMU-01 agriculture readings <span class="status stale">not live</span></div><div class="sub">Observed ${esc(humanTime(observed))} · ${esc(ageText(observed))}${esc(radio)}</div></div></div><div class="metricGrid">${cards}</div></div>`}
    return `<div class="section"><div class="sectionTitle">Sensor measurements · live + last known</div>${known?`<div class="deviceStrip">${known}</div>`:''}<div class="waiting">${msg}</div>${latestBlock}</div>`;
  }
  let latestReceived=latest.received_at||latest.time;
  let summary=`<div class="sensorSummary"><div class="summaryItem"><div class="summaryLabel">Newest arrival</div><div class="summaryValue online">${esc(ageText(latestReceived))}</div><div class="sub">${esc(humanTime(latestReceived))}</div></div><div class="summaryItem"><div class="summaryLabel">Senders seen</div><div class="summaryValue">${t.sender_count??new Set(ups.map(p=>p.device_eui)).size} / ${devices.length||'—'}</div><div class="sub">known research nodes in live window</div></div><div class="summaryItem"><div class="summaryLabel">Packets received</div><div class="summaryValue">${t.packet_count??ups.length}</div><div class="sub">last ${windowMin} min · showing ${ups.length}</div></div><div class="summaryItem"><div class="summaryLabel">Database feed</div><div class="summaryValue ${t.status==='online'?'online':'error'}">${t.status==='online'?'Live arrivals':'Last good data'}</div><div class="sub">refresh 5 s · ${esc(t.source_server||'read retry')}</div></div></div>`;
  let deviceCards=devices.map(d=>{let seen=(d.packet_count||0)>0,readOk=d.query_status!=='unavailable',state=seen?'Receiving':(readOk?'No fresh packets':'Telemetry observation unavailable'),cls=seen?'online':(readOk?'stale':'error');return `<div class="deviceCard"><div class="deviceName">${esc(d.sender_name||'Unknown sensor')} <span class="status ${cls}">${state}</span></div><div class="sub">${esc(d.sender_role||'LoRaWAN device')} · ${seen?`${d.packet_count} packet${d.packet_count===1?'':'s'} · ${esc(ageText(d.latest_packet_at))}`:(readOk?`no packets in last ${windowMin} min`:'live read retrying')}</div></div>`}).join('');
  let senderGroups=devices.filter(d=>(d.packet_count||0)>0).map((d,di)=>{let eui=(d.device_eui||'').toLowerCase(),dups=ups.filter(p=>(p.device_eui||'').toLowerCase()===eui);let names=new Set();dups.forEach(p=>(p.measurements||[]).forEach(m=>names.add(m.metric_name)));let ordered=eui==='ac1f09fffe296d29'?[...METRIC_ORDER,...[...names].filter(x=>!METRIC_ORDER.includes(x)).sort()]:[...names].sort();let cards=ordered.map(name=>{let points=[],last=null;for(const p of dups){let m=(p.measurements||[]).find(x=>x.metric_name===name);if(!m)continue;last=m;let md=metricDisplay(m);if(md.numeric!=null)points.push({v:md.numeric})}let md=metricDisplay(last),chart=points.length>=2?lineChart([{name:METRIC_NAMES[name]||name,color:COLORS[di%COLORS.length],values:points}],{pad:true,decimals:md.unit==='%'||md.unit==='°C'?1:2,suffix:md.unit==='%'?'%':'',aria:`${d.sender_name||eui} ${METRIC_NAMES[name]||name} history`,leftLabel:`${dups.length} packets ago`}):'<div class="sub" style="margin-top:18px">No valid numeric trend in this window</div>';return `<div class="sensorMetric"><div class="metricName">${esc(METRIC_NAMES[name]||name)}</div><div class="metricValue">${esc(md.text)}</div><div class="metricQuality">${esc(last?.quality||'not reported in this packet window')}</div><div class="miniChart">${chart}</div></div>`}).join('');return `<div class="senderBlock"><div class="senderHead"><div class="senderTitle">${esc(d.sender_name||eui)} sensor trends</div><div class="senderMeta">${dups.length} displayed packets${d.measurement_status==='delayed'?' · decoded values delayed':''}</div></div>${cards?`<div class="metricGrid">${cards}</div>`:'<div class="waiting">Packets are arriving; decoded measurement values are not available yet.</div>'}</div>`}).join('');
  let rows=ups.slice(-30).reverse().map(p=>{let readings=(p.measurements||[]).map(m=>`${METRIC_NAMES[m.metric_name]||m.metric_name}: ${metricDisplay(m).text}`).join(' · ');let radio=`RSSI ${n(p.rssi_dbm,1)} dBm · SNR ${n(p.snr_db,1)} dB`;let freq=p.gateway_frequency_hz==null?'—':n(Number(p.gateway_frequency_hz)/1000000,3)+' MHz';let counter=`${p.f_cnt==null?'—':n(p.f_cnt,0)} / ${p.test_sequence==null?'—':n(p.test_sequence,0)}`;return `<tr><td>${esc(humanTime(p.received_at||p.time))}<div class="sub online">${esc(ageText(p.received_at||p.time))}</div></td><td><strong>${esc(p.sender_name||senderName(p.device_eui))}</strong><div class="sub">${esc(p.sender_role||'LoRaWAN device')}</div></td><td>${esc(counter)}<div class="sub">FCnt / sequence</div></td><td>${esc(radio)}<div class="sub">${esc(freq)}</div></td><td class="readingCell">${esc(readings||'Packet received; decoded measurements unavailable')}</td></tr>`}).join('');
  return `<div class="section"><div class="sectionTitle">Sensor measurements · live values and history</div>${summary}<div class="deviceStrip">${deviceCards}</div>${senderGroups}<div class="tableWrap"><table class="packetTable"><thead><tr><th>Arrived</th><th>Sender</th><th>FCnt / sequence</th><th>Radio</th><th>Sensor values</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}
function runSection(s){if(!s.run)return `<div class="section"><div class="sectionTitle">Research test result</div><div class="waiting">No completed test found yet.</div></div>`;let r=s.run,m=r.metrics||{},src=r.source||{},fabric=m.fabric_status||{},pending=fabric.pending??0,committed=m.fabric_committed_with_txid??0;return `<div class="section"><div class="sectionTitle">${s.active?'Current research test':'Latest sealed research test'}</div><div class="runbar"><div class="runname">${esc(r.id)}</div><div class="muted">${esc(r.group)}${r.condition?' · '+esc(r.condition):''}${s.active?' · recording now':' · sealed result'}</div></div><div class="cards"><div class="card"><div class="label">Messages sent</div><div class="metric">${src.attempts??0}</div><div class="sub">${src.send_ok??0} sent successfully</div></div><div class="card"><div class="label">LoRaWAN PDR</div><div class="metric">${m.formal_pdr==null?'Pending':n(m.formal_pdr,1)+'%'}</div><div class="sub">ChirpStack acceptance boundary · ${esc(m.formal_pdr_status||'not derived')}</div></div><div class="card"><div class="label">Database delivery</div><div class="metric">${m.database_delivery==null?'Pending':n(m.database_delivery,1)+'%'}</div><div class="sub">${m.exact_matches??'—'} of ${m.eligible_source_attempts??'—'} exact payload matches</div></div><div class="card"><div class="label">Network delay</div><div class="metric">${m.latency_mean_ms==null?'Pending':n(m.latency_mean_ms,1)+' ms'}</div><div class="sub">application event to database</div></div><div class="card"><div class="label">Signal strength</div><div class="metric">${m.rssi_mean_dbm==null?'Pending':n(m.rssi_mean_dbm,1)+' dBm'}</div><div class="sub">mean RSSI</div></div><div class="card"><div class="label">Signal quality</div><div class="metric">${m.snr_mean_db==null?'Pending':n(m.snr_mean_db,1)+' dB'}</div><div class="sub">mean SNR</div></div><div class="card"><div class="label">Fabric</div><div class="metric">${pending} waiting</div><div class="sub">${committed} committed with transaction ID</div></div></div></div>`}
function monitorSection(m){
  m=m||{};let sv=m.services||[],nodes=m.nodes||{},history=m.service_history||[],events=m.recent_events||[],pipe=m.pipeline||{},pc=pipe.counts||{};
  let db=m.database||{},roles=Object.entries(db).map(([k,v])=>`${nodes?.[k]?.name||k}: ${v}`).join(' · ');
  let evidenceItems=Object.values(m.evidence||{}),evidenceReady=evidenceItems.length>0&&evidenceItems.every(x=>x?.ready===true);
  let fabric=pipe.fabric_status||{},committed=0,waiting=0,attention=0;for(const [k,v] of Object.entries(fabric)){let q=Number(v)||0,lab=fabricLabel(k);if(lab==='Committed')committed+=q;else if(lab==='Waiting')waiting+=q;else attention+=q}
  let expectedInactive=x=>x?.node==='ulc03'&&x?.service==='mosquitto'&&['inactive','stopped'].includes(String(x.state||'').toLowerCase());
  let unhealthy=sv.filter(x=>!expectedInactive(x)&&!['online','running','active'].includes(String(x.state||'').toLowerCase()));
  let cards=`<div class="card"><div class="label">Database</div><div class="metric ${Object.values(db).filter(x=>x==='leader').length===1?'online':'error'}">${Object.values(db).filter(x=>x==='leader').length===1?'1 leader':'Check topology'}</div><div class="sub">${esc(roles||'role observation pending')}</div></div>`;
  cards+=`<div class="card"><div class="label">Evidence</div><div class="metric ${evidenceReady?'online':'error'}">${evidenceReady?'Ready':'Needs attention'}</div><div class="sub">collector / verifier readiness</div></div>`;
  cards+=`<div class="card"><div class="label">Fabric</div><div class="metric">${committed} committed</div><div class="sub">${waiting} waiting · ${attention} needs attention</div></div>`;
  cards+=`<div class="card"><div class="label">Service issues</div><div class="metric ${unhealthy.length?'error':'online'}">${unhealthy.length}</div><div class="sub">${unhealthy.length?'current non-running observations':'all discovered services healthy'}</div></div>`;
  cards+=`<div class="card"><div class="label">Stored uplinks</div><div class="metric">${esc(pc.uplinks??'—')}</div><div class="sub">telemetry records</div></div>`;
  cards+=`<div class="card"><div class="label">Decoded values</div><div class="metric">${esc(pc.measurements??'—')}</div><div class="sub">measurement records</div></div>`;
  let issueRows=unhealthy.map(x=>`<tr><td>${esc(nodes?.[x.node]?.name||x.node)}</td><td>${esc(x.service)}</td><td><span class="status error">${esc(x.state||'unknown')}</span></td><td>${esc(x.detail||'')}</td></tr>`).join('');
  let historyRows=history.slice(0,40).map(e=>`<tr><td>${esc(humanTime(e.observed_at))}</td><td>${esc(nodes?.[e.node]?.name||e.node)}</td><td>${esc(e.service)}</td><td>${esc(e.previous_state==null?e.state:`${e.previous_state} → ${e.state}`)}</td></tr>`).join('');
  let logRows=events.slice(0,30).map(e=>`<tr><td>${esc(humanTime(e.observed_at))}</td><td>${esc(nodes?.[e.node]?.name||e.node)}</td><td>${esc(e.service)}</td><td class="readingCell">${esc(e.message)}</td></tr>`).join('');
  let issues=unhealthy.length?`<div class="tableWrap"><table class="packetTable"><thead><tr><th>System</th><th>Service</th><th>State</th><th>Detail</th></tr></thead><tbody>${issueRows}</tbody></table></div>`:`<div class="waiting online">No current service issue is visible.</div>`;
  let advanced=`<details><summary>Advanced service diagnostics</summary><div class="tableWrap"><table class="packetTable"><thead><tr><th>Observed</th><th>System</th><th>Service</th><th>State change</th></tr></thead><tbody>${historyRows||'<tr><td colspan="4">No retained state changes.</td></tr>'}</tbody></table></div><div class="tableWrap"><table class="packetTable"><thead><tr><th>Observed</th><th>System</th><th>Service</th><th>Warning / error</th></tr></thead><tbody>${logRows||'<tr><td colspan="4">No retained warnings or errors.</td></tr>'}</tbody></table></div></details>`;
  return `<div class="section"><div class="sectionTitle">Pipeline & integrity health</div><div class="cards">${cards}</div>${issues}${advanced}</div>`;
}
function timingSection(m){
  let c=m?.clock||{},nodes=c.nodes||{},offset=c.server_minus_workstation_seconds,spread=c.cloud_spread_seconds,gatewayCloud=c.gateway_minus_cloud_seconds;
  let nodeCards=['ulc01','ulc02','ulc03','gateway'].map(k=>{let x=nodes[k],name=x?.name||({ulc01:'Server 1',ulc02:'Server 2',ulc03:'Server 3',gateway:'Gateway'}[k]||k);if(!x)return `<div class="card"><div class="label">${esc(name)} clock</div><div class="metric stale">Not observed</div><div class="sub">waiting for a fresh management-stream timestamp</div></div>`;let lim=k==='gateway'?(c.gateway_skew_limit_seconds??1.5):(c.workstation_skew_limit_seconds??.25),good=x.fresh&&Math.abs(Number(x.server_minus_workstation_seconds))<=Number(lim);return `<div class="card"><div class="label">${esc(name)} clock</div><div class="metric ${good?'online':'error'}">${Number(x.server_minus_workstation_seconds)>=0?'+':''}${n(x.server_minus_workstation_seconds,3)} s</div><div class="sub">server − workstation · ${x.fresh?'fresh':'stale'} · limit ±${n(lim,3)} s</div></div>`}).join('');
  let reasons=(c.reasons||[]).map(x=>`<div class="sub">• ${esc(x)}</div>`).join('');
  return `<div class="section"><div class="sectionTitle">Timing preflight · fail closed before counted testing</div><div class="runbar"><div><div class="runname">Clock gate <span class="status ${c.ready?'online':'error'}">${esc(c.status||'NO-GO')}</span></div><div class="muted">EMU source lines are timestamped by this workstation; formal experiment windows use server UTC. The recorder independently re-checks cloud clocks with midpoint-corrected probes and also compares Gateway-01 against cloud UTC before it can create a run.</div>${reasons}</div><div class="status ${c.ready?'online':'error'}">${c.ready?'TIMING READY':'DO NOT START LATENCY-SENSITIVE TRIALS'}</div></div><div class="cards"><div class="card"><div class="label">Cloud − workstation</div><div class="metric ${c.ready?'online':'error'}">${offset==null?'—':(Number(offset)>=0?'+':'')+n(offset,3)+' s'}</div><div class="sub">cluster median · hard recorder limit ±${n(c.workstation_skew_limit_seconds??.25,3)} s</div></div><div class="card"><div class="label">Gateway − cloud</div><div class="metric ${gatewayCloud!=null&&Math.abs(Number(gatewayCloud))<=Number(c.gateway_skew_limit_seconds??1.5)?'online':'error'}">${gatewayCloud==null?'—':(Number(gatewayCloud)>=0?'+':'')+n(gatewayCloud,3)+' s'}</div><div class="sub">stream estimate · hard recorder uses midpoint-corrected snapshot · limit ±${n(c.gateway_skew_limit_seconds??1.5,3)} s</div></div><div class="card"><div class="label">Cloud internal spread</div><div class="metric">${spread==null?'—':n(spread,3)+' s'}</div><div class="sub">ULC-01/02/03 stream estimates · formal recorder probes are authoritative</div></div>${nodeCards}</div></div>`;
}
function stagingSection(s){
  let m=s.monitor||{},c=m.clock||{},db=m.database||{},e=m.evidence||{},p=m.pipeline||{},t=s.telemetry||{},sys=s.systems||{};
  let dbRoles=Object.values(db),checks=[
    ['Timing gate',!!c.ready,c.ready?'clock domains are within staging limits':'clock gate is NO-GO'],
    ['Cloud monitor', ['ulc01','ulc02','ulc03'].every(k=>sys?.[k]?.status==='online'), 'all three cloud resource streams must be live'],
    ['Gateway management', sys?.gateway?.status==='online', sys?.gateway?.status==='online'?'gateway stream is live':'gateway management observation is unavailable'],
    ['Database topology', dbRoles.filter(x=>x==='leader').length===1&&dbRoles.filter(x=>x==='replica').length===2, `roles: ${['ulc01','ulc02','ulc03'].map(k=>`${k}=${db[k]||'—'}`).join(' · ')}`],
    ['Evidence readiness', ['ulc01','ulc02','ulc03'].every(k=>e?.[k]?.ready===true), 'collector/verifier/Fabric readiness observations'],
    ['Pipeline counters', !!p.observed_at&&Object.keys(p.counts||{}).length>=7, p.observed_at?`leader counters observed ${ageText(p.observed_at)}`:'leader counters not yet observed'],
    ['Telemetry read path', t.status!=='error', t.status==='online'?'sensor packets currently visible':t.status==='idle'||t.status==='stale'?'database read path available; fresh packets are not required for staging':'telemetry observation unavailable'],
    ['No formal run active', !s.active, s.active?'a recorder run is already active':'safe staging state'],
  ];
  let go=checks.every(x=>x[1]);let cards=checks.map(x=>`<div class="card"><div class="label">${esc(x[0])}</div><div class="metric ${x[1]?'online':'error'}">${x[1]?'PASS':'BLOCKED'}</div><div class="sub">${esc(x[2])}</div></div>`).join('');
  return `<div class="section"><div class="sectionTitle">Overall staging readiness · live observations only</div><div class="runbar"><div><div class="runname">Infrastructure staging <span class="status ${go?'online':'error'}">${go?'GO':'NO-GO'}</span></div><div class="muted">This prevents obvious setup mistakes before a counted run. It is not a research result. The recorder's own preflight remains the final gate and additionally verifies local USB/serial requirements.</div></div><div class="status ${go?'online':'error'}">${go?'READY FOR RECORDER PREFLIGHT':'REPAIR BLOCKERS FIRST'}</div></div><div class="cards">${cards}</div></div>`;
}
function render(s){lastRefresh=Date.now();document.getElementById('stamp').textContent=`Updated ${new Date(s.generated_at).toLocaleTimeString()} · systems 1 s · sensors 5 s`;document.getElementById('grafana').href=s.links?.grafana||'#';document.getElementById('chirp').href=s.links?.chirpstack||'#';let systems=`<div class="section"><div class="sectionTitle">Infrastructure now · actual usage</div><div class="tableWrap"><div class="systems"><div class="cell head">System</div><div class="cell head">CPU</div><div class="cell head">RAM used / total</div><div class="cell head">Receiving</div><div class="cell head">Sending</div>`;for(const key of KEYS){let x=s.systems?.[key]||{};systems+=`<div class="cell"><div class="name">${esc(x.name||key)}</div><div class="status ${x.status||'unavailable'}">${statusText(x.status)}</div></div><div class="cell">${cpu(x)}</div><div class="cell">${ram(x)}</div><div class="cell">${traffic(x.receive_mbps,x.receive_capacity_mbps,x.capacity_label||'live traffic')}</div><div class="cell">${traffic(x.send_mbps,x.send_capacity_mbps,x.capacity_label||'live traffic')}</div>`}systems+='</div></div></div>';let advanced=`<details class="advancedWrap"><summary>Advanced preflight & resource trends</summary>${stagingSection(s)}${timingSection(s.monitor||{})}${resourceHistory(s.systems||{})}</details>`;document.getElementById('app').innerHTML=sensorHistory(s.telemetry||{})+runSection(s)+packetSection(s.packets||{})+systems+monitorSection(s.monitor||{})+advanced}
function updateLive(){let e=document.getElementById('liveText');if(!lastRefresh){e.textContent='CONNECTING';return}let age=(Date.now()-lastRefresh)/1000;e.textContent=age<2?'LIVE · 1s':'RECONNECTING'}
async function tick(){try{let r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);render(await r.json())}catch(e){document.getElementById('stamp').textContent='Connection lost — retrying';}updateLive()}
tick();setInterval(tick,REFRESH_MS);setInterval(updateLive,200);
</script></body></html>''' 


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/state":
            body = json.dumps(build_state(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route in ("/", "/index.html"):
            body = INDEX.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        return


def main():
    ap = argparse.ArgumentParser(description="Local read-only LoRaWAN live research monitor")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--telemetry-worker", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.telemetry_worker:
        telemetry_worker_main()
        return
    start_telemetry_collector()
    start_live_collectors()
    TESTING_MONITOR.start()
    PACKET_MONITOR.start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"RESEARCH_COCKPIT=http://{args.host}:{args.port}", flush=True)
    print("LIVE_SYSTEM_METRICS=1-second SSH streams; LIVE_SENSOR_HISTORY=read-only Timescale exports; sealed research results remain authoritative", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        PACKET_MONITOR.stop()
        TESTING_MONITOR.stop()
        stop_live_collectors()
        stop_telemetry_collector()


if __name__ == "__main__":
    main()
