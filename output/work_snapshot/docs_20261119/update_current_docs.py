from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return (ROOT/p).read_text(encoding='utf-8')
def write(p,t):(ROOT/p).write_text(t.rstrip()+'\n',encoding='utf-8',newline='\n')
def rep(p,a,b):
 t=read(p)
 if a not in t:raise ValueError(f'Anchor missing in {p}: {a[:70]}')
 write(p,t.replace(a,b))
def add(p,t):write(p,read(p)+'\n'+t)
def notice(p,t):
 a,b=read(p).split('\n',1);write(p,a+'\n\n'+t+'\n'+b)
status='Updated 19 November 2026 for **v1.1.8 / 8148c3afe9b8**. Last hardware-verified firmware: v1.1.7. Flashing v1.1.8 and final CAN timing/GUI ON/OFF checks remain pending. ESP32 BMS diagnostic success remains unverified. See the project `docs/RELEASE_STATUS.md` for current evidence.'
for p in ['README.md','backend/README.md','frontend/README.md','firmware/README.md','docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md','docs/firmware/CAN_GUIDE.md','output/firmware/README.md']:
 notice(p,status)
rep('README.md','On this laptop, Apache and MariaDB are already running. Setup reuses that','This laptop uses the existing XAMPP MariaDB server; ensure it is running before startup. Setup reuses that')
rep('README.md','Local development login is `admin` / `admin`; change the password in Account','A new development database seeds `admin` / `admin`; the existing account has a changed password. Change the initial password in Account')
rep('README.md','GPIO25 (TX) and GPIO26 (RX), in listen-only mode. Open `/can`','GPIO25 (TX) and GPIO26 (RX), starting in listen-only mode. Diagnostics or periodic TX temporarily enable normal mode. Open `/can`')
rep('README.md','ESP32 transmission is enabled only during diagnostic jobs and returns to\nlisten-only afterward.','Diagnostic transmission is enabled during its job and returns to listen-only afterward. Periodic TX is a separate, mutually exclusive control.')
rep('README.md','The updated firmware is flashed on COM3; 75 backend and 27 frontend tests,','Historical verification on 18 November: firmware was flashed on COM3; 75 backend and 27 frontend tests,')
add('README.md','''## Current instructions and periodic transmission

The [documentation index](docs/README.md) lists setup, API, firmware, database,
test plans, reports and offline editions. Read [release status](docs/RELEASE_STATUS.md)
before interpreting a historical capture or deploying a packaged binary.

On `/can`, **Periodic CAN transmission** switches both standard CAN frames:

| CAN ID | Bytes | Period |
|---|---|---|
| `0x014` | `00 60 00` | 100 ms |
| `0x548` | `00 00 00 00 00 00 00 08` | 10 ms |

Use a changed-password admin account, wait for fresh synchronized device status,
then click ON/OFF and wait for device confirmation. Both start OFF after reboot;
MQTT disconnect or three consecutive failures stop them. Closing the browser
does not stop an enabled device. Unknown status is not confirmation of OFF.
There are no counter/checksum changes or arbitrary-payload controls.
See [wiring, operation and acceptance](docs/firmware/CAN_TX_GUIDE.md).
The v1.1.7 wire test received both payloads but failed timing; v1.1.8's bounded
arbitration retry correction is built and packaged, not yet flashed.
''')
rep('frontend/README.md','Output A is GPIO25 and output B is GPIO26.','Output A is GPIO2 and output B is GPIO0. GPIO25 TX and GPIO26 RX are reserved for CAN.')
add('frontend/README.md','''## CAN and BMS pages

`/can` adds latest/history per ID, DBC signals, current-run/all-saved views,
search by ID/name/signal/DBC/raw bytes, and expandable CAN statistics. Search
applies before pagination while live updates continue; statistics cover the bus.
Multiple definitions are read from project `can_dbc/` with explicit conflicts.

Periodic CAN transmission polls confirmed state every second and controls the
two fixed frames together. ON requires admin, changed password, synchronized
clock, fresh state and idle diagnostics. Known stale state still permits a
best-effort OFF, but acknowledgement is required. See
[CAN TX guide](../docs/firmware/CAN_TX_GUIDE.md). GUI and device versions are
independent; updating the GUI does not flash firmware.

`/bms` provides 55 CDD services, 44 BAT workflows, five Quick reads, previews,
guarded changes and saved responses from HVBEOSK/be_repo. Successful diagnostic
responses through ESP32 remain unverified. Turn periodic TX OFF before BMS work.
''')
add('backend/README.md','''## CAN and BMS backend

Migration head is 0004: 0003 adds CAN history/latest/legacy DBC, and 0004 adds
BMS job/exchange history. CAN uses a separate bounded worker and shared project
DBC folder. See API_CONTRACT.md for CAN/BMS routes and validation.

GET/POST `/api/v1/can/tx` exposes fixed periodic transmission. POST requires
changed-password admin and CSRF, publishes a boot-bound four-second request to
`navsphere/<device_id>/can/tx/request`, and waits up to five seconds for matching
device state. Apply the updated MQTT ACL. Toggle submissions are audited as
`can_tx_toggle`; no new table/migration or durable per-frame TX log is added.
Do not run the simulator under the physical device ID during hardware tests.
''')
rep('docs/firmware/CAN_GUIDE.md','The ESP32 TWAI controller runs in LISTEN_ONLY','The ESP32 TWAI controller starts in LISTEN_ONLY')
rep('docs/firmware/CAN_GUIDE.md','no CAN data or acknowledgements. Other active nodes must acknowledge traffic.','no CAN data or acknowledgements in that mode. Diagnostics or periodic TX temporarily enables normal mode. Other active nodes must acknowledge traffic while ESP32 listens only.')
rep('docs/firmware/CAN_GUIDE.md',"On another PC use `http://192.168.9.253:5173/can` for this laptop's Ethernet\naddress, or `http://192.168.9.59:5173/can` for Wi-Fi.",'The last verified office Wi-Fi URL was `http://192.168.9.59:5173/can`. The older Ethernet address 192.168.9.253 was disconnected; select the current active adapter address.')
rep('docs/firmware/CAN_GUIDE.md','Build with `firmware/tools/build.ps1`','Build from root with `firmware/tools/build.ps1 -ProjectDirectory .`')
add('docs/firmware/CAN_GUIDE.md','''## Search, statistics and transmission

Search CAN messages by hexadecimal ID, message/signal name, DBC filename or
spaced/compact raw bytes. Search precedes pagination; live refresh continues.
Current ESP32 run is the GUI default; All saved IDs retains prior-boot values.
Statistics cover all traffic, not just search matches. Expand CAN statistics &
protocol details for hardware/server rates, throughput, utilization bounds,
standard/extended/RTR counts, DLC distribution, per-ID timing, errors and drops.
Per-ID intervals use the last 64 delivered intervals. Estimated load excludes
error-frame wire time; no voltage/termination/ACK waveform measurement is provided.

The new Periodic CAN transmission section controls 0x014 at 100 ms and 0x548
at 10 ms together. Read [CAN TX guide](CAN_TX_GUIDE.md) for exact payloads,
TJA1042/3 VCC/VIO wiring, GUI operation, command limits and remaining tests.
Successful periodic frames do not establish successful BMS diagnostic responses.
''')
api='''## CAN, DBC and statistics APIs (v1.1.8)

GET routes require a session; DBC writes require admin and CSRF.

| Route | Parameters and behavior |
|---|---|
| GET /api/v1/can/latest | device_id; offset 0..1000000; limit 1..500 (100 default); current_boot_only (API false, GUI true); search up to 128 chars. Returns frames, has_more, dbc/library, status, current_boot_id, server_time and metrics |
| GET /api/v1/can/history | device_id; optional numeric can_id and extended; before_id cursor; limit 1..1000 (100 default). Returns frames and next_before_id |
| GET /api/v1/can/statistics | device_id; bounded process/device statistics and server ingestion metrics |
| POST /api/v1/can/dbc/files | JSON filename/content; project folder file up to 2 MiB; replacement only after valid parse |
| POST /api/v1/can/dbc | Legacy per-device DBC up to 512 KiB; fallback when project folder is empty |

Query can_id is decimal: can_id=20 selects 0x014. Search accepts hex spelling.
History is newest first. The folder library supports 128 files/32 MiB total.

## Periodic CAN control

GET `/api/v1/can/tx?device_id=ESP32_001` returns profiles, supported,
clock_ready, fresh, age_seconds, boot_id, mode and nullable state. Profiles
contain numeric can_id, hex data, dlc and period_ms. State contains enabled,
command_id, reason, sent_014, sent_548, failures and skipped. Reasons are off,
on, connection_lost, transmit_failed and controller_busy_or_unavailable.
Modes include listen_only, diagnostic, periodic_tx and unavailable. Fresh
requires supported status under five seconds old and backend MQTT connected;
clock_ready requires synchronized telemetry matching the CAN boot ID.

POST `/api/v1/can/tx` accepts exactly:

```json
{"device_id":"ESP32_001","enabled":true}
```

Set enabled false for OFF. Numeric/string booleans and extra fields are rejected.
Admin, changed initial password, cookie and X-CSRF-Token are required. ON needs
fresh state, valid clock and idle diagnostics. OFF with known stale state is
best effort. The backend waits up to five seconds for matching device state.
HTTP 200 can still contain enabled=false with a refusal reason: check the state.
409 covers conflicts/unavailability; 504 acknowledgement timeout; 422 validation;
401/403 auth restrictions; unknown-device GET is 404. Only one toggle may wait
for confirmation at a time. Submissions are audited as can_tx_toggle.

The fixed profiles are standard 0x014/006000/100ms and
0x548/0000000000000008/10ms. No arbitrary transmit API exists. Counter/status
state is not a durable per-frame TX log. See docs/firmware/CAN_TX_GUIDE.md from root.

## BMS diagnostics API

Active catalogue: HVBEOSK/be_repo, 55 CDD services and 44 BAT workflows.
ESP32 diagnostic responses remain unverified. GET requires session; all POST
routes require changed-password admin and CSRF.

| Route | Request / result |
|---|---|
| GET /api/v1/bms/catalog | Catalogue and reference status; no keys |
| POST /api/v1/bms/preview | device_id, kind cdd/preset, entry_id, values; optional instance, ecu, session, security, image_filename, image_id, inject_crc; returns preview/token |
| POST /api/v1/bms/jobs | token and confirmation from preview; HTTP 202 job |
| POST /api/v1/bms/read | device_id; command qr/serial/hardware/manufacturing/mode; optional instance and ecu; HTTP 202 job |
| GET /api/v1/bms/jobs | device_id; recent saved jobs |
| GET /api/v1/bms/jobs/{job_id} | optional offset >=0; job and exchanges |
| POST /api/v1/bms/jobs/{job_id}/cancel | Cancel requested job |

Profile abs_hv uses 0x7E4/0x7EC; abs_hv_old uses 0x640/0x650. State-changing
workflows require preview confirmation; Quick reads execute documented preparation.
Turn periodic TX OFF first. See docs/development/BE_CLIENT_IMPLEMENTATION.md.

## CAN and diagnostic MQTT extensions

`navsphere/<device_id>/can` carries non-retained schema-v1 batches, at most 24
classic frames and 8192 bytes at backend, plus CAN stats. Optional software
version, mode and periodic_tx fields preserve earlier firmware compatibility.
`can/tx/request` is backend-write/device-read, QoS1 and never retained. Its exact
five-field schema and TTL rules are in the CAN TX guide; confirmations arrive
in CAN stats, not GPIO ack. Diagnostic transport uses diag/request and
diag/response separately. Existing ADC/GPIO MQTT interfaces remain unchanged.
'''
for p in ['backend/API_CONTRACT.md','docs/api/API_REFERENCE.md']:
 notice(p,'Updated 19 November 2026 for application v1.1.8. Existing analog/GPIO interfaces are retained; CAN/DBC/BMS/TX extensions follow below. The generated docs/api/openapi.json matches the current routes.')
 add(p,api)
