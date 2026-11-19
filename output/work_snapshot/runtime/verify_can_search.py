import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'interfaces': {}}
for origin in ('http://127.0.0.1:8000', 'http://192.168.9.59:5173'):
    with httpx.Client(base_url=origin, timeout=15) as client:
        client.post('/api/v1/auth/login', json={'username': 'admin', 'password': os.environ['NAV_TEST_PASSWORD']}).raise_for_status()
        def get(term):
            response = client.get('/api/v1/can/latest', params={'search': term, 'current_boot_only': True})
            response.raise_for_status()
            return response.json()
        first = get('0x06E')
        assert [f['can_id'] for f in first['frames']] == [0x6e]
        time.sleep(3)
        second = get('0x06E')
        assert second['frames'][0]['sequence'] > first['frames'][0]['sequence']
        assert second['frames'][0]['received_at'] > first['frames'][0]['received_at']
        names = get('bms_vcu')
        assert names['frames'] and all('bms_vcu' in f['message_name'].lower() for f in names['frames'])
        raw = get('FF 03 00 81')
        assert raw['frames'] and all('FF030081' in f['data'] for f in raw['frames'])
        assert not get('no-such-message')['frames']
        cleared = get('')
        assert len(cleared['frames']) > 1
        report['interfaces'][origin] = {
            'id_samples': [first['frames'][0], second['frames'][0]],
            'name_matches': len(names['frames']), 'raw_matches': len(raw['frames']),
            'clear_restores_ids': len(cleared['frames']), 'reported_firmware': second['status']['sw_version']}
Path('output/testing/can-search-live-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({origin: {k: v for k, v in info.items() if k != 'id_samples'} for origin, info in report['interfaces'].items()}, indent=2))
