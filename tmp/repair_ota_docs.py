from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
# These were clean at task start. Restore only this task's documentation edits
# before reapplying them using explicit UTF-8 throughout.
for name in ('backend/API_CONTRACT.md','docs/api/API_REFERENCE.md','docs/README.md',
             'docs/testing/HARDWARE_TEST_PLAN.md','firmware/test/HARDWARE_TEST_PLAN.md',
             'IMPLEMENTATION_REPORT.md'):
    original=subprocess.check_output(['git','show','HEAD:'+name],cwd=root)
    (root/name).write_bytes(original)
