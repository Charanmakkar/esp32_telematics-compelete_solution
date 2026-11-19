import argparse
import collections
import json
import threading
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

import can
sys.path.append('C:/Espressif/tools/python/v6.0.2/venv/Lib/site-packages')
import serial

p = argparse.ArgumentParser()
p.add_argument('label')
p.add_argument('--seconds', type=float, default=15)
a = p.parse_args()
out = Path('output/testing')
out.mkdir(exist_ok=True)
bus = can.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
port = serial.Serial()
port.port = 'COM3'
port.baudrate = 115200
port.timeout = .1
port.dtr = False
port.rts = False
counts = collections.Counter()
errors = 0
raw = bytearray()
stop = threading.Event()

def capture_can():
    global errors
    while not stop.is_set():
        m = bus.recv(.05)
        if m is not None:
            counts[f'0x{m.arbitration_id:03X}'] += 1
            errors += int(m.is_error_frame)

t = threading.Thread(target=capture_can)
started = datetime.now(timezone.utc).isoformat()
try:
    port.open()
    t.start()
    end = time.monotonic() + a.seconds
    while time.monotonic() < end:
        raw.extend(port.read(max(port.in_waiting, 1)))
    status = bus.status_string()
finally:
    stop.set()
    if t.is_alive():
        t.join(1)
    port.close()
    bus.shutdown()
log = raw.decode('utf-8', 'replace')
Path(f'.runtime/{a.label}-serial.log').write_text(log, encoding='utf-8')
lines = log.splitlines()
can_lines = [s for s in lines if 'CAN seq=' in s]
report = dict(time_utc=started, duration_seconds=a.seconds, serial_port='COM3',
              pcan_frames=sum(counts.values()), pcan_ids=dict(counts),
              pcan_error_frames=errors, pcan_status=status,
              serial_can_frames=len(can_lines), serial_can_examples=can_lines[:5],
              serial_lines=len(lines),
              serial_status=[s for s in lines if any(x in s for x in
                            ('can:', 'resources:', 'ELF file SHA256:', 'Project name:',
                             'App version:', 'Compile time:', 'chip revision:',
                             'CAN_STATUS', 'CAN_BUILD'))][-30:],
              can_requests_sent=False)
(out / f'{a.label}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
