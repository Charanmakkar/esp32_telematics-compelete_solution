"""Capture temporary project work without copying local credentials or caches."""
import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit, unquote
import zipfile

root = Path.cwd()
destination = root / 'output/work_snapshot'
destination.mkdir(parents=True, exist_ok=True)
def git_files(*args):
    return set(subprocess.check_output(['git', '-c', 'core.longpaths=true', 'ls-files', '-z', *args]).decode().split('\0')) - {''}
normal = git_files('--cached', '--others', '--exclude-standard')
ignored = git_files('--others', '--ignored', '--exclude-standard')
secrets = set(json.loads(os.environ.get('NAV_REDACT_VALUES', '[]')))
secret_key = re.compile(r'password|passwd|passphrase|secret|token|api_key', re.I)
def remember(value):
    if isinstance(value, str) and len(value) >= 6 and not value.startswith(('${', '<', 'REDACTED')):
        secrets.add(value)
for name in ('backend/.env', '.runtime/device.env'):
    p = root / name
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            if '=' not in line or line.lstrip().startswith('#'): continue
            key, value = line.split('=', 1)
            value = value.strip().strip('\"\'')
            if secret_key.search(key): remember(value)
            if '://' in value:
                try: remember(unquote(urlsplit(value).password or ''))
                except ValueError: pass
for name in ignored:
    p = root / name
    if p.suffix == '.py' and p.parts[len(root.parts)] in ('.runtime', 'tmp'):
        try:
            tree = ast.parse(p.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if isinstance(key, ast.Constant) and isinstance(key.value, str) and secret_key.search(key.value) and isinstance(value, ast.Constant): remember(value.value)
                elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    if any(isinstance(t, ast.Name) and secret_key.search(t.id) for t in node.targets): remember(node.value.value)
        except (OSError, SyntaxError, UnicodeError): pass
secret_bytes = [s.encode() for s in secrets if len(s) >= 6]
text_suffixes = {'.py','.ps1','.mjs','.js','.ts','.tsx','.json','.ndjson','.log','.txt','.md','.csv','.conf','.ini','.cmake','.yml','.yaml','.xml','.dbc','.map','.html','.css'}
def sanitize(blob, name):
    changed = False
    if Path(name).suffix.lower() == '.zip':
        stream = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(blob)) as zin, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                parts = Path(info.filename).parts
                if any(p in ('.env', '.env.local', '.local', 'nvs.bin', 'passwords') for p in parts):
                    changed = True
                    continue
                safe, altered = sanitize(zin.read(info), info.filename)
                changed |= altered
                zout.writestr(info, safe)
        return (stream.getvalue() if changed else blob), changed
    for secret in secret_bytes:
        if secret in blob:
            if Path(name).suffix.lower() not in text_suffixes:
                raise ValueError('Credential-containing binary retained locally')
            blob = blob.replace(secret, b'<REDACTED_LOCAL_SECRET>')
            changed = True
    return blob, changed

def excluded(name):
    p = Path(name)
    if p.suffix in ('.db', '.db-shm', '.db-wal'): return 'Runtime database retained locally'
    if name.startswith('.runtime/backups/'): return 'Database backup retained locally'
    if name.startswith(('.runtime/be_client_inspection/', '.runtime/bms_exe_inspection/')): return 'Private reference executable/security extraction retained locally'
    if '.local' in p.parts or p.name in ('.env','.env.local','device.env','passwords','passwd'): return 'Credentials/provisioning material retained locally'
    if any(part in ('.venv','node_modules','.tools','managed_components') for part in p.parts): return 'Installed dependency/tool retained locally'
    if any(part in ('__pycache__','.pytest_cache','.ruff_cache') for part in p.parts) or p.suffix in ('.pyc','.tsbuildinfo'): return 'Reproducible cache retained locally'
    if any(part in ('build','recovery-old-build','recovery-old-firmware-build') for part in p.parts):
        if p.name not in ('firmware.bin','firmware.elf','firmware.map','bootloader.bin','partition-table.bin'):
            return 'Intermediate build cache retained locally'
    return ''

records=[]
copied=redacted=0
for name in sorted(normal | ignored):
    if name.startswith('output/work_snapshot/'): continue
    p=root/name
    if not p.is_file(): continue
    record={'original_path':name,'bytes':p.stat().st_size,'disposition':'Project file included directly','snapshot_path':'','sha256':''}
    if name in ignored:
        reason=excluded(name)
        if reason:
            record['disposition']=reason
        else:
            try:
                data, changed = sanitize(p.read_bytes(), name)
                relative=Path(name)
                if relative.parts[0]=='.runtime': relative=Path('runtime',*relative.parts[1:])
                relative=Path(*(part if part != 'build' else 'build_outputs' for part in relative.parts))
                target=destination/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
                record.update(disposition='Temporary/build file included (secrets redacted)' if changed else 'Temporary/build file included', snapshot_path=target.relative_to(root).as_posix(),sha256=hashlib.sha256(data).hexdigest())
                copied+=1;redacted+=int(changed)
            except ValueError as exc: record['disposition']=str(exc)
    records.append(record)
with (destination/'inventory.csv').open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=['original_path','bytes','disposition','snapshot_path','sha256'])
    writer.writeheader();writer.writerows(records)
summary={'inventoried_files':len(records),'temporary_files_included':copied,'files_with_credentials_redacted':redacted,'excluded_files':sum('locally' in r['disposition'] for r in records)}
(destination/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(destination/'README.md').write_text('''# Temporary work snapshot

This directory preserves temporary project scripts, logs, screenshots, report
work files, DBC inputs, GUI output and final firmware build artifacts for the
requested commit. Paths mirror their original locations; `runtime/` maps to
the original `.runtime/` folder, and `build_outputs/` maps to `build/`.
These are historical work records, not files
to overwrite the running services with.

`inventory.csv` accounts for project files and ignored files, identifying each
included copy or the reason it remains local. Credential values in included
text were replaced with `<REDACTED_LOCAL_SECRET>`. Original files were not
modified or deleted. Credentials, NVS/full-chip backups, database backups,
private reference executable/security extractions, installed dependencies,
downloaded tools and intermediate caches remain local. Final firmware images,
ELF/map files and generated GUI output are included.

The application release archive contains source and selected release artifacts;
this directory is also committed directly so its logs remain available offline.
''',encoding='utf-8')
print(json.dumps(summary,indent=2))
