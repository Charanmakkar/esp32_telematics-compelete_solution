"""Bench integration test: only the two user-approved periodic frames are enabled."""
import hashlib
import json
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import can
import httpx
import serial

report = {'time_utc': datetime.now(timezone.utc).isoformat(),
          'release': json.loads(Path('version.json').read_text()),
          'firmware_sha256': hashlib.sha256(Path('build/firmware.bin').read_bytes()).hexdigest()}
records = []
errors = []
running = threading.Event()
running.set()
bus = can.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000, state=can.BusState.ACTIVE)

def receive():
    while running.is_set():
        frame = bus.recv(.05)
        if frame is not None:
            now = time.monotonic()
            if frame.is_error_frame:
                errors.append(now)
            else:
                records.append((now, frame.timestamp, frame.arbitration_id, bytes(frame.data).hex().upper(),
                                frame.dlc, frame.is_extended_id, frame.is_remote_frame))

reader = threading.Thread(target=receive, daemon=True)
reader.start()
serial_port = serial.Serial()
serial_port.port, serial_port.baudrate, serial_port.timeout = 'COM3', 115200, .05
serial_port.dtr = serial_port.rts = False
serial_port.open()
serial_bytes = bytearray()
def receive_serial():
    while running.is_set():
        serial_bytes.extend(serial_port.read(max(serial_port.in_waiting, 1)))
serial_reader = threading.Thread(target=receive_serial, daemon=True)
serial_reader.start()

def window(seconds):
    start = time.monotonic()
    time.sleep(seconds)
    finish = time.monotonic()
    return [f for f in records if start <= f[0] <= finish]

def target_frames(frames):
    return [f for f in frames if f[2] in (0x014, 0x548) and not f[5]]

with httpx.Client(base_url='http://127.0.0.1:8000', timeout=15) as client:
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': os.environ['NAV_TEST_PASSWORD']})
    login.raise_for_status()
    client.headers['X-CSRF-Token'] = login.json()['csrf_token']
    def get(path):
        result = client.get(path); result.raise_for_status(); return result.json()
    def toggle(enabled):
        result = client.post('/api/v1/can/tx', json={'device_id': 'ESP32_001', 'enabled': enabled})
        result.raise_for_status()
        value = result.json()
        report.setdefault('commands', []).append(value)
        assert value['state']['enabled'] is enabled, value
        return value
    activated = False
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = get('/api/v1/can/tx')
            if ready['fresh'] and ready.get('clock_ready'):
                break
            time.sleep(1)
        report['initial'] = get('/api/v1/can/tx')
        assert report['initial']['fresh'], report['initial']
        assert report['initial'].get('clock_ready'), 'ESP32 clock did not synchronize'
        if report['initial']['state']['enabled']:
            report['state_before_test'] = report['initial']
            toggle(False)
            time.sleep(.3)
            report['initial'] = get('/api/v1/can/tx')
        assert not report['initial']['state']['enabled'], 'Expected default OFF after flash'
        baseline = window(3)
        report['baseline_target_frames'] = target_frames(baseline)
        report['baseline_frames'] = len(baseline)
        assert baseline, 'No bus traffic'
        assert not report['baseline_target_frames'], 'Another source is still transmitting a target ID'
        report['can_before'] = get('/api/v1/can/statistics')
        report['telemetry_before'] = get('/api/v1/telemetry/latest?device_id=ESP32_001')
        activated = True
        toggle(True)
        print('ESP32 confirmed ON; measuring CAN wire timing for 10 seconds.', flush=True)
        time.sleep(.5)
        frames = window(10)
        report['timing'] = {}
        for can_id, payload, dlc, period in ((0x014, '006000', 3, 100), (0x548, '0000000000000008', 8, 10)):
            selected = [f for f in frames if f[2] == can_id and not f[5]]
            assert selected, f'Missing {can_id:#x} on PCAN'
            assert all(f[3] == payload and f[4] == dlc and not f[6] for f in selected)
            intervals = [(b[1] - a[1])*1000 for a,b in zip(selected, selected[1:])]
            result = {'frames': len(selected), 'payload': payload, 'dlc': dlc, 'requested_period_ms': period,
                      'mean_ms': statistics.mean(intervals), 'median_ms': statistics.median(intervals),
                      'min_ms': min(intervals), 'max_ms': max(intervals),
                      'p95_ms': sorted(intervals)[int(len(intervals)*.95)]}
            report['timing'][f'0x{can_id:03X}'] = result
            assert abs(result['mean_ms'] - period) < period*.05, result
            assert result['max_ms'] < period*2, result
        report['active'] = get('/api/v1/can/tx')
        assert report['active']['state']['enabled']
        assert report['active']['state']['failures'] == report['initial']['state']['failures'], report['active']
        toggle(False); activated = False
        time.sleep(.3)
        report['off_target_frames'] = target_frames(window(3))
        assert not report['off_target_frames'], 'Target frames continue after confirmed OFF'
        report['can_after'] = get('/api/v1/can/statistics')
        report['telemetry_after'] = get('/api/v1/telemetry/latest?device_id=ESP32_001')
        assert report['can_after']['device']['rx_total'] > report['can_before']['device']['rx_total']
        assert report['telemetry_after']['persisted']['sequence'] > report['telemetry_before']['persisted']['sequence']
        report['final'] = get('/api/v1/can/tx')
        assert report['final']['mode'] == 'listen_only'
        report['error_frames'] = len(errors)
        report['pcan_status'] = bus.status_string()
        report['passed'] = True
        print(json.dumps({'timing': report['timing'], 'off_frames': len(report['off_target_frames']),
                          'errors': report['error_frames'], 'final': report['final']}, indent=2), flush=True)
    except Exception as exc:
        report['passed'] = False
        report['error'] = str(exc)
        report['failed_can_status'] = get('/api/v1/can/statistics')
        report['wire_target_frames'] = target_frames(records)
        report['error_frames'] = len(errors)
        print(json.dumps({'error': str(exc), 'controller': report['failed_can_status'].get('device'),
                          'target_frames': len(report['wire_target_frames']), 'error_frames': len(errors)}, indent=2), flush=True)
        raise
    finally:
        if activated:
            try: toggle(False)
            except Exception as exc: report['cleanup_error'] = str(exc)
        running.clear(); reader.join(2); serial_reader.join(2); serial_port.close(); bus.shutdown()
        serial_text = serial_bytes.decode('utf-8', 'replace')
        Path('.runtime/can-tx-live-serial.log').write_text(serial_text, encoding='utf-8')
        report['serial_tx_failures'] = [s for s in serial_text.splitlines() if 'CAN_TX_FAILED' in s]
        report['serial_tx_pin'] = [s for s in serial_text.splitlines() if 'CAN_TX_PIN' in s]
        print(json.dumps({'serial_tx_failure_count': len(report['serial_tx_failures']),
                          'serial_tx_failures': report['serial_tx_failures'][:3],
                          'serial_tx_pin': report['serial_tx_pin'][:3]}), flush=True)
        Path('output/testing/can-tx-live.json').write_text(json.dumps(report, indent=2))
