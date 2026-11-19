import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path.cwd()
version = json.loads(Path('version.json').read_text(encoding='utf-8'))
serial = json.loads(Path('output/testing/can-gui-fix-serial.json').read_text())
live = json.loads(Path('output/testing/can-gui-live-verification.json').read_text())
browser = json.loads(Path('output/testing/can-gui-browser-verification.json').read_text())
flash = Path('.runtime/can-gui-fix-flash.log').read_text(encoding='utf-8', errors='replace')
assert flash.count('Hash of data verified.') == 3
assert 'ec:62:60:9c:40:84' in flash
assert serial['sw_version'] == version['sw_version'] == '1.1.3'
assert serial['can_serial_frames'] > 0
assert browser['samples'][0]['raw'] != browser['samples'][1]['raw']
assert all(v['advanced_ids'] for v in live['interfaces'].values())

# Open and close exclusively without configuring DTR/RTS or reading data.
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL
handle = kernel.CreateFileW(r'\\.\COM3', 0xC0000000, 0, None, 3, 0, None)
if handle == ctypes.c_void_p(-1).value:
    raise ctypes.WinError(ctypes.get_last_error())
assert kernel.CloseHandle(handle)

receipt = {
    'time_utc': datetime.now(timezone.utc).isoformat(),
    'sw_version': version['sw_version'], 'sw_build': version['source_sha256'][:12],
    'firmware_sha256': hashlib.sha256(Path('build/firmware.bin').read_bytes()).hexdigest(),
    'port': 'COM3', 'mac': 'ec:62:60:9c:40:84', 'baud': 115200,
    'verified_components': ['bootloader@0x1000', 'partition_table@0x8000', 'application@0x10000'],
    'nvs_written': False, 'serial_capture_seconds': serial['seconds'],
    'can_serial_lines': serial['can_serial_frames'], 'com3_exclusive_open_and_close_passed': True,
    'gui_samples': browser['samples'],
    'interfaces': {origin: {k: v for k, v in data.items() if k != 'snapshots'}
                   for origin, data in live['interfaces'].items()},
    'lan_test_scope': 'Laptop using its LAN address; not a separate remote PC',
    'diagnostic_tx_retested': False,
    'limitations': 'Existing serial/MQTT drops remain; this is not a lossless logging claim.',
}
Path('output/testing/can-gui-flash-verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')

report_path = Path('docs/development/BE_CLIENT_IMPLEMENTATION.md')
report = report_path.read_text(encoding='utf-8')
start = report.index('**Deployment interruption:** the 1.1.3 COM3 flash')
report = report[:start] + '''**Deployment recovered on 18 November 2026:** the first flash lost its USB
connection during the application write, and the second connection timed out.
After the user unplugged and reconnected USB, a complete retry at 115200 baud
succeeded on COM3 (ESP32 MAC `ec:62:60:9c:40:84`). The bootloader, partition
table and application all passed the flash tool's hash verification. NVS was
not written. The application SHA-256 is
`6dc913faf334c11229077318780b2d11552694bd8806c8b5bb04689e128336f0`.

The startup log reported **SW_VERSION=1.1.3**, build `8097dcac11e0`. A
20-second serial capture contained **2,806 CAN frame lines**, with the device
in listen-only mode. Both the direct backend and LAN dashboard address returned
31 current-run IDs; the all-saved view retained 69 IDs. Four-second comparisons
confirmed advancing sequence numbers and database receive timestamps for 21
IDs through the direct backend and 25 through the LAN address. The LAN request
was made from this laptop, not a separate remote PC.

The actual browser showed matching GUI/ESP32 versions and CAN logger online.
For ID 0x06E, the visible raw bytes changed from `BB DB FF 03 00 81 16 00`
at 17:29:06 UTC to `72 D5 FF 03 00 81 16 00` at 17:29:23 UTC; the saved-frame
count advanced from 2,208,252 to 2,208,442. Existing serial and MQTT delivery
drops remain visible in the statistics; this verification does not establish
lossless logging. BMS diagnostic transmission was not retested in this recovery
and its previously recorded failure remains unresolved.

COM3 was closed after capture and an exclusive open/close check passed without
changing the serial control lines. The offline firmware manifest is updated
to `hardware_flashed=true` for this verified build.

Evidence: [flash receipt](../../output/testing/can-gui-flash-verification.json),
[serial capture summary](../../output/testing/can-gui-fix-serial.json),
[backend and LAN comparisons](../../output/testing/can-gui-live-verification.json),
[actual browser value changes](../../output/testing/can-gui-browser-verification.json),
and [live dashboard screenshot](../../output/testing/bms/can-gui-current-run.jpg).
'''
report_path.write_text(report, encoding='utf-8')

implementation = Path('IMPLEMENTATION_REPORT.md')
text = implementation.read_text(encoding='utf-8')
text += '''
The interrupted USB flash was recovered after reconnection on 18 November.
All three firmware components passed flash verification, and startup plus the
GUI confirmed version 1.1.3. Live checks found 31 current-run CAN IDs, retained
69 saved IDs, and verified advancing database records through both the backend
and the laptop's LAN dashboard address. A 20-second serial capture contained
2,806 CAN frame lines. Actual browser samples confirmed changing 0x06E bytes
and counts. COM3 is released; the offline package records this verified flash.
Existing delivery drops and the unresolved BMS diagnostic TX failure remain
documented in the BE report.
'''
implementation.write_text(text, encoding='utf-8')
print(json.dumps({k: v for k, v in receipt.items() if k != 'gui_samples'}, indent=2))
