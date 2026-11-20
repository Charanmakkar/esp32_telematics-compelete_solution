from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
links = {
    'README.md': 'docs/firmware/OTA_GUIDE.md',
    'firmware/README.md': '../docs/firmware/OTA_GUIDE.md',
    'frontend/README.md': '../docs/firmware/OTA_GUIDE.md',
    'backend/README.md': '../docs/firmware/OTA_GUIDE.md',
    'docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md': '../firmware/OTA_GUIDE.md',
    'docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md': 'OTA_GUIDE.md',
    'output/firmware/README.md': '../../docs/firmware/OTA_GUIDE.md',
}
version = json.loads((root/'version.json').read_text())
identity = f"v{version['sw_version']} / {version['source_sha256'][:12]}"
for name, link in links.items():
    path = root/name
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    if lines[2].startswith('Updated '):
        lines[2] = f'Updated 20 November 2026 for **{identity}**. OTA is implemented and software-checked; USB migration and hardware OTA acceptance remain pending. Last recorded hardware-verified firmware: v1.1.7. See `docs/RELEASE_STATUS.md` for prior CAN/BMS limitations.'
    text = '\n'.join(lines) + '\n'
    marker = '## Wi-Fi OTA update'
    if marker not in text:
        text += f'\n{marker}\n\nOpen **Manage → OTA over Wi-Fi** (`/ota`) to upload an application BIN/Intel HEX,\nreview its target version and update the ESP32 through the existing MQTT connection.\nThe page reports the actual running chip version and image SHA-256; success requires\na new confirmed boot with the uploaded fingerprint. See the [OTA guide]({link})\nfor accepted files, permissions, recovery and the required initial USB migration.\n\nThe packaged firmware now uses two OTA slots. Earlier factory-only flashing\ncommands in this guide are historical: use `scripts/migrate_ota.ps1` for the first\ninstallation. Future application updates use the OTA page. Never erase NVS.\n'
    text = text.replace('No OTA flashing workflow is implemented.', 'The OTA workflow and one-time partition migration are documented in [OTA_GUIDE.md](OTA_GUIDE.md).')
    text = text.replace('Source, GUI and packaged application are v1.1.8 / 8148c3afe9b8.', f'Source, GUI and packaged application are {identity}.')
    old_command = 'python -m esptool --chip esp32 --port COMx --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x10000 output/firmware/navsphere.bin'
    text = text.replace(old_command, 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts/migrate_ota.ps1 -Port COMx')
    text = text.replace('This preserves NVS, bootloader and partition table. Verify the hash and startup', 'The migration preserves NVS and replaces the bootloader, partition table and application. Verify the hash and startup')
    text = text.replace('board needs only the application update, from the repository root in an IDF terminal:', 'board requires the one-time OTA migration below. Future updates use /ota:')
    if name == 'output/firmware/README.md':
        text = text.replace('0x8000 partition-table.bin 0x10000 navsphere.bin', '0x8000 partition-table.bin 0x10000 navsphere.bin 0x3F0000 ota_data_initial.bin')
    path.write_text(text, encoding='utf-8')

for name in ('backend/API_CONTRACT.md', 'docs/api/API_REFERENCE.md'):
    path = root/name
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    lines[2] = f'Updated 20 November 2026 for application {identity}. Existing interfaces are retained; OTA routes are additive.'
    text = '\n'.join(lines) + '\n'
    if '## Firmware OTA API' not in text:
        text += '''
## Firmware OTA API

`GET /api/v1/ota?device_id=ESP32_001` returns live chip identity, freshness,
prepared image and job state. Authenticated viewers may read it.
`POST /api/v1/ota/image?device_id=ESP32_001&filename=app.bin` accepts a raw
`application/octet-stream` body (6 MiB maximum); BIN or app-only Intel HEX is
validated and staged for ten minutes. It returns `upload_id`, version, size,
whole-file SHA-256 and image SHA-256. `POST /api/v1/ota/start` takes
`{"device_id":"ESP32_001","upload_id":"..."}`. Both POSTs require admin,
changed password, session and CSRF token. Busy/stale/migration-required state
returns 409; invalid image returns 400; oversized upload returns 413.

MQTT adds `{prefix}/{device}/ota/request`, `ota/response`, and `ota/status`.
All are non-retained QoS 1. Requests are start/chunk/finish, bound to a UUID
and boot ID. Start includes size, full-file SHA-256 and a maximum 30-second
deadline; chunks contain offset and up to 768 bytes encoded as hex. Responses
echo id/op/offset/boot_id, protocol=1, source=hardware, ok and optional error.
Status contains protocol/source, boot_id, version, build, running image SHA-256,
partition, slot_size, confirmed and state. Success requires a matching image
and new confirmed boot. See docs/firmware/OTA_GUIDE.md for full operation.
'''
    path.write_text(text, encoding='utf-8')

path=root/'docs/README.md'
text=path.read_text(encoding='utf-8')
if '| Wi-Fi OTA' not in text:
    text=text.replace('| Purpose |', '| Purpose |')
    text=text.replace('| Fixed periodic messages', '| Wi-Fi OTA upload, chip confirmation and USB migration | [OTA guide](firmware/OTA_GUIDE.md) |\n| Fixed periodic messages')
text=text.replace('Four regenerated engineering PDFs are in `output/pdf/`.', 'Historical engineering PDFs are in `output/pdf/`; they predate the OTA addition. Use the current Markdown guides for OTA instructions.')
path.write_text(text,encoding='utf-8')

for name in ('docs/testing/HARDWARE_TEST_PLAN.md','firmware/test/HARDWARE_TEST_PLAN.md'):
    path=root/name
    text=path.read_text(encoding='utf-8')
    if '## OTA acceptance' not in text:
        text+='''
## OTA acceptance (pending physical hardware)

- USB migration preserves provisioned NVS; OTA slots and rollback bootloader match the package.
- Upload valid BIN and Intel HEX; verify chip version, boot ID and exact image hash after reboot.
- Update in both slot directions; verify existing ADC/CAN/control/diagnostic behavior afterward.
- Reject corrupt, wrong-chip, oversized, merged, legacy, stale and unauthorized uploads/requests.
- Reject OTA while GPIO outputs, periodic CAN or diagnostic sessions are active.
- Interrupt Wi-Fi and power mid-transfer: old image boots, maintenance gates release, retry succeeds.
- Force new-image startup failure: rollback selects prior firmware and GUI never reports success.
- Measure heap/stack margins and CAN/ADC gaps during transfer; document observed limits.
'''
    path.write_text(text,encoding='utf-8')

path=root/'IMPLEMENTATION_REPORT.md'
text=path.read_text(encoding='utf-8')
if '## Wi-Fi OTA addition — 20 November 2026' not in text:
    text+='''
## Wi-Fi OTA addition — 20 November 2026

Added /ota, authenticated BIN/Intel HEX validation and staging, MQTT chunk
transfer, inactive-slot firmware writes, SHA-256 checks, startup rollback and
live chip version/hash confirmation. Existing control/CAN logic has only
maintenance gates required to prevent concurrent actuation during OTA. NVS
offsets are preserved. Added broker ACLs, migration backup helper, API schema,
release packaging and OTA operation/acceptance documentation. No serial device
was connected during implementation; physical migration and OTA acceptance
remain pending. See docs/RELEASE_STATUS.md for software-check results.
'''
    path.write_text(text,encoding='utf-8')
