import struct
from pathlib import Path
d=Path('.runtime/ota-backups/before-ota-20261120.bin').read_bytes()
parts=[]
for off in range(0x8000,0x8c00,32):
    row=struct.unpack_from('<HBBII16sI',d,off)
    if row[0]!=0x50aa: break
    parts.append(dict(type=row[1],subtype=row[2],offset=hex(row[3]),size=hex(row[4]),label=row[5].split(b'\0')[0].decode()))
print('Original partitions:',parts)
keys=set()
for page in range(0x9000,0xf000,4096):
    for off in range(page+64,page+4096,32):
        key=d[off+8:off+24].split(b'\0')[0]
        if key and all(32<=c<127 for c in key): keys.add(key.decode())
print('NavSphere credential keys present:', sorted(keys.intersection({'wifi_ssid','wifi_pass','mqtt_uri','mqtt_user','mqtt_pass','device_id','navsphere'})))
