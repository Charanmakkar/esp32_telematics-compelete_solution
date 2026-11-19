import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import time
import httpx

version = json.loads(Path('version.json').read_text())
wire = json.loads(Path('output/testing/can-tx-live.json').read_text())
wire_passed = wire.get('passed') is True and wire.get('release') == version
report = {'version': version, 'interfaces': {},
          'firmware_sha256': hashlib.sha256(Path('build/firmware.bin').read_bytes()).hexdigest(),
          'live_transmission_verified': wire_passed,
          'power_correction_confirmed_by_user': True,
          'live_test_result': 'PCAN payload, timing and OFF checks passed.' if wire_passed else 'See can-tx-live.json for the latest wire-test failure.'}
for origin in ('http://127.0.0.1:8000', 'http://192.168.9.59:5173'):
    with httpx.Client(base_url=origin, timeout=15) as client:
        client.post('/api/v1/auth/login', json={'username':'admin', 'password':os.environ['NAV_TEST_PASSWORD']}).raise_for_status()
        before = client.get('/api/v1/health').json()
        first = client.get('/api/v1/can/statistics').json()
        time.sleep(3)
        after = client.get('/api/v1/health').json()
        last = client.get('/api/v1/can/statistics').json()
        state = client.get('/api/v1/can/tx').json()
        assert after['mqtt_connected'] and after['database_connected']
        assert after['metrics']['persisted'] > before['metrics']['persisted']
        assert last['device']['rx_total'] > first['device']['rx_total']
        assert last['server']['persisted'] > first['server']['persisted']
        assert last['device']['sw_version'] == version['sw_version']
        assert last['device']['sw_build'] == version['source_sha256'][:12]
        assert state['fresh'] and not state['state']['enabled'] and state['mode'] == 'listen_only'
        report['interfaces'][origin] = {
            'new_analog_database_rows': after['metrics']['persisted'] - before['metrics']['persisted'],
            'new_can_database_rows': last['server']['persisted'] - first['server']['persisted'],
            'device_state': state, 'version_matched': True,
        }
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
handle = kernel.CreateFileW(r'\\.\COM3', 0xC0000000, 0, None, 3, 0, None)
if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
assert kernel.CloseHandle(handle)
report['com3_released'] = True
Path('output/testing/can-tx-verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
