import os, json, time, hashlib
from pathlib import Path
from datetime import datetime, timezone
import httpx

version = json.loads(Path('version.json').read_text(encoding='utf-8'))
report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'release': version,
          'firmware_sha256':hashlib.sha256(Path('build/firmware.bin').read_bytes()).hexdigest(),
          'interfaces': {}}
for origin in ('http://127.0.0.1:8000', 'http://192.168.9.59:5173'):
    with httpx.Client(base_url=origin, timeout=15) as c:
        r=c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']});r.raise_for_status()
        snapshots=[]
        for i in range(2):
            r=c.get('/api/v1/can/latest?current_boot_only=true');r.raise_for_status()
            value=r.json(); assert value['frames']
            assert all(f['boot_id']==value['current_boot_id'] for f in value['frames'])
            assert value['status']['sw_version']==version['sw_version']
            snapshots.append(value)
            if i==0:time.sleep(4)
        old={ (f['can_id'],f['extended'],f['rtr']):f for f in snapshots[0]['frames'] }
        changed=[f for f in snapshots[1]['frames'] if (prior:=old.get((f['can_id'],f['extended'],f['rtr']))) and f['sequence']>prior['sequence'] and f['received_at']>prior['received_at']]
        assert changed, 'Latest values did not advance'
        all_saved=c.get('/api/v1/can/latest').json()
        assert len(all_saved['frames'])>=len(snapshots[-1]['frames'])
        report['interfaces'][origin]={'current_ids':len(snapshots[-1]['frames']),
            'all_saved_ids':len(all_saved['frames']), 'advanced_ids':[hex(f['can_id']) for f in changed],
            'snapshots':snapshots}
Path('output/testing/redeploy-20261119-can-live.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({origin:{k:v for k,v in data.items() if k!='snapshots'} for origin,data in report['interfaces'].items()},indent=2))
