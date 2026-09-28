#!/usr/bin/env python3
"""Fail-closed Chapter 3 F1/F2 flooding orchestrator.

Formal mode runs 0/s, 10/s, and 50/s for 300 seconds each, three repetitions,
with a 300-second recovery window after every run. Commissioning mode uses the
same orchestration with shorter windows and is never counted research.

The harness can mutate only the reviewed isolated research fixtures through the
restricted research-actions SSH key. It never uses an administrator key and it
never publishes to production MQTT topics.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "test" / "automation" / "research_contract.py"
RECORDER = ROOT / "test" / "automation" / "research-recorder" / "research_recorder.py"
CONN_FLOOD = ROOT / "test" / "automation" / "load-tools" / "connection_flood.py"
MSG_FLOOD = ROOT / "test" / "automation" / "load-tools" / "invalid_message_stream.py"
MQTT_PUBLISH = ROOT / "test" / "automation" / "load-tools" / "mqtt_publish_stream.py"
SSH = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
HOME = Path.home()
ACTION_KEY = HOME / ".ssh" / "id_ed25519_lorawan_research_actions"
TUNNEL_KEY = HOME / ".ssh" / "id_ed25519_lorawan_flood_win"
RECORDER_KEY = HOME / ".ssh" / "id_ed25519_research_recorder"
ULC01 = "opsadmin@143.198.205.54"
ULC03 = "opsadmin@159.223.50.57"
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 11885
TEST_USER = "flood_publisher"
# Deliberately non-secret and valid only on the ephemeral isolated listener.
TEST_PASSWORD = "lorawan-research-flood-only"
WRONG_PASSWORD = "intentionally-wrong-research-password"
FAKE_DEV_EUI = "0000000000000001"
EMU_DEV_EUI = "ac1f09fffe296d29"


def load_contract_module():
    spec = importlib.util.spec_from_file_location("research_contract", CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import research contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RC = load_contract_module()


def run(argv: list[str], *, input_text: str | None = None, timeout: float = 60.0,
        check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(argv, cwd=ROOT, input=input_text, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and cp.returncode != 0:
        tail = "\n".join(((cp.stdout or "") + (cp.stderr or "")).splitlines()[-20:])
        raise RuntimeError(f"command failed ({cp.returncode}): {' '.join(argv)}\n{tail}")
    return cp


def ssh_base(key: Path, target: str) -> list[str]:
    return [str(SSH), "-i", str(key), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            "-o", "ConnectionAttempts=1", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", target]


def action(target: str, command: str, *, timeout: float = 45.0) -> str:
    cp = run(ssh_base(ACTION_KEY, target) + [command], timeout=timeout)
    return cp.stdout.strip()


def recorder_remote(target: str, command: str, *, timeout: float = 30.0) -> str:
    cp = run(ssh_base(RECORDER_KEY, target) + [command], timeout=timeout)
    return cp.stdout.strip()


def measurement_clock_offset_seconds(run_dir: Path) -> float:
    """Return recorder-measured ULC-01 minus workstation UTC offset."""
    meta_path = run_dir / "metadata" / "run-meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if meta.get("measurement_clock_calibration_status") not in {None, "PASS"}:
        raise RuntimeError(f"recorder measurement clock calibration is not usable: {meta.get('measurement_clock_calibration_status')}")
    try:
        return float(meta["measurement_clock_server_minus_workstation_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("recorder measurement clock offset is missing or invalid") from exc


def calibrated_utc_now(clock_offset_seconds: float) -> str:
    """Project workstation UTC onto the recorder's authoritative ULC-01 clock."""
    value = datetime.now(timezone.utc) + timedelta(seconds=clock_offset_seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def require_files() -> None:
    for path in (RECORDER, CONN_FLOOD, MSG_FLOOD, MQTT_PUBLISH, SSH, ACTION_KEY,
                 TUNNEL_KEY, RECORDER_KEY):
        if not path.is_file():
            raise RuntimeError(f"required file missing: {path}")


def wait_port(open_expected: bool, timeout: float = 12.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((LOCAL_HOST, LOCAL_PORT), timeout=0.5):
                opened = True
        except OSError:
            opened = False
        if opened == open_expected:
            return
        time.sleep(0.2)
    raise RuntimeError(f"local tunnel port {LOCAL_PORT} open={opened}, expected={open_expected}")


def start_tunnel() -> subprocess.Popen[str]:
    # Fail closed if a previous SSH forward still owns the local test port.
    # Merely observing an open port after Popen is insufficient: a stale tunnel
    # can otherwise make a newly failed SSH process look healthy.
    try:
        with socket.create_connection((LOCAL_HOST, LOCAL_PORT), timeout=0.25):
            raise RuntimeError(
                f"local flood tunnel port {LOCAL_PORT} is already open; "
                "refusing to reuse an unowned/stale forward"
            )
    except ConnectionRefusedError:
        pass
    except OSError:
        # No listener is the expected clean baseline.
        pass

    argv = ssh_base(TUNNEL_KEY, ULC01)[:-1] + [
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=2",
        "-N", "-L", f"{LOCAL_HOST}:{LOCAL_PORT}:127.0.0.1:1885", ULC01,
    ]
    proc = subprocess.Popen(argv, cwd=ROOT, text=True, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    deadline = time.monotonic() + 12.0
    while time.monotonic() < deadline:
        rc = proc.poll()
        if rc is not None:
            detail = proc.stderr.read().strip() if proc.stderr else ""
            raise RuntimeError(
                f"research flood tunnel exited during startup rc={rc}: {detail}"
            )
        try:
            with socket.create_connection((LOCAL_HOST, LOCAL_PORT), timeout=0.5):
                return proc
        except OSError:
            time.sleep(0.2)

    proc.terminate()
    try:
        proc.wait(3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(3)
    detail = proc.stderr.read().strip() if proc.stderr else ""
    raise RuntimeError(f"research flood tunnel did not become ready: {detail}")


def stop_tunnel(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)
    wait_port(False, timeout=5.0)


def parse_pipe_metrics(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "|" in line:
            key, value = line.split("|", 1)
            out[key.strip()] = value.strip()
    return out


def flood_counter() -> dict[str, int]:
    text = action(ULC03, "flood-summary")
    latest: dict[str, int] = {"received": 0, "rejected": 0, "accepted": 0}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if all(k in obj for k in latest):
            latest = {k: int(obj[k]) for k in latest}
    return latest


def publish_lines(lines: str) -> str:
    cp = run([sys.executable, str(MQTT_PUBLISH), "--host", LOCAL_HOST, "--port", str(LOCAL_PORT),
              "--user", TEST_USER, "--password", TEST_PASSWORD, "--topic", "test/flood/invalid"],
             input_text=lines, timeout=30)
    return (cp.stdout + cp.stderr).strip()


def flush_f2() -> dict[str, int]:
    publish_lines('{"__research_flush":true}\n')
    time.sleep(0.5)
    return flood_counter()


def run_f1(rate: int, seconds: int) -> dict[str, object]:
    if rate == 0:
        time.sleep(seconds)
        return {"planned": 0, "launched": 0, "accepted": 0, "rejected": 0,
                "target_observed": 0, "local_errors": 0,
                "generator_achieved_rate_per_second": 0.0,
                "target_observed_rate_per_second": 0.0,
                "raw": "normal 0/s"}
    cp = run([sys.executable, str(CONN_FLOOD), "--host", LOCAL_HOST, "--port", str(LOCAL_PORT),
              "--rate", str(rate), "--seconds", str(seconds), "--user", TEST_USER,
              "--password", WRONG_PASSWORD], timeout=max(45.0, seconds + 30.0))
    metrics: dict[str, int] = {}
    for line in cp.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                metrics[k] = int(v)
            except ValueError:
                pass
    planned = int(metrics.get("planned_attempts", rate * seconds))
    launched = int(metrics.get("launched_attempts", 0))
    accepted = int(metrics.get("result_accepted", 0))
    broker_rejected = sum(v for k, v in metrics.items() if k.startswith("result_connack_"))
    local_errors = sum(v for k, v in metrics.items() if k.startswith("result_error_"))
    target_observed = accepted + broker_rejected
    return {"planned": planned, "launched": launched, "accepted": accepted,
            "rejected": broker_rejected, "target_observed": target_observed,
            "local_errors": local_errors,
            "generator_achieved_rate_per_second": launched / seconds if seconds else 0.0,
            "target_observed_rate_per_second": target_observed / seconds if seconds else 0.0,
            "raw": cp.stdout.strip()}


def run_f2(rate: int, seconds: int) -> dict[str, object]:
    before = flush_f2()
    if rate == 0:
        time.sleep(seconds)
        generated = 0
        published = 0
        raw = "normal 0/s"
    else:
        gen = subprocess.Popen([sys.executable, str(MSG_FLOOD), "--rate", str(rate), "--seconds", str(seconds)],
                               cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if gen.stdout is None:
            gen.kill()
            raise RuntimeError("could not open invalid-message generator stdout")
        pub = subprocess.run([sys.executable, str(MQTT_PUBLISH), "--host", LOCAL_HOST,
                              "--port", str(LOCAL_PORT), "--user", TEST_USER,
                              "--password", TEST_PASSWORD, "--topic", "test/flood/invalid"],
                             cwd=ROOT, stdin=gen.stdout, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=max(45.0, seconds + 30.0))
        gen.stdout.close()
        gen_err = gen.stderr.read() if gen.stderr else ""
        gen_rc = gen.wait(10)
        if gen_rc != 0 or pub.returncode != 0:
            raise RuntimeError(f"F2 generator/publisher failed gen={gen_rc} pub={pub.returncode}: {gen_err} {pub.stderr}")
        gm = re.search(r"generated_messages=(\d+)", gen_err)
        pm = re.search(r"published_messages=(\d+)", pub.stderr)
        generated = int(gm.group(1)) if gm else -1
        published = int(pm.group(1)) if pm else -1
        raw = (gen_err + "\n" + pub.stderr).strip()
    after = flush_f2()
    delta = {k: after[k] - before[k] for k in before}
    return {"planned": rate * seconds, "generated": generated, "published": published,
            "received": delta["received"], "rejected": delta["rejected"],
            "accepted": delta["accepted"],
            "generator_achieved_rate_per_second": published / seconds if seconds and published >= 0 else None,
            "target_observed_rate_per_second": delta["received"] / seconds if seconds else 0.0,
            "raw": raw}


def recorder_start(run_id: str, test_id: str, rate: int, formal: bool) -> Path:
    condition = f"{test_id} {'normal' if rate == 0 else ('moderate' if rate == 10 else 'high')} flooding at {rate}/s"
    expected = "invalid traffic rejected; legitimate EMU-01 traffic continues; no unauthorized DB/Fabric record"
    argv = [sys.executable, str(RECORDER), "start", "--group", "dos-flooding", "--run-id", run_id,
            "--condition", condition, "--expected", expected, "--scope", "full", "--interval", "5"]
    if not formal:
        # Commissioning still uses the real sensor when available; never label it counted research.
        pass
    run(argv, timeout=180)
    state = json.loads((ROOT / "chapter4-results" / "_recorder-active.json").read_text(encoding="utf-8"))
    return Path(state["run_dir"])


def recorder_mark(message: str) -> None:
    run([sys.executable, str(RECORDER), "mark", "--message", message], timeout=45)


def recorder_stop() -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(RECORDER), "stop"], timeout=240, check=False)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_session(path: Path, value: dict[str, object]) -> None:
    """Publish an atomic checkpoint after each real window, before teardown."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".tmp")
    staged.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(staged, path)


def validate_run(test_id: str, rate: int, seconds: int, load: dict[str, object],
                 window: dict[str, str], guard: dict[str, str], formal: bool) -> list[str]:
    errors: list[str] = []
    target = rate * seconds
    if test_id == "F1":
        if int(load.get("launched", -1)) != target:
            errors.append(f"F1 launched={load.get('launched')} target={target}")
        if int(load.get("accepted", -1)) != 0:
            errors.append(f"F1 accepted invalid connections={load.get('accepted')}")
        if int(load.get("rejected", -1)) != target:
            errors.append(f"F1 rejected={load.get('rejected')} target={target}")
        if int(load.get("target_observed", -1)) != target:
            errors.append(f"F1 broker-observed CONNACK responses={load.get('target_observed')} target={target}")
        if int(load.get("local_errors", -1)) != 0:
            errors.append(f"F1 local/unobserved connection errors={load.get('local_errors')}")
    else:
        for key in ("generated", "published", "received", "rejected"):
            if int(load.get(key, -1)) != target:
                errors.append(f"F2 {key}={load.get(key)} target={target}")
        if int(load.get("accepted", -1)) != 0:
            errors.append(f"F2 accepted malformed messages={load.get('accepted')}")
    if int(window.get("UNAUTHORIZED_UPLINKS", "-1")) != 0:
        errors.append(f"unauthorized uplinks={window.get('UNAUTHORIZED_UPLINKS')}")
    if int(window.get("UNAUTHORIZED_OUTBOX", "-1")) != 0:
        errors.append(f"unauthorized outbox={window.get('UNAUTHORIZED_OUTBOX')}")
    if int(guard.get("FAKE_UPLINKS_TOTAL", "-1")) != 0:
        errors.append(f"global fake uplinks={guard.get('FAKE_UPLINKS_TOTAL')}")
    if int(guard.get("FAKE_OUTBOX_TOTAL", "-1")) != 0:
        errors.append(f"global fake outbox={guard.get('FAKE_OUTBOX_TOTAL')}")
    if int(guard.get("EMU_LAST_2M", "0")) <= 0:
        errors.append("no recent legitimate EMU-01 telemetry")
    if (formal or seconds >= 20) and int(window.get("VALID_DELIVERED", "0")) <= 0:
        errors.append("no legitimate EMU-01 delivery during flood window")
    return errors


def one_run(test_id: str, rate: int, repetition: int, seconds: int, recovery: int,
            formal: bool, stamp: str) -> dict[str, object]:
    mode = "formal" if formal else "rehearsal"
    run_id = f"{test_id}-{mode}-r{rate}-n{repetition}-{stamp}"
    run_dir = recorder_start(run_id, test_id, rate, formal)
    raw_dir = run_dir / "raw"
    clock_offset_seconds = measurement_clock_offset_seconds(run_dir)
    result: dict[str, object] = {"run_id": run_id, "rate_per_second": rate,
                                 "repetition": repetition, "formal": formal,
                                 "measurement_clock_server_minus_workstation_seconds": clock_offset_seconds}
    stop_cp: subprocess.CompletedProcess[str] | None = None
    try:
        recorder_mark(f"FLOOD_START test={test_id} rate={rate}")
        start = calibrated_utc_now(clock_offset_seconds)
        load = run_f1(rate, seconds) if test_id == "F1" else run_f2(rate, seconds)
        if test_id == "F1":
            generator_count = int(load.get("launched", 0))
        else:
            load["target_observed"] = int(load.get("received", 0))
            generator_count = int(load.get("generated", 0))
        load["planned_rate_per_second"] = rate
        load["generator_achieved_rate_per_second"] = generator_count / seconds if seconds else 0.0
        load["target_observed_rate_per_second"] = int(load.get("target_observed", 0)) / seconds if seconds else 0.0
        end = calibrated_utc_now(clock_offset_seconds)
        recorder_mark(f"FLOOD_STOP test={test_id} rate={rate}")
        time.sleep(recovery)
        recorder_mark(f"RECOVERY_END test={test_id} rate={rate}")
        window = parse_pipe_metrics(action(ULC01, f"flood-window {start} {end}"))
        guard = parse_pipe_metrics(action(ULC01, "flood-db-guard"))
        result.update({"flood_start_utc": start, "flood_end_utc": end,
                       "duration_seconds": seconds, "recovery_seconds": recovery,
                       "load": load, "window": window, "db_guard": guard})
        write_json(raw_dir / "flood-harness-observation.json", result)
    finally:
        stop_cp = recorder_stop()
    result["recorder_returncode"] = stop_cp.returncode if stop_cp else -1
    result["recorder_tail"] = "\n".join(((stop_cp.stdout or "") + (stop_cp.stderr or "")).splitlines()[-12:]) if stop_cp else ""
    errors = validate_run(test_id, rate, seconds, result.get("load", {}),
                          result.get("window", {}), result.get("db_guard", {}), formal)
    if stop_cp is None or stop_cp.returncode != 0:
        errors.append(f"recorder finalization returncode={-1 if stop_cp is None else stop_cp.returncode}")
    result["status"] = "PASS" if not errors else "FAIL"
    result["errors"] = errors
    write_json(run_dir / "derived" / "flood-harness-result.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("test", choices=("F1", "F2"))
    ap.add_argument("--rehearsal-seconds", type=int, default=0,
                    help="non-counted commissioning window; 0 selects formal 300-second windows")
    ap.add_argument("--rehearsal-recovery-seconds", type=int, default=0,
                    help="non-counted recovery window; defaults to rehearsal-seconds")
    args = ap.parse_args()
    require_files()
    if args.rehearsal_seconds < 0 or args.rehearsal_recovery_seconds < 0:
        raise RuntimeError("rehearsal durations must be non-negative")
    formal = args.rehearsal_seconds == 0
    seconds = 300 if formal else args.rehearsal_seconds
    recovery = 300 if formal else (args.rehearsal_recovery_seconds or args.rehearsal_seconds)
    if not formal and seconds < 1:
        raise RuntimeError("rehearsal-seconds must be >=1")
    repetitions = 3 if formal else 1
    RC.validate_static_contract()
    RC.validate_flood_profile(args.test, (0, 10, 50), seconds, repetitions, recovery, formal)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tunnel: subprocess.Popen[str] | None = None
    branch_installed = False
    listener_started = False
    results: list[dict[str, object]] = []
    cleanup_errors: list[str] = []
    out = ROOT / "chapter4-results" / "dos-flooding" / "_sessions" / f"{args.test}-{stamp}.json"
    session: dict[str, object] = {
        "test": args.test, "formal": formal, "phase_seconds": seconds,
        "recovery_seconds": recovery, "expected_runs": 3 * repetitions,
        "results": results, "cleanup_errors": cleanup_errors,
        "status": "RUNNING", "operator_exit_code": None,
    }
    save_session(out, session)
    failure: Exception | KeyboardInterrupt | None = None
    try:
        print(action(ULC01, "version"))
        print(action(ULC03, "version"))
        # The listener/branch are ephemeral research fixtures. Always normalize
        # them to an inactive baseline first so an interrupted prior rehearsal
        # cannot make the next one fail before evidence capture begins.
        try:
            print(action(ULC03, "flood-branch-remove"))
        except Exception as exc:
            print(f"FIXTURE_BASELINE_NOTICE=branch-remove:{exc}", file=sys.stderr)
        try:
            print(action(ULC01, "flood-listener-stop"))
        except Exception as exc:
            print(f"FIXTURE_BASELINE_NOTICE=listener-stop:{exc}", file=sys.stderr)
        print(action(ULC01, "flood-listener-start"))
        listener_started = True
        print(action(ULC01, "flood-listener-smoke"))
        if args.test == "F2":
            print(action(ULC03, "flood-branch-install"))
            branch_installed = True
        tunnel = start_tunnel()
        for rate in (0, 10, 50):
            for rep in range(1, repetitions + 1):
                print(f"RUN_BEGIN test={args.test} rate={rate} repetition={rep} formal={formal}", flush=True)
                result = one_run(args.test, rate, rep, seconds, recovery, formal, stamp)
                results.append(result)
                # Persist each completed run before beginning another window.
                save_session(out, session)
                print(f"RUN_END run_id={result['run_id']} status={result['status']}", flush=True)
                if result["status"] != "PASS":
                    raise RuntimeError("flood run failed: " + "; ".join(result["errors"]))
        session["status"] = "FINALIZING"
        save_session(out, session)
    except (Exception, KeyboardInterrupt) as exc:
        failure = exc
        session["failure"] = f"{type(exc).__name__}: {exc}"
        session["status"] = "INCOMPLETE"
        save_session(out, session)
    finally:
        try:
            stop_tunnel(tunnel)
        except Exception as exc:
            cleanup_errors.append(f"tunnel: {exc}")
        if branch_installed:
            try:
                print(action(ULC03, "flood-branch-remove"))
            except Exception as exc:
                cleanup_errors.append(f"branch: {exc}")
        if listener_started:
            try:
                print(action(ULC01, "flood-listener-stop"))
            except Exception as exc:
                cleanup_errors.append(f"listener: {exc}")
        complete = failure is None and not cleanup_errors and len(results) == 3 * repetitions and all(
            r.get("status") == "PASS" for r in results
        )
        session["status"] = "COMPLETE" if complete else "INCOMPLETE"
        session["operator_exit_code"] = 0 if complete else 130 if isinstance(failure, KeyboardInterrupt) else 2
        save_session(out, session)
    if cleanup_errors:
        print("CLEANUP_ERRORS=" + "; ".join(cleanup_errors), file=sys.stderr)
    if failure is not None:
        if isinstance(failure, KeyboardInterrupt):
            print("FLOOD_HARNESS=INTERRUPTED SESSION_INCOMPLETE", file=sys.stderr)
            return 130
        raise failure
    if session["status"] != "COMPLETE":
        print(f"FLOOD_HARNESS=INCOMPLETE SESSION_RESULT={out}", file=sys.stderr)
        return 2
    print(f"FLOOD_HARNESS=PASS test={args.test} formal={formal} runs={len(results)}")
    print(f"SESSION_RESULT={out}")
    return 0


if __name__ == "__main__":
    # A cooperative SIGTERM can finalize the checkpoint and tear down fixtures.
    # A force-kill cannot run Python cleanup, but prior windows stay checkpointed.
    def _on_sigterm(_signum, _frame):
        raise KeyboardInterrupt("operator process terminated")

    signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
