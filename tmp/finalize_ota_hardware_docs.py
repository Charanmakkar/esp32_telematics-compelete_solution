from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,re,sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.services.ota_image import inspect_image
release=json.loads((root/'version.json').read_text());version=release['sw_version'];build=release['source_sha256'][:12]
data,info=inspect_image('navsphere.bin',(root/'build/firmware.bin').read_bytes())
assert version==info['version']
final_state=json.loads((root/'output/testing/ota-final-hardware-state.json').read_text())
assert final_state['passed'] and final_state['chip']['image_sha256']==info['image_sha256']
evidence={name:json.loads((root/f'output/testing/ota-live-{name}.json').read_text()) for name in ('bin-verified','hex-verified','safety','transfer-reset','rollback','regression','gui-regression','can-tx')}
for name in ('safety','transfer-reset','rollback','regression','gui-regression'):assert evidence[name]['passed'],name
for name in ('bin-verified','hex-verified'):assert evidence[name]['after']['job']['state']=='confirmed',name
assert evidence['bin-verified']['after']['chip']['image_sha256']==info['image_sha256']
assert evidence['rollback']['after']['chip']['image_sha256']==evidence['rollback']['before']['image_sha256']
assert evidence['regression']['chip']['image_sha256']==info['image_sha256']
bms=json.loads((root/'output/testing/ota-live-bms-read.json').read_text())
assert bms['passed'] and bms['chip']['image_sha256']==info['image_sha256']
summary={'tested_at_utc':datetime.now(timezone.utc).isoformat(),'release':release,'image':info,'hardware':{'port':'COM3','chip':'ESP32-D0WDQ6 rev1.0','flash_bytes':4194304,'backup_bytes':4194304,'nvs_preserved':final_state['nvs_byte_identical'],'max_chunk_bytes':2048,'usb_migration_verified':True,'bin_ota_verified':True,'hex_ota_verified':True,'rollback_reset_verified':True},'software':{'backend_full_tests':116,'frontend_tests':45,'ota_backend_tests':26,'firmware_host_tests':'passed','firmware_build':'passed','frontend_build':'passed','version_tests':3},'evidence_files':[f'ota-live-{n}.json' for n in evidence],'can_tx_passed':evidence['can-tx']['passed'],'limits':['No physical power-cut test','No output voltage or ADC calibration measurement','No destructive BMS programming/erase','No 24-hour soak or production TLS deployment'],'fixes':['15-second start deadline below chip maximum, allowing small clock skew','Pause large CAN MQTT batches during OTA only','Disable Wi-Fi modem sleep during OTA only, restoring policy on abort','Negotiate 2048-byte chunks with 768-byte fallback for older firmware']}
(root/'output/testing/ota-hardware-validation-20261120.json').write_text(json.dumps(summary,indent=2))
notice=f'Updated 20 November 2026 for **v{version} / {build}**. USB migration, live BIN/HEX OTA and reset-triggered startup rollback were verified on the connected ESP32. See `docs/RELEASE_STATUS.md` for exact evidence and remaining hardware limits.'
maintained=['README.md','backend/README.md','frontend/README.md','firmware/README.md','output/firmware/README.md','docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md','docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md']
for name in maintained:
    path=root/name;text=path.read_text(encoding='utf-8')
    text=re.sub(r'Updated 20 November 2026 for \*\*v[^\n]+',notice,text,count=1)
    text=text.replace('hardware_flashed is false.','The manifest records this exact image as hardware verified.')
    text=text.replace('arbitration retry correction is built and packaged, not yet flashed.','arbitration retry correction is included in the installed release. See the current release status for the latest wire test.')
    text=text.replace('Current v1.1.8 flashing is pending; see docs/RELEASE_STATUS.md.','Current OTA firmware is installed; see docs/RELEASE_STATUS.md for exact verification scope.')
    text=re.sub(r'(0x3F0000 ota_data_initial.bin)(?: 0x3F0000 ota_data_initial.bin)+',r'\1',text)
    path.write_text(text,encoding='utf-8')
for name in ('backend/API_CONTRACT.md','docs/api/API_REFERENCE.md','docs/README.md'):
    path=root/name;text=path.read_text();text=re.sub(r'v1\.1\.12 / 9ba9f7be53ad',f'v{version} / {build}',text)
    text=text.replace('this build is packaged but not\nyet flashed.','this build has passed live OTA installation and chip confirmation.')
    path.write_text(text,encoding='utf-8')
