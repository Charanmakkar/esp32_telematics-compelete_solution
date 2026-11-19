import json
import time
from pathlib import Path
import serial

version = json.loads(Path('version.json').read_text())
port = serial.Serial()
port.port, port.baudrate, port.timeout = 'COM3', 115200, .1
port.dtr = port.rts = False
raw = bytearray()
with port:
    end = time.monotonic() + 20
    while time.monotonic() < end:
        raw.extend(port.read(max(port.in_waiting, 1)))
text = raw.decode('utf-8', 'replace')
Path('.runtime/can-tx-serial.log').write_text(text, encoding='utf-8')
lines = text.splitlines()
report = {'port': 'COM3', 'version': version, 'identity': [s for s in lines if 'SW_VERSION=' in s],
          'status': [s for s in lines if 'CAN_STATUS' in s],
          'serial_can_frames': sum('CAN seq=' in s for s in lines),
          'errors': [s for s in lines if 'Guru Meditation' in s or 'assert failed' in s]}
Path('output/testing/can-tx-serial.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert not report['errors']
assert any('SW_VERSION=' + version['sw_version'] in s for s in report['identity'])
