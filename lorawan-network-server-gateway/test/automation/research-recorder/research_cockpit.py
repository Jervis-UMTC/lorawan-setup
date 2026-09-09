#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RESULTS_ROOT = PROJECT_ROOT / "chapter4-results"
ACTIVE_STATE = RESULTS_ROOT / "_recorder-active.json"
SUMMARY_DIR = RESULTS_ROOT / "summaries"
TX_RE = re.compile(r"SENSOR_TX,seq=(\d+).*?send_status=(-?\d+)")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def read_csv(path: Path):
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def num(value):
    try:
        return float(value)
    except Exception:
        return None


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_latest_run() -> Path | None:
    if ACTIVE_STATE.exists():
        state = read_json(ACTIVE_STATE, {})
        p = Path(state.get("run_dir", ""))
        if p.exists():
            return p
    candidates = []
    if RESULTS_ROOT.exists():
        for p in RESULTS_ROOT.glob("*/*"):
            if not p.is_dir() or p.parent.name.startswith("_") or p.parent.name == "summaries":
                continue
            marker = p / "metadata" / "run-meta.json"
            if marker.exists():
                candidates.append((marker.stat().st_mtime, p))
    return max(candidates, default=(0, None), key=lambda x: x[0])[1]


def latest_resource(path: Path):
    rows = read_csv(path)
    if not rows:
        return {"latest": {}, "series": []}
    series = []
    for r in rows[-60:]:
        series.append({
            "t": r.get("timestamp_utc", ""),
            "cpu": num(r.get("cpu_percent")),
            "mem": num(r.get("memory_percent")),
            "load": num(r.get("load1")),
        })
    r = rows[-1]
    return {
        "latest": {
            "timestamp": r.get("timestamp_utc", ""),
            "cpu": num(r.get("cpu_percent")),
            "mem": num(r.get("memory_percent")),
            "load": num(r.get("load1")),
        },
        "series": series,
    }


def source_state(path: Path):
    if not path.exists():
        return {"attempts": 0, "send_ok": 0, "send_fail": 0, "last_seq": None, "last_timestamp": None, "recent": []}
    rows = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = TX_RE.search(line)
            if not m:
                continue
            ts = line.split("|", 1)[0]
            rows.append({"timestamp": ts, "seq": int(m.group(1)), "send_status": int(m.group(2))})
    except Exception:
        pass
    return {
        "attempts": len(rows),
        "send_ok": sum(1 for r in rows if r["send_status"] == 0),
        "send_fail": sum(1 for r in rows if r["send_status"] != 0),
        "last_seq": rows[-1]["seq"] if rows else None,
        "last_timestamp": rows[-1]["timestamp"] if rows else None,
        "recent": rows[-12:],
    }


def health_state(path: Path):
    rows = read_csv(path)
    counts = {}
    for r in rows:
        s = r.get("status", "UNKNOWN") or "UNKNOWN"
        counts[s] = counts.get(s, 0) + 1
    last = rows[-1] if rows else {}
    return {
        "counts": counts,
        "last_status": last.get("status", "NO_DATA") if last else "NO_DATA",
        "last_timestamp": last.get("authoritative_timestamp_utc") or last.get("workstation_midpoint_utc") or "",
        "clock_offset_s": num(last.get("server_minus_workstation_seconds")) if last else None,
        "detail": last.get("detail", "") if last else "",
    }


def study_progress():
    rows = read_csv(SUMMARY_DIR / "test-readiness.csv")
    result = []
    for r in rows:
        required = int(r.get("required") or 0)
        done = int(r.get("countable_completed") or 0)
        result.append({
            "area": r.get("test_area", ""),
            "unit": r.get("count_unit", ""),
            "required": required,
            "done": done,
            "remaining": int(r.get("remaining") or max(required-done, 0)),
            "status": r.get("status", ""),
            "method": r.get("methodology", ""),
            "percent": round((100.0 * done / required), 1) if required else 0.0,
        })
    return result


