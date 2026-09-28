from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, time, re
import serial
from serial.tools import list_ports

ROOT=Path(__file__).resolve().parents[3]
CFG=ROOT/"chapter4-results"/"_configuration"/"emu01-counted-test-15s"
REC=json.loads((CFG/"build-record.json").read_text(encoding="utf-8-sig"))
PKG=ROOT/REC["upload_package_path"]
EXPECTED=REC["upload_package_sha256"]
NRF=Path.home()/"AppData"/"Local"/"Arduino15"/"packages"/"RAKwireless"/"hardware"/"nrf52"/"1.3.3"/"tools"/"adafruit-nrfutil"/"win32"/"adafruit-nrfutil.exe"
SN="69D8B0D3239621F1"

stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
OUT=ROOT/"chapter4-results"/"authentication"/"lorawan"/f"A1-LORAWAN-emu-reboot-canary-{stamp}"
OUT.mkdir(parents=True,exist_ok=False)

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def find(pid:int)->str|None:
    for p in list_ports.comports():
        if (p.serial_number or "").upper()==SN and p.pid==pid:
            return p.device
    return None

def wait_port(pid:int, timeout:float)->str:
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        p=find(pid)
        if p: return p
        time.sleep(.25)
    raise RuntimeError(f"EMU USB port PID {pid:04X} not found")

result={"status":"FAIL","counted_research":False,"package_sha256":sha256(PKG),"expected_package_sha256":EXPECTED}
try:
    if result["package_sha256"]!=EXPECTED:
        raise RuntimeError("counted firmware package SHA-256 mismatch")
    app=wait_port(0x8029,5)
    result["application_port_before"]=app
    s=serial.Serial(app,1200,timeout=.2)
    s.close()
    dfu=wait_port(0x002A,10)
    result["dfu_port"]=dfu
    cp=subprocess.run([str(NRF),"dfu","serial","--package",str(PKG),"--port",dfu,"--baudrate","115200"],
                      text=True,capture_output=True,timeout=90,check=False)
    (OUT/"dfu.stdout.txt").write_text(cp.stdout,encoding="utf-8",errors="replace")
    (OUT/"dfu.stderr.txt").write_text(cp.stderr,encoding="utf-8",errors="replace")
    result["dfu_exit_code"]=cp.returncode
    if cp.returncode!=0 or "Device programmed" not in (cp.stdout+cp.stderr):
        raise RuntimeError(f"same-image DFU failed rc={cp.returncode}")
    app2=wait_port(0x8029,15)
    result["application_port_after"]=app2
    lines=[]
    joined=False; tx=False; profile=False; tx_uptimes=[]; cadence_ok=False
    with serial.Serial(app2,115200,timeout=.25) as s:
        end=time.monotonic()+50
        while time.monotonic()<end and not (joined and tx and (profile or cadence_ok)):
            raw=s.readline()
            if not raw: continue
            line=raw.decode("utf-8","replace").strip()
            if not line: continue
            lines.append(line)
            profile |= line=="EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S"
            joined |= line.startswith("EMU01_OTAA_JOIN=PASS")
            successful_tx = line.startswith("SENSOR_TX,") and "join=1" in line and "send_status=0" in line
            tx |= successful_tx
            if successful_tx:
                match=re.search(r"(?:^|,)uptime_ms=(\d+)(?:,|$)",line)
                if match:
                    tx_uptimes.append(int(match.group(1)))
                    cadence_ok=len(tx_uptimes)>=3 and all(14500<=b-a<=15500 for a,b in zip(tx_uptimes[-3:],tx_uptimes[-2:]))
    (OUT/"emu-serial.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    # The CDC serial handle may open after the boot banner. A hash-verified DFU
    # followed by three successful ~15 s uplinks also proves the frozen profile.
    profile_ok=profile or cadence_ok
    # UART may attach after the boot-only join callback; three independently
    # reported joined successful MAC sends also establish the joined state.
    join_ok=joined or (tx and len(tx_uptimes)>=3)
    result.update({"profile_ok":profile_ok,"profile_boot_banner_seen":profile,
                   "profile_15s_cadence_observed":cadence_ok,
                   "profile_proof_method":"boot_banner" if profile else "verified_dfu_and_15s_cadence" if cadence_ok else "unproven",
                   "otaa_join_pass":join_ok,"join_boot_banner_seen":joined,
                   "join_proof_method":"join_callback" if joined else "three_joined_successful_mac_sends" if join_ok else "unproven",
                   "successful_uplink":tx})
    if not (profile_ok and join_ok and tx):
        raise RuntimeError(f"post-DFU proof incomplete profile={profile_ok} joined={join_ok} tx={tx}")
    result["status"]="PASS"
finally:
    result["finished_at_utc"]=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    (OUT/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(f"EMU_REBOOT_CANARY={result['status']}")
print(f"RUN_DIR={OUT}")
