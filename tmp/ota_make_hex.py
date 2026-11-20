from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.services.ota_image import inspect_image
source=Path(sys.argv[1]);data=source.read_bytes()
def record(kind,address,payload=b''):
    raw=bytes([len(payload)])+address.to_bytes(2,'big')+bytes([kind])+payload
    return ':'+(raw+bytes([-sum(raw)&255])).hex()
lines=[];upper=None
for offset in range(0,len(data),32):
    address=0x10000+offset
    if address>>16!=upper:
        upper=address>>16;lines.append(record(4,0,upper.to_bytes(2,'big')))
    lines.append(record(0,address&65535,data[offset:offset+32]))
lines.append(record(1,0))
raw=('\n'.join(lines)+'\n').encode()
decoded,info=inspect_image('navsphere.hex',raw);assert decoded==data
destination=Path(sys.argv[2]);destination.write_bytes(raw)
print('Verified application HEX',info['version'],len(raw),'bytes')
