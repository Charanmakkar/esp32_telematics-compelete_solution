from pathlib import Path
import json,time,httpx
auth=json.loads(Path('.runtime/ota-session.json').read_text())
c=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],headers={'X-CSRF-Token':auth['csrf']},timeout=20)
ota=c.get('/api/v1/ota').json();assert ota['chip']['state']=='idle' and not ota['busy']
assert c.get('/api/v1/can/tx').json()['state']['enabled'] is False
r=c.post('/api/v1/bms/read',json={'device_id':'ESP32_001','instance':1,'ecu':'abs_hv','command':'hardware'})
result={'read_only_hardware_query':True,'chip':ota['chip'],'http':r.status_code,'initial':r.json()}
if r.is_success:
    job=r.json();id=job['id'];deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        job=c.get('/api/v1/bms/jobs/'+id).json()
        if job['status'] not in ('queued','running'):break
        time.sleep(.5)
    result['result']=job
    if job['status'] in ('queued','running'):
        c.post('/api/v1/bms/jobs/'+id+'/cancel').raise_for_status()
result['can_after']=c.get('/api/v1/can/tx').json()
result['passed']=r.is_success and result.get('result',{}).get('status')=='completed' and result['can_after']['state']['enabled'] is False
Path('output/testing/ota-live-bms-read.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'http':r.status_code,'status':result.get('result',{}).get('status'),'result':result.get('result',{}).get('result')},indent=2))
assert result['passed'], 'Read-only BMS regression failed; inspect saved evidence'
