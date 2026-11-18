import os,json,time,httpx
from pathlib import Path
from datetime import datetime,timezone
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as c:
 r=c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']});r.raise_for_status()
 rows=[]
 for i in range(2):
  latest=c.get('/api/v1/can/latest').json();stats=c.get('/api/v1/can/statistics').json()
  rows.append({'time':datetime.now(timezone.utc).isoformat(),'latest':latest,'stats':stats})
  if i==0:time.sleep(4)
 Path('output/testing/can-gui-before-fix.json').write_text(json.dumps(rows,indent=2))
 for row in rows:
  print('SNAPSHOT',row['time'],'status',row['latest']['status'],'metrics',row['latest']['metrics'])
  print('FIRST IDS',[(hex(f['can_id']),f['sequence'],f['data'],f['received_at'],f['boot_id'],f['frame_count']) for f in row['latest']['frames'][:10]])
  print('LATEST',sorted([(f['received_at'],hex(f['can_id']),f['data'],f['sequence']) for f in row['latest']['frames']],reverse=True)[:5])
  print('CONFLICTS',len(row['latest']['dbc_library']['conflicts']))
