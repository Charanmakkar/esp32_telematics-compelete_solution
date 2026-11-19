"""Add documented CAN-TX status to the existing v1.1.8 manifest/ZIP.

Run after scripts/package_release.py. This never builds/flashes or changes source identity.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import zipfile

ROOT=Path(__file__).resolve().parents[2]
def main():
    release=json.loads((ROOT/'version.json').read_text())
    if release['sw_version']!='1.1.8' or release['source_sha256'][:12]!='8148c3afe9b8':
        raise SystemExit('Review release/verification metadata before using this helper for another build.')
    path=ROOT/'output/firmware/manifest.json';manifest=json.loads(path.read_text())
    binary=ROOT/'output/firmware/navsphere.bin'
    assert manifest['sw_version']==release['sw_version']
    assert manifest['files']['navsphere.bin']['sha256']==hashlib.sha256(binary.read_bytes()).hexdigest()
    assert manifest['hardware_flashed'] is False, 'Review new hardware evidence instead of overwriting it.'
    manifest['can']['mode_is_startup_default']=True
    manifest['can']['periodic_transmission']={
        'available':True,'default_enabled':False,'mutually_exclusive_with_diagnostics':True,
        'profiles':[{'can_id':'0x014','dlc':3,'data':'006000','period_ms':100},
                    {'can_id':'0x548','dlc':8,'data':'0000000000000008','period_ms':10}],
        'gui_path':'/can','request_topic':'navsphere/<device_id>/can/tx/request',
        'stops_on':['MQTT disconnection','three consecutive failed sends','reboot'],
        'arbitration_retry_budget_us':5000,'maximum_attempts':16,
        'latest_payload_delivery_verified_version':'1.1.7',
        'current_build_wire_timing_verified':False}
    manifest['documentation']={'reviewed_utc':datetime.now(timezone.utc).isoformat(),
        'index':'docs/README.md','release_status':'docs/RELEASE_STATUS.md',
        'validation':'docs/testing/documentation-review.json'}
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    archive=ROOT/'output/NavSphere_Source_and_Docs.zip';temporary=archive.with_suffix('.docs-refresh.tmp')
    try:
        with zipfile.ZipFile(archive) as old,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as new:
            for entry in old.infolist():
                if entry.filename=='NavSphere/output/firmware/manifest.json':
                    new.writestr(entry,path.read_bytes())
                else:new.writestr(entry,old.read(entry.filename))
        os.replace(temporary,archive)
    finally:
        if temporary.exists():temporary.unlink()
    print('Updated release documentation metadata and matching offline ZIP.')

if __name__=='__main__':main()
