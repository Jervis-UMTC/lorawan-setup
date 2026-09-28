#!/usr/bin/env python3
"""Offline regression tests for repository-contained MQTT research tooling."""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from mqtt_wire import MQTTClient, connect_packet, publish_packet


def read_packet(conn: socket.socket):
    first = conn.recv(1)
    if not first:
        return None, b""
    mult = 1
    remaining = 0
    while True:
        raw = conn.recv(1)
        if not raw:
            raise RuntimeError("short MQTT remaining length")
        value = raw[0]
        remaining += (value & 0x7F) * mult
        if not value & 0x80:
            break
        mult *= 128
    body = bytearray()
    while len(body) < remaining:
        chunk = conn.recv(remaining - len(body))
        if not chunk:
            raise RuntimeError("short MQTT packet body")
        body.extend(chunk)
    return first[0], bytes(body)


class MQTTWireTests(unittest.TestCase):
    def test_packet_headers(self):
        self.assertEqual(connect_packet("x", "u", "p")[0], 0x10)
        self.assertEqual(publish_packet("a/b", "{}")[0], 0x30)

    def test_connect_and_publish_against_mock_broker(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        seen = []

        def broker():
            conn, _ = server.accept()
            with conn:
                packet_type, _ = read_packet(conn)
                seen.append(packet_type)
                conn.sendall(b"\x20\x02\x00\x00")
                packet_type, _ = read_packet(conn)
                seen.append(packet_type)
                read_packet(conn)
            server.close()

        thread = threading.Thread(target=broker)
        thread.start()
        client = MQTTClient("127.0.0.1", port, username="u", password="p", client_id="unit")
        ack = client.connect()
        self.assertEqual(ack.return_code, 0)
        client.publish("proof/topic", "hello")
        client.close()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(seen[:2], [0x10, 0x30])

    def test_connection_flood_tool_against_mock_broker(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(100)
        port = server.getsockname()[1]
        accepted = 0
        lock = threading.Lock()
        stop = threading.Event()

        def handle(conn):
            nonlocal accepted
            with conn:
                packet_type, _ = read_packet(conn)
                if packet_type != 0x10:
                    return
                conn.sendall(b"\x20\x02\x00\x00")
                packet_type, _ = read_packet(conn)
                if packet_type == 0x30:
                    with lock:
                        accepted += 1
                read_packet(conn)

        def accept_loop():
            server.settimeout(0.2)
            while not stop.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=handle, args=(conn,), daemon=True).start()

        thread = threading.Thread(target=accept_loop)
        thread.start()
        cp = subprocess.run(
            [sys.executable, str(HERE / "connection_flood.py"), "--host", "127.0.0.1",
             "--port", str(port), "--rate", "12", "--seconds", "0.5", "--user", "u", "--password", "p"],
            text=True, capture_output=True, timeout=15,
        )
        stop.set()
        thread.join(3)
        server.close()
        time.sleep(0.1)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        launched = int(next(x.split("=", 1)[1] for x in cp.stdout.splitlines() if x.startswith("launched_attempts=")))
        self.assertGreaterEqual(launched, 5)
        self.assertEqual(accepted, launched)

    def test_connection_flood_rejected_connack_is_target_observed(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(100)
        port = server.getsockname()[1]
        observed = 0
        lock = threading.Lock()
        stop = threading.Event()

        def handle(conn):
            nonlocal observed
            with conn:
                packet_type, _ = read_packet(conn)
                if packet_type != 0x10:
                    return
                with lock:
                    observed += 1
                # MQTT 3.1.1 CONNACK return code 5 = not authorized.
                conn.sendall(b"\x20\x02\x00\x05")

        def accept_loop():
            server.settimeout(0.2)
            while not stop.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=handle, args=(conn,), daemon=True).start()

        thread = threading.Thread(target=accept_loop)
        thread.start()
        cp = subprocess.run(
            [sys.executable, str(HERE / "connection_flood.py"), "--host", "127.0.0.1",
             "--port", str(port), "--rate", "12", "--seconds", "0.5",
             "--user", "u", "--password", "wrong"],
            text=True, capture_output=True, timeout=15,
        )
        stop.set()
        thread.join(3)
        server.close()
        time.sleep(0.1)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        metrics = {}
        for line in cp.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                metrics[key] = int(value)
        launched = metrics["launched_attempts"]
        self.assertGreaterEqual(launched, 5)
        self.assertEqual(metrics.get("result_connack_5", 0), launched)
        self.assertFalse(any(k.startswith("result_error_") for k in metrics))
        self.assertEqual(observed, launched)

    def test_publish_stream_against_mock_broker(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        publishes = []

        def broker():
            conn, _ = server.accept()
            with conn:
                packet_type, _ = read_packet(conn)
                self.assertEqual(packet_type, 0x10)
                conn.sendall(b"\x20\x02\x00\x00")
                while True:
                    packet_type, body = read_packet(conn)
                    if packet_type in (None, 0xE0):
                        break
                    if packet_type == 0x30:
                        publishes.append(body)
            server.close()

        thread = threading.Thread(target=broker)
        thread.start()
        cp = subprocess.run(
            [sys.executable, str(HERE / "mqtt_publish_stream.py"), "--host", "127.0.0.1",
             "--port", str(port), "--user", "u", "--password", "p"],
            input='{"x":1}\n{"x":2}\n{"x":3}\n', text=True, capture_output=True, timeout=10,
        )
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(len(publishes), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
