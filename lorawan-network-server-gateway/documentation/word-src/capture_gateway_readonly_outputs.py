import os
import json
import datetime
import pathlib
import paramiko
import re

BASE=pathlib.Path('lorawan-network-server-gateway/documentation/assets/live-gateway-fullpage-headless-20260922')
BASE.mkdir(parents=True, exist_ok=True)
secret=os.environ.get('GATEWAY_AUTH')
if not secret:
    raise SystemExit('No gateway password environment supplied')
client=paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.20.11',username='root',password=secret,allow_agent=False,look_for_keys=False,timeout=8,auth_timeout=8)

checks = {
  'radio': '''uname -n; date -u; uci show chirpstack-concentratord | grep -E 'enabled|model|region|channel_plan' | head -n 16; uci -q get chirpstack-mqtt-forwarder.@mqtt[0].qos''',
  'lte': '''uname -n; date -u; echo '-- UCI PDP --'; uci -q get network.lte.pdptype; echo '-- LTE interface --'; ubus call network.interface.lte status | grep -E 'up|device|address' | head -n 8; echo '-- Default route --'; ip route show default; echo '-- Cloud sessions --'; (ss -tn 2>/dev/null || netstat -tn 2>/dev/null) | grep ':8883' | head -n 5''',
  'mosquitto': '''uname -n; date -u; echo '-- Active process --'; ps w | grep '[m]osquitto' | head -n 3; echo '-- Local broker --'; grep -E '^(persistence |persistence_location |autosave_interval |max_queued_messages |max_queued_bytes |queue_qos0_messages |listener |allow_anonymous |include_dir )' /etc/mosquitto/mosquitto.conf; echo '-- Listener --'; (ss -lnt 2>/dev/null || netstat -lnt 2>/dev/null) | grep ':1883' | head -n 3; echo '-- Persistent database --'; ls -lh /etc/mosquitto/data/mosquitto.db 2>/dev/null || true; df -h /etc/mosquitto/data | tail -n 1''',
  'bridges': '''uname -n; date -u; echo '-- Bridge identities/destination/topics only --'; grep -E '^(connection |address |remote_clientid |bridge_insecure |topic )' /etc/mosquitto/conf.d/bridge.conf; echo '-- Cloud MQTT sockets --'; (ss -tn 2>/dev/null || netstat -tn 2>/dev/null) | grep ':8883' | head -n 6; echo '-- LTE default route --'; ip route show default'''
}
data={'capture_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':'192.168.20.11','checks':{}}
for name,command in checks.items():
    _in,stdout,stderr=client.exec_command(command,timeout=15)
    text=stdout.read().decode('utf-8','replace')[:9500]
    err=stderr.read().decode('utf-8','replace')[:1400]
    status=stdout.channel.recv_exit_status()
    if re.search(r'(?i)(appkey|nwkkey|secret[_ -]?id|password\s*=|private key)',text):
        raise RuntimeError('Potential secret in output '+name)
    data['checks'][name]={'command':command,'stdout':text,'stderr':err,'exit_code':status}
client.close()
(BASE/'read-only-gateway-operator-output.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print('READONLY_CAPTURE_OK',list(data['checks']), 'pdp=',data['checks']['lte']['stdout'].split('-- UCI PDP --')[-1].splitlines()[1])

