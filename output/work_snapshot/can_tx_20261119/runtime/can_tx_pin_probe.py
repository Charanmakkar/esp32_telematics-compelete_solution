"""Bounded pin-configuration observation; not a CAN wire-delivery test."""
import json
import os
from pathlib import Path
import threading
import time
import httpx
import serial

data = bytearray()
running = threading.Event()
running.set()
port = serial.Serial()
port.port, port.baudrate, port.timeout = 'COM3', 115200, .05
port.dtr = port.rts = False
result = {'kind': 'pin_configuration_only', 'wire_delivery_verified': False}
with port, httpx.Client(base_url='http://127.0.0.1:8000', timeout=15) as client:
    def capture():
        while running.is_set():
            data.extend(port.read(max(port.in_waiting, 1)))
    reader = threading.Thread(target=capture, daemon=True)
    reader.start()
    response = client.post('/api/v1/auth/login', json={'username':'admin', 'password':os.environ['NAV_TEST_PASSWORD']})
    response.raise_for_status()
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    try:
        response = client.post('/api/v1/can/tx', json={'device_id':'ESP32_001', 'enabled':True})
        result['on_response'] = response.json()
        time.sleep(.5)
    finally:
        response = client.post('/api/v1/can/tx', json={'device_id':'ESP32_001', 'enabled':False})
        result['off_response'] = response.json()
        time.sleep(1)
        running.clear(); reader.join(2)
text = data.decode('utf-8', 'replace')
result['serial'] = [s for s in text.splitlines() if 'CAN_TX_FAILED' in s or 'CAN_TX_PIN' in s]
Path('output/testing/can-tx-pin-probe.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