add('database/README.md','''## Current storage and migration head

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
''')
for p in ['firmware/README.md','docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md']:
 rep(p,'-File firmware/tools/build.ps1\n','-File firmware/tools/build.ps1 -ProjectDirectory .\n')
 rep(p,'no board was flashed automatically during this implementation.','earlier firmware has been flashed on COM3. Current v1.1.8 flashing is pending; see docs/RELEASE_STATUS.md.')
 add(p,'''## CAN and shared software version extensions

Classic CAN is 500 kbit/s on GPIO25 TX/GPIO26 RX. It starts listen-only; diagnostic
jobs or explicit periodic ON temporarily own normal mode, mutually exclusively.
Accept-all standard/extended DATA/RTR receive uses separate bounded MQTT/serial
queues. UART 115200 prints CAN frames when capacity allows; CAN_STATUS exposes
counters even with no frames. Mode switches and busy queues can lose frames.

The can_tx_rules/can_tx modules define 0x014 (00 60 00, 100 ms) and
0x548 (00 00 00 00 00 00 00 08, 10 ms), a priority-5 4096-byte task and
eight-command queue. Default OFF; stop on MQTT disconnect or three consecutive
failures; skip missed slots. v1.1.8 retries arbitration-only loss within
5 ms/16 attempts. Exact payloads have no changing counter/checksum. State is
confirmed in CAN stats; GPIO and BMS request protocols are retained. Read the
root docs/firmware/CAN_TX_GUIDE.md for full behavior, VCC/VIO wiring and tests.

version.json generates SW_VERSION, SW_BUILD_ID and SW_BUILD_UTC and matching
GUI constants. The UI compares its own build with actual device reports.
Root builds use build/ and sdkconfig; standalone builds use firmware/build/
and independent firmware/sdkconfig. Do not mix them. An already provisioned
board needs only the application update, from the repository root in an IDF terminal:

```powershell
python -m esptool --chip esp32 --port COMx --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x10000 output/firmware/navsphere.bin
```

Detect the actual port, close monitors, verify written hash and startup identity,
then release the port. Preserve NVS; do not erase or reprovision for routine updates.
New-board provisioning is separate. No OTA flashing workflow is implemented.
''')
p='docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md'
rep(p,'Six onboard ADC channels, ESP32S-WROOM. Updated 11 November 2026.',status)
rep(p,"192.168.31.50, different from the original prompt's192.168.9.59 example.",'192.168.31.50 at initial setup; the last verified office Wi-Fi address on 19 November was 192.168.9.59.')
rep(p,'Open http://localhost:5173. The initial local development account is admin/admin.','Open http://localhost:5173. A new development database seeds admin/admin; the existing installation has a changed password.')
rep(p,"database session. Browser visual QA could not be completed in the agent's\nComputer Use session; automated component and integration tests are reported\nseparately.",'database session. Browser checks and genuine dated screenshots are preserved under output/testing and output/reports; consult their actual firmware versions.')
rep(p,'Native development binds MQTT1883, API8000 and frontend5173 to loopback. All','The native frontend defaults to 0.0.0.0:5173; backend remains loopback:8000. MQTT1883 must be reachable from the physical ESP32. All')
rep(p,'-File firmware/tools/build.ps1\n','-File firmware/tools/build.ps1 -ProjectDirectory .\n')
rep(p,'After checking the physical wiring, actual serial port and any existing NVS\nbackup, run from firmware in the IDF terminal:','For a NEW board only, check wiring, actual serial port and NVS backup, build the standalone configuration, then run from firmware in the IDF terminal:')
rep(p,'Replace COMx with the detected port. Flashing was not performed by the agent.','Replace COMx with the detected port. Earlier firmware was verified on COM3; v1.1.8 flashing is pending. Use the application-only procedure below for the existing provisioned board.')
add(p,'''## Current application update and CAN operation

Source, GUI and packaged application are v1.1.8 / 8148c3afe9b8. The manifest
records hardware_flashed=false. Last verified device firmware is v1.1.7. Close
serial monitors, detect the port (previously COM3) and run from root in an IDF terminal:

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
python -m esptool --chip esp32 --port COMx --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x10000 output/firmware/navsphere.bin
```

This preserves NVS, bootloader and partition table. Verify the hash and startup
version/build. Do not erase flash. Updating the GUI does not flash the device.

On /can select Current ESP32 run or All saved IDs, search CAN messages, inspect
raw history and expand CAN statistics & protocol details. Put multiple DBC files
directly in can_dbc/; changes reload automatically and conflicts are explicit.
Periodic CAN transmission controls standard 0x014 / 00 60 00 / 100 ms and
0x548 / 00 00 00 00 00 00 00 08 / 10 ms together. Use changed-password admin,
fresh synchronized status and idle diagnostics. Wait for actual ON/OFF confirmation.
Closing the browser does not stop enabled TX. See
[full instructions and acceptance](../firmware/CAN_TX_GUIDE.md).

/bms provides the BE reference's 55 CDD services and 44 workflows. Keep the local
HVBEOSK/be_repo reference and private keys/images available. ESP32 diagnostic
response success remains unverified; turn periodic TX OFF before BMS work.
Programming/erase/reset commands are not connectivity tests.

The database is navsphere on existing XAMPP MariaDB at 127.0.0.1:3306, data
under C:/xampp/mysql/data/navsphere. Received CAN goes to can_frames/can_latest;
ADC goes to telemetry_readings; BMS jobs/exchanges and audits are separate.
TX counters do not imply a durable per-frame TX log. Check advancing persisted
counters and row timestamps, not only an online badge. See database/README.md.

Remote PCs must use the laptop's CURRENT IPv4 address with HTTP and port 5173.
192.168.9.59 was last verified; 192.168.9.253 is historical. Check frontend binding,
LocalSubnet firewall rules and FRONTEND_ORIGINS. The proxy keeps port 8000 private.
Office VLAN/client isolation may require an office network rule.

RX without TX: check TJA1042/3 VCC=5 V, VIO=3.3 V, STB LOW, GPIO25->TXD,
GPIO26<-RXD, ground, termination and another normal-mode node supplying ACK.
PCAN active receive can supply ACK without application messages; listen-only cannot.
The preserved receiver helper is in output/work_snapshot/can_tx_20261119/runtime;
restore it to .runtime before use. Only one test/helper should own PCAN.
Do not stop unrelated processes. Power correction restored payload delivery on
v1.1.7, but v1.1.8 timing acceptance is still pending.

## Documentation and release refresh

Use [documentation index](../README.md) for current/historical scope and
[document export tools](../tools/README.md) for reproducible offline editions.
After application changes, rebuild firmware and GUI, check their shared identity,
then run `backend/.venv/Scripts/python.exe scripts/package_release.py --build-directory build`.
Use --hardware-flashed only after verifying this exact image on hardware; it
does not itself certify CAN timing or BMS behavior. Preserve historical evidence.
''')
rep('output/firmware/README.md','It starts in listen-only; BMS diagnostics temporarily enable transmission.','It starts in listen-only; diagnostics or periodic ON temporarily enable transmission, with mutually exclusive ownership.')
add('output/firmware/README.md','''## Existing provisioned board: application-only update

From this directory in an IDF terminal, close monitors and use the detected port:

```powershell
python -m esptool --chip esp32 --port COMx --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x10000 navsphere.bin
```

Preserve NVS, bootloader and partition table. Verify hash and startup identity.
v1.1.8 / 8148c3afe9b8 application SHA-256 is
5f48790458c4f0903e2ce1249dd9ba49b8e5b3d0a625fd5781c3d88160166ced.
hardware_flashed is false. The periodic frames are 0x014/006000/100ms and
0x548/0000000000000008/10ms, switched together on /can. See the root
docs/firmware/CAN_TX_GUIDE.md for operation and pending acceptance.
''')
rep('firmware/test/HARDWARE_TEST_PLAN.md','Status: **not executed on a physical board**. The source is compiled for classic\nESP32, and command logic is tested on Windows. No firmware was flashed as part\nof those checks.','Status: earlier firmware was flashed and CAN/telemetry paths exercised on hardware. Full electrical/calibration/soak acceptance remains incomplete. v1.1.8 is built but not flashed; see docs/RELEASE_STATUS.md.')
rep('firmware/test/HARDWARE_TEST_PLAN.md','Place meter or high-impedance scope on GPIO25 and GPIO26','Place meter or high-impedance scope on GPIO2 and GPIO0')
rep('firmware/test/HARDWARE_TEST_PLAN.md','A=1 drives only GPIO25 HIGH; B=1 drives only GPIO26 HIGH','A=1 drives only GPIO2 HIGH; B=1 drives only GPIO0 HIGH')
rep('firmware/test/HARDWARE_TEST_PLAN.md','Observe reset, brownout and reboot using external pull-downs','Observe reset/brownout with actual driver/load; keep GPIO0 HIGH at reset and GPIO2 LOW or floating for serial flashing')
rep('docs/testing/HARDWARE_TEST_PLAN.md','These hardware checks are pending until a board, wiring and serial port are\navailable. See integration-results.json for the separately measured host path.','Earlier firmware was flashed and CAN/telemetry tested, but full electrical/calibration/soak acceptance is incomplete. See ../RELEASE_STATUS.md. integration-results.json is historical simulator evidence.')
for p in ['docs/testing/HARDWARE_TEST_PLAN.md','firmware/test/HARDWARE_TEST_PLAN.md']:
 add(p,'''## Periodic CAN TX acceptance, v1.1.8

The v1.1.7 test delivered exact bytes after power correction but failed timing.
v1.1.8 arbitration retry correction needs a physical test. Follow the root
docs/firmware/CAN_TX_GUIDE.md: verify exact image/hash, supplies, bitrate and ACK;
OFF baseline with no duplicate source; 10 s ON with exact IDs/DLC/bytes;
mean periods within 5% of 100/10 ms, max below twice period, no new failures;
OFF plus 300 ms grace and 3 s without either ID. Exercise actual GUI controls,
verify RX/ADC persistence, reboot default OFF and MQTT disconnect stopping TX.
Reconnect must not re-enable it. Leave OFF and release COM. Diagnostic success
is a separate unresolved check; no BMS programming/erase/reset belongs here.
''')
notice('docs/architecture/CODEBASE_ASSESSMENT.md','Historical baseline assessment, 11 November 2026. Current extension map follows below; current validation is in ../RELEASE_STATUS.md.')
add('docs/architecture/CODEBASE_ASSESSMENT.md','''## Current extensions, 19 November 2026

The native C/FreeRTOS, FastAPI, MariaDB and React foundation remains. Independent
CAN queues/worker feed raw history/latest and shared DBC decoding. The CAN page
adds search, statistics and confirmed fixed-frame TX. can_tx_rules/can_tx use
CAN manager ownership shared exclusively with diagnostics. The BE BMS service
prepares 55 CDD services/44 BAT workflows, ESP32 ISO-TP and persistent jobs;
hardware diagnostic success remains unverified. Shared release identity covers
firmware/GUI. Reports and snapshots document scope without altering runtime behavior.
''')
notice('docs/development/BE_CLIENT_IMPLEMENTATION.md','Status update, 19 November 2026: this remains the active BMS reference. Separate periodic frames were received on v1.1.7 after supply correction; that does not verify BMS/UDS responses. Diagnostics were not rewritten or retested. v1.1.8 timing correction is unflashed. Turn periodic TX OFF before BMS jobs; see ../RELEASE_STATUS.md.')
notice('docs/development/CAN_BMS_IMPLEMENTATION.md','Historical HVP work record. Current status is in ../RELEASE_STATUS.md and BE_CLIENT_IMPLEMENTATION.md. Preserve old counts and results as dated evidence, not current instructions.')
notice('MASTER DEVELOPMENT PROMPT.md',"Historical requirements with later scope appended below. Original implementation directives are background, not permission to rerun programming/hardware actions. Current status: docs/RELEASE_STATUS.md.")
add('MASTER DEVELOPMENT PROMPT.md','''# Scope additions through 19 November 2026

Preserve six ADC1 inputs and GPIO2/GPIO0 controls. Add 500 kbit/s classic CAN on
GPIO25 TX/GPIO26 RX, raw history/latest, multiple project can_dbc files, search
and separate statistics. The active BMS reference is HVBEOSK/be_repo, replacing
HVP: 55 CDD services, 44 BAT workflows, ESP32 ISO-TP, responses and saved history.
BMS diagnostic hardware success remains unresolved and was deferred by the user.

Latest feature: one ON/OFF button for standard 0x014 = 00 60 00 every 100 ms
and 0x548 = 00 00 00 00 00 00 00 08 every 10 ms. Repeat exact bytes; 0x548
supersedes the screenshot's 0x584. Keep prior features intact and use shared
SW_VERSION. Track code, failures, tests, screenshots, instructions and AI effort;
do not invent credits or label pending hardware tests as passed.
''')
add('can_dbc/README.md','''The library decodes received frames. Adding a DBC does not change fixed periodic
TX payloads or firmware. Search/statistics remain on /can; see the root
docs/firmware/CAN_TX_GUIDE.md for the separate transmission feature.
''')
add('bms_images/README.txt','''Status, 19 November 2026: successful ESP32 diagnostic responses remain unverified.
Turn periodic CAN TX OFF before BMS work. Active reference: HVBEOSK/be_repo,
55 CDD services and 44 BAT workflows. No BMS erase/program/reset validation was
performed for the periodic TX feature.
''')
notice('IMPLEMENTATION_REPORT.md','Current documentation review: 19 November 2026. The dated sections below are chronological evidence; docs/RELEASE_STATUS.md summarizes the latest v1.1.8 build and pending hardware tests. docs/README.md indexes the refreshed instructions and offline reports.')
print('Updated maintained documents; application source unchanged.')
