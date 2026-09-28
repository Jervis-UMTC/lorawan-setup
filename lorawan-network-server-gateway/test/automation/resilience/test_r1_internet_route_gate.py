#!/usr/bin/env python3
"""Hardware-free R1 LTE management-route and outage proof parser tests."""
from __future__ import annotations
import importlib.util
import hashlib
import io
import json
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

TARGET=Path(__file__).with_name("r1_internet_route_gate.py")
spec=importlib.util.spec_from_file_location("r1_internet_route_gate",TARGET)
assert spec and spec.loader
r1=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r1)

LTE="100.70.105.133"
CLOUD="129.212.208.168"

def snapshot(*, phase="pre", default="default via 100.70.105.134 dev wwan0 src 100.70.105.133 metric 10",
             cloud_route=None, probe=None, mqtt=None, lte_ip=LTE, lan=True):
    lte={"up":True,"l3_device":"wwan0","ipv4-address":[{"address":lte_ip}]}
    routes=default+"\n"+("192.168.20.0/24 dev br-lan proto kernel scope link src 192.168.20.11\n" if lan else "")
    cr=cloud_route if cloud_route is not None else f"{CLOUD} via 100.70.105.134 dev wwan0 src {LTE}"
    check=probe if probe is not None else ("tcp_8883=UNREACHABLE" if phase=="outage" else "tcp_8883=REACHABLE")
    sockets=mqtt if mqtt is not None else f"tcp 0 0 {lte_ip}:39030 {CLOUD}:8883 ESTABLISHED"
    return "\n".join([f"--- lte ---\n{json.dumps(lte)}","--- routes ---\n"+routes,
         "--- cloud-route ---\n"+cr,"--- cloud-probe ---\n"+check,
         "--- mqtt-sockets ---\n"+sockets, "--- end ---\n"])

class R1OfflineTests(unittest.TestCase):
    def test_pre_and_recovery_require_lte_socket_and_probe(self):
        for phase in ("pre","recovery"):
            with self.subTest(phase=phase):
                self.assertEqual(r1.parse_snapshot(snapshot(phase=phase),phase)["status"],"PASS")

    def test_outage_requires_cloud_unreachable_while_lan_preserved(self):
        result=r1.parse_snapshot(snapshot(phase="outage",mqtt=""),"outage")
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["cloud_probe"],"tcp_8883=UNREACHABLE")

    def test_ethernet_default_route_fails(self):
        result=r1.parse_snapshot(snapshot(default="default via 192.168.20.1 dev eth0"),"pre")
        self.assertTrue(any("default route is not wwan0" in e for e in result["errors"]))

    def test_multiple_defaults_fail(self):
        result=r1.parse_snapshot(snapshot(default=("default via 100.70.105.134 dev wwan0\n"
                 "default via 192.168.20.1 dev eth0")),"pre")
        self.assertTrue(any("default route count=2" in e for e in result["errors"]))

    def test_management_lan_absence_fails(self):
        self.assertTrue(any("management LAN route" in e for e in
            r1.parse_snapshot(snapshot(lan=False),"pre")["errors"]))

    def test_stale_or_absent_cloud_tcp_probe_fails(self):
        self.assertTrue(any("TCP probe" in e for e in
            r1.parse_snapshot(snapshot(probe=""),"pre")["errors"]))
        self.assertTrue(any("prove outage" in e for e in
            r1.parse_snapshot(snapshot(phase="outage",probe="tcp_8883=REACHABLE"),"outage")["errors"]))

    def test_cloud_route_must_use_wwan(self):
        self.assertTrue(any("cloud route is not wwan0" in e for e in
            r1.parse_snapshot(snapshot(cloud_route=f"{CLOUD} via 192.168.20.1 dev eth0"),"pre")["errors"]))

    def test_mqtt_peer_port_not_just_local_port(self):
        bad=f"tcp 0 0 {LTE}:8883 {CLOUD}:45678 ESTABLISHED"
        self.assertTrue(any("no established gateway MQTT" in e for e in
            r1.parse_snapshot(snapshot(mqtt=bad),"pre")["errors"]))

    def test_mqtt_socket_exact_lte_source(self):
        bad=f"tcp 0 0 10.70.105.133:39030 {CLOUD}:8883 ESTABLISHED"
        self.assertTrue(any("not sourced from LTE IPv4" in e for e in
            r1.parse_snapshot(snapshot(mqtt=bad),"pre")["errors"]))

    def test_invalid_lte_ipv4_fails(self):
        self.assertTrue(any("IPv4 address invalid" in e for e in
            r1.parse_snapshot(snapshot(lte_ip="not-an-ip"),"pre")["errors"]))

    def test_unstructured_lte_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"LTE snapshot"):
            r1.parse_snapshot("--- lte ---\nnot JSON","pre")

    def test_cloud_route_must_use_real_lte_source(self):
        bad=f"{CLOUD} via 100.70.105.134 dev wwan0 src 192.168.20.11"
        result=r1.parse_snapshot(snapshot(cloud_route=bad),"pre")
        self.assertTrue(any("cloud route source" in err for err in result["errors"]))

    def test_cloud_route_must_match_actual_mqtt_peer(self):
        bad=f"8.8.8.8 via 100.70.105.134 dev wwan0 src {LTE}"
        result=r1.parse_snapshot(snapshot(cloud_route=bad),"pre")
        self.assertTrue(any("cloud route target" in err for err in result["errors"]))

    def test_malformed_gateway_snapshot_is_sealed_as_failure(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(r1.RR,"run_remote",return_value=types.SimpleNamespace(stdout="--- lte ---\\nmalformed")),
            patch("sys.argv",["r1_internet_route_gate.py","--phase","pre","--output-dir",td]),
            redirect_stdout(io.StringIO())
        ):
            code=r1.main()
            proofs=list(Path(td).glob("r1-route-proof-pre-*.json"))
            self.assertEqual(code,2)
            self.assertEqual(len(proofs),1)
            proof=json.loads(proofs[0].read_text(encoding="utf-8"))
            self.assertEqual(proof["status"],"FAIL")
            self.assertTrue(proof["errors"])
            digest=hashlib.sha256(proofs[0].read_bytes()).hexdigest()
            self.assertEqual(proofs[0].with_suffix(".json.sha256").read_text().strip(),digest)
            self.assertEqual(len(list(Path(td).glob("gateway-snapshot-pre-*.txt"))),1)


if __name__=="__main__":
    unittest.main()
