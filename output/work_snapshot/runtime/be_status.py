import os,json,httpx
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as c:
 r=c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']});r.raise_for_status()
 for url in ('/api/v1/health/ready','/api/v1/can/statistics','/api/v1/bms/catalog'):
  v=c.get(url).json()
  if url.endswith('catalog'):v={'error':v['error'],'metadata':v['metadata']}
  if url.endswith('statistics'):v={k:v.get(k) for k in ('available','age_seconds','boot_id','device','hardware_fps')}
  print(url,json.dumps(v))
