from pathlib import Path
import json,sys,time
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
import httpx
from websockets.sync.client import connect
auth=json.loads((root/'.runtime/ota-session.json').read_text())
client=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],headers={'X-CSRF-Token':auth['csrf']},timeout=20)
checks=[];evidence={}
def get(path):
    r=client.get(path);r.raise_for_status();return r.json()
def passed(message):checks.append(message);print(message,flush=True)
chip=get('/api/v1/ota')['chip'];assert chip['confirmed'] and chip['state']=='idle'
before=get('/api/v1/telemetry/latest')['persisted'];time.sleep(2);after=get('/api/v1/telemetry/latest')['persisted']
assert before['boot_id']==after['boot_id']==chip['boot_id'] and after['sequence']>before['sequence']
assert len(after['channels'])==6 and after['source']=='hardware';evidence['telemetry']={'before_sequence':before['sequence'],'after_sequence':after['sequence'],'channels':list(after['channels'])}
passed('Six hardware ADC channels continue to persist after OTA')
cookie='; '.join(f'{k}={v}' for k,v in client.cookies.items())
with connect('ws://127.0.0.1:8000/ws/v1/telemetry',additional_headers={'Cookie':cookie},origin='http://127.0.0.1:8000') as ws:
    stages=set();deadline=time.monotonic()+10
    while time.monotonic()<deadline and stages!={'received','persisted'}:
        event=json.loads(ws.recv(timeout=10))
        if event.get('type')=='telemetry' and event.get('data',{}).get('boot_id')==chip['boot_id']:stages.add(event['stage'])
    assert stages=={'received','persisted'}
passed('Live WebSocket delivers received and database-persisted readings')
for channel in range(1,7):
    history=get(f'/api/v1/telemetry/channels/{channel}?limit=20');assert history['points']
passed('All six analytics history APIs return readings')
can_before=get('/api/v1/can/statistics');time.sleep(2);can_after=get('/api/v1/can/statistics')
assert can_after['device']['rx_total']>can_before['device']['rx_total'];assert can_after['boot_id']==chip['boot_id']
latest=get('/api/v1/can/latest?current_boot_only=true&limit=50');assert latest['frames']
evidence['can']={'before':can_before['device'],'after':can_after['device'],'stored_current_boot_ids':len(latest['frames'])}
passed('Passive CAN reception, statistics and current-boot database capture resume')
for key in ('A','B'):
    response=client.post('/api/v1/commands',json={'device_id':'ESP32_001','key':key,'value':0});response.raise_for_status();id=response.json()['command_id']
    for _ in range(40):
        state=get('/api/v1/commands/'+id)
        if state['status'] in ('applied','rejected','timed_out'):break
        time.sleep(.25)
    assert state['status']=='applied',state
passed('Both safe OFF commands receive applied hardware acknowledgements')
devices=get('/api/v1/devices');evidence['devices']=devices
assert next(d for d in devices['devices'] if d['device_id']=='ESP32_001')['controls']=={'A':0,'B':0}
catalog=get('/api/v1/bms/catalog');evidence['bms_catalog_counts']={k:len(v) for k,v in catalog.items() if isinstance(v,list)}
assert catalog
get('/api/v1/bms/jobs');get('/api/v1/health/ready')
passed('Existing BMS catalog/jobs and dependency readiness remain accessible')
result={'passed':True,'live_hardware':True,'chip':chip,'checks':checks,'evidence':evidence}
(root/'output/testing/ota-live-regression.json').write_text(json.dumps(result,indent=2));client.close()
