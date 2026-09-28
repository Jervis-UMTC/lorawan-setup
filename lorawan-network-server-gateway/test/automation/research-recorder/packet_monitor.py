#!/usr/bin/env python3
"""Live packet-path observations for the LoRaWAN research cockpit.

This module is deliberately observational.  It correlates gateway uplink evidence,
local Gateway-01 RF log evidence, accepted application rows, verifier state, and
Fabric-outbox state.  It never classifies a formal research trial PASS/FAIL; the
sealed recorder bundle remains authoritative for that decision.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

PACKET_WINDOW_MINUTES = 30
POLL_SECONDS = 5
RETENTION_DAYS = 7
MAX_LIVE_PACKETS = 250
MAX_RF_EVENTS = 500

FRAME_RE = re.compile(
    r"^(?P<stamp>[A-Z][a-z]{2} [A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4}).*?"
    r"Frame received, uplink_id: (?P<uplink>\d+), count_us: \d+, freq: (?P<freq>\d+), "
    r"bw: (?P<bw>\d+), mod: (?P<mod>[^,]+), dr: (?P<dr>SF\d+)"
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def query_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class PacketMonitor:
    def __init__(
        self,
        ssh_exe: Path,
        key: Path,
        targets: dict[str, str],
        gateway_eui: str,
        application_dev_euis: list[str] | tuple[str, ...] | None = None,
    ):
        self.ssh_exe = ssh_exe
        self.key = key
        self.targets = targets
        self.gateway_eui = gateway_eui.lower()
        self.application_dev_euis = tuple(
            dict.fromkeys(str(value).strip().lower() for value in (application_dev_euis or ()) if str(value).strip())
        )
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "LoRaWAN"
        local.mkdir(parents=True, exist_ok=True)
        self.db_path = local / "packet-monitor.sqlite3"
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.server_thread: threading.Thread | None = None
        self.gateway_thread: threading.Thread | None = None
        self.gateway_process: subprocess.Popen[str] | None = None
        self.rf_by_uplink: dict[str, dict] = {}
        self.rf_events: deque[dict] = deque(maxlen=MAX_RF_EVENTS)
        self.state = {
            "status": "starting",
            "updated_at": None,
            "source_server": None,
            "query_mode": None,
            "per_packet_verification_available": False,
            "window_minutes": PACKET_WINDOW_MINUTES,
            "counts": {},
            "packets": [],
            "packet_history": [],
            "rf_events": [],
            "error": "",
            "truth_note": (
                "Live packet observations are not formal PASS/FAIL results. A replay/spoof attempt counts only "
                "when RF/gateway reception is proven and sealed trial evidence proves the ChirpStack/downstream decision."
            ),
        }
        self._init_db()

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=3)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _init_db(self):
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS packet_observation(
                  gateway_event_id INTEGER PRIMARY KEY,
                  broker_received_at TEXT NOT NULL,
                  gateway_id TEXT NOT NULL,
                  uplink_id TEXT,
                  phy_payload_sha256 TEXT,
                  frequency_hz INTEGER,
                  rssi_dbm REAL,
                  snr_db REAL,
                  rf_log_proven INTEGER NOT NULL DEFAULT 0,
                  data_rate TEXT,
                  bandwidth_hz INTEGER,
                  event_key TEXT,
                  dev_eui TEXT,
                  f_cnt INTEGER,
                  test_sequence INTEGER,
                  verification_status TEXT,
                  verification_reason TEXT,
                  outbox_status TEXT,
                  fabric_tx_id TEXT,
                  submitted_at TEXT,
                  committed_at TEXT,
                  duplicate_class TEXT,
                  last_observed_at TEXT NOT NULL,
                  application_state TEXT,
                  fcnt_anomaly TEXT,
                  sequence_anomaly TEXT,
                  mqtt_to_db_ms REAL,
                  mqtt_to_fabric_submit_ms REAL,
                  mqtt_to_fabric_commit_ms REAL
                );
                CREATE INDEX IF NOT EXISTS packet_observation_time ON packet_observation(broker_received_at DESC);
                CREATE INDEX IF NOT EXISTS packet_observation_phy ON packet_observation(phy_payload_sha256);
                CREATE INDEX IF NOT EXISTS packet_observation_uplink ON packet_observation(uplink_id);
                """
            )
            existing = {row[1] for row in db.execute("PRAGMA table_info(packet_observation)")}
            for name, sql_type in (
                ("application_state", "TEXT"),
                ("fcnt_anomaly", "TEXT"),
                ("sequence_anomaly", "TEXT"),
                ("mqtt_to_db_ms", "REAL"),
                ("mqtt_to_fabric_submit_ms", "REAL"),
                ("mqtt_to_fabric_commit_ms", "REAL"),
            ):
                if name not in existing:
                    db.execute(f"ALTER TABLE packet_observation ADD COLUMN {name} {sql_type}")

    def _ssh_argv(self, node: str, command: str) -> list[str]:
        return [
            str(self.ssh_exe),
            "-o", "BatchMode=yes",
            "-o", f"IdentityFile={self.key}",
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=5",
            self.targets[node],
            command,
        ]

    def start(self):
        if self.server_thread and self.server_thread.is_alive():
            return
        self.stop_event.clear()
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True, name="packet-monitor-server")
        self.gateway_thread = threading.Thread(target=self._gateway_loop, daemon=True, name="packet-monitor-gateway")
        self.server_thread.start()
        self.gateway_thread.start()

    def stop(self):
        self.stop_event.set()
        p = self.gateway_process
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        for thread in (self.server_thread, self.gateway_thread):
            if thread:
                thread.join(timeout=3)

    def _parse_gateway_frame(self, line: str) -> dict | None:
        match = FRAME_RE.search(line)
        if not match:
            return None
        try:
            stamp = datetime.strptime(match.group("stamp"), "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
            return {
                "observed_at": stamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "uplink_id": match.group("uplink"),
                "frequency_hz": int(match.group("freq")),
                "bandwidth_hz": int(match.group("bw")),
                "modulation": match.group("mod").strip(),
                "data_rate": match.group("dr"),
                "raw_log": line[-700:],
            }
        except Exception:
            return None

    def _remember_rf_frame(self, frame: dict) -> None:
        with self.lock:
            self.rf_by_uplink[frame["uplink_id"]] = frame
            self.rf_events.append(frame)
            # Bound the lookup map even if uplink IDs never repeat.
            if len(self.rf_by_uplink) > 1500:
                keep = {x["uplink_id"] for x in list(self.rf_events)[-MAX_RF_EVENTS:]}
                self.rf_by_uplink = {k: v for k, v in self.rf_by_uplink.items() if k in keep}

    def _seed_gateway_recent(self) -> None:
        """Backfill recent gateway receptions before tailing the live log.

        This makes RF proof immediately useful after a cockpit restart instead of
        requiring every displayed packet to have arrived after the monitor process.
        The bounded gateway wrapper returns only recent RAK5146 frame log lines.
        """
        try:
            cp = subprocess.run(
                self._ssh_argv("gateway", f"radio-recent {MAX_RF_EVENTS}"),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return
        if cp.returncode != 0:
            return
        for line in cp.stdout.splitlines():
            frame = self._parse_gateway_frame(line.strip())
            if frame is not None:
                self._remember_rf_frame(frame)

    def _gateway_loop(self):
        while not self.stop_event.is_set():
            process = None
            try:
                self._seed_gateway_recent()
                process = subprocess.Popen(
                    self._ssh_argv("gateway", "logstream"),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                self.gateway_process = process
                assert process.stdout is not None
                for line in process.stdout:
                    if self.stop_event.is_set():
                        break
                    frame = self._parse_gateway_frame(line.strip())
                    if frame is not None:
                        self._remember_rf_frame(frame)
            except Exception:
                pass
            finally:
                self.gateway_process = None
                if process is not None and process.poll() is None:
                    try:
                        process.terminate()
                    except Exception:
                        pass
            self.stop_event.wait(2)

    def _run_export(self, node: str, table: str, start: datetime, end: datetime, identity: str) -> list[dict]:
        cp = subprocess.run(
            self._ssh_argv(node, f"db-export {table} {query_time(start)} {query_time(end)} {identity}"),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip().splitlines()
            raise RuntimeError((detail[-1] if detail else f"{table} export failed")[:160])
        return list(csv.DictReader(io.StringIO(cp.stdout)))

    def _query_packetflow_v4(self, node: str, start: datetime, end: datetime) -> list[dict]:
        """Build packet-flow rows locally from the recorder-v4 read-only exports.

        gatewaymqtt is deliberately the left side of the join.  A replay or bad-MIC
        packet can therefore remain visible even when ChirpStack correctly creates
        no application row and no Fabric outbox row.
        """
        gateway_rows = [
            row for row in self._run_export(node, "gatewaymqtt", start, end, self.gateway_eui)
            if (row.get("mqtt_topic") or "").endswith("/event/up")
        ]
        uplinks: list[dict] = []
        outbox: list[dict] = []
        for dev_eui in self.application_dev_euis:
            uplinks.extend(self._run_export(node, "uplinks", start, end, dev_eui))
            outbox.extend(self._run_export(node, "outbox", start, end, dev_eui))

        uplink_by_gateway_id: dict[tuple[str, str], dict] = {}
        for row in uplinks:
            key = ((row.get("gateway_id") or "").strip().lower(), (row.get("gateway_uplink_id") or "").strip())
            if key[0] and key[1]:
                uplink_by_gateway_id[key] = row
        outbox_by_source = {
            (row.get("source_event_key") or "").strip(): row
            for row in outbox
            if (row.get("source_event_key") or "").strip()
        }

        joined: list[dict] = []
        for gateway in gateway_rows:
            key = ((gateway.get("gateway_id") or "").strip().lower(), (gateway.get("uplink_id") or "").strip())
            app = uplink_by_gateway_id.get(key, {})
            fabric = outbox_by_source.get((app.get("event_key") or "").strip(), {}) if app else {}
            joined.append(
                {
                    **gateway,
                    "event_key": app.get("event_key", ""),
                    "application_time": app.get("time", ""),
                    "database_received_at": app.get("received_at", ""),
                    "dev_eui": app.get("dev_eui", ""),
                    "f_cnt": app.get("f_cnt", ""),
                    "test_sequence": app.get("test_sequence", ""),
                    "verification_status": "",
                    "verification_reason": "aggregate-only on recorder-v4" if app else "",
                    "outbox_status": fabric.get("status", ""),
                    "fabric_tx_id": fabric.get("fabric_tx_id", ""),
                    "submitted_at": fabric.get("submitted_at", ""),
                    "committed_at": fabric.get("committed_at", ""),
                }
            )
        return joined

    def _query_packetflow(self) -> tuple[str, str, bool, list[dict]]:
        # Use a wide live window because the workstation and the gateway have had
        # clock corrections during commissioning. Formal recorder calculations use
        # sealed run boundaries instead of this convenience window.
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=max(PACKET_WINDOW_MINUTES + 5, 90))
        end = now + timedelta(minutes=5)
        last_error = ""
        for node in ("ulc03", "ulc01", "ulc02"):
            try:
                rows = self._run_export(node, "packetflow", start, end, self.gateway_eui)
                return node, "server-v5-joined", True, rows
            except Exception as v5_exc:
                try:
                    rows = self._query_packetflow_v4(node, start, end)
                    return node, "server-v4-local-join", False, rows
                except Exception as v4_exc:
                    last_error = f"{node}: v5={type(v5_exc).__name__}; v4={str(v4_exc)[:110]}"
                    continue
        raise RuntimeError(last_error or "packet-flow query unavailable")

    @staticmethod
    def _int(value):
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(value):
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _latency_ms(start_value: str | None, end_value: str | None) -> float | None:
        start = parse_dt(start_value)
        end = parse_dt(end_value)
        if start is None or end is None:
            return None
        value = (end - start).total_seconds() * 1000.0
        return round(value, 3) if value >= 0 else None

    @staticmethod
    def _counter_anomaly(previous: int | None, current: int | None, reset_label: str) -> tuple[str, int]:
        if previous is None or current is None:
            return "", 0
        if current == previous:
            return "repeat", 0
        if current < previous:
            return reset_label, 0
        if current > previous + 1:
            missing = current - previous - 1
            return f"gap:+{missing}", missing
        return "normal", 0

    def _classify(self, rows: list[dict]) -> tuple[list[dict], dict]:
        phy_rows: dict[str, list[dict]] = {}
        uplink_counts = Counter()
        for row in rows:
            phy = (row.get("phy_payload_sha256") or "").strip().lower()
            uplink = (row.get("uplink_id") or "").strip()
            if phy:
                phy_rows.setdefault(phy, []).append(row)
            if uplink:
                uplink_counts[uplink] += 1

        out: list[dict] = []
        with self.lock:
            rf_map = dict(self.rf_by_uplink)
        for row in rows:
            phy = (row.get("phy_payload_sha256") or "").strip().lower()
            uplink = (row.get("uplink_id") or "").strip()
            group = phy_rows.get(phy, []) if phy else []
            distinct_ids = {str(x.get("uplink_id") or "") for x in group if x.get("uplink_id") not in (None, "")}
            if len(distinct_ids) > 1:
                duplicate_class = "exact_phy_repeat_new_rf_id"
            elif len(group) > 1 or (uplink and uplink_counts[uplink] > 1):
                duplicate_class = "transport_or_duplicate_capture"
            else:
                duplicate_class = "unique_observation"
            rf = rf_map.get(uplink, {})
            app_accepted = bool((row.get("event_key") or "").strip())
            observed_at = row.get("broker_received_at") or ""
            age = None
            dt = parse_dt(observed_at)
            if dt:
                age = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
            application_state = "accepted_application" if app_accepted else ("no_accepted_application_observed" if age is None or age >= 5 else "decision_pending")
            out.append(
                {
                    "gateway_event_id": self._int(row.get("gateway_event_id")),
                    "gateway_id": row.get("gateway_id") or "",
                    "broker_received_at": observed_at,
                    "uplink_id": uplink,
                    "phy_payload_sha256": phy,
                    "phy_repeat_count": len(group),
                    "distinct_uplink_ids_for_phy": len(distinct_ids),
                    "duplicate_class": duplicate_class,
                    "frequency_hz": self._int(row.get("frequency_hz")),
                    "rssi_dbm": self._float(row.get("rssi_dbm")),
                    "snr_db": self._float(row.get("snr_db")),
                    "rf_log_proven": bool(rf),
                    "rf_observed_at": rf.get("observed_at"),
                    "data_rate": rf.get("data_rate"),
                    "bandwidth_hz": rf.get("bandwidth_hz"),
                    "event_key": row.get("event_key") or "",
                    "application_time": row.get("application_time") or "",
                    "database_received_at": row.get("database_received_at") or "",
                    "dev_eui": (row.get("dev_eui") or "").lower(),
                    "f_cnt": self._int(row.get("f_cnt")),
                    "test_sequence": self._int(row.get("test_sequence")),
                    "application_state": application_state,
                    "verification_status": row.get("verification_status") or "",
                    "verification_reason": row.get("verification_reason") or "",
                    "outbox_status": row.get("outbox_status") or "",
                    "fabric_tx_id": row.get("fabric_tx_id") or "",
                    "submitted_at": row.get("submitted_at") or "",
                    "committed_at": row.get("committed_at") or "",
                    "mqtt_to_db_ms": self._latency_ms(observed_at, row.get("database_received_at")),
                    "mqtt_to_fabric_submit_ms": self._latency_ms(observed_at, row.get("submitted_at")),
                    "mqtt_to_fabric_commit_ms": self._latency_ms(observed_at, row.get("committed_at")),
                    "fcnt_anomaly": "",
                    "sequence_anomaly": "",
                }
            )

        out.sort(key=lambda x: (x.get("broker_received_at") or "", x.get("gateway_event_id") or 0))
        fcnt_gap_missing = 0
        sequence_gap_missing = 0
        accepted_by_device: dict[str, list[dict]] = {}
        for packet in out:
            if packet["application_state"] == "accepted_application" and packet.get("dev_eui"):
                accepted_by_device.setdefault(packet["dev_eui"], []).append(packet)
        for device_packets in accepted_by_device.values():
            previous_fcnt = None
            previous_sequence = None
            for packet in device_packets:
                fcnt_state, fcnt_missing = self._counter_anomaly(previous_fcnt, packet.get("f_cnt"), "regression/session-reset-candidate")
                sequence_state, sequence_missing = self._counter_anomaly(previous_sequence, packet.get("test_sequence"), "regression/reboot-candidate")
                packet["fcnt_anomaly"] = fcnt_state
                packet["sequence_anomaly"] = sequence_state
                fcnt_gap_missing += fcnt_missing
                sequence_gap_missing += sequence_missing
                if packet.get("f_cnt") is not None:
                    previous_fcnt = packet["f_cnt"]
                if packet.get("test_sequence") is not None:
                    previous_sequence = packet["test_sequence"]

        repeat_groups = [g for g in phy_rows.values() if len(g) > 1]
        distinct_repeat_groups = [
            g for g in repeat_groups
            if len({str(x.get("uplink_id") or "") for x in g if x.get("uplink_id") not in (None, "")}) > 1
        ]
        db_latencies = [x["mqtt_to_db_ms"] for x in out if x.get("mqtt_to_db_ms") is not None]
        fabric_latencies = [x["mqtt_to_fabric_commit_ms"] for x in out if x.get("mqtt_to_fabric_commit_ms") is not None]
        counts = {
            "gateway_uplink_events": len(rows),
            "rf_log_matches": sum(1 for x in out if x["rf_log_proven"]),
            "application_accepted": sum(1 for x in out if x["application_state"] == "accepted_application"),
            "not_propagated_observed": sum(1 for x in out if x["application_state"] == "no_accepted_application_observed"),
            "decision_pending": sum(1 for x in out if x["application_state"] == "decision_pending"),
            "exact_phy_repeat_groups": len(repeat_groups),
            "exact_phy_repeat_events": sum(len(g) for g in repeat_groups),
            "same_phy_distinct_rf_id_groups": len(distinct_repeat_groups),
            "same_phy_distinct_rf_id_events": sum(len(g) for g in distinct_repeat_groups),
            "same_uplink_id_duplicate_events": sum(max(0, value - 1) for value in uplink_counts.values()),
            "fcnt_repeats": sum(1 for x in out if x.get("fcnt_anomaly") == "repeat"),
            "fcnt_gap_events": sum(1 for x in out if str(x.get("fcnt_anomaly", "")).startswith("gap:")),
            "fcnt_gap_missing": fcnt_gap_missing,
            "fcnt_regressions": sum(1 for x in out if str(x.get("fcnt_anomaly", "")).startswith("regression/")),
            "sequence_repeats": sum(1 for x in out if x.get("sequence_anomaly") == "repeat"),
            "sequence_gap_events": sum(1 for x in out if str(x.get("sequence_anomaly", "")).startswith("gap:")),
            "sequence_gap_missing": sequence_gap_missing,
            "sequence_regressions": sum(1 for x in out if str(x.get("sequence_anomaly", "")).startswith("regression/")),
            "mqtt_to_db_avg_ms": round(sum(db_latencies) / len(db_latencies), 3) if db_latencies else None,
            "mqtt_to_db_max_ms": round(max(db_latencies), 3) if db_latencies else None,
            "mqtt_to_fabric_commit_avg_ms": round(sum(fabric_latencies) / len(fabric_latencies), 3) if fabric_latencies else None,
            "mqtt_to_fabric_commit_max_ms": round(max(fabric_latencies), 3) if fabric_latencies else None,
            "verification_verified": sum(1 for x in out if x["verification_status"] == "verified"),
            "fabric_committed": sum(1 for x in out if x["committed_at"] and x["fabric_tx_id"]),
            "fabric_pending": sum(1 for x in out if x["outbox_status"] == "pending"),
        }
        return out[-MAX_LIVE_PACKETS:], counts

    def _persist(self, packets: list[dict]):
        now = iso_now()
        rows = []
        for p in packets:
            event_id = p.get("gateway_event_id")
            if event_id is None:
                continue
            rows.append(
                (
                    event_id, p.get("broker_received_at") or now, p.get("gateway_id") or "",
                    p.get("uplink_id") or "", p.get("phy_payload_sha256") or "", p.get("frequency_hz"),
                    p.get("rssi_dbm"), p.get("snr_db"), 1 if p.get("rf_log_proven") else 0,
                    p.get("data_rate") or "", p.get("bandwidth_hz"), p.get("event_key") or "",
                    p.get("dev_eui") or "", p.get("f_cnt"), p.get("test_sequence"),
                    p.get("verification_status") or "", p.get("verification_reason") or "",
                    p.get("outbox_status") or "", p.get("fabric_tx_id") or "",
                    p.get("submitted_at") or "", p.get("committed_at") or "",
                    p.get("duplicate_class") or "", now, p.get("application_state") or "",
                    p.get("fcnt_anomaly") or "", p.get("sequence_anomaly") or "",
                    p.get("mqtt_to_db_ms"), p.get("mqtt_to_fabric_submit_ms"), p.get("mqtt_to_fabric_commit_ms"),
                )
            )
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat().replace("+00:00", "Z")
        with self._connect() as db:
            if rows:
                db.executemany(
                    """
                    INSERT INTO packet_observation(
                      gateway_event_id,broker_received_at,gateway_id,uplink_id,phy_payload_sha256,frequency_hz,
                      rssi_dbm,snr_db,rf_log_proven,data_rate,bandwidth_hz,event_key,dev_eui,f_cnt,test_sequence,
                      verification_status,verification_reason,outbox_status,fabric_tx_id,submitted_at,committed_at,
                      duplicate_class,last_observed_at,application_state,fcnt_anomaly,sequence_anomaly,
                      mqtt_to_db_ms,mqtt_to_fabric_submit_ms,mqtt_to_fabric_commit_ms
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(gateway_event_id) DO UPDATE SET
                      rf_log_proven=excluded.rf_log_proven,data_rate=excluded.data_rate,bandwidth_hz=excluded.bandwidth_hz,
                      event_key=excluded.event_key,dev_eui=excluded.dev_eui,f_cnt=excluded.f_cnt,test_sequence=excluded.test_sequence,
                      verification_status=excluded.verification_status,verification_reason=excluded.verification_reason,
                      outbox_status=excluded.outbox_status,fabric_tx_id=excluded.fabric_tx_id,submitted_at=excluded.submitted_at,
                      committed_at=excluded.committed_at,duplicate_class=excluded.duplicate_class,last_observed_at=excluded.last_observed_at,
                      application_state=excluded.application_state,fcnt_anomaly=excluded.fcnt_anomaly,
                      sequence_anomaly=excluded.sequence_anomaly,mqtt_to_db_ms=excluded.mqtt_to_db_ms,
                      mqtt_to_fabric_submit_ms=excluded.mqtt_to_fabric_submit_ms,
                      mqtt_to_fabric_commit_ms=excluded.mqtt_to_fabric_commit_ms
                    """,
                    rows,
                )
            db.execute("DELETE FROM packet_observation WHERE broker_received_at < ?", (cutoff,))

    def _history(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT gateway_event_id,broker_received_at,gateway_id,uplink_id,phy_payload_sha256,frequency_hz,
                       rssi_dbm,snr_db,rf_log_proven,data_rate,bandwidth_hz,event_key,dev_eui,f_cnt,test_sequence,
                       verification_status,verification_reason,outbox_status,fabric_tx_id,submitted_at,committed_at,
                       duplicate_class,last_observed_at,application_state,fcnt_anomaly,sequence_anomaly,
                       mqtt_to_db_ms,mqtt_to_fabric_submit_ms,mqtt_to_fabric_commit_ms
                FROM packet_observation ORDER BY broker_received_at DESC,gateway_event_id DESC LIMIT 500
                """
            ).fetchall()
        keys = (
            "gateway_event_id","broker_received_at","gateway_id","uplink_id","phy_payload_sha256","frequency_hz",
            "rssi_dbm","snr_db","rf_log_proven","data_rate","bandwidth_hz","event_key","dev_eui","f_cnt",
            "test_sequence","verification_status","verification_reason","outbox_status","fabric_tx_id","submitted_at",
            "committed_at","duplicate_class","last_observed_at","application_state","fcnt_anomaly","sequence_anomaly",
            "mqtt_to_db_ms","mqtt_to_fabric_submit_ms","mqtt_to_fabric_commit_ms",
        )
        return [dict(zip(keys, row)) for row in rows]

    def _server_loop(self):
        while not self.stop_event.is_set():
            try:
                node, query_mode, verification_detail, rows = self._query_packetflow()
                packets, counts = self._classify(rows)
                self._persist(packets)
                history = self._history()
                with self.lock:
                    self.state.update(
                        status="online",
                        updated_at=iso_now(),
                        source_server=node,
                        query_mode=query_mode,
                        per_packet_verification_available=verification_detail,
                        counts=counts,
                        packets=packets,
                        packet_history=history,
                        rf_events=list(self.rf_events)[-100:],
                        error="",
                    )
            except Exception as exc:
                with self.lock:
                    self.state.update(status="unavailable", updated_at=iso_now(), error=str(exc)[:180], rf_events=list(self.rf_events)[-100:])
            self.stop_event.wait(POLL_SECONDS)

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.state))