def summary_metrics(run_dir: Path):
    s = read_json(run_dir / "derived" / "run-summary.json", {})
    telemetry = s.get("telemetry", {})
    correlation = s.get("correlation", {})
    fabric = s.get("fabric_outbox", {})
    rssi = telemetry.get("rssi_dbm", {})
    snr = telemetry.get("snr_db", {})
    latency = telemetry.get("application_event_to_db_ms", {})
    return {
        "sealed": (run_dir / "metadata" / "SHA256SUMS.csv").exists(),
        "pdr": telemetry.get("pdr_percent_exact_payload_clock_aligned"),
        "latency_mean_ms": latency.get("mean"),
        "latency_sd_ms": latency.get("sd_sample"),
        "rssi_mean_dbm": rssi.get("mean"),
        "snr_mean_db": snr.get("mean"),
        "db_rows": telemetry.get("rows"),
        "exact_matches": correlation.get("eligible_exact_payload_matches"),
        "eligible_source_attempts": correlation.get("eligible_source_attempts_in_db_export_window"),
        "fabric_rows": fabric.get("rows"),
        "fabric_status": fabric.get("status_counts", {}),
        "fabric_committed_with_txid": fabric.get("committed_with_tx_id"),
    }


def build_state():
    run_dir = find_latest_run()
    active = ACTIVE_STATE.exists()
    if not run_dir:
        return {"generated_at": iso_now(), "active": active, "run": None, "study": study_progress()}
    meta = read_json(run_dir / "metadata" / "run-meta.json", {})
    status_text = ""
    try:
        status_text = (run_dir / "derived" / "run-status.txt").read_text(encoding="utf-8").strip()
    except Exception:
        pass
    resources = {
        "gateway": latest_resource(run_dir / "raw" / "gateway-resource.csv"),
        "ulc01": latest_resource(run_dir / "raw" / "ulc01-host-resource.csv"),
        "ulc02": latest_resource(run_dir / "raw" / "ulc02-host-resource.csv"),
        "ulc03": latest_resource(run_dir / "raw" / "ulc03-host-resource.csv"),
    }
    trials = read_csv(run_dir / "derived" / "trial-results.csv")
    trial_counts = {}
    for t in trials:
        k = t.get("status", "UNCLASSIFIED") or "UNCLASSIFIED"
        trial_counts[k] = trial_counts.get(k, 0) + 1
    return {
        "generated_at": iso_now(),
        "active": active,
        "run": {
            "id": meta.get("run_id", run_dir.name),
            "group": meta.get("group", run_dir.parent.name),
            "scope": meta.get("scope", ""),
            "condition": meta.get("condition", ""),
            "expected": meta.get("expected_result", ""),
            "start_utc": meta.get("start_utc", ""),
            "status": status_text or ("RUNNING" if active else "RECORDED"),
            "source": source_state(run_dir / "raw" / "emu-01-source.log"),
            "health": health_state(run_dir / "raw" / "control-plane-health.csv"),
            "resources": resources,
            "metrics": summary_metrics(run_dir),
            "trial_counts": trial_counts,
            "trial_rows": len(trials),
            "path": str(run_dir),
        },
        "study": study_progress(),
        "links": {
            "grafana": "http://127.0.0.1:3000/d/lorawan-research-cockpit/lorawan-research-test-cockpit?orgId=1&refresh=15s",
            "chirpstack": "https://smartagri-chirpstack.duckdns.org",
        },
    }


