from pathlib import Path
import hashlib, json, queue, sys, time, uuid
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.core.config import Settings
import httpx
import paho.mqtt.client as mqtt
s=Settings(_env_file=root/'backend/.env')
auth=json.loads((root/'.runtime/ota-session.json').read_text())
http=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],headers={'X-CSRF-Token':auth['csrf']},timeout=20)
before=http.get('/api/v1/ota').json()['chip']
assert before['confirmed'] and before['state']=='idle'
acks=queue.Queue(); connected=__import__('threading').Event()
client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='ota-hardware-safety-test')
client.username_pw_set(s.mqtt_username,s.mqtt_password)
if s.mqtt_tls:client.tls_set(ca_certs=s.mqtt_ca_file)
topic=f'{s.mqtt_topic_prefix}/ESP32_001/ota/'
def on_connect(c,*_):c.subscribe(topic+'response',1)
def on_subscribe(*_):connected.set()
def on_message(c,u,m):acks.put(json.loads(m.payload))
client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
client.connect(s.mqtt_host,s.mqtt_port);client.loop_start();assert connected.wait(10)
checks=[]
def passed(name):checks.append(name);print(name,flush=True)
def request(op,id,**fields):
    packet={'id':id,'boot_id':before['boot_id'],'op':op,**fields}
    client.publish(topic+'request',json.dumps(packet),qos=1).wait_for_publish(5)
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        ack=acks.get(timeout=8)
        if ack.get('id')==id and ack.get('op')==op:return ack
    raise AssertionError('Missing acknowledgement')
def start(size,sha=None):
    id=str(uuid.uuid4());ack=request('start',id,size=size,sha256=sha or '0'*64,expires_at_ms=int(time.time()*1000)+15000)
    return id,ack
def wait_idle(timeout=40):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        state=http.get('/api/v1/ota').json()
        if state['fresh'] and state['chip']['state']=='idle':return state['chip']
        time.sleep(.5)
    raise AssertionError('Device did not release OTA locks')
try:
    with httpx.Client(base_url='http://127.0.0.1:8000') as anonymous:
        assert anonymous.get('/api/v1/ota').status_code==401
        assert anonymous.post('/api/v1/ota/start',json={'device_id':'ESP32_001','upload_id':str(uuid.uuid4())}).status_code in (401,403)
    passed('Unauthenticated OTA blocked on live server')
    with httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie']) as missing_csrf:
        assert missing_csrf.post('/api/v1/ota/image?device_id=ESP32_001&filename=bad.bin',content=b'bad').status_code==403
    passed('Upload without CSRF blocked')
    for name,data in [('bad.bin',b'not firmware'),('bad.hex',b':00000001FE\n'),('bootloader.bin',(root/'output/firmware/bootloader.bin').read_bytes()),('oversize.bin',b'\0'*(6*1024*1024+1))]:
        response=http.post('/api/v1/ota/image',params={'device_id':'ESP32_001','filename':name},content=data)
        assert response.status_code==(413 if name=='oversize.bin' else 400),(name,response.status_code,response.text)
    passed('Bad BIN, invalid HEX, bootloader and oversized upload rejected')
    id,ack=start(0x1F0000+1);assert not ack['ok'];passed('Chip independently rejects oversized image')
    capacity=before.get('max_chunk_bytes',768)
    data=(root/'.runtime/ota-test-images/v1.1.12.bin').read_bytes()[:capacity]
    id,ack=start(capacity*2);assert ack['ok'],ack
    assert request('chunk',id,offset=0,data=data.hex())['ok']
    assert request('chunk',id,offset=0,data=data.hex())['ok'];passed('Duplicate chunk accepted without a second write')
    command=http.post('/api/v1/commands',json={'device_id':'ESP32_001','key':'A','value':0});command.raise_for_status()
    cid=command.json()['command_id']
    for _ in range(25):
        outcome=http.get('/api/v1/commands/'+cid).json()
        if outcome['status'] in ('rejected','applied','timed_out'):break
        time.sleep(.2)
    assert outcome['status']=='rejected' and outcome.get('reason')=='firmware_update_in_progress',outcome
    passed('Safe OFF command rejected while OTA maintenance owns controls')
    altered=bytes([data[0]^1])+data[1:]
    ack=request('chunk',id,offset=0,data=altered.hex());assert not ack['ok'] and 'duplicate' in ack['error'];wait_idle()
    passed('Conflicting duplicate aborts transfer and releases locks')
    id,ack=start(capacity*2);assert ack['ok'];ack=request('chunk',id,offset=capacity,data=data.hex());assert not ack['ok'] and 'order' in ack['error'];wait_idle()
    passed('Out-of-order chunk rejected')
    id,ack=start(capacity);assert ack['ok'];assert request('chunk',id,offset=0,data=data.hex())['ok']
    ack=request('finish',id);assert not ack['ok'] and 'SHA-256' in ack['error'];wait_idle()
    passed('Whole-image SHA mismatch rejected before boot selection')
    id,ack=start(capacity,hashlib.sha256(data).hexdigest());assert ack['ok'];assert request('chunk',id,offset=0,data=data.hex())['ok']
    ack=request('finish',id);assert not ack['ok'] and 'ESP32 rejected' in ack['error'];wait_idle()
    passed('ESP32 independently rejects a truncated image with a correct transport hash')
    id,ack=start(capacity*2);assert ack['ok'];assert request('chunk',id,offset=0,data=data.hex())['ok']
    time.sleep(3);assert http.get('/api/v1/ota').json()['chip']['state']=='transferring'
    begin=time.monotonic();after=wait_idle(40)
    passed('Interrupted transfer times out and releases locks (%.1fs observed)'%(time.monotonic()-begin))
    assert after['boot_id']==before['boot_id'] and after['image_sha256']==before['image_sha256'] and after['confirmed']
    passed('Every rejected or interrupted transfer preserved the running confirmed image')
    result={'passed':True,'live_hardware':True,'chunk_bytes_tested':capacity,'checks':checks,'before':before,'after':after}
    (root/'output/testing/ota-live-safety.json').write_text(json.dumps(result,indent=2))
finally:
    client.disconnect();client.loop_stop();http.close()
