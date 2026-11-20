from pathlib import Path
import json,sys,time,subprocess
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.services.ota_image import inspect_image
import httpx
auth=json.loads((root/'.runtime/ota-session.json').read_text())
c=httpx.Client(base_url='http://127.0.0.1:8000',cookies=auth['cookie'],timeout=15)
def status():
    r=c.get('/api/v1/ota');r.raise_for_status();return r.json()
before=status();assert before['fresh'] and before['chip']['confirmed'] and before['chip']['state']=='idle' and not before['busy']
assert c.get('/api/v1/can/tx').json()['state']['enabled'] is False
device=next(v for v in c.get('/api/v1/devices').json()['devices'] if v['device_id']=='ESP32_001');assert device['controls']=={'A':0,'B':0}
address={'ota_0':'0x10000','ota_1':'0x200000'}[before['chip']['partition']]
image=root/'build/firmware.bin';_,info=inspect_image('app.bin',image.read_bytes())
python=r'C:\Espressif\tools\python\v6.0.2\venv\Scripts\python.exe'
base=[python,'-m','esptool','--chip','esp32','--port','COM3','--baud','460800']
with (root/'.runtime/ota-final-restore.log').open('w') as log:
    subprocess.run(base+['write-flash','--flash-mode','dio','--flash-freq','40m','--flash-size','4MB','0x1000',str(root/'build/bootloader/bootloader.bin'),'0x8000',str(root/'build/partition_table/partition-table.bin'),address,str(image)],stdout=log,stderr=subprocess.STDOUT,check=True)
    nvs=root/'.runtime/ota-backups/after-nvs.bin'
    subprocess.run(base+['read-flash','0x9000','0x6000',str(nvs)],stdout=log,stderr=subprocess.STDOUT,check=True)
original=(root/'.runtime/ota-backups/before-ota-20261120.bin').read_bytes()[0x9000:0xF000]
identical=nvs.read_bytes()==original
deadline=time.monotonic()+90
while time.monotonic()<deadline:
    after=status();chip=after['chip']
    if after['fresh'] and chip['boot_id']!=before['chip']['boot_id'] and chip['confirmed'] and chip['image_sha256']==info['image_sha256'] and chip['version']==info['version']:break
    time.sleep(.5)
else:raise AssertionError('Final image was not confirmed on the chip')
report={'passed':True,'final_install_method':'USB restoration after intentional rollback test; same image previously passed OTA','write_offset':address,'before':before['chip'],'chip':chip,'nvs_byte_identical':identical,'original_backup_bytes':4194304,'image':info}
(root/'output/testing/ota-final-hardware-state.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'version':chip['version'],'partition':chip['partition'],'nvs_byte_identical':identical,'confirmed':chip['confirmed']}))
