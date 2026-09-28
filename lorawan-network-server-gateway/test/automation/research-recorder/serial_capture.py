#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.tools import list_ports


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_line(fp, label: str, port: str, text: str) -> None:
    safe = text.replace("\r", "").replace("\n", "")
    fp.write(f"{utc_now()}|{label}|{port}|{safe}\n")
    fp.flush()


def find_port(pattern: re.Pattern[str]):
    for p in list_ports.comports():
        haystack = " ".join(str(x or "") for x in (p.device, p.description, p.hwid))
        if pattern.search(haystack):
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-reconnecting USB serial evidence capture")
    ap.add_argument("--label", required=True)
    ap.add_argument("--vidpid-regex", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument(
        "--pause-file",
        default=None,
        help="Optional sentinel path. While it exists, keep the collector alive but release the serial port.",
    )
    args = ap.parse_args()

    pattern = re.compile(args.vidpid_regex, re.IGNORECASE)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pause_file = Path(args.pause_file) if args.pause_file else Path(str(out) + ".pause")
    last_state = None
    paused = False

    with out.open("a", encoding="utf-8", buffering=1) as fp:
        while True:
            if pause_file.exists():
                if not paused:
                    write_line(fp, args.label, "NONE", f"RECORDER_SERIAL_PAUSED,pause_file={pause_file}")
                    paused = True
                time.sleep(0.25)
                continue
            if paused:
                write_line(fp, args.label, "NONE", "RECORDER_SERIAL_RESUMED")
                paused = False
                last_state = None

            info = find_port(pattern)
            if info is None:
                if last_state != "ABSENT":
                    write_line(fp, args.label, "NONE", "RECORDER_DEVICE_ABSENT")
                    last_state = "ABSENT"
                time.sleep(0.75)
                continue

            port = info.device
            if last_state != port:
                write_line(fp, args.label, port, f"RECORDER_DEVICE_PRESENT,hwid={info.hwid}")
                last_state = port

            ser = None
            try:
                ser = serial.Serial(
                    port=port,
                    baudrate=args.baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1.0,
                    write_timeout=1.0,
                    dsrdtr=False,
                    rtscts=False,
                )
                ser.dtr = True
                ser.rts = False
                write_line(fp, args.label, port, "RECORDER_SERIAL_OPEN")
                while ser.is_open:
                    if pause_file.exists():
                        write_line(fp, args.label, port, f"RECORDER_SERIAL_PAUSED,pause_file={pause_file}")
                        paused = True
                        break
                    raw = ser.readline()
                    if not raw:
                        continue
                    write_line(fp, args.label, port, raw.decode("utf-8", errors="replace").rstrip("\r\n"))
            except (serial.SerialException, OSError) as exc:
                write_line(fp, args.label, port, f"RECORDER_SERIAL_ERROR,{str(exc).replace(chr(10), ' ')}")
                time.sleep(0.75)
            finally:
                if ser is not None:
                    try:
                        ser.close()
                    except Exception:
                        pass
                    if paused:
                        write_line(fp, args.label, port, "RECORDER_SERIAL_RELEASED")


if __name__ == "__main__":
    raise SystemExit(main())
