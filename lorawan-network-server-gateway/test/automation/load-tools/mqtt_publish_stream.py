#!/usr/bin/env python3
"""Publish newline-delimited research fixtures to an isolated MQTT listener.

Reads UTF-8 lines from stdin and publishes each as QoS-0 using the repository's
stdlib-only MQTT client. Intended for F2 together with invalid_message_stream.py.
"""
from __future__ import annotations

import argparse
import sys

from mqtt_wire import MQTTClient, MQTTError


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", required=True, type=int)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--topic", default="test/flood/invalid")
    ap.add_argument("--timeout", type=float, default=3.0)
    return ap.parse_args()


def main():
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")
    sent = 0
    client = MQTTClient(args.host, args.port, username=args.user, password=args.password,
                        client_id="f2-invalid-stream", timeout=args.timeout)
    try:
        ack = client.connect()
        if ack.return_code != 0:
            raise MQTTError(f"broker rejected CONNECT with CONNACK code {ack.return_code}")
        for raw in sys.stdin:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            client.publish(args.topic, line)
            sent += 1
    finally:
        client.close()
    print(f"published_messages={sent}", file=sys.stderr)


if __name__ == "__main__":
    main()
