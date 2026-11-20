from pathlib import Path
import json,time,httpx
auth=json.loads(Path('.runtime/ota-session.json').read_text());c=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],timeout=15)
ota=c.get('/api/v1/ota').json();assert ota['job']['state']=='transferring'
start=time.monotonic();before=c.get('/api/v1/telemetry/latest').json()['persisted'];time.sleep(10)
after=c.get('/api/v1/telemetry/latest').json()['persisted'];elapsed=time.monotonic()-start
assert after['boot_id']==before['boot_id'] and after['sequence']>before['sequence']
result={'passed':True,'during_ota_transfer':True,'start_progress':ota['job']['progress'],'elapsed_s':elapsed,'sequence_advance':after['sequence']-before['sequence'],'observed_sequence_rate_hz':(after['sequence']-before['sequence'])/elapsed,'before':before,'after':after,'note':'Sequence advancement is not a lossless-sampling or voltage-accuracy certification.'}
Path('output/testing/ota-live-during-transfer.json').write_text(json.dumps(result,indent=2));print({k:result[k] for k in ('elapsed_s','sequence_advance','observed_sequence_rate_hz')})
