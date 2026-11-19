import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import httpx
from sqlalchemy import create_engine, text

root=Path.cwd()
sys.path.insert(0,str(root/'backend'))
from app.core.config import Settings
version=json.loads((root/'version.json').read_text())
report={'time_utc':datetime.now(timezone.utc).isoformat(),'version':version,
        'firmware_sha256':hashlib.sha256((root/'build/firmware.bin').read_bytes()).hexdigest(),
        'application_offset':'0x10000','port':'COM3','mac':'ec:62:60:9c:40:84',
        'nvs_written':False,'interfaces':{}}
flash=(root/'.runtime/redeploy-20261119-flash.log').read_text(encoding='utf-8',errors='replace')
assert flash.count('Hash of data verified.')==1
assert report['mac'] in flash
serial=json.loads((root/'output/testing/redeploy-20261119-serial.json').read_text())
assert any('SW_VERSION=1.1.4 BUILD=2ae749ea5903' in line for line in serial['identity'])
report['serial']=serial
engine=create_engine(Settings(_env_file=str(root/'backend/.env')).db_url)
with engine.connect() as c:
    first_id=c.execute(text('SELECT MAX(id) FROM telemetry_readings')).scalar_one()
for origin in ('http://127.0.0.1:8000','http://192.168.9.59:5173'):
    with httpx.Client(base_url=origin,timeout=15) as c:
        c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']}).raise_for_status()
        before=c.get('/api/v1/health').json()
        time.sleep(3)
        after=c.get('/api/v1/health').json()
        assert after['mqtt_connected'] and after['database_connected']
        assert after['metrics']['persisted']>before['metrics']['persisted']
        current=c.get('/api/v1/can/latest?current_boot_only=true').json()
        assert current['status']['sw_version']==version['sw_version']
        assert current['status']['sw_build']==version['source_sha256'][:12]
        stats=c.get('/api/v1/can/statistics').json()
        assert stats['age_seconds']<5
        all_saved=c.get('/api/v1/can/latest').json()
        report['interfaces'][origin]={'analog_rows_persisted_in_3_seconds':after['metrics']['persisted']-before['metrics']['persisted'],
            'current_can_ids':len(current['frames']),'saved_can_ids':len(all_saved['frames']),
            'can_status':current['status'],'health':after}
with engine.connect() as c:
    report['new_analog_database_rows']=c.execute(text('SELECT COUNT(*) FROM telemetry_readings WHERE id>:first'),{'first':first_id}).scalar_one()
    assert report['new_analog_database_rows']>0
engine.dispose()
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
kernel.CreateFileW.restype=wintypes.HANDLE
kernel.CloseHandle.argtypes=[wintypes.HANDLE]
handle=kernel.CreateFileW(r'\\.\COM3',0xC0000000,0,None,3,0,None)
if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
assert kernel.CloseHandle(handle)
report['com3_released']=True
report['can_receive_verified']=any(v['current_can_ids'] for v in report['interfaces'].values())
(root/'output/testing/redeploy-20261119-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'version':version['sw_version'],'new_analog_database_rows':report['new_analog_database_rows'],'can_receive_verified':report['can_receive_verified'],'com3_released':True},indent=2))
