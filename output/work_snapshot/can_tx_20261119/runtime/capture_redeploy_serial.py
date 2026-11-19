import json
from pathlib import Path
import time
from datetime import datetime, timezone
import serial

version = json.loads(Path('version.json').read_text())
port = serial.Serial()
port.port, port.baudrate, port.timeout = 'COM3', 115200, .1
port.dtr = port.rts = False
raw = bytearray()
with port:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        raw.extend(port.read(max(port.in_waiting, 1)))
text = raw.decode('utf-8', 'replace')
Path('.runtime/redeploy-20261119-serial.log').write_text(text, encoding='utf-8')
lines = text.splitlines()
frames = [line for line in lines if 'CAN seq=' in line]
identity = [line for line in lines if 'SW_VERSION=' in line]
report = dict(time_utc=datetime.now(timezone.utc).isoformat(), port='COM3', baud=115200,
              seconds=20, sw_version=version['sw_version'], sw_build=version['source_sha256'][:12],
              identity=identity, can_serial_frames=len(frames), examples=frames[:5],
              status=[line for line in lines if 'CAN_STATUS' in line])
Path('output/testing/redeploy-20261119-serial.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert any(f"SW_VERSION={version['sw_version']}" in line for line in identity), 'Version not captured on serial'
assert frames, 'No CAN frames captured on serial'
