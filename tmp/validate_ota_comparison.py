from pathlib import Path
import hashlib
import json
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.services.ota_image import MAX_IMAGE, inspect_image

package = root / 'output/firmware'
manifest = json.loads((package / 'manifest.json').read_text())
for name, entry in manifest['files'].items():
    blob = (package / name).read_bytes()
    assert len(blob) == entry['bytes']
    assert hashlib.sha256(blob).hexdigest() == entry['sha256']
data, info = inspect_image('navsphere.bin', (package / 'navsphere.bin').read_bytes())
assert info['version'] == manifest['sw_version']
assert MAX_IMAGE == 1984 * 1024

def record(kind, address, payload=b''):
    raw = bytes([len(payload)]) + address.to_bytes(2, 'big') + bytes([kind]) + payload
    return ':' + (raw + bytes([-sum(raw) & 255])).hex()

lines = []
upper = None
for offset in range(0, len(data), 32):
    address = 0x10000 + offset
    if address >> 16 != upper:
        upper = address >> 16
        lines.append(record(4, 0, upper.to_bytes(2, 'big')))
    lines.append(record(0, address & 65535, data[offset:offset + 32]))
lines.append(record(1, 0))
decoded, hex_info = inspect_image('navsphere.hex', ('\n'.join(lines) + '\n').encode())
assert decoded == data
assert hex_info['image_sha256'] == info['image_sha256']
with zipfile.ZipFile(root / 'output/NavSphere_Source_and_Docs.zip') as release:
    assert release.read('NavSphere/output/firmware/navsphere.bin') == data
    assert json.loads(release.read('NavSphere/output/firmware/manifest.json')) == manifest
gui = json.loads((root / 'frontend/dist/sw-version.json').read_text())
assert gui == {'sw_version': manifest['sw_version'], 'sw_build': manifest['sw_build']}
print(json.dumps({'binary_and_hex_actual_release': 'passed', 'package_hashes': 'passed',
                  'gui_firmware_identity': 'passed', 'version': info['version'],
                  'app_limit_kib': MAX_IMAGE // 1024, 'application_bytes': len(data)}))
