# Temporary work snapshot

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
