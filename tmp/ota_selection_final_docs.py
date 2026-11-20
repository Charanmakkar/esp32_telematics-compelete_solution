from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
r=json.loads((root/'version.json').read_text(encoding='utf-8'))
e=json.loads((root/'output/testing/ota-file-selection-20261120.json').read_text(encoding='utf-8'))
assert e['passed'] and e['new_image']['version']==r['sw_version'] and not e['installation_started']
user_update=json.loads((root/'output/testing/ota-user-update-v1.1.21.json').read_text(encoding='utf-8'))
assert user_update['passed'] and user_update['after']['job']['state']=='confirmed'
version=r['sw_version'];build=r['source_sha256'][:12];installed=e['after']['version']
files=['README.md','backend/README.md','frontend/README.md','firmware/README.md','output/firmware/README.md','docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md','docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md','backend/API_CONTRACT.md','docs/api/API_REFERENCE.md','docs/README.md']
for name in files:
 p=root/name;t=p.read_text(encoding='utf-8').replace('v1.1.21 / bd9ed0ad6a1b',f'v{version} / {build}')
 t=t.replace('The connected chip remained on hardware-verified v1.1.20;',f'The connected chip reported v{installed};')
 t=t.replace('board remained on v1.1.20 during upload validation.',f'board reported v{installed} during final upload validation.')
 p.write_text(t,encoding='utf-8',newline='\n')
p=root/'docs/RELEASE_STATUS.md';t=p.read_text(encoding='utf-8');old_sha=re.search(r'Application SHA-256: `([0-9a-f]+)`',t).group(1)
t=t.replace('v1.1.21 / bd9ed0ad6a1b',f'v{version} / {build}').replace('claim a v1.1.21 flash',f'claim a v{version} flash').replace(old_sha,e['new_image']['sha256'])
t=t.replace('The connected board remained on **v1.1.20** during this validation;',f'The connected board remained on **v{installed}** during the final upload validation;')
t=t.replace('Evidence: `output/testing/ota-file-selection-20261120.json`', 'The user also completed a v1.1.21 OTA update successfully; the chip confirmed\nthe exact uploaded image. Evidence: `output/testing/ota-user-update-v1.1.21.json`.\nThis does not claim installation of the newer v'+version+' image.\n\nEvidence: `output/testing/ota-file-selection-20261120.json`')
t=t.replace('retained filename feedback and rejection of stale-image installation.', 'retained filename feedback and rejection of stale-image installation. Rejected\n  selections now hide previous target details, and the native picker retains the\n  chosen filename. These cases directly address the supplied screenshot.')
p.write_text(t,encoding='utf-8',newline='\n')
p=root/'docs/firmware/OTA_GUIDE.md';t=p.read_text(encoding='utf-8')
t=t.replace('beside the picker. A rejected selection blocks installing an older staged file.', 'beside the picker. A rejected selection hides the previous target metadata and\nblocks installing an older staged file. Reopening the picker allows the same\nfilename to be selected again after rebuilding it.')
p.write_text(t,encoding='utf-8',newline='\n')
p=root/'IMPLEMENTATION_REPORT.md';t=p.read_text(encoding='utf-8')
t+=f'\n## OTA screenshot follow-up - 20 November 2026\n\nRelease v{version} / {build} hides previously staged image details after a rejected\nselection and retains the chosen filename in the native picker. Both build\nfolders were refreshed. Eight OTA GUI tests and live old-file rejection/new-file\nacceptance checks passed; the board remained on v{installed}, with no flash started.\n'
p.write_text(t,encoding='utf-8',newline='\n')
print('Updated final release identity and screenshot-specific validation notes.')