for name in ('docs/testing/HARDWARE_TEST_PLAN.md','firmware/test/HARDWARE_TEST_PLAN.md'):
    path=root/name;text=path.read_text();text=text.replace('## OTA acceptance (pending physical hardware)','## OTA acceptance')
    text=text.replace('v1.1.8 arbitration retry correction needs a physical test.',f'The arbitration retry correction was exercised in v{evidence["can-tx"]["release"]["sw_version"]}; the periodic TX test failed with an ESP-IDF TWAI assertion/reset. See docs/RELEASE_STATUS.md before further transmission tests.')
    text+='\n20 November bench results: see `output/testing/ota-hardware-validation-20261120.json` and\n`docs/RELEASE_STATUS.md`. BIN/HEX, both slots, invalid-file/permission checks,\nincomplete-transfer recovery, active-CAN rejection and reset-before-confirmation\nrollback were exercised. Physical power cuts and long-duration/electrical tests\nremain separate acceptance items; do not mark the entire checklist complete.\n'
    path.write_text(text)
for name,note in [
    ('docs/firmware/CAN_TX_GUIDE.md',f'Current bench result, 20 November 2026 (v{evidence["can-tx"]["release"]["sw_version"]}): periodic transmission triggered `twai_handle_tx_buffer_frame` / `tx_msg_count >= 0` assertion and an ESP32 reset. The OFF cleanup request timed out during the reset; subsequent live status confirmed periodic TX OFF, listen-only mode and both controls OFF. The periodic-transmit implementation was not changed by OTA. Its root cause remains unresolved; keep periodic TX OFF pending investigation. See `output/testing/ota-live-can-tx.json` and `docs/RELEASE_STATUS.md`. Earlier results below remain historical.'),
    ('docs/development/BE_CLIENT_IMPLEMENTATION.md',f'20 November 2026 OTA regression check (v{version}): the existing read-only hardware-number quick read returned a positive response (`62 F1 91 ...`) and restored listen-only mode. Evidence: `output/testing/ota-live-bms-read.json`. This verifies that one read path only; earlier limitations for other diagnostic/programming workflows are not superseded. No destructive BMS operation was tested.')
]:
    path=root/name;text=path.read_text();heading,rest=text.split('\n',1)
    if name.endswith('CAN_TX_GUIDE.md'):
        rest=rest.replace('Updated 19 November 2026. Source/package:', 'Historical 19 November 2026 source/package record:').replace('This build has not yet been flashed or accepted on hardware.','That build had not been flashed or accepted at the time of the record; use the current result above.')
    path.write_text(heading+'\n\n'+note+'\n'+rest)
