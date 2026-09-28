#!/usr/bin/env python3
"""R1 external-Internet interruption safety/readiness gate.

This helper does not induce the outage. It proves the gateway's application WAN
is LTE-only before a counted R1 run and emits a sealed route proof. The actual
outage harness must preserve the LAN management route and local LoRa capture.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
RECORDER=ROOT/"test"/"automation"/"research-recorder"/"research_recorder.py"
CONTRACT=ROOT/"test"/"automation"/"research_contract.py"
RESULTS=ROOT/"chapter4-results"/"_preflight"/"r1-route"

def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"cannot import {path}")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

RR=load(RECORDER,"research_recorder")
RC=load(CONTRACT,"research_contract")
RC.validate_static_contract()

def section(text:str,name:str)->str:
    marker=f"--- {name} ---"
    if marker not in text: return ""
    tail=text.split(marker,1)[1]
    return tail.split("--- ",1)[0].strip()

def parse_snapshot(text:str, phase:str)->dict:
    errs=[]
    lte_text=section(text,"lte")
    try: lte=json.loads(lte_text)
    except Exception as exc:
        raise RuntimeError(f"gateway LTE snapshot is not valid JSON: {exc}") from exc

    routes=section(text,"routes").splitlines()
    default_routes=[x.strip() for x in routes if x.strip().startswith("default ")]
    lan_routes=[x.strip() for x in routes if x.strip().startswith("192.168.20.0/24 ")]
    cloud=section(text,"cloud-route")
    probe=section(text,"cloud-probe").strip()
    sockets=section(text,"mqtt-sockets").splitlines()

    l3=str(lte.get("l3_device") or "")
    addr=""
    for item in lte.get("ipv4-address") or []:
        if isinstance(item,dict) and item.get("address"):
            addr=str(item["address"]); break

    if lte.get("up") is not True: errs.append("LTE interface is not up")
    if l3!="wwan0": errs.append(f"LTE l3_device={l3!r}, expected wwan0")
    if not addr: errs.append("LTE IPv4 address missing")
    else:
        try: ipaddress.IPv4Address(addr)
        except ValueError: errs.append(f"LTE IPv4 address invalid:{addr!r}")
    if len(default_routes)!=1: errs.append(f"default route count={len(default_routes)}, expected exactly 1")
    elif " dev wwan0 " not in f" {default_routes[0]} ": errs.append(f"default route is not wwan0: {default_routes[0]}")
    if not lan_routes or not any(" dev br-lan " in f" {x} " for x in lan_routes):
        errs.append("management LAN route 192.168.20.0/24 via br-lan missing")
    if " dev wwan0 " not in f" {cloud} ": errs.append(f"cloud route is not wwan0: {cloud!r}")
    if addr and f" src {addr} " not in f" {cloud} ":
        errs.append("cloud route source is not the LTE IPv4 address")
    established=[]
    for line in sockets:
        parts=line.split()
        # OpenWrt netstat: proto, recvq, sendq, local, peer, state.
        # Require cloud peer :8883; a local :8883 port proves nothing.
        if len(parts)>=6 and parts[-1]=="ESTABLISHED" and parts[4].endswith(":8883"):
            established.append(line)
    if phase in {"pre","recovery"}:
        if probe != "tcp_8883=REACHABLE": errs.append(f"cloud TCP probe not reachable in {phase}: {probe or 'missing'}")
        if not established: errs.append("no established gateway MQTT :8883 socket")
        if addr and established and not any(x.split()[3].rsplit(":",1)[0]==addr for x in established):
            errs.append("established MQTT socket is not sourced from LTE IPv4")
        routed_dest = cloud.split()[0] if cloud.split() else ""
        if established and not any(
            x.split()[4].rsplit(":", 1)[0] == routed_dest for x in established
        ):
            errs.append("cloud route target does not match an established MQTT peer")
    elif phase == "outage":
        if probe != "tcp_8883=UNREACHABLE": errs.append(f"cloud TCP probe did not prove outage: {probe or 'missing'}")
    else:
        errs.append(f"unsupported R1 phase {phase}")

    alternate_defaults=[x for x in default_routes if " dev wwan0 " not in f" {x} "]
    result={
        "lte_up":lte.get("up") is True,
        "lte_l3_device":l3,
        "lte_ipv4":addr,
        "default_routes":default_routes,
        "alternate_default_routes":alternate_defaults,
        "management_lan_routes":lan_routes,
        "cloud_route":cloud,
        "cloud_probe":probe,
        "phase":phase,
        "established_mqtt_8883_sockets":established,
        "status":"PASS" if not errs else "FAIL",
        "errors":errs,
    }
    return result

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir",default=str(RESULTS))
    ap.add_argument("--phase",choices=("pre","outage","recovery"),default="pre")
    args=ap.parse_args()
    cp=RR.run_remote("gateway","snapshot",check=True)
    raw=cp.stdout or ""
    try:
        parsed=parse_snapshot(raw,args.phase)
    except Exception as exc:
        # Preserve a failed or malformed gateway snapshot for diagnosis;
        # otherwise a failed R1 gate can exit without any retained evidence.
        parsed={"phase":args.phase,"status":"FAIL","errors":[str(exc)]}
    now=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    outdir=Path(args.output_dir); outdir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    raw_path=outdir/f"gateway-snapshot-{args.phase}-{stamp}.txt"
    json_path=outdir/f"r1-route-proof-{args.phase}-{stamp}.json"
    raw_path.write_text(raw,encoding="utf-8")
    proof={
        "schema_version":"1.0",
        "test_id":"R1",
        "generated_utc":now,
        "contract":{"lte_route_required":True,"alternate_wan_forbidden":True},
        "snapshot_sha256":hashlib.sha256(raw.encode()).hexdigest(),
        **parsed,
    }
    json_path.write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    sha=hashlib.sha256(json_path.read_bytes()).hexdigest()
    json_path.with_suffix(json_path.suffix+".sha256").write_text(sha+"\n",encoding="ascii")
    print(f"R1_ROUTE_GATE={parsed['status']} phase={args.phase}")
    print(f"R1_ROUTE_PROOF={json_path}")
    print(f"LTE_DEVICE={parsed.get('lte_l3_device','')} LTE_IPV4={parsed.get('lte_ipv4','')}")
    if parsed["errors"]:
        for e in parsed["errors"]: print("ERROR="+e)
        return 2
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR={exc}")
        raise SystemExit(1)
