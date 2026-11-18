import can,os,json,time,httpx,threading
from pathlib import Path
from datetime import datetime,timezone
bus=can.Bus(interface='pcan',channel='PCAN_USBBUS1',bitrate=500000,receive_own_messages=True)
frames=[];stop=threading.Event();start=time.monotonic()
def capture():
 while not stop.is_set():
  m=bus.recv(.05)
  if m:frames.append(dict(t=round(time.monotonic()-start,6),id=m.arbitration_id,data=m.data.hex().upper(),error=m.is_error_frame,rx=m.is_rx))
worker=threading.Thread(target=capture);worker.start()
try:
 with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as c:
  r=c.post('/api/v1/auth/login',json={'username':'admin','password':os.environ['NAV_TEST_PASSWORD']});r.raise_for_status();c.headers['X-CSRF-Token']=r.json()['csrf_token']
  time.sleep(3);before=c.get('/api/v1/can/statistics').json()
  r=c.post('/api/v1/bms/read',json=dict(device_id='ESP32_001',command='serial'));r.raise_for_status();ident=r.json()['id']
  deadline=time.monotonic()+25
  while time.monotonic()<deadline:
   result=c.get('/api/v1/bms/jobs/'+ident).json()
   if result['status'] not in ('queued','running'):break
   time.sleep(.25)
  time.sleep(2);after=c.get('/api/v1/can/statistics').json()
 report=dict(time_utc=datetime.now(timezone.utc).isoformat(),job=result,pcan_status=bus.status_string(),stats_before=before,stats_after=after,pcan_received_frames=len(frames),diagnostic_frames=[f for f in frames if f['id'] in (0x7E4,0x7EC)],destructive_tests_run=False)
 Path('output/testing/be-dual-interface-read.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k not in ('stats_before','stats_after','diagnostic_frames','job')},indent=2));print('ESP32 stats',json.dumps(after.get('device')));print('Result',json.dumps(result['result']));print('Diagnostic frames',len(report['diagnostic_frames']))
finally:
 stop.set();worker.join(1);bus.shutdown()
