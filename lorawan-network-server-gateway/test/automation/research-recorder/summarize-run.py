#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import json
import math
import re
import statistics
import struct
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def parse_dt(value: str):
    if not value:
        return None
    value = value.strip().replace(' ', 'T')
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def nums(values):
    out = []
    for v in values:
        try:
            if v is not None and str(v).strip() != '':
                x = float(v)
                if math.isfinite(x):
                    out.append(x)
        except (TypeError, ValueError):
            pass
    return out


def stats(values):
    vals = nums(values)
    if not vals:
        return None
    return {
        'count': len(vals),
        'mean': statistics.fmean(vals),
        'min': min(vals),
        'max': max(vals),
        'sd_sample': statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def read_csv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def sequence_summary(values):
    seq = sorted(set(int(v) for v in values if str(v).strip().isdigit()))
    if not seq:
        return {'count': 0, 'min': None, 'max': None, 'gaps': []}
    gaps = [x for x in range(seq[0], seq[-1] + 1) if x not in set(seq)]
    return {'count': len(seq), 'min': seq[0], 'max': seq[-1], 'gaps': gaps}


def source_attempt_details(path: Path):
    attempts = []
    if not path.exists():
        return attempts

    required = {
        'seq', 'reason', 'uptime_ms', 'soil_pct', 'soil_temp_c', 'uv_index',
        'baro_pa', 'baro_temp_c', 'light_veml_lux', 'light_opt_lux',
        'env_temp_c', 'env_humidity_pct', 'env_pressure_pa', 'env_gas_ohm',
        'rain_wet', 'battery_mv', 'valid', 'join', 'send_status',
    }

    with path.open('r', encoding='utf-8-sig', errors='replace') as f:
        for line_no, line in enumerate(f, start=1):
            if '|SENSOR_TX,' not in line:
                continue
            try:
                timestamp_text, _label, _port, text = line.rstrip('\r\n').split('|', 3)
            except ValueError as exc:
                raise ValueError(f'malformed SENSOR_TX recorder line {line_no}') from exc

            fields = {}
            for token in text.split(',')[1:]:
                if '=' in token:
                    key, value = token.split('=', 1)
                    fields[key] = value
            missing = sorted(required - set(fields))
            if missing:
                raise ValueError(f'SENSOR_TX line {line_no} missing fields: {missing}')

            def x100(name: str) -> int:
                return int(round(float(fields[name]) * 100.0))

            payload = bytearray(46)
            payload[0] = 2
            struct.pack_into('>I', payload, 1, int(fields['seq']))
            struct.pack_into('>I', payload, 5, int(fields['uptime_ms']))
            struct.pack_into('>H', payload, 9, x100('soil_pct'))
            struct.pack_into('>h', payload, 11, x100('soil_temp_c'))
            struct.pack_into('>H', payload, 13, x100('uv_index'))
            struct.pack_into('>I', payload, 15, int(fields['baro_pa']))
            struct.pack_into('>h', payload, 19, x100('baro_temp_c'))
            struct.pack_into('>I', payload, 21, x100('light_veml_lux'))
            struct.pack_into('>I', payload, 25, x100('light_opt_lux'))
            struct.pack_into('>h', payload, 29, x100('env_temp_c'))
            struct.pack_into('>H', payload, 31, x100('env_humidity_pct'))
            struct.pack_into('>I', payload, 33, int(fields['env_pressure_pa']))
            struct.pack_into('>I', payload, 37, int(fields['env_gas_ohm']))
            payload[41] = 1 if int(fields['rain_wet']) else 0
            struct.pack_into('>H', payload, 42, int(fields['battery_mv']))
            struct.pack_into('>H', payload, 44, int(fields['valid'], 0))

            attempts.append({
                'timestamp': parse_dt(timestamp_text),
                'sequence': int(fields['seq']),
                'reason': fields['reason'],
                'send_status': int(fields['send_status']),
                'raw_data': base64.b64encode(bytes(payload)).decode('ascii'),
            })
    return attempts


def source_summary(path: Path, details=None):
    attempts = source_attempt_details(path) if details is None else details
    return {
        'capture_present': path.exists(),
        'attempts': len(attempts),
        'send_ok': sum(1 for a in attempts if a['send_status'] == 0),
        'sequences': sequence_summary([a['sequence'] for a in attempts]),
        'reasons': dict(Counter(a['reason'] for a in attempts)),
    }


ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m')
DEDUP_ID_RE = re.compile(r'deduplication_id\s*=\s*([0-9a-fA-F-]{36})')
DEV_EUI_RE = re.compile(r'dev_eui\s*=\s*"?([0-9a-fA-F]{16})"?')


def chirpstack_acceptance_summary(paths, dev_eui: str, start_window=None, end_window=None):
    accepted = set()
    owned = set()
    files_present = 0
    lines_in_window = 0
    timestamp_parse_failures = 0
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        files_present += 1
        with path.open('r', encoding='utf-8-sig', errors='replace') as f:
            for line in f:
                clean = ANSI_ESCAPE_RE.sub('', line)
                if start_window is not None and end_window is not None:
                    first = clean.split(None, 1)[0] if clean.strip() else ''
                    stamp = parse_dt(first)
                    if stamp is None:
                        timestamp_parse_failures += 1
                        continue
                    if not (start_window <= stamp < end_window):
                        continue
                    lines_in_window += 1
                m = DEDUP_ID_RE.search(clean)
                if not m:
                    continue
                dedup_id = m.group(1).lower()
                if 'chirpstack::uplink' in clean and 'Uplink received' in clean and 'DataUp' in clean:
                    accepted.add(dedup_id)
                d = DEV_EUI_RE.search(clean)
                if d and d.group(1).lower() == dev_eui.lower():
                    owned.add(dedup_id)
    accepted_for_device = accepted & owned
    return {
        'files_present': files_present,
        'target_dev_eui': dev_eui.lower(),
        'window_filter_status': 'MEASURED_DOCKER_TIMESTAMP_WINDOW' if start_window is not None and end_window is not None else 'UNFILTERED_LEGACY',
        'lines_in_window': lines_in_window,
        'timestamp_parse_failures': timestamp_parse_failures,
        'accepted_uplink_ids_all_devices': len(accepted),
        'dedup_ids_with_target_device_evidence': len(owned),
        'unique_accepted_target_uplinks': len(accepted_for_device),
        'accepted_without_target_device_evidence': len(accepted - owned),
        'accepted_deduplication_ids': sorted(accepted_for_device),
    }

def resource_summary(path: Path):
    rows = read_csv(path)
    return {
        'samples': len(rows),
        'cpu_percent': stats(r.get('cpu_percent') for r in rows),
        'memory_percent': stats(r.get('memory_percent') for r in rows),
        'load1': stats(r.get('load1') for r in rows),
    }


def docker_summary(path: Path):
    rows = read_csv(path)
    by = defaultdict(list)
    for r in rows:
        by[r.get('container', 'unknown')].append(r)
    return {
        name: {
            'samples': len(rs),
            'cpu_percent': stats(r.get('cpu_percent') for r in rs),
            'memory_percent': stats(r.get('memory_percent') for r in rs),
        }
        for name, rs in sorted(by.items())
    }


def normalize_decision(value: str) -> str:
    text = (value or '').strip().lower()
    if any(word in text for word in ('allow', 'accept', 'joinaccept')):
        return 'allow'
    if any(word in text for word in ('reject', 'deny', 'denied')):
        return 'reject'
    return 'other'


def trial_summary(rows):
    status = Counter((r.get('status') or '').strip() for r in rows if (r.get('status') or '').strip())
    conditions = Counter((r.get('test_condition') or '').strip() for r in rows if (r.get('test_condition') or '').strip())
    gateway_received = Counter((r.get('gateway_received') or 'unknown').strip().lower() for r in rows)
    false_acceptance = 0
    false_rejection = 0
    for row in rows:
        expected = normalize_decision(row.get('expected_result', ''))
        actual = normalize_decision(row.get('actual_result', ''))
        false_acceptance += int(expected == 'reject' and actual == 'allow')
        false_rejection += int(expected == 'allow' and actual == 'reject')
    return {
        'rows': len(rows),
        'counted_attempts': status.get('PASS', 0) + status.get('FAIL', 0),
        'status_counts': dict(sorted(status.items())),
        'condition_counts': dict(sorted(conditions.items())),
        'gateway_received_counts': dict(sorted(gateway_received.items())),
        'false_acceptance': false_acceptance,
        'false_rejection': false_rejection,
        'duration_seconds': stats(r.get('duration_seconds') for r in rows),
        'decision_time_seconds': stats(r.get('decision_time_seconds') for r in rows),
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: summarize-run.py RUN_DIR')
    run_dir = Path(sys.argv[1]).resolve()
    raw = run_dir / 'raw'
    derived = run_dir / 'derived'
    derived.mkdir(parents=True, exist_ok=True)

    source_details = source_attempt_details(raw / 'emu-01-source.log')
    source = source_summary(raw / 'emu-01-source.log', source_details)
    uplinks = read_csv(raw / 'uplinks.csv')
    measurements = read_csv(raw / 'measurements.csv')
    outbox = read_csv(raw / 'fabric-outbox.csv')
    gateway_mqtt = read_csv(raw / 'gateway-mqtt-events.csv')
    trials = read_csv(derived / 'trial-results.csv')

    event_keys = [r.get('event_key', '') for r in uplinks if r.get('event_key')]
    unique_events = len(set(event_keys))
    db_sequences = [r.get('test_sequence', '') for r in uplinks]
    fcnts = [r.get('f_cnt', '') for r in uplinks]
    db_sequence_counts = Counter(int(v) for v in db_sequences if str(v).strip().isdigit())
    fcnt_counts = Counter(int(v) for v in fcnts if str(v).strip().isdigit())

    latencies = []
    for r in uplinks:
        t0 = parse_dt(r.get('time', ''))
        t1 = parse_dt(r.get('received_at', ''))
        if t0 and t1:
            latencies.append((t1 - t0).total_seconds() * 1000.0)

    freq = Counter()
    for r in uplinks:
        f = r.get('gateway_frequency_hz', '')
        if f:
            freq[f] += 1

    measurements_per_event = Counter(r.get('event_key', '') for r in measurements if r.get('event_key'))
    measurement_counts = list(measurements_per_event.values())
    outbox_status = Counter(r.get('status', '') for r in outbox if r.get('status'))

    gateway_projected = [r for r in gateway_mqtt if r.get('correlation_digest_sha256')]
    gateway_freq = Counter(r.get('frequency_hz', '') for r in gateway_projected if r.get('frequency_hz'))
    gateway_topics = Counter(r.get('mqtt_topic', '') for r in gateway_mqtt if r.get('mqtt_topic'))
    gateway_phy = {r.get('phy_payload_sha256', '') for r in gateway_projected if r.get('phy_payload_sha256')}
    gateway_phy_rows = defaultdict(list)
    gateway_uplink_id_counts = Counter()
    for row in gateway_projected:
        phy = (row.get('phy_payload_sha256') or '').strip().lower()
        uplink_id = (row.get('uplink_id') or '').strip()
        if phy:
            gateway_phy_rows[phy].append(row)
        if uplink_id:
            gateway_uplink_id_counts[uplink_id] += 1
    exact_phy_repeat_groups = {phy: rows for phy, rows in gateway_phy_rows.items() if len(rows) > 1}
    same_phy_distinct_uplink_groups = {
        phy: rows for phy, rows in exact_phy_repeat_groups.items()
        if len({(row.get('uplink_id') or '').strip() for row in rows if (row.get('uplink_id') or '').strip()}) > 1
    }
    db_gateway_uplink_ids = {(row.get('gateway_uplink_id') or '').strip() for row in uplinks if (row.get('gateway_uplink_id') or '').strip()}
    gateway_frames_with_application_match = sum(1 for row in gateway_projected if (row.get('uplink_id') or '').strip() in db_gateway_uplink_ids)
    gateway_frames_without_application_match = len(gateway_projected) - gateway_frames_with_application_match
    gateway_times = [parse_dt(r.get('broker_received_at', '')) for r in gateway_mqtt]
    gateway_times = [t for t in gateway_times if t is not None]
    trials_summary = trial_summary(trials)

    resource = {}
    for node in ('gateway', 'ulc01', 'ulc02', 'ulc03'):
        p = raw / f'{node}-host-resource.csv'
        if node == 'gateway':
            p = raw / 'gateway-resource.csv'
        resource[node] = resource_summary(p)
    docker = {node: docker_summary(raw / f'{node}-docker-resource.csv') for node in ('ulc01', 'ulc02', 'ulc03')}

    db_by_raw = defaultdict(list)
    for row in uplinks:
        raw_data = row.get('raw_data', '')
        if raw_data:
            db_by_raw[raw_data].append(row)

    source_raw = {a['raw_data'] for a in source_details}
    exact_pairs = []
    clock_offsets = []
    for attempt in source_details:
        matches = db_by_raw.get(attempt['raw_data'], [])
        if not matches:
            continue
        row = matches[0]
        exact_pairs.append((attempt, row))
        db_time = parse_dt(row.get('time', ''))
        if attempt['timestamp'] and db_time:
            clock_offsets.append((db_time - attempt['timestamp']).total_seconds())

    clock_offset_median = statistics.median(clock_offsets) if clock_offsets else None
    meta = run_dir / 'metadata'
    start_window = parse_dt((meta / 'start-utc.txt').read_text(encoding='utf-8').strip()) if (meta / 'start-utc.txt').exists() else None
    end_window = parse_dt((meta / 'end-utc.txt').read_text(encoding='utf-8').strip()) if (meta / 'end-utc.txt').exists() else None

    eligible_source = []
    if clock_offset_median is not None and start_window and end_window:
        for attempt in source_details:
            if attempt['timestamp'] is None:
                continue
            projected_db_time = attempt['timestamp'] + timedelta(seconds=clock_offset_median)
            if start_window <= projected_db_time <= end_window:
                eligible_source.append(attempt)

    eligible_exact_matches = sum(1 for a in eligible_source if a['raw_data'] in db_by_raw)
    database_delivery = 100.0 * eligible_exact_matches / len(eligible_source) if eligible_source else None

    run_meta_path = meta / 'run-meta.json'
    run_meta = json.loads(run_meta_path.read_text(encoding='utf-8')) if run_meta_path.exists() else {}

    # The serial recorder starts before the formal window so it can prove the
    # port is already open. Map workstation-stamped source lines to authoritative
    # cloud UTC using the independent start/end midpoint-corrected calibration.
    # Recorder v9 fails finalization if that calibration drifts beyond its limit.
    formal_source = []
    source_window_offset_start = run_meta.get('measurement_clock_server_minus_workstation_seconds')
    source_window_offset_end = run_meta.get('measurement_clock_end_server_minus_workstation_seconds')
    calibration_status = str(run_meta.get('measurement_clock_calibration_status') or '')
    source_window_filter_status = 'WITHHELD_MISSING_SOURCE_WINDOW_CLOCK_MAPPING'
    try:
        source_window_offset_start = float(source_window_offset_start)
    except (TypeError, ValueError):
        source_window_offset_start = None
    try:
        source_window_offset_end = float(source_window_offset_end)
    except (TypeError, ValueError):
        source_window_offset_end = None

    def project_source_to_server(timestamp):
        if timestamp is None or source_window_offset_start is None:
            return None
        offset = source_window_offset_start
        if (source_window_offset_end is not None and calibration_status == 'PASS'
                and start_window and end_window):
            local_start = start_window - timedelta(seconds=source_window_offset_start)
            local_end = end_window - timedelta(seconds=source_window_offset_end)
            span = (local_end - local_start).total_seconds()
            if span > 0:
                fraction = (timestamp - local_start).total_seconds() / span
                fraction = max(0.0, min(1.0, fraction))
                offset = source_window_offset_start + fraction * (source_window_offset_end - source_window_offset_start)
        return timestamp + timedelta(seconds=offset)

    if source_window_offset_start is not None and start_window and end_window:
        for attempt in source_details:
            projected_server_time = project_source_to_server(attempt['timestamp'])
            if projected_server_time is not None and start_window <= projected_server_time <= end_window:
                formal_source.append(attempt)
        if source_window_offset_end is not None and calibration_status == 'PASS':
            source_window_filter_status = 'MEASURED_START_END_CALIBRATED_OFFSET'
        else:
            source_window_filter_status = 'MEASURED_START_OFFSET_ONLY'

    source_capture = source
    source = source_summary(raw / 'emu-01-source.log', formal_source)
    source['captured_attempts_total'] = source_capture['attempts']
    source['out_of_window_attempts'] = source_capture['attempts'] - len(formal_source)
    source['formal_window_filter_status'] = source_window_filter_status
    source['formal_window_server_minus_workstation_seconds'] = source_window_offset_start
    source['formal_window_end_server_minus_workstation_seconds'] = source_window_offset_end
    source['clock_calibration_status'] = calibration_status or 'MISSING'

    target_dev_eui = str(run_meta.get('dev_eui') or '').strip().lower()
    chirpstack_acceptance = chirpstack_acceptance_summary(
        [raw / 'ulc01-chirpstack.log', raw / 'ulc02-chirpstack.log'],
        target_dev_eui,
        start_window,
        end_window,
    ) if target_dev_eui else {
        'files_present': 0,
        'target_dev_eui': '',
        'accepted_uplink_ids_all_devices': 0,
        'dedup_ids_with_target_device_evidence': 0,
        'unique_accepted_target_uplinks': 0,
        'accepted_without_target_device_evidence': 0,
        'accepted_deduplication_ids': [],
    }
    formal_pdr_denominator = source['attempts']
    formal_pdr_numerator = chirpstack_acceptance['unique_accepted_target_uplinks']
    if source_window_filter_status not in {'MEASURED_START_END_CALIBRATED_OFFSET', 'MEASURED_START_OFFSET_ONLY'}:
        formal_pdr = None
        formal_pdr_status = 'WITHHELD_MISSING_SOURCE_WINDOW_CLOCK_MAPPING'
    elif not target_dev_eui:
        formal_pdr = None
        formal_pdr_status = 'WITHHELD_MISSING_TARGET_DEV_EUI'
    elif chirpstack_acceptance['files_present'] == 0:
        formal_pdr = None
        formal_pdr_status = 'WITHHELD_MISSING_CHIRPSTACK_LOG_EVIDENCE'
    elif formal_pdr_denominator == 0:
        formal_pdr = None
        formal_pdr_status = 'WITHHELD_NO_SENSOR_TRANSMISSION_ATTEMPTS'
    elif formal_pdr_numerator < unique_events:
        formal_pdr = None
        formal_pdr_status = 'WITHHELD_CHIRPSTACK_LOG_COVERAGE_BELOW_STORED_UPLINKS'
    elif formal_pdr_numerator > formal_pdr_denominator:
        formal_pdr = None
        formal_pdr_status = 'WITHHELD_OBSERVATION_BOUNDARY_MISMATCH_ACCEPTED_EXCEEDS_TRANSMITTED'
    else:
        formal_pdr = 100.0 * formal_pdr_numerator / formal_pdr_denominator
        formal_pdr_status = 'MEASURED_CHIRPSTACK_ACCEPTANCE_BOUNDARY'

    formal_source_raw = {a['raw_data'] for a in formal_source}
    source_unmatched = sum(1 for a in formal_source if a['raw_data'] not in db_by_raw)
    db_unmatched = sum(1 for row in uplinks if row.get('raw_data', '') not in formal_source_raw)

    sensor_to_database_latencies = []
    for attempt, row in exact_pairs:
        if attempt['raw_data'] not in formal_source_raw:
            continue
        source_server_time = project_source_to_server(attempt['timestamp'])
        database_storage_time = parse_dt(row.get('received_at', ''))
        if source_server_time is not None and database_storage_time is not None:
            sensor_to_database_latencies.append((database_storage_time - source_server_time).total_seconds() * 1000.0)
    if calibration_status != 'PASS' or source_window_offset_end is None:
        sensor_to_database_status = 'WITHHELD_MISSING_STABLE_START_END_CLOCK_CALIBRATION'
    elif not sensor_to_database_latencies:
        sensor_to_database_status = 'WITHHELD_NO_MATCHED_SOURCE_DATABASE_ROWS'
    elif any(value < 0 for value in sensor_to_database_latencies):
        sensor_to_database_status = 'WITHHELD_NEGATIVE_CALIBRATED_LATENCY'
    else:
        sensor_to_database_status = 'MEASURED_CALIBRATED_SENSOR_TO_DATABASE'
    delivery_note = (
        'Database-delivery correlation uses byte-exact payload matches. Source timestamps are shifted by the median '
        'DB-minus-source clock offset estimated from exact matches; only projected source attempts '
        'inside the DB export window are eligible. This is NOT the formal Chapter 3 PDR, whose numerator is unique legitimate uplinks accepted by ChirpStack.'
        if database_delivery is not None else
        'Database-delivery correlation withheld because a byte-exact clock-aligned source/DB observation window could not be established. Formal Chapter 3 PDR is also withheld unless unique ChirpStack acceptance evidence is derived.'
    )

    summary = {
        'run_dir': str(run_dir),
        'source': source,
        'telemetry': {
            'rows': len(uplinks),
            'unique_event_keys': unique_events,
            'duplicate_event_rows': len(event_keys) - unique_events,
            'formal_chapter3_pdr_percent': formal_pdr,
            'formal_chapter3_pdr_numerator_unique_chirpstack_accepted': formal_pdr_numerator,
            'formal_chapter3_pdr_denominator_sensor_transmission_attempts': formal_pdr_denominator,
            'formal_chapter3_pdr_status': formal_pdr_status,
            'formal_chapter3_pdr_note': 'Chapter 3 PDR uses unique accepted EMU-01 ChirpStack deduplication IDs from the exact formal server-UTC window divided by scheduled SENSOR_TX attempts projected into that same window with the recorded ULC-01/workstation clock offset. Warm-up source lines are excluded; a scheduled source-side send failure inside the window remains in the denominator. Database storage is not the numerator.',
            'database_delivery_percent_exact_payload_clock_aligned': database_delivery,
            'pdr_percent_exact_payload_clock_aligned': database_delivery,
            'pdr_note': 'DEPRECATED LABEL: this legacy field is source-to-database delivery correlation, not formal Chapter 3 PDR. ' + delivery_note,
            'database_delivery_note': delivery_note,
            'test_sequence': sequence_summary(db_sequences),
            'duplicate_test_sequence_values': {str(k): v for k, v in sorted(db_sequence_counts.items()) if v > 1},
            'frame_counter': sequence_summary(fcnts),
            'duplicate_frame_counter_values': {str(k): v for k, v in sorted(fcnt_counts.items()) if v > 1},
            'rssi_dbm': stats(r.get('rssi_dbm') for r in uplinks),
            'snr_db': stats(r.get('snr_db') for r in uplinks),
            'gateway_frequency_hz_counts': dict(sorted(freq.items())),
            'application_event_to_db_ms': stats(latencies),
            'sensor_to_database_ms': stats(sensor_to_database_latencies),
            'sensor_to_database_status': sensor_to_database_status,
            'latency_note': 'sensor_to_database_ms is received_at minus the independently calibrated SENSOR_TX workstation timestamp; application_event_to_db_ms remains received_at - application event time',
        },
        'chirpstack_acceptance': chirpstack_acceptance,
        'correlation': {
            'exact_payload_matches': len(exact_pairs),
            'source_payloads_total': len(source_details),
            'source_payloads_unmatched_to_db': source_unmatched,
            'db_payloads_total': len(uplinks),
            'db_payloads_unmatched_to_source': db_unmatched,
            'clock_offset_db_minus_source_seconds': stats(clock_offsets),
            'clock_offset_median_seconds': clock_offset_median,
            'measurement_clock_start_server_minus_workstation_seconds': source_window_offset_start,
            'measurement_clock_end_server_minus_workstation_seconds': source_window_offset_end,
            'measurement_clock_calibration_status': calibration_status or 'MISSING',
            'measurement_clock_drift_seconds': run_meta.get('measurement_clock_drift_seconds'),
            'eligible_source_attempts_in_db_export_window': len(eligible_source),
            'eligible_exact_payload_matches': eligible_exact_matches,
        },
        'measurements': {
            'rows': len(measurements),
            'events': len(measurements_per_event),
            'per_event_count': stats(measurement_counts),
            'events_with_13_measurements': sum(1 for n in measurement_counts if n == 13),
        },
        'fabric_outbox': {
            'rows': len(outbox),
            'status_counts': dict(sorted(outbox_status.items())),
            'committed_with_tx_id': sum(1 for r in outbox if r.get('committed_at') and r.get('fabric_tx_id')),
        },
        'gateway_mqtt_evidence': {
            'rows': len(gateway_mqtt),
            'projected_uplink_frames': len(gateway_projected),
            'unique_phy_payload_sha256': len(gateway_phy),
            'exact_phy_payload_repeat_groups': len(exact_phy_repeat_groups),
            'exact_phy_payload_repeat_events': sum(len(rows) for rows in exact_phy_repeat_groups.values()),
            'same_phy_distinct_uplink_id_groups': len(same_phy_distinct_uplink_groups),
            'same_phy_distinct_uplink_id_events': sum(len(rows) for rows in same_phy_distinct_uplink_groups.values()),
            'same_uplink_id_duplicate_events': sum(count - 1 for count in gateway_uplink_id_counts.values() if count > 1),
            'gateway_frames_with_application_match': gateway_frames_with_application_match,
            'gateway_frames_without_application_match': gateway_frames_without_application_match,
            'repeated_phy_payloads': {
                phy: {
                    'events': len(rows),
                    'distinct_uplink_ids': sorted({(row.get('uplink_id') or '').strip() for row in rows if (row.get('uplink_id') or '').strip()}),
                }
                for phy, rows in sorted(exact_phy_repeat_groups.items())
            },
            'frequency_hz_counts': dict(sorted(gateway_freq.items())),
            'rssi_dbm': stats(r.get('rssi_dbm') for r in gateway_projected),
            'snr_db': stats(r.get('snr_db') for r in gateway_projected),
            'mqtt_topic_counts': dict(sorted(gateway_topics.items())),
            'first_broker_received_at': min(gateway_times).isoformat() if gateway_times else None,
            'last_broker_received_at': max(gateway_times).isoformat() if gateway_times else None,
            'evidence_note': 'Gateway MQTT evidence is captured before ChirpStack application acceptance and can prove RF/gateway reception of rejected frames by PHYPayload digest and radio metadata.',
        },
        'trials': trials_summary,
        'resources': resource,
        'docker_resources': docker,
    }

    with (derived / 'run-summary.json').open('w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    flat = [
        ('source_attempts', source['attempts']),
        ('source_send_ok', source['send_ok']),
        ('db_uplink_rows', len(uplinks)),
        ('unique_db_events', unique_events),
        ('duplicate_event_rows', len(event_keys) - unique_events),
        ('exact_payload_matches', len(exact_pairs)),
        ('eligible_source_attempts', len(eligible_source)),
        ('eligible_exact_payload_matches', eligible_exact_matches),
        ('source_payloads_unmatched_to_db', source_unmatched),
        ('db_payloads_unmatched_to_source', db_unmatched),
        ('formal_chapter3_pdr_percent', '' if formal_pdr is None else f'{formal_pdr:.6f}'),
        ('formal_chapter3_pdr_numerator_unique_chirpstack_accepted', formal_pdr_numerator),
        ('formal_chapter3_pdr_denominator_sensor_transmission_attempts', formal_pdr_denominator),
        ('formal_chapter3_pdr_status', formal_pdr_status),
        ('sensor_to_database_status', sensor_to_database_status),
        ('database_delivery_percent', '' if database_delivery is None else f'{database_delivery:.6f}'),
        ('pdr_percent_deprecated_legacy_label', '' if database_delivery is None else f'{database_delivery:.6f}'),
        ('measurement_rows', len(measurements)),
        ('outbox_rows', len(outbox)),
        ('gateway_mqtt_rows', len(gateway_mqtt)),
        ('gateway_mqtt_projected_uplink_frames', len(gateway_projected)),
        ('gateway_mqtt_unique_phy_payload_sha256', len(gateway_phy)),
        ('gateway_exact_phy_repeat_groups', len(exact_phy_repeat_groups)),
        ('gateway_exact_phy_repeat_events', sum(len(rows) for rows in exact_phy_repeat_groups.values())),
        ('gateway_same_phy_distinct_uplink_id_groups', len(same_phy_distinct_uplink_groups)),
        ('gateway_same_phy_distinct_uplink_id_events', sum(len(rows) for rows in same_phy_distinct_uplink_groups.values())),
        ('gateway_same_uplink_id_duplicate_events', sum(count - 1 for count in gateway_uplink_id_counts.values() if count > 1)),
        ('gateway_frames_with_application_match', gateway_frames_with_application_match),
        ('gateway_frames_without_application_match', gateway_frames_without_application_match),
        ('trial_rows', trials_summary['rows']),
        ('trial_counted_attempts', trials_summary['counted_attempts']),
        ('trial_false_acceptance', trials_summary['false_acceptance']),
        ('trial_false_rejection', trials_summary['false_rejection']),
    ]
    rssi = summary['telemetry']['rssi_dbm']
    snr = summary['telemetry']['snr_db']
    latency = summary['telemetry']['application_event_to_db_ms']
    sensor_latency = summary['telemetry']['sensor_to_database_ms']
    for prefix, s in [('rssi_dbm', rssi), ('snr_db', snr), ('application_event_to_db_ms', latency), ('sensor_to_database_ms', sensor_latency)]:
        if s:
            for key in ('mean', 'min', 'max', 'sd_sample'):
                flat.append((f'{prefix}_{key}', f"{s[key]:.6f}"))
    with (derived / 'run-summary.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['metric', 'value'])
        w.writerows(flat)


if __name__ == '__main__':
    main()
