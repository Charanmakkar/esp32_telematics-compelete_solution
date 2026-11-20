from pathlib import Path
import json,time,httpx
a=json.loads(Path('.runtime/ota-session.json').read_text())
p=Path('output/testing/ota-user-update-v1.1.21.json');report=json.loads(p.read_text())
original=report['observed_during'];job_id=original['job']['id']
deadline=time.monotonic()+240
with httpx.Client(base_url='http://127.0.0.1:8000',cookies=a['cookie'],timeout=15) as c:
 while time.monotonic()<deadline:
  response=c.get('/api/v1/ota');response.raise_for_status();s=response.json()
  assert s['job']['id']==job_id,'User started a different update; preserve the original observation'
  print(json.dumps({'state':s['job']['state'],'progress':s['job']['progress']}),flush=True)
  if s['job']['state'] in ('confirmed','failed','unconfirmed'):
   report['after']=s;report['passed']=s['job']['state']=='confirmed' and s['chip']['version']=='1.1.21' and s['chip']['confirmed'] and s['chip']['image_sha256']==s['job']['image']['image_sha256'] and s['chip']['boot_id']!=original['chip']['boot_id']
   p.write_text(json.dumps(report,indent=2),encoding='utf-8')
   assert report['passed'],s['job']['message']
   print('User update confirmed by the chip.',flush=True)
   break
  time.sleep(5)
 else:raise AssertionError('Update remains in progress; no modifications made')
