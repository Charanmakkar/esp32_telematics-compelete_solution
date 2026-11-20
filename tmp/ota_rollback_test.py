from pathlib import Path
import json,sys,time
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
sys.path.append(r'C:\Espressif\tools\python\v6.0.2\venv\Lib\site-packages')
import httpx,serial
auth=json.loads((root/'.runtime/ota-session.json').read_text())
client=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],headers={'X-CSRF-Token':auth['csrf']},timeout=20)
def status():
    r=client.get('/api/v1/ota');r.raise_for_status();return r.json()
before=status();assert before['fresh'] and before['chip']['confirmed'] and before['chip']['state']=='idle' and not before['busy']
data=Path(sys.argv[1]).read_bytes() if len(sys.argv)>1 else (root/'.runtime/ota-test-images/v1.1.17.bin').read_bytes()
response=client.post('/api/v1/ota/image?device_id=ESP32_001&filename=rollback-test.bin',content=data);response.raise_for_status();image=response.json()
assert image['image_sha256']!=before['chip']['image_sha256']
response=client.post('/api/v1/ota/start',json={'device_id':'ESP32_001','upload_id':image['upload_id']});response.raise_for_status();job=response.json()
pending=None;after=None;last='';deadline=time.monotonic()+900
while time.monotonic()<deadline:
    state=status();j=state['job'];chip=state['chip']
    progress=f"{j['state']} {int(j['progress']//10)*10}%"
    if progress!=last:print(progress,flush=True);last=progress
    if chip['boot_id']!=before['chip']['boot_id'] and chip['image_sha256']==image['image_sha256']:
        assert not chip['confirmed'],'Pending-verification window was missed; no reset performed'
        pending=chip
        port=serial.Serial();port.port='COM3';port.baudrate=115200;port.timeout=.1;port.dtr=False;port.rts=False;port.open()
        port.rts=True;time.sleep(.1);port.rts=False
        end=time.monotonic()+3;trace=bytearray()
        while time.monotonic()<end:trace.extend(port.read(4096))
        port.close();(root/'.runtime/ota-rollback-serial.log').write_bytes(trace)
        print('Reset the new boot before startup confirmation',flush=True)
        break
    assert j['state'] not in ('failed','unconfirmed'),j
    time.sleep(.25)
assert pending,'New pending boot was not observed'
deadline=time.monotonic()+90
while time.monotonic()<deadline:
    after=status();chip=after['chip']
    if after['fresh'] and chip['boot_id'] not in (before['chip']['boot_id'],pending['boot_id']) and chip['confirmed']:
        assert chip['image_sha256']==before['chip']['image_sha256'],chip
        if after['job']['state']=='failed':break
    time.sleep(.5)
assert after['job']['state']=='failed' and 'rollback' in after['job']['message']
result={'passed':True,'method':'RTS reset before new boot confirmation; not a physical power-cut test','before':before['chip'],'pending':pending,'after':after}
(root/'output/testing/ota-live-rollback.json').write_text(json.dumps(result,indent=2));print('Rollback restored the previous confirmed firmware; GUI/API did not report success',flush=True)
client.close()
