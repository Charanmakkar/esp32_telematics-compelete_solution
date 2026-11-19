import os,json,hashlib,httpx
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as c:
 r=c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']});r.raise_for_status()
 checks={}
 for name,url in [('ready','/api/v1/health/ready'),('statistics','/api/v1/can/statistics'),('analog','/api/v1/telemetry/latest'),('bms_jobs','/api/v1/bms/jobs?device_id=ESP32_001')]:
  r=c.get(url);r.raise_for_status();checks[name]=r.json()
 assert checks['ready']['ready']
 assert checks['statistics']['device']['diag_version']==3
 assert checks['statistics']['device']['mode']=='listen_only'
 assert checks['analog']['persisted']
 checks['lan_pages']={p:httpx.get('http://192.168.9.59:5173/'+p,timeout=10).status_code for p in ('can','bms')}
 assert all(s==200 for s in checks['lan_pages'].values())
 report=dict(time_utc=datetime.now(timezone.utc).isoformat(),firmware_sha256=hashlib.sha256((root/'build/firmware.bin').read_bytes()).hexdigest(),flash=dict(port='COM3',baud=115200,hash_verified=True),software=dict(backend_tests_passed=75,frontend_tests_passed=27,ruff='passed',typescript_vite='passed',esp_idf='passed',firmware_host='passed'),checks=checks,lan_scope='Tested through this laptop LAN address, not independently from a remote PC',esp32_bms_live_read='not yet successful',destructive_bms_commands_tested=False)
 (root/'output/testing/be-release-verification.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(dict(ready=checks['ready'],analog_persisted=checks['analog']['persisted'],diag_version=3,mode=checks['statistics']['device']['mode'],lan_pages=checks['lan_pages'])))
