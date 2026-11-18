import os,json,time,httpx,hashlib
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as c:
 r=c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']});r.raise_for_status();c.headers['X-CSRF-Token']=r.json()['csrf_token']
 before=c.get('/api/v1/can/statistics').json()
 r=c.post('/api/v1/bms/read',json=dict(device_id='ESP32_001',command='serial'));r.raise_for_status();ident=r.json()['id']
 deadline=time.monotonic()+25
 while time.monotonic()<deadline:
  result=c.get('/api/v1/bms/jobs/'+ident).json()
  if result['status'] not in ('queued','running'):break
  time.sleep(.25)
 after=c.get('/api/v1/can/statistics').json()
 report=dict(time_utc=datetime.now(timezone.utc).isoformat(),firmware_sha256=hashlib.sha256((root/'build/firmware.bin').read_bytes()).hexdigest(),job=result,stats_before=before,stats_after=after,destructive_tests_run=False)
 (root/'output/testing/be-esp32-live-read.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(result,indent=2))
