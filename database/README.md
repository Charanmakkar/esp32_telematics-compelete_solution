# Database operations

Use the existing MySQL/MariaDB server. `phpMyAdmin` administers the server; Python connects on the actual MySQLTCP port3306. Create a dedicated `navsphere` database and application account with permissions limited to that database. Keep passwords in ignored `backend/.env`, never SQL source.

Canonical migration: from `backend/`, run `.venv/Scripts/python.exe -m alembic upgrade head`. Revision0001 freezes the initial schema. Revision0002 implements the user's revised requirement of six onboard channels, removing channels7–10. New installations run both and finish with only `analog_1` through `analog_6`. Removing these columns cannot recover prior values on downgrade; migration0002 documents the structural rollback behavior. No preexisting project telemetry existed when the development database was migrated.

`schema.sql` is a generated current schema reference, with six channels and all application tables. Prefer Alembic for deployment so revision tracking remains correct. The admin seed is created by backend startup with a scrypt password hash and a required first password change; no plaintext seed password is stored in SQL.

`telemetry_readings` has unsigned serial ID/sequence/epoch/values, millisecond receive and persistence timestamps, JSON raw readings/status, validity mask, and reboot-safe `(device_id,boot_id,sequence_number)` uniqueness. Device+epoch, device+observed time and device+receive indexes support latest/history; a receive index supports retention. Device timestamp is nullable for unsynchronized readings, with `observed_ms` selecting device epoch or server receipt for bounded historical queries. Per-channel statistics exclude invalid mask bits. History aggregation runs in SQL; the API does not load a day of raw measurements into memory.

At10Hz, one device creates864000 records/day regardless of six channel count. Measure actual row/index bytes and query latency on the deployment hardware before choosing retention. Start with30days only if storage measurements support it. Compression, partitioning and an archive tier are future deployment-specific work; they are not claimed as implemented.

Retention is explicit and dry-run by default:

```powershell
# from backend/
.venv/Scripts/python.exe -m app.maintenance --days 30
.venv/Scripts/python.exe -m app.maintenance --days 30 --execute
```

Deletion commits in batches of10000. Schedule it using Windows Task Scheduler only after backup and retention approval. This command retains user, command and audit records; establish separate organizational retention for those tables.

Back up with the installed `mysqldump`/`mariadb-dump` using `--single-transaction --routines --triggers --databases navsphere`. Use a restricted backup account and a protected client option file rather than passwords in shell arguments. Protect backups, copy them off this laptop, record retention, and regularly restore into a separate verification database. Never validate restore by replacing the live database. Do not run a second MySQL instance over the existing XAMPP data directory.
