from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
release=json.loads((root/'version.json').read_text())
version=release['sw_version'];build=release['source_sha256'][:12]
test=json.loads((root/'output/testing/ota-file-selection-20261120.json').read_text())
assert test['passed'] and test['new_image']['version']==version and not test['installation_started']
installed=test['after']['version']
notice=f'Updated 20 November 2026 for **v{version} / {build}**. File-selection feedback is fixed and the rebuilt firmware passed live GUI upload validation. The connected chip remained on hardware-verified v{installed}; this new image has not been flashed. See `docs/RELEASE_STATUS.md` for evidence and limitations.'
for name in ('README.md','backend/README.md','frontend/README.md','firmware/README.md','output/firmware/README.md','docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md','docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md'):
 p=root/name;t=p.read_text();t=re.sub(r'Updated 20 November 2026 for \*\*v[^\n]+',notice,t,count=1)
 t=t.replace('The manifest records this exact image as hardware verified.', 'The manifest records this new image as built and upload-validated, not yet hardware flashed.')
 p.write_text(t)
for name in ('backend/API_CONTRACT.md','docs/api/API_REFERENCE.md','docs/README.md'):
 p=root/name;t=p.read_text();t=t.replace('v1.1.20 / 1fb9fadf201c',f'v{version} / {build}')
 t=t.replace('this build has passed live OTA installation and chip confirmation.',f'this build passed live file-upload validation; v{installed} remains the last fully flashed and hardware-verified release.')
 p.write_text(t)
p=root/'docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md';t=p.read_text()
t=t.replace('Source, GUI, packaged application and connected board are v1.1.20 / 1fb9fadf201c.\nThe manifest records this exact image as flashed and verified over OTA. The connected\nboard has already been migrated; use `/ota` for its future application updates.',f'Source, GUI and packaged application are v{version} / {build}. The connected\nboard remained on v{installed} during upload validation. This new image is ready for\ninstallation through `/ota`; the board has already received its one-time migration.')
p.write_text(t)
p=root/'docs/firmware/OTA_GUIDE.md';t=p.read_text();heading='## If a BIN file does not load'
assert heading not in t
section='''## If a BIN file does not load

Use `output/firmware/navsphere.bin` from the current release. The standalone
build writes `firmware/build/firmware.bin`; the root build writes
`build/firmware.bin`. These are separate build directories: rebuilding one does
not refresh the other. Confirm the target version displayed after selection.

The 20 November file-loading issue was caused by an old pre-OTA application in
`firmware/build/firmware.bin`. It was selected successfully but rejected because
installing it would remove OTA support. That directory has now been rebuilt.
The page keeps the selected filename visible and displays validation errors
beside the picker. A rejected selection blocks installing an older staged file.

Refresh the page, select the newly rebuilt application file and wait for
**File accepted** and the target version. Then acknowledge the maintenance
notice and install. If the chip already runs that exact image, the server
rejects a redundant installation. Do not select `bootloader.bin`, a partition
table, or a full-flash bundle.

'''
t=t.replace('## Accepted files',section+'## Accepted files');p.write_text(t)
p=root/'docs/RELEASE_STATUS.md';previous=p.read_text()
previous=previous.replace('# Current release and verification status','# Previous hardware verification — v1.1.20',1)
previous=previous.replace('is installed on the\nconnected ESP32 and its running fingerprint matches the packaged application.','was installed on the\nconnected ESP32 and matched the application packaged for that release.',1)
previous='\n'.join('#'+line if line.startswith('#') else line for line in previous.splitlines())
intro=f'''# Current release and verification status

Updated 20 November 2026. **v{version} / {build}** fixes firmware-file feedback.
The connected board remained on **v{installed}** during this validation; no flash
or reboot was requested by the upload-only test.

- Root and standalone ESP-IDF builds and the GUI production build passed.
- Eight focused OTA GUI tests passed, including visible validation errors,
  retained filename feedback and rejection of stale-image installation.
- A real browser with normal administrator authentication reproduced the old
  BIN rejection (HTTP 400) and accepted the rebuilt `firmware/build/firmware.bin`
  (HTTP 200). Desktop/mobile checks passed with no page errors.
- The packaged `output/firmware/navsphere.bin` is the exact standalone image
  tested by the uploader. Application SHA-256: `{test['new_image']['sha256']}`.
- This image is ready for the user to install. Its manifest records
  `hardware_flashed=false` and `hardware_ota_verified=false`; the earlier v1.1.20
  hardware results below are historical and do not claim a v{version} flash.
- The temporary upload-test account was disabled and its sessions revoked.
  Existing login credentials and board settings were unchanged.

Evidence: `output/testing/ota-file-selection-20261120.json` and
`output/testing/screenshots/ota-file-*`. See the OTA guide's file-loading section.
The unresolved periodic CAN reset and other hardware limits from the previous
validation remain applicable; periodic CAN transmission remains OFF.

'''
p.write_text(intro+previous+'\n')
p=root/'IMPLEMENTATION_REPORT.md';t=p.read_text()
t+=f'\n## OTA file-selection correction — 20 November 2026\n\nRelease v{version} / {build} moves upload errors beside the picker, retains selected\nfilename feedback and blocks installing a stale staged image after rejection.\nThe user-selected standalone build was a pre-OTA application; both build roots\nwere rebuilt. Eight GUI tests and live rejection/acceptance checks passed.\nThe chip remained on v{installed}; the new release is upload-validated, not flashed.\nSee docs/RELEASE_STATUS.md for current and historical evidence.\n'
p.write_text(t)
print('Updated file-loading guidance and separated new upload validation from prior hardware evidence.')
