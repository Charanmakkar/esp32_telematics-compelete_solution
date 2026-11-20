from pathlib import Path
import json,sys,time
sys.path.append(r'C:\Espressif\tools\python\v6.0.2\venv\Lib\site-packages')
import httpx,serial
auth=json.loads(Path('.runtime/ota-session.json').read_text())
c=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],timeout=15)
before=c.get('/api/v1/ota').json();assert before['job']['state']=='transferring' and 10<before['job']['progress']<90
port=serial.Serial();port.port='COM3';port.baudrate=115200;port.dtr=False;port.rts=False;port.open();port.rts=True;time.sleep(.1);port.rts=False;port.close()
deadline=time.monotonic()+70
while time.monotonic()<deadline:
    after=c.get('/api/v1/ota').json();chip=after['chip']
    if after['fresh'] and chip['boot_id']!=before['chip']['boot_id'] and chip['confirmed'] and not after['busy']:
        assert chip['image_sha256']==before['chip']['image_sha256'];assert chip['state']=='idle';assert after['job']['state']=='failed';break
    time.sleep(.5)
else:raise AssertionError('Reset recovery was not confirmed')
Path('output/testing/ota-live-transfer-reset.json').write_text(json.dumps({'passed':True,'method':'RTS reset mid-transfer; not a physical power cut','before':before,'after':after},indent=2))
print('Reset during %.1f%% transfer preserved the previous confirmed image and released OTA locks'%before['job']['progress'])
