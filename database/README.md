# Database operations

Use the existing MySQL/MariaDB server. `phpMyAdmin` administers the server; Python connects on the actual MySQLTCP port3306. Create a dedicated `navsphere` database and application account with permissions limited to that database. Keep passwords in ignored `backend/.env`, never SQL source.

Canonical migration: from `backend/`, run `.venv/Scripts/python.exe -m alembic upgrade head`. Revision0001 freezes the initial schema. Revision0002 implements the user's revised requirement of six onboard channels, removing channels7–10. These first two revisions leave only `analog_1` through `analog_6`; new installations must continue through CAN/BMS revision0004, described below. Removing these columns cannot recover prior values on downgrade; migration0002 documents the structural rollback behavior. No preexisting project telemetry existed when the development database was migrated.

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

## Current storage and migration head

As of 19 November 2026 the head is 0004, not 0002. Revision 0003 adds
can_frames (received history), can_latest (latest by device/ID/STD-EXT/DATA-RTR)
and can_dbc (legacy fallback). Revision 0004 adds bms_jobs and bms_exchanges.
Current DBC files live in can_dbc/ on disk, not in the legacy table. The refreshed
schema.sql is a MySQL reference from current models; use Alembic for deployment.

This laptop uses navsphere on 127.0.0.1:3306, backed by
C:/xampp/mysql/data/navsphere. Credentials stay in backend/.env. Use SQL backups,
not copies of running database files. Received CAN history has no automatic
purge; analog maintenance does not delete CAN/BMS rows. Security bytes in saved
diagnostic traces are redacted. No retention schedule is installed.

Periodic TX adds no table or migration. audit_events records can_tx_toggle;
device counters reset on reboot and backend status is in memory. There is no
durable per-transmitted-frame log or guaranteed RX self-echo. Independent PCAN
capture establishes wire delivery. Check advancing can_latest frame_count and
payload timestamps, can_frames IDs and statistics.server.persisted for incoming
CAN storage; telemetry_readings and health.persisted cover ADC storage.
