from pathlib import Path
import json
from dotenv import dotenv_values
import httpx
root=Path(__file__).resolve().parents[1]
values=dotenv_values(root/'.runtime/ota-test.env',encoding='utf-8-sig')
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as client:
    r=client.post('/api/v1/auth/login',json={'username':values['NAV_TEST_USERNAME'],'password':values['NAV_TEST_PASSWORD']})
    print('Login HTTP',r.status_code);r.raise_for_status()
    (root/'.runtime/ota-session.json').write_text(json.dumps({'cookie':dict(client.cookies),'csrf':r.json()['csrf_token']}))
    for path in ('/api/v1/health/ready','/api/v1/devices/ESP32_001/status','/api/v1/can/tx'):
        reply=client.get(path); print(path,reply.status_code,json.dumps(reply.json()))
