from pathlib import Path
import json,sys,time
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.core.config import Settings
import paho.mqtt.client as mqtt
s=Settings(_env_file=root/'backend/.env');c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='ota-ack-observer')
c.username_pw_set(s.mqtt_username,s.mqtt_password)
if s.mqtt_tls:c.tls_set(ca_certs=s.mqtt_ca_file)
f=(root/'.runtime/ota-ack-trace.jsonl').open('w')
def on_connect(c,*_):c.subscribe(f'{s.mqtt_topic_prefix}/ESP32_001/ota/+',1)
def on_message(c,u,m):
    f.write(json.dumps({'time':time.time(),'topic':m.topic,'data':json.loads(m.payload)})+'\n');f.flush()
c.on_connect=on_connect;c.on_message=on_message;c.connect(s.mqtt_host,s.mqtt_port);c.loop_start()
time.sleep(55);c.disconnect();c.loop_stop();f.close()