can=evidence['can-tx'];can_text=('Passed exact payloads, mean timing within 5%, maximum intervals below twice the requested period, and OFF verification.' if can['passed'] else 'FAILED: the ESP-IDF TWAI transmit-count assertion reset the device during periodic transmission; PCAN observed error frames and timing could not be evaluated. The cleanup OFF request timed out during reboot; subsequent live status independently confirmed listen-only mode, periodic TX OFF and both controls OFF. Periodic-transmit code was unchanged by OTA; root cause remains unresolved.')
status=f'''# Current release and verification status

Updated **20 November 2026**. Release **v{version} / {build}** is installed on the
connected ESP32 and its running fingerprint matches the packaged application.

| Item | Verified record |
|---|---|
| Source / GUI / firmware | v{version} / {build} |
| Source SHA-256 | {release['source_sha256']} |
| Application SHA-256 | {info['sha256']} |
| Running-image SHA-256 | {info['image_sha256']} |
| Application size / slot | {len(data)} / 2031616 bytes |
| USB migration | Full 4 MiB private backup, preserved NVS, verified writes |
| Hardware OTA | BIN and Intel HEX confirmed by new boot, exact hash and version |
| Startup rollback | Reset pending boot; previous confirmed image restored |
| Current hardware flags | hardware_flashed=true, hardware_ota_verified=true |

## Screenshot comparison and delivered additions

The OTA page now has chip-reported installed version, IP, Wi-Fi signal and uptime;
single-file drag/drop; visible 1984 KiB application and 6 MiB upload limits; a
before-upload guide; progress, offline/stale reporting; and browser/server/device
transport-security information. It retains the existing administrator login and
server-side HEX conversion. No separate OTA password or browser HEX parser is required.

Transfers use the chip-advertised 2048-byte capacity, with a 768-byte fallback for
earlier OTA builds. Final USB restoration after the deliberate rollback test kept
the original NVS bytes identical and restored the packaged build.

The first upload test exposed a clock-skew boundary, fixed by using a 15-second
deadline below the chip's 30-second maximum. Wi-Fi/MQTT timeouts occurred under
heavy CAN traffic and weak signal. Large CAN MQTT batches now pause only during
OTA, and modem sleep is disabled only during transfer. ADC telemetry and passive
CAN capture remain enabled, subject to flash delays. Abort releases the locks
and restores the power policy; reboot briefly interrupts all device reporting.
No previous GPIO, ADC, periodic CAN or BMS behavior was changed outside OTA.

An earlier run with the final chunk configuration stopped when the board reset
unexpectedly at 53% transfer. The previous confirmed image survived; the cause
was not captured and remains unassigned. The subsequent fully logged BIN and
HEX runs passed. These successful runs do not establish long-duration reliability.
See `output/testing/ota-live-bin-large-reset.json` for the failed attempt.

## Verification evidence

- 116 backend tests, 45 frontend tests, 3 version tests, firmware host checks,
  ESP-IDF build and GUI production build passed. The 26 targeted OTA tests overlap
  the backend total. One existing Starlette/httpx deprecation warning remains.
- Live BIN and HEX page uploads, both slot directions, mobile/desktop rendering,
  chip hash/version confirmation, reset mid-transfer and reset-before-confirmation
  rollback passed.
  BIN installed v1.1.20; drag/drop HEX installed v1.1.19 from the same final source
  revision. Confirmation took about 306 and 305 seconds respectively. The board
  was restored to v1.1.20 after the deliberate rollback test.
- Live server authentication/CSRF, bad BIN/HEX, bootloader and oversize rejection;
  chip size/hash/image checks; duplicate/conflicting/out-of-order chunks;
  interrupted-transfer timeout and maintenance control rejection passed.
- After OTA, six ADC channels persisted, WebSocket received/persisted events arrived,
  all six history APIs returned data, CAN capture/storage resumed, both safe OFF
  commands received applied hardware acknowledgements, and existing pages loaded.
- CAN wire test: {can_text}
- Active periodic CAN causes OTA rejection while CAN remains enabled. All bench
  testing ends with periodic CAN OFF and both GPIO controls OFF.
- A read-only BMS hardware-number query completed with a positive response and
  restored listen-only mode. This does not establish all diagnostic workflows.
- The temporary test administrator was used through normal login/password-change
  flows, then disabled and its sessions revoked. The user's password was unchanged.

Machine-readable summary: `output/testing/ota-hardware-validation-20261120.json`.
Individual `ota-live-*.json` files and `output/testing/screenshots/ota-live-*`
contain measured results. Earlier failed attempts retain their failure labels.
The flash backup remains private under `.runtime/ota-backups/` and is excluded
from the release ZIP, along with credentials and live database files.

## Remaining acceptance limits

Reset-triggered rollback is verified; a physical power-cut test was not performed.
Output voltages, ADC accuracy, 24-hour stability, production TLS and lossless CAN
logging are not certified. CAN/ADC drop counters can increase during flash writes.
The transfer serial captures contain truncated characters/numeric fields, so their
raw resource minima cannot certify heap/stack margin. OTA worker stack margin and
reliable worst-case heap measurements remain unverified.
BMS catalog/jobs, page access and one read-only hardware-number response were
checked; destructive BMS operations were not performed. Other BMS workflows
remain outside this hardware acceptance result. Periodic CAN transmission has
the unresolved driver assertion described above; leave it OFF pending investigation.

## Artifact interpretation

`output/firmware/manifest.json` records exact binary hashes and verification flags.
`output/NavSphere_Source_and_Docs.zip` contains current source and documentation.
Earlier PDFs, reports, snapshots and screenshots remain historical evidence;
use the current Markdown OTA guide and this record for deployment decisions.
No Git commit or remote publication is implied by this package.
'''
(root/'docs/RELEASE_STATUS.md').write_text(status)
path=root/'IMPLEMENTATION_REPORT.md';text=path.read_text();text=re.sub(r'Current documentation review:[^\n]+',f'Current documentation review: 20 November 2026. Dated sections below are chronological evidence; docs/RELEASE_STATUS.md records the current v{version} hardware validation.',text,count=1)
text+=f'\n## Live OTA validation and screenshot gaps — 20 November 2026\n\nRelease v{version} / {build} was verified on the connected board. Added actual\nIP/RSSI/uptime, drag/drop, limits, guidance and connection-security reporting.\nBacked up flash and preserved provisioned credentials. BIN/HEX updates and startup\nrollback passed; ADC/CAN persistence, existing pages and safe OFF controls were\nchecked. Fixed OTA deadline skew and isolated OTA network capacity/power handling.\nSee docs/RELEASE_STATUS.md and output/testing/ota-hardware-validation-20261120.json\nfor exact tests, evidence and remaining hardware limits.\n'
path.write_text(text)
print('Updated current guides, release status and hardware validation summary for',version)
