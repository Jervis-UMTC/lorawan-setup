#!/usr/bin/env python3
"""Generate deterministic malformed/invalid telemetry JSON at a fixed rate.

Pipe this only into the temporary isolated flooding-test MQTT listener described in
Execution 07. The script itself performs no network I/O.
"""

import argparse
import json
import sys
import time


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", required=True, type=float)
    ap.add_argument("--seconds", required=True, type=float)
    return ap.parse_args()


def main():
    args = parse_args()
    if args.rate <= 0 or args.seconds <= 0:
        raise SystemExit("rate and seconds must be positive")

    fixtures = [
        {"missing": "device identity"},
        {"dev_eui": "not-a-valid-eui", "value": 35},
        {"dev_eui": "0000000000000001", "time": "not-a-time", "value": 35},
        {
            "dev_eui": "0000000000000001",
            "time": "2000-01-01T00:00:00Z",
            "value": "wrong-type",
        },
    ]

    interval = 1.0 / args.rate
    target = max(1, int(round(args.rate * args.seconds)))
    started_at = time.monotonic()
    phase_end = started_at + args.seconds

    for sent in range(target):
        due_at = started_at + (sent * interval)
        now = time.monotonic()
        if now < due_at:
            time.sleep(due_at - now)
        fixture = dict(fixtures[sent % len(fixtures)])
        fixture["test_sequence"] = sent
        print(json.dumps(fixture, separators=(",", ":")), flush=True)

    remaining = phase_end - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)
    print(f"planned_messages={target}", file=sys.stderr)
    print(f"generated_messages={target}", file=sys.stderr)


if __name__ == "__main__":
    main()
