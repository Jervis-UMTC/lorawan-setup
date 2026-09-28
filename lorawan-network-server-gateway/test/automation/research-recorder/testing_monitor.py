#!/usr/bin/env python3
"""Read-only operational monitor behind the LoRaWAN research cockpit.

Operational observations are deliberately separate from formal experiment results.
The chapter PDFs tell us what should be measured; live verified state tells us what
is deployed; sealed chapter4-results captures tell us what happened in a trial.
"""
from __future__ import annotations

import base64
import csv
import json
import os
import sqlite3
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY_HOURS = 24
RETENTION_DAYS = 7
MAX_EVENTS = 120
PERSIST_SECONDS = 60
CLOCK_SKEW_LIMIT_SECONDS = 0.250
CLOUD_CLOCK_SPREAD_LIMIT_SECONDS = 0.250
GATEWAY_CLOCK_SKEW_LIMIT_SECONDS = 1.500  # gateway stream timestamps are whole-second resolution
CLOCK_SAMPLE_FRESH_SECONDS = 5
NODE_NAMES = {"gateway":"Gateway","ulc01":"Server 1","ulc02":"Server 2","ulc03":"Server 3"}
ROLE_HINTS = {
    "chirpstack":"LoRaWAN network server","node-red-node-red-1":"Telemetry processing",
    "lorawan-gateway-evidence-ingest-1":"Evidence ingest","lorawan-gateway-evidence-collector-1":"MQTT evidence collector",
    "lorawan-gateway-evidence-verifier-1":"Evidence verifier","lorawan-gateway-evidence-fabric-adapter-1":"Fabric adapter",
    "openbao":"Evidence signing KMS","seaweedfs":"Evidence object store","seaweedfs-metadata-etcd":"Object-store metadata",
    "spilo":"PostgreSQL / TimescaleDB","etcd":"Database consensus","grafana":"Research dashboards",
    "mosquitto":"MQTT broker","haproxy":"TLS / service routing","pgbouncer":"PostgreSQL connection pool",
    "fail2ban":"Host intrusion throttling","ufw":"Host firewall",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")


class TestingMonitor:
    """Consumes the multiplexed restricted SSH streams; opens no SSH sessions itself."""
    def __init__(self, ssh_exe: Path, key: Path, results_root: Path):
        self.results_root = results_root
        local = Path(os.environ.get("LOCALAPPDATA", str(results_root))) / "LoRaWAN"
        local.mkdir(parents=True, exist_ok=True)
        self.db_path = local / "testing-monitor.sqlite3"
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._last_persist = 0.0
        self._service_map: dict[tuple[str,str],dict] = {}
        self._clock_samples: dict[str, deque[float]] = {}
        self.state = {
            "status":"starting","updated_at":None,"observation_history":str(self.db_path),
            "history_hours":HISTORY_HOURS,"nodes":{},"services":[],"evidence":{},"database":{},
            "pipeline":{"observed_at":None,"source_node":None,"counts":{},"fabric_status":{},"verification_results":{}},
            "clock":{
                "ready":False,"status":"NO-GO","observed_at":None,
                "reference":"cloud monitor stream; formal recorder uses midpoint-corrected utc-now probes",
                "workstation_skew_limit_seconds":CLOCK_SKEW_LIMIT_SECONDS,
                "cloud_spread_limit_seconds":CLOUD_CLOCK_SPREAD_LIMIT_SECONDS,
                "gateway_skew_limit_seconds":GATEWAY_CLOCK_SKEW_LIMIT_SECONDS,
                "server_minus_workstation_seconds":None,"cloud_spread_seconds":None,
                "nodes":{},"reasons":["clock samples are still starting"],
            },
            "service_history":[],"recent_events":[],"test_history":[],
            "truth_model":{"live_state":"restricted live observations","formal_results":"sealed chapter4-results captures","chapters":"requirements reference only; not runtime or result truth"},
        }
        self._init_db()

    @staticmethod
    def _parse_time(value: str) -> datetime:
        text=value.strip()
        if text.endswith("Z"): text=text[:-1]+"+00:00"
        dt=datetime.fromisoformat(text)
        if dt.tzinfo is None: raise ValueError("timestamp has no timezone")
        return dt.astimezone(timezone.utc)

    def _recompute_clock_locked(self):
        clock=self.state["clock"]
        current=datetime.now(timezone.utc)
        fresh={}
        for node,item in clock.get("nodes",{}).items():
            try:
                age=(current-self._parse_time(item["observed_at"])).total_seconds()
            except Exception:
                age=999999
            item["age_seconds"]=max(0.0,age)
            item["fresh"]=age<=CLOCK_SAMPLE_FRESH_SECONDS
            if item["fresh"]: fresh[node]=item

        cloud=[fresh[n] for n in ("ulc01","ulc02","ulc03") if n in fresh]
        reasons=[]
        cluster_offset=None; spread=None
        cloud_ready=len(cloud)==3
        if not cloud_ready:
            reasons.append("fresh clock observations are required from all three cloud nodes")
        else:
            offsets=[float(x["server_minus_workstation_seconds"]) for x in cloud]
            cluster_offset=statistics.median(offsets)
            spread=max(offsets)-min(offsets)
            if abs(cluster_offset)>CLOCK_SKEW_LIMIT_SECONDS:
                cloud_ready=False
                reasons.append(
                    f"workstation differs from cloud UTC by {cluster_offset:+.3f}s "
                    f"(limit +/-{CLOCK_SKEW_LIMIT_SECONDS:.3f}s)"
                )
            if spread>CLOUD_CLOCK_SPREAD_LIMIT_SECONDS:
                cloud_ready=False
                reasons.append(
                    f"cloud clock spread is {spread:.3f}s "
                    f"(limit {CLOUD_CLOCK_SPREAD_LIMIT_SECONDS:.3f}s)"
                )

        gateway=fresh.get("gateway")
        gateway_ready=gateway is not None
        if gateway is None:
            reasons.append("Gateway clock is not currently observable through the management stream")
        elif abs(float(gateway["server_minus_workstation_seconds"]))>GATEWAY_CLOCK_SKEW_LIMIT_SECONDS:
            gateway_ready=False
            reasons.append(
                f"Gateway differs from workstation by {float(gateway['server_minus_workstation_seconds']):+.3f}s "
                f"(whole-second stream limit +/-{GATEWAY_CLOCK_SKEW_LIMIT_SECONDS:.3f}s)"
            )

        gateway_minus_cloud=None
        if gateway is not None and cluster_offset is not None:
            gateway_minus_cloud=float(gateway["server_minus_workstation_seconds"])-cluster_offset
            if abs(gateway_minus_cloud)>GATEWAY_CLOCK_SKEW_LIMIT_SECONDS:
                gateway_ready=False
                reasons.append(
                    f"Gateway differs from cloud UTC by {gateway_minus_cloud:+.3f}s "
                    f"(whole-second stream limit +/-{GATEWAY_CLOCK_SKEW_LIMIT_SECONDS:.3f}s)"
                )

        ready=cloud_ready and gateway_ready
        clock.update(
            ready=ready,status="GO" if ready else "NO-GO",observed_at=iso_now(),
            server_minus_workstation_seconds=cluster_offset,cloud_spread_seconds=spread,
            gateway_minus_cloud_seconds=gateway_minus_cloud,
            reasons=reasons or ["cloud, workstation and gateway clocks are within the staging limits"],
        )

    def ingest_clock_sample(self,node:str,server_timestamp:str):
        try:
            server_time=self._parse_time(server_timestamp)
        except Exception:
            return
        local_time=datetime.now(timezone.utc)
        offset=(server_time-local_time).total_seconds()
        with self.lock:
            samples=self._clock_samples.setdefault(node,deque(maxlen=9))
            samples.append(offset)
            median=statistics.median(samples)
            self.state["clock"].setdefault("nodes",{})[node]={
                "name":NODE_NAMES.get(node,node),"observed_at":iso_now(),
                "server_timestamp_utc":server_timestamp,
                "server_minus_workstation_seconds":median,
                "latest_sample_seconds":offset,"sample_count":len(samples),
            }
            self._recompute_clock_locked()

    def _connect(self):
        c=sqlite3.connect(self.db_path,timeout=3); c.execute("PRAGMA journal_mode=WAL"); return c

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS service_observation(observed_at TEXT NOT NULL,node TEXT NOT NULL,service TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,detail TEXT,role TEXT,PRIMARY KEY(observed_at,node,service));
            CREATE INDEX IF NOT EXISTS service_observation_recent ON service_observation(observed_at,node,service);
            CREATE TABLE IF NOT EXISTS monitor_event(observed_at TEXT NOT NULL,node TEXT NOT NULL,service TEXT NOT NULL,severity TEXT NOT NULL,message TEXT NOT NULL,PRIMARY KEY(observed_at,node,service,message));
            CREATE INDEX IF NOT EXISTS monitor_event_recent ON monitor_event(observed_at);
            """)

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.thread=threading.Thread(target=self._maintenance,daemon=True,name="testing-monitor"); self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=3)

    def set_node_status(self,node:str,status:str,error:str=""):
        now=iso_now()
        with self.lock:
            n=self.state["nodes"].setdefault(node,{"name":NODE_NAMES.get(node,node)})
            n.update(status=status,error=error,stream_observed_at=now)
            self.state["updated_at"]=now
            self.state["status"]="online" if any(x.get("status")=="online" for x in self.state["nodes"].values()) else "unavailable"

    def ingest_stream_line(self,node:str,line:str):
        p=line.rstrip("\r\n").split("|")
        if not p: return
        kind=p[0]
        now=iso_now()
        event=None
        with self.lock:
            n=self.state["nodes"].setdefault(node,{"name":NODE_NAMES.get(node,node)})
            n.update(status="online",error="",stream_observed_at=now)
            if kind=="HOST" and len(p)>=4:
                n.update(timestamp_utc=p[1],hostname=p[2],uptime_seconds=int(float(p[3] or 0)))
            elif kind=="SERVICE" and len(p)>=6:
                name=p[2]; row={"node":node,"service":name,"kind":"container","state":p[3],"image":p[4],"detail":"|".join(p[5:]),"role":ROLE_HINTS.get(name,"Discovered container")}
                self._service_map[(node,name)]=row
            elif kind=="UNIT" and len(p)>=4:
                name=p[2]; row={"node":node,"service":name,"kind":"systemd","state":p[3],"detail":p[3],"role":ROLE_HINTS.get(name,"Host service")}
                self._service_map[(node,name)]=row
            elif kind=="DBROLE" and len(p)>=3:
                self.state["database"][node]=p[2]
            elif kind=="READY" and len(p)>=6:
                label,state,code=p[2],p[3],p[4]; body="|".join(p[5:])
                e=self.state["evidence"].setdefault(node,{"ready":True,"checks":[]})
                e["checks"]=[x for x in e.get("checks",[]) if x.get("label")!=label]
                e["checks"].append({"label":label,"state":state,"http":code,"detail":body,"raw":f"{label}: {state} (HTTP {code})"})
                e["ready"]=all(x.get("state")=="ready" for x in e["checks"])
            elif kind=="DBMETRIC" and len(p)>=4:
                metric,value=p[2],p[3]
                key_map={
                    "telemetry.uplinks":"uplinks",
                    "telemetry.measurements":"measurements",
                    "evidence.mqtt_events":"mqtt_events",
                    "evidence.segments":"segments",
                    "evidence.checkpoints":"checkpoints",
                    "evidence.verifications":"verifications",
                    "fabric.outbox":"fabric_outbox",
                }
                pipe=self.state.setdefault("pipeline",{"observed_at":None,"source_node":None,"counts":{},"fabric_status":{},"verification_results":{}})
                if pipe.get("observed_at")!=p[1] or pipe.get("source_node")!=node:
                    pipe={"observed_at":p[1],"source_node":node,"counts":{},"fabric_status":{},"verification_results":{}}
                    self.state["pipeline"]=pipe
                try: parsed=int(value)
                except (TypeError,ValueError): parsed=value
                if metric.startswith("fabric.status."):
                    pipe["fabric_status"][metric.removeprefix("fabric.status.")]=parsed
                elif metric.startswith("evidence.verification_status."):
                    pipe["verification_results"][metric.removeprefix("evidence.verification_status.")]=parsed
                else:
                    pipe["counts"][key_map.get(metric,metric)]=parsed
            elif kind=="PIPELINE" and len(p)>=4:
                counts={}
                for i in range(2,len(p)-1,2):
                    try: counts[p[i]]=int(p[i+1])
                    except (TypeError,ValueError): counts[p[i]]=p[i+1]
                self.state["pipeline"]={"observed_at":p[1],"source_node":node,"counts":counts,"fabric_status":{},"verification_results":{}}
            elif kind=="FABRICCOUNT" and len(p)>=4:
                pipe=self.state.setdefault("pipeline",{"observed_at":p[1],"source_node":node,"counts":{},"fabric_status":{},"verification_results":{}})
                pipe["observed_at"]=p[1]; pipe["source_node"]=node
                try: pipe.setdefault("fabric_status",{})[p[2]]=int(p[3])
                except (TypeError,ValueError): pipe.setdefault("fabric_status",{})[p[2]]=p[3]
            elif kind=="VERIFYCOUNT" and len(p)>=4:
                pipe=self.state.setdefault("pipeline",{"observed_at":p[1],"source_node":node,"counts":{},"fabric_status":{},"verification_results":{}})
                pipe["observed_at"]=p[1]; pipe["source_node"]=node
                try: pipe.setdefault("verification_results",{})[p[2]]=int(p[3])
                except (TypeError,ValueError): pipe.setdefault("verification_results",{})[p[2]]=p[3]
            elif kind=="LOG" and len(p)>=5:
                try: msg=base64.b64decode(p[4]).decode("utf-8",errors="replace")[-1000:]
                except Exception: msg=p[4][-1000:]
                event=(p[1] or now,node,p[2],p[3],msg)
            self.state["services"]=sorted(self._service_map.values(),key=lambda x:(x["node"],x["kind"],x["service"]))
            self.state["updated_at"]=now
            self.state["status"]="online"
        if event:
            with self._connect() as db: db.execute("INSERT OR IGNORE INTO monitor_event VALUES(?,?,?,?,?)",event)

    def _test_history(self):
        inventory=self.results_root/"summaries"/"run-inventory.csv"
        if inventory.exists():
            try:
                with inventory.open("r",encoding="utf-8-sig",newline="") as fh: return list(csv.DictReader(fh))[-30:][::-1]
            except Exception: pass
        rows=[]
        for meta in self.results_root.glob("*/*/metadata/run-meta.json"):
            try:
                data=json.loads(meta.read_text(encoding="utf-8")); run=meta.parents[1]
                status_file=run/"derived"/"run-status.txt"
                rows.append({"run_id":data.get("run_id",run.name),"group":data.get("group",run.parent.name),"condition":data.get("condition",""),"status":status_file.read_text(encoding="utf-8",errors="replace").strip() if status_file.exists() else "RECORDED_UNCLASSIFIED","sealed":str((run/"metadata"/"SHA256SUMS.csv").exists()).lower()})
            except Exception: continue
        return rows[-30:][::-1]

    def _service_history(self):
        cutoff=(datetime.now(timezone.utc)-timedelta(hours=HISTORY_HOURS)).isoformat().replace("+00:00","Z")
        sql="""
        WITH history AS (
          SELECT observed_at,node,service,kind,state,detail,role,
                 LAG(state) OVER (PARTITION BY node,service ORDER BY observed_at) AS previous_state
          FROM service_observation
          WHERE observed_at>=?
        )
        SELECT observed_at,node,service,kind,previous_state,state,detail,role
        FROM history
        WHERE previous_state IS NULL OR previous_state<>state
        ORDER BY observed_at DESC
        LIMIT ?
        """
        with self._connect() as db: rows=db.execute(sql,(cutoff,MAX_EVENTS)).fetchall()
        keys=("observed_at","node","service","kind","previous_state","state","detail","role")
        return [dict(zip(keys,r)) for r in rows]

    def _recent_events(self):
        cutoff=(datetime.now(timezone.utc)-timedelta(hours=HISTORY_HOURS)).isoformat().replace("+00:00","Z")
        with self._connect() as db: rows=db.execute("SELECT observed_at,node,service,severity,message FROM monitor_event WHERE observed_at>=? ORDER BY observed_at DESC LIMIT ?",(cutoff,MAX_EVENTS)).fetchall()
        return [dict(zip(("observed_at","node","service","severity","message"),r)) for r in rows]

    def _persist(self):
        observed=iso_now()
        with self.lock: rows=[(observed,x["node"],x["service"],x["kind"],x["state"],x.get("detail",""),x.get("role","")) for x in self._service_map.values()]
        cutoff=(datetime.now(timezone.utc)-timedelta(days=RETENTION_DAYS)).isoformat().replace("+00:00","Z")
        with self._connect() as db:
            if rows: db.executemany("INSERT OR REPLACE INTO service_observation VALUES(?,?,?,?,?,?,?)",rows)
            db.execute("DELETE FROM service_observation WHERE observed_at<?",(cutoff,)); db.execute("DELETE FROM monitor_event WHERE observed_at<?",(cutoff,))

    def _maintenance(self):
        while not self.stop_event.is_set():
            now=time.monotonic()
            if now-self._last_persist>=PERSIST_SECONDS:
                self._last_persist=now
                try: self._persist()
                except Exception: pass
            service_history=self._service_history()
            recent_events=self._recent_events()
            test_history=self._test_history()
            with self.lock:
                self.state["service_history"]=service_history
                self.state["recent_events"]=recent_events
                self.state["test_history"]=test_history
                # A missing stream is observation-unavailable, not a service failure.
                current=datetime.now(timezone.utc)
                for node,n in self.state["nodes"].items():
                    stamp=n.get("stream_observed_at")
                    if stamp:
                        try:
                            age=(current-datetime.fromisoformat(stamp.replace("Z","+00:00"))).total_seconds()
                            if age>90: n.update(status="unavailable",error=f"monitor stream stale for {int(age)} s")
                        except Exception: pass
                self.state["status"]="online" if any(n.get("status")=="online" for n in self.state["nodes"].values()) else "unavailable"
                self._recompute_clock_locked()
            self.stop_event.wait(10)

    def snapshot(self):
        with self.lock: return json.loads(json.dumps(self.state))
