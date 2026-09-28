#!/usr/bin/env python3
"""Controlled MQTT connection-attempt generator for Chapter IV F1.

Use only against the temporary isolated flooding-test MQTT listener documented in
Execution 07. This implementation is dependency-free and no longer requires
mosquitto_pub on the operator workstation.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import time
from collections import Counter

from mqtt_wire import MQTTClient


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", required=True, type=int)
    ap.add_argument("--rate", required=True, type=float)
    ap.add_argument("--seconds", required=True, type=float)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--timeout", type=float, default=2.0)
    return ap.parse_args()


def one_attempt(args, seq: int) -> str:
    client = MQTTClient(
        args.host,
        args.port,
        username=args.user,
        password=args.password,
        client_id=f"f1-{seq}-{time.monotonic_ns() & 0xfffffff:x}",
        timeout=args.timeout,
    )
    try:
        ack = client.connect()
        if ack.return_code != 0:
            return f"connack_{ack.return_code}"
        client.publish("test/flood/connection-probe", f"connection-flood-{seq}")
        return "accepted"
    except Exception as exc:
        return f"error_{type(exc).__name__}"
    finally:
        client.close()


def main():
    args = parse_args()
    if args.rate <= 0 or args.seconds <= 0 or args.timeout <= 0:
        raise SystemExit("rate, seconds and timeout must be positive")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")

    interval = 1.0 / args.rate
    target = max(1, int(round(args.rate * args.seconds)))
    started_at = time.monotonic()
    phase_end = started_at + args.seconds
    futures: list[concurrent.futures.Future[str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        for seq in range(target):
            due_at = started_at + (seq * interval)
            now = time.monotonic()
            if now < due_at:
                time.sleep(due_at - now)
            futures.append(pool.submit(one_attempt, args, seq))
        remaining = phase_end - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        counts = Counter(f.result() for f in futures)

    print(f"planned_attempts={target}")
    print(f"launched_attempts={target}")
    for key in sorted(counts):
        print(f"result_{key}={counts[key]}")


if __name__ == "__main__":
    main()
