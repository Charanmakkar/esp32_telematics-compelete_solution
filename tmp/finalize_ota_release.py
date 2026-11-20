from pathlib import Path
import hashlib
import json
import re
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.services.ota_image import inspect_image
release=json.loads((root/'version.json').read_text())
image, info=inspect_image('navsphere.bin',(root/'build/firmware.bin').read_bytes())
assert info['version']==release['sw_version'], (info, release)
assert (release['source_sha256'][:12].encode()+b'\0') in image
gui=json.loads((root/'frontend/dist/sw-version.json').read_text())
assert gui=={'sw_version':release['sw_version'],'sw_build':release['source_sha256'][:12]}
identity=f"v{release['sw_version']} / {release['source_sha256'][:12]}"
for name in ('README.md','firmware/README.md','frontend/README.md','backend/README.md',
             'docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md',
             'docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md','output/firmware/README.md',
             'docs/README.md','backend/API_CONTRACT.md','docs/api/API_REFERENCE.md'):
    path=root/name
    text=path.read_text(encoding='utf-8')
    text=re.sub(r'v1\.1\.(?:9|10|11) / [0-9a-f]{12}',identity,text)
    path.write_text(text,encoding='utf-8')

path=root/'docs/RELEASE_STATUS.md'
text=path.read_text(encoding='utf-8')
start=text.index('Documentation reviewed:')
end=text.index('## Delivered features')
text=text[:start]+f'''Updated **20 November 2026** for the OTA implementation. Current working-tree
release: **{identity}**. Device installation was deferred by the user until USB
connection is available. Existing backend/broker processes were not restarted.

| Item | Current record |
|---|---|
| Source, built GUI and packaged application | {identity} |
| Source SHA-256 | {release['source_sha256']} |
| Application SHA-256 | {info['sha256']} |
| Running-image fingerprint expected after OTA | {info['image_sha256']} |
| OTA support | /ota upload, MQTT transfer, chip version/hash confirmation, rollback |
| Latest hardware-verified firmware | v1.1.7 / b323d1f42a84 |
| Current hardware_flashed / hardware_ota_verified | false / false |
| Initial USB migration | Required; backs up flash and preserves NVS |
| BMS diagnostic response through ESP32 | Prior limitation remains unverified |

Software evidence for this change: the full backend suite passed 102 tests;
after final OTA error-handling changes, all 13 OTA tests passed. These counts
overlap. All 41 frontend tests passed, followed by both final OTA page tests.
Firmware host tests (including maintenance gating), ESP-IDF firmware/bootloader
build, GUI production build, changed Python-file lint, and migration-script
syntax checks passed. The compiled binary was accepted by the upload validator.
Desktop/mobile browser checks used mocked API data and passed upload/confirmation
gates with no page errors or mobile overflow; those are not hardware results.
See `output/testing/ota-20261120-verification.json` and the [OTA guide](firmware/OTA_GUIDE.md).

'''+text[end:]
text=text.replace('## Delivered features\n','## Delivered features\n\n- Wi-Fi OTA page with application BIN/Intel HEX upload, admin/CSRF checks,\n  chunked MQTT transfer, inactive-slot writes, rollback and chip identity confirmation.\n')
text=text.replace('## Evidence and limits','## Earlier evidence and remaining hardware limits')
text=text.replace('This documentation update does not turn those host checks into hardware approval.','Those prior host checks do not establish hardware OTA acceptance.')
path.write_text(text,encoding='utf-8')

evidence={
 'review_date':'2026-11-20','sw_version':release['sw_version'],
 'sw_build':release['source_sha256'][:12],'application':info,
 'backend_full_suite':{'passed':102},'backend_final_ota_tests':{'passed':13,'overlaps_full_suite':True},
 'frontend_full_suite':{'passed':41},'frontend_final_ota_tests':{'passed':2,'overlaps_full_suite':True},
 'firmware_host_tests':'passed; existing CAN/ISO-TP/command rules plus maintenance gate',
 'firmware_build':'passed with ESP-IDF 6.0.2','gui_build':'passed',
 'python_changed_file_lint':'passed','migration_powershell_syntax':'passed',
 'image_validator_accepts_compiled_binary':True,
 'browser':{'mocked_api':True,'desktop':'passed','mobile':'passed','upload_gate':'passed',
            'reboot_confirmation_gate':'passed','no_page_errors':True,
            'screenshots':['screenshots/ota-desktop-fixture.png','screenshots/ota-mobile-fixture.png']},
 'hardware_flashed':False,'hardware_ota_verified':False,
 'physical_tests':'Deferred by user; USB device was not connected',
 'existing_services_restarted':False,
}
(root/'output/testing/ota-20261120-verification.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'version':identity,'bytes':len(image),'slot_free_bytes':0x1f0000-len(image),'sha256':hashlib.sha256(image).hexdigest()}))
