#!/usr/bin/env python3
"""Tiny dependency-free MQTT 3.1.1 client used only by research load tools.

Supports TCP CONNECT, QoS-0 PUBLISH and DISCONNECT. It intentionally avoids
third-party/operator-host MQTT packages so a clean research workstation can run
F1/F2 after repository checkout and Python installation alone.
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass


class MQTTError(RuntimeError):
    pass


def _utf8(value: str) -> bytes:
    data = value.encode("utf-8")
    if len(data) > 65535:
        raise MQTTError("MQTT UTF-8 field is too long")
    return struct.pack("!H", len(data)) + data


def _remaining_length(n: int) -> bytes:
    if n < 0 or n > 268435455:
        raise MQTTError("invalid MQTT remaining length")
    out = bytearray()
    while True:
        digit = n % 128
        n //= 128
        if n:
            digit |= 0x80
        out.append(digit)
        if not n:
            return bytes(out)


def connect_packet(client_id: str, username: str | None, password: str | None, keepalive: int = 15) -> bytes:
    flags = 0x02
    payload = _utf8(client_id)
    if username is not None:
        flags |= 0x80
        payload += _utf8(username)
    if password is not None:
        if username is None:
            raise MQTTError("password requires username")
        flags |= 0x40
        payload += _utf8(password)
    variable = _utf8("MQTT") + bytes((4, flags)) + struct.pack("!H", keepalive)
    body = variable + payload
    return bytes((0x10,)) + _remaining_length(len(body)) + body


def publish_packet(topic: str, payload: bytes | str) -> bytes:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    body = _utf8(topic) + data
    return bytes((0x30,)) + _remaining_length(len(body)) + body


@dataclass(frozen=True)
class Connack:
    session_present: bool
    return_code: int


class MQTTClient:
    def __init__(self, host: str, port: int, *, username: str | None = None, password: str | None = None,
                 client_id: str = "research-tool", timeout: float = 3.0):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def connect(self) -> Connack:
        if self.sock is not None:
            raise MQTTError("client is already connected")
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        try:
            sock.sendall(connect_packet(self.client_id, self.username, self.password))
            reply = _recv_exact(sock, 4)
            if reply[0] != 0x20 or reply[1] != 0x02:
                raise MQTTError(f"unexpected CONNACK framing: {reply.hex()}")
            connack = Connack(bool(reply[2] & 0x01), reply[3])
            if connack.return_code != 0:
                sock.close()
                return connack
            self.sock = sock
            return connack
        except Exception:
            try:
                sock.close()
            except OSError:
                pass
            raise

    def publish(self, topic: str, payload: bytes | str) -> None:
        if self.sock is None:
            raise MQTTError("client is not connected")
        self.sock.sendall(publish_packet(topic, payload))

    def close(self) -> None:
        sock, self.sock = self.sock, None
        if sock is None:
            return
        try:
            sock.sendall(b"\xe0\x00")
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def __enter__(self) -> "MQTTClient":
        connack = self.connect()
        if connack.return_code:
            raise MQTTError(f"broker rejected CONNECT with CONNACK code {connack.return_code}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise MQTTError("broker closed connection before complete response")
        out.extend(chunk)
    return bytes(out)
