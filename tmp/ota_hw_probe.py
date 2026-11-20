from pathlib import Path
import json, os, sys, time
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.core.config import Settings
import paho.mqtt.client as mqtt
import httpx
s=Settings(_env_file=root/'backend/.env')
result={}
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as http:
    login=http.post('/api/v1/auth/login',json={'username':s.initial_admin_username,'password':s.initial_admin_password})
    result['configured_login_status']=login.status_code
    if login.is_success:
        (root/'.runtime/ota-session.json').write_text(json.dumps({'cookie':dict(http.cookies),'csrf':login.json()['csrf_token']}))
        for key,path in [('device','/api/v1/devices/ESP32_001/status'),('can','/api/v1/can/tx'),('ota','/api/v1/ota')]:
            reply=http.get(path); result[key]={'http':reply.status_code,'data':reply.json()}
messages={}
client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='ota-bench-probe')
client.username_pw_set(s.mqtt_username,s.mqtt_password)
if s.mqtt_tls: client.tls_set(ca_certs=s.mqtt_ca_file)
def connected(c,*_):
    c.subscribe([(f'{s.mqtt_topic_prefix}/ESP32_001/{suffix}',1) for suffix in ('status','can','telemetry','ota/status')])
def received(c,u,m):
    try:
        value=json.loads(m.payload)
        if m.topic.endswith('/can'): value={'boot_id':value.get('boot_id'),'stats':value.get('stats')}
        if m.topic.endswith('/telemetry'): value={k:value.get(k) for k in ('boot_id','sequence','source','uptime_ms','time_valid')}
        messages[m.topic]={'retained':m.retain,'data':value}
    except ValueError: pass
client.on_connect=connected; client.on_message=received
client.connect(s.mqtt_host,s.mqtt_port);client.loop_start();time.sleep(5)
client.disconnect();client.loop_stop()
result['mqtt']=messages
(root/'output/testing/ota-hardware-baseline-20261120.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
