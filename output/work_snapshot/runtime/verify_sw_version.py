import os
import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

version = json.loads(Path('version.json').read_text())
with httpx.Client(base_url='http://127.0.0.1:8000', timeout=15) as c:
    r = c.post('/api/v1/auth/login', json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']})
    r.raise_for_status()
    before = c.get('/api/v1/can/statistics').json()
    time.sleep(6)
    after = c.get('/api/v1/can/statistics').json()
    latest = c.get('/api/v1/can/latest').json()
    analog = c.get('/api/v1/telemetry/latest').json()
    ready = c.get('/api/v1/health/ready').json()
    device = after['device']
    assert ready['ready'] and after['age_seconds'] < 5
    assert before['boot_id'] == after['boot_id']
    assert device['sw_version'] == version['sw_version']
    assert device['sw_build'] == version['source_sha256'][:12]
    assert device['diag_version'] == 3 and device['mode'] == 'listen_only'
    delta = device['rx_total'] - before['device']['rx_total']
    persisted = after['server']['persisted'] - before['server']['persisted']
    assert delta > 0 and persisted > 0 and latest['frames']
    assert analog['persisted']['boot_id'] == after['boot_id']
    report = dict(time_utc=datetime.now(timezone.utc).isoformat(), release=version,
                  firmware_sha256=hashlib.sha256(Path('build/firmware.bin').read_bytes()).hexdigest(),
                  ready=ready, before=before, after=after, can_capture_delta=delta,
                  can_database_delta=persisted, latest_can_ids=len(latest['frames']),
                  latest_examples=latest['frames'][:3], analog=analog['persisted'],
                  gui_build=json.loads(Path('frontend/dist/sw-version.json').read_text()))
    Path('output/testing/sw-version-live-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('release','firmware_sha256','ready','can_capture_delta','can_database_delta','latest_can_ids','gui_build')},indent=2))