INDEX = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LoRaWAN Research Cockpit</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;background:#08111f;color:#e5edf7}body{margin:0}.wrap{max-width:1500px;margin:auto;padding:18px}.top{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.title{font-size:26px;font-weight:800}.muted{color:#8fa5bd}.badge{padding:5px 10px;border-radius:999px;font-weight:700;font-size:12px;background:#23314a}.good{background:#123b2b;color:#80f0b2}.warn{background:#4a3514;color:#ffd27d}.bad{background:#481f2a;color:#ff9bac}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:10px;margin-top:12px}.card{background:#0f1c2d;border:1px solid #23344a;border-radius:12px;padding:13px;box-shadow:0 8px 24px #0003}.span2{grid-column:span 2}.span3{grid-column:span 3}.span4{grid-column:span 4}.span6{grid-column:span 6}.span12{grid-column:span 12}.metric{font-size:28px;font-weight:800;margin-top:4px}.label{font-size:12px;color:#90a7bf;text-transform:uppercase;letter-spacing:.08em}.small{font-size:12px}.resource{display:grid;grid-template-columns:130px 1fr 1fr 1.4fr;gap:8px;padding:7px 0;border-bottom:1px solid #1d2d42}.bar{height:8px;background:#1b2b40;border-radius:99px;overflow:hidden;margin-top:5px}.fill{height:100%;background:linear-gradient(90deg,#40c4ff,#55e6a5)}.progress{display:grid;grid-template-columns:170px 1fr 90px 190px;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid #1d2d42}a{color:#78c8ff;text-decoration:none}.links{display:flex;gap:10px}.btn{background:#173455;padding:8px 12px;border-radius:8px}.chart{width:100%;height:90px}.truth{border-left:4px solid #55e6a5}.provisional{border-left:4px solid #ffd166}@media(max-width:900px){.span2,.span3,.span4,.span6{grid-column:span 12}.resource{grid-template-columns:90px 1fr 1fr}.resource svg{grid-column:1/-1}.progress{grid-template-columns:120px 1fr 70px}.progress .method{grid-column:1/-1}}</style></head><body><div class="wrap">
<div class="top"><div><div class="title">LoRaWAN Research Test Cockpit</div><div class="muted" id="stamp">Loading…</div></div><div class="links"><a class="btn" id="grafana" target="_blank">Live DB / Fabric Grafana</a><a class="btn" id="chirp" target="_blank">ChirpStack</a></div></div>
<div id="app"></div></div><script>
const f=(v,d=2)=>v==null?'—':Number(v).toFixed(d); const pct=v=>v==null?'—':f(v,1)+'%';
function spark(points,key){let vals=points.map(x=>x[key]).filter(v=>v!=null);if(!vals.length)return '';let mn=Math.min(...vals),mx=Math.max(...vals),w=500,h=90,p=5;let coords=points.map((x,i)=>{let v=x[key];if(v==null)return null;let X=p+i*(w-2*p)/Math.max(points.length-1,1);let Y=h-p-(v-mn)*(h-2*p)/Math.max(mx-mn,.001);return X.toFixed(1)+','+Y.toFixed(1)}).filter(Boolean).join(' ');return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline fill="none" stroke="currentColor" stroke-width="2" points="${coords}"/></svg>`}
function card(label,value,sub='',cls=''){return `<div class="card span2 ${cls}"><div class="label">${label}</div><div class="metric">${value}</div><div class="small muted">${sub}</div></div>`}
function render(s){document.getElementById('stamp').textContent=`Dashboard ${s.generated_at} · auto-refresh 3 s · visualization only`;document.getElementById('grafana').href=s.links?.grafana||'#';document.getElementById('chirp').href=s.links?.chirpstack||'#';let r=s.run;if(!r){document.getElementById('app').innerHTML='<div class="card span12">No recorder run found.</div>';return}
let health=r.health.last_status;let hcls=health==='PASS'?'good':health==='WARN'?'warn':'bad';let m=r.metrics||{},src=r.source||{};let fabric=Object.entries(m.fabric_status||{}).map(([k,v])=>`${k}:${v}`).join(' · ')||'post-run export pending';
let html=`<div class="grid"><div class="card span12"><div class="top"><div><b>${r.id}</b> <span class="badge ${s.active?'good':''}">${s.active?'RUNNING':'LATEST SEALED/RECORDED'}</span> <span class="badge ${hcls}">health ${health}</span></div><div class="small muted">${r.group} · ${r.condition||'—'} · start ${r.start_utc||'—'}</div></div></div>`;
html+=card('Source TX attempts',src.attempts??0,`send OK ${src.send_ok??0} · failures ${src.send_fail??0}`,'provisional');
html+=card('Latest sequence',src.last_seq??'—',src.last_timestamp||'No source frame yet','provisional');
html+=card('Final PDR',m.pdr==null?'pending':pct(m.pdr),m.pdr==null?'Computed only from sealed exact payload correlation':`${m.exact_matches}/${m.eligible_source_attempts} exact eligible matches`,'truth');
html+=card('App→DB latency',m.latency_mean_ms==null?'pending':f(m.latency_mean_ms)+' ms',m.latency_sd_ms==null?'sealed result only':`SD ${f(m.latency_sd_ms)} ms`,'truth');
html+=card('Mean RSSI',m.rssi_mean_dbm==null?'pending':f(m.rssi_mean_dbm)+' dBm',m.rssi_mean_dbm==null?'sealed result only':'DB/gateway radio observation','truth');
html+=card('Mean SNR',m.snr_mean_db==null?'pending':f(m.snr_mean_db)+' dB',m.snr_mean_db==null?'sealed result only':'DB/gateway radio observation','truth');
html+=`<div class="card span12"><div class="label">Fabric / evidence result from sealed run</div><div class="metric" style="font-size:20px">${fabric}</div><div class="small muted">Committed with transaction ID: ${m.fabric_committed_with_txid??'pending export'} · live DB/evidence state is in Grafana</div></div>`;
html+=`<div class="card span12"><div class="label">Resource headroom · latest recorder samples</div>`;for(const [name,obj] of Object.entries(r.resources||{})){let x=obj.latest||{};html+=`<div class="resource"><b>${name}</b><span>CPU ${pct(x.cpu)}</span><span>RAM ${pct(x.mem)}</span><span>${spark(obj.series||[],'cpu')}</span></div>`}html+='</div>';
html+=`<div class="card span6"><div class="label">Supervisor / clock witness</div><div class="metric">${health}</div><div>Clock offset: ${r.health.clock_offset_s==null?'—':f(r.health.clock_offset_s,3)+' s'}</div><div class="small muted">${r.health.detail||''}</div></div>`;
html+=`<div class="card span6"><div class="label">Trial classifications in current run</div><div class="metric">${r.trial_rows}</div><div>${Object.entries(r.trial_counts||{}).map(([k,v])=>`${k}: ${v}`).join(' · ')||'No trials classified yet'}</div></div>`;
html+=`<div class="card span12"><div class="label">Chapter IV formal test completion</div>`;for(const q of s.study||[]){html+=`<div class="progress"><b>${q.area}</b><div><div class="bar"><div class="fill" style="width:${q.percent}%"></div></div></div><span>${q.done}/${q.required}</span><span class="small muted method">${q.method}</span></div>`}html+='</div>';
html+=`<div class="card span12 truth"><b>Truth boundary</b><div class="small">Live source/resource cards are provisional observations from the active recorder files. Final PDR, latency, RF aggregates, Fabric state and Chapter IV cells are promoted only from sealed raw evidence and generated summaries. Grafana is a read-only DB/evidence visualization.</div></div></div>`;document.getElementById('app').innerHTML=html}
async function tick(){try{let r=await fetch('/api/state',{cache:'no-store'});render(await r.json())}catch(e){document.getElementById('stamp').textContent='Dashboard error: '+e}}tick();setInterval(tick,3000);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/state":
            body = json.dumps(build_state(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route in ("/", "/index.html"):
            body = INDEX.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        return


def main():
    ap = argparse.ArgumentParser(description="Local read-only LoRaWAN research test cockpit")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"RESEARCH_COCKPIT=http://{args.host}:{args.port}", flush=True)
    print("VISUALIZATION_ONLY=raw recorder evidence and generated summaries remain authoritative", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
