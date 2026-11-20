# NavSphere complete implementation report

Current documentation review: 20 November 2026. Dated sections below are chronological evidence; docs/RELEASE_STATUS.md records the current v1.1.20 hardware validation.

11 November 2026 · ESP32S-WROOM · Six onboard ADC1 channels

## 1. Delivered scope

NavSphere implements a local telemetry pipeline from ESP32 firmware through
authenticated MQTT, FastAPI, the existing MySQL-compatible server and a React
dashboard. The user explicitly reduced the initial ten-channel request to six
onboard channels with no extra acquisition hardware. The master development
prompt, firmware, payload schema, simulator, database and UI reflect that change.

The software is implemented and host-tested. Hardware measurement accuracy,
physical output voltages, RF behavior and long-duration stability remain pending
on an actual connected board. No board was flashed. Browser visual verification
could not be completed because Computer Use stopped when it could not establish
the current Edge URL confidently. Docker execution is unverified.

## 2. Requirements and existing codebase

The initial repository contained only the master prompt and a native ESP-IDF
CMake skeleton. `firmware/main/main.c` had an empty `app_main()`. No Wi-Fi
implementation, event handlers, SDK target, pin assignment or credentials were
provided. The original ESP-IDF/CMake foundation was extended, with no Arduino
migration and no working Wi-Fi module replaced. Preservation of pre-existing
Wi-Fi behavior cannot be claimed because the supplied code contained none.
The detailed pre-implementation assessment is in docs/architecture/.

The user identified ESP32S-WROOM. Classic ESP32 ADC2 shares resources with Wi-Fi;
the selected six exposed ADC1 GPIOs avoid that conflict. GPIO37/38 are not
assumed to be exposed on the WROOM board. All six telemetry fields are logical
names with an explicitly documented physical mapping.

## 3. System architecture

```text
ESP32 ADC1 acquisition -> bounded sample queue -> MQTT publish at nominal 100 ms
                                            -> Mosquitto authenticated topics
                                            -> bounded backend ingress queue
                                            -> validation -> MySQL commit
                                            -> WebSocket received/persisted events
                                            -> React overview and analytics
Admin -> authenticated REST -> audited command -> MQTT -> ESP32 GPIO latch
                                                  <- accepted/applied/rejected ack
```

Services and artifacts are segregated into firmware/, backend/, frontend/,
database/, mqtt/, simulator/, scripts/, docs/ and output/pdf/. Secrets and
downloaded tools are excluded from source. The optional container topology
has no MySQL service, so it cannot silently start a second database instance.

## 4. Firmware and FreeRTOS design

Native C11 modules separate application configuration, Wi-Fi events, ADC access,
MQTT transport, command validation and output handling. The acquisition task
has priority 5 and 4096 bytes of stack. The publishing task has priority 4 and
6144 bytes. Wi-Fi and MQTT reconnect workers use priority 3 and 3072 bytes each.
Both periodic tasks use `vTaskDelayUntil()`. Acquisition is independent of
broker availability. The statically allocated four-sample queue discards older
samples under pressure and counts losses; publishing drains to the newest
sample. The MQTT outbox is capped at 16 KiB with a bounded residence policy.

There is no disconnected flash telemetry journal. Offline samples are dropped
and counted rather than accumulating indefinitely. Stale publication preserves
the original acquisition sequence and timestamp. It cannot masquerade as a new
measurement. Telemetry construction uses bounded buffers; cJSON command parsing
and SDK MQTT allocations are documented exceptions to static-memory preference.
No formal MISRA or CERT compliance certification is claimed.

## 5. ADC and output mapping

| Logical signal | Physical function |
|---|---|
| analog_1 | GPIO32 / ADC1 |
| analog_2 | GPIO33 / ADC1 |
| analog_3 | GPIO34 / ADC1 |
| analog_4 | GPIO35 / ADC1 |
| analog_5 | GPIO36 / ADC1 / VP |
| analog_6 | GPIO39 / ADC1 / VN |
| A | GPIO2, active-high LED/output |
| B | GPIO0, active-high output |

The ADC uses12 bit resolution,12 dB attenuation and configurable averaging
(default 4 reads per channel). The driver requires usable eFuse calibration;
if unavailable, values are explicitly invalid instead of claiming calibrated
millivolts from an assumed reference. Six validity bits give a full mask of 63.
An invalid numeric zero is not a zero-volt measurement. Floating pins can
return readable but meaningless values. Attenuation is not5V protection.

GPIO2/0 initialize LOW and return LOW after observed network disconnection,
clock invalidity or the configurable 60-second inactivity watchdog. Reset-time
electrical guarantees require suitable external circuit design. An applied ack
means the software GPIO latch write succeeded, not that an independent sensor
measured the voltage or load action. No built-in LED pin was assumed.

## 6. MQTT communication

Topics are `navsphere/{device_id}/telemetry`, `/command`, `/ack` and `/status`.
Telemetry uses QoS1, one versioned JSON message containing six millivolt values,
six raw values, valid_mask, device/boot identity, unsigned32 sequence, original
sample time, clock validity, uptime, stale flag, source and loss counters.
SNTP supplies valid epoch time; otherwise epoch is null. Commands without a
valid device clock are rejected. Per-device usernames and ACLs constrain topic
access. Status and LWT are retained; telemetry, commands and acks are not.

Commands contain a unique ID, A/B key, integer0/1, issue time and expiry. Strict
validation rejects extra/duplicate fields, malformed JSON, oversized or retained
messages, invalid IDs and expired delivery. A bounded replay guard prevents
duplicate execution. Publication stays pending until a boot-bound ack arrives.
Backend command records have pending/accepted/applied/rejected/timed_out states.

Mosquitto 2.1.2 was downloaded from the publisher and extracted locally, without
running the installer or registering a Windows service. Anonymous access is
disabled. The tested listener is127.0.0.1:1883. TLS configuration is supported
for protected deployments; plaintext loopback is the executed development mode.

## 7. Python backend

FastAPI modules implement authentication, devices, health, telemetry queries,
commands, MQTT and database services. Pydantic validates exact six-channel
schemas and numeric/time invariants. The MQTT network callback only transfers
bounded messages; database work runs outside it. The default 2048message RAM
queue bounds memory. A failed head insertion retries for up to 10 seconds, then
drops/counts it. Continued database outage can overflow the queue. Recovery is
tested; no disk spool is claimed. One Uvicorn worker owns MQTT and WebSocket
state. Multiworker use requires a shared bus and rate limiter.

Clients receive explicit received and persisted events. Persisted events are
emitted only after successful transaction commit. The persisted_at field is
assigned just before insertion work and is not an exact commit-completion
timestamp. Counters and recent frequency cover the current backend process,
not lifetime database totals. Health/readiness distinguish process availability
from broker/database readiness. Structured logs avoid credentials.

## 8. Database architecture

The existing XAMPP MariaDB 10.4.32 at 127.0.0.1:3306 is reused. Setup creates
navsphere and an isolated application account. Alembic0001 records the initial
schema;0002 explicitly reduces analog storage to six columns. The current
telemetry table stores unsigned serial ID, device/boot/sequence, nullable epoch,
server timestamps, six unsigned millivolt fields, validity mask and JSON metadata.
Users, sessions, devices, commands and audit events are separate tables.

The unique device/boot/sequence index handles QoS1 repeats and reboot sequence
reuse. Device/time, receive-time and retention indexes support latest/history
queries. History has a maximum 31day window and 2–2000points; SQL time buckets
bound returned points and preserve full-range valid min/max/average statistics.
The dashboard exports plotted points, including averages when downsampled.

At 10 Hz one device produces 864,000 rows/day. Measure actual table/index growth
before selecting retention. A dry-run maintenance command reports candidates;
explicit execution deletes eligible telemetry in bounded batches. Backups use
single-transaction mysqldump of NavSphere only; a real local backup was generated
successfully. Automatic retention scheduling was not enabled.

## 9. Frontend architecture and behavior

React 19, TypeScript, Vite, Recharts and local Inter font assets provide a
responsive industrial dashboard. Hooks manage authenticated sessions, CSRF,
bounded600sample browser histories and reconnecting WebSockets. Pages cover
login, overview, six dedicated analytics routes, Account and admin Controls.
Cards show physical mappings, validity, original sample freshness, sparklines
and receipt/persistence distinctions. Dark mode is default, with light mode.

Analytics supports live/history, local timestamps, UTC CSV, common time ranges,
custom ranges, brush zoom/pan and full-range statistics. Invalid values are
chart gaps. Loading, unavailable, stale, interrupted and error states are
explicit. Simulator source is labelled. Commands are never optimistically
displayed as applied; status and returned controls reflect backend evidence.

## 10. Security architecture

Passwords use salted scrypt. Random session tokens are stored as hashes and
sent through HttpOnly/SameSite cookies. Mutations require per-session CSRF.
Role checks protect commands, and the initial development password must change
before actuation. Login attempts are rate-limited, sessions expire/revoke, and
administrative activity is audited. OpenAPI declares cookie auth and CSRF input.
Production settings reject default admin credentials, insecure cookies,
plaintext MQTT, SQLite and non-HTTPS frontend origins. Startup also refuses
active stored accounts that still verify against the default development
password, including accounts retained when promoting a development database.

Local .env/NVS provisioning keeps secrets out of source. Development NVS is
not encrypted; production needs reviewed secure boot/flash/NVS encryption and
trusted TLS certificates. No irreversible eFuse changes were performed. MQTT
messages rely on authenticated scoped broker identities rather than independent
application signatures. Deployment hardening and real electrical validation
remain operator responsibilities, not completed certification claims.

## 11. Installation and configuration

Use scripts/setup_windows.ps1, then scripts/start_local.ps1. They download
portable tools, install Python/frontend dependencies, preserve existing local
configuration, generate random service credentials and apply migrations. Detailed
commands are in the separate deployment/user guide. All development services
bind to loopback. LAN exposure/firewall changes are explicit operator steps.
The prompt's192.168.9.59 is configurable; the adapter observed on this laptop
was192.168.31.50. The dashboard and docs are at localhost5173 and 8000.

The master prompt and component documents specify the final six-channel scope.
Firmware settings are centralized in app_config.h and Kconfig; secrets are
provisioned into the navsphere NVS namespace. Backend uses environment variables,
the frontend uses Vite variables/proxy settings, and broker paths are generated
for the local workspace. No secret value is included in this report.

## 12. Test and performance evidence

The automated backend suite passed 28 tests including validation, auth/CSRF,
roles, persistence, deduplication, WebSocket delivery, command state transitions,
status/safe-state updates and database failure recovery. Ruff and Python
compilation passed. These unit tests use isolated SQLite databases; they do not
substitute for the separately executed MariaDB test.

The frontend suite passed 15 tests across API, pages and live WebSocket behavior.
The production TypeScript/Vite build passed. The dependency audit reported zero
known vulnerabilities at the executed check. Visual browser QA remains incomplete.
Firmware compiles against installed ESP-IDF 6.0.2 for classic ESP32. Host C tests
cover 13 command-rule assertions and actual parser/dedupe/queue/watchdog logic.
The simulator suite passes 10 tests; process-tree shutdown was tested with a
sacrificial parent/child and with the live stack, leaving Apache/MySQL running. Firmware
hardware accuracy, measured scheduling jitter and 24hour soak are not yet tested.

The final live integration run stored 300 of 300 synthetic records over 30.002 s
(9.999 Hz), with zero simulator drops. It verified six channels in MariaDB,
received/persisted WebSocket messages, all six histories, A/B on/off acks,
malformed-message counting, QoS1 deduplication, authorization, CSRF, password
change, logout, Swagger/ReDoc/OpenAPI and readiness. The current run's exact
measurements are recorded in docs/testing/integration-results.json.

In that run, sample-to-insert-timestamp latency was median 1 ms, p95 3 ms, maximum 19 ms.
Observed latest committed reading age via REST was median 56.63 ms, p95 104.11 ms.
These are same-host synthetic measurements, include scheduling effects, and
do not measure sensor/RF latency. Target 10 Hz and p95 committed-reading age under
250 ms at one simulated device were met in this run. No multi-device capacity
or hardware CPU/heap endurance claim is made.

## 13. Phase delivery record

| Phase | Concrete outputs and verification |
|---|---|
| 1 Assessment | Inspected all original firmware files; assessment in docs/architecture; identified empty app and later confirmed board |
| 2 Architecture | Six-channel schema, topic contract, GPIO map, configuration and safe states defined |
| 3 Firmware | Native ADC/Wi-Fi/MQTT/commands implemented; IDF build and host C tests executed; board tests pending |
| 4 Broker | Portable Mosquitto, PBKDF2 passwords, scoped ACLs; authenticated live connection tested |
| 5 Backend | FastAPI/MQTT/WS/auth modular source;28 tests and Ruff passed |
| 6 Database | Alembic head0002 on existing MariaDB; actual six-column storage/deduplication and backup tested |
| 7 Frontend | React six-card dashboard, six analytics routes, admin/account;15 tests and build passed |
| 8 Integration | Real broker/backend/MariaDB path plus synthetic device and command acks tested |
| 9 Measurement |30second10 Hz test; measured throughput and read-age; no hardware benchmark claimed |
| 10 Delivery | Separate Markdown/PDF reports, guides, test evidence, native scripts and optional Compose |

Commands include `idf.py build` via firmware/tools/build.ps1, firmware host
tests, `python -m pytest -q`, `python -m ruff check app tests migrations`,
`npm test`, `npm run build`, `python scripts/integration_test.py`,
`python scripts/backup_database.py` and the native Windows start helpers.
The next implementation step is physical provisioning and the hardware test plan.

The final firmware binary is 988,272 bytes, leaving about 69% of the 3 MiB
application partition free. Link-time IRAM is 87,999/131,072 bytes (67.14%);
static DRAM is 44,511/180,736 bytes (24.63%). Runtime heap and stack margins
require hardware measurements. Build evidence and SHA256 are recorded in
docs/testing/build-results.json and output/firmware/manifest.json.

## 14. Limitations, troubleshooting and future work

Physical ADC calibration/linearity, actual output levels, reset behavior,
10 Hz jitter, Wi-Fi recovery and heap/stack soak must be verified on the board.
No connected serial device was detected. An end-to-end simulator cannot prove
these. Browser rendering remains unverified by the agent because its UI tool
stopped on URL policy. Docker was not installed, so Compose was not executed.

Database/broker startup failures appear in readiness and local logs. Check
credentials and actual ports rather than treating phpMyAdmin as the database
endpoint. Invalid/stale cards require valid sensors and timestamps, not just a
connected MQTT socket. Commands can fail on first-login restrictions, CSRF,
stale devices, clock synchronization, expiry or unavailable broker. The output
watchdog is intentional. The deployment guide has reproducible troubleshooting
and manual QA instructions.

Future improvements can include measured hardware calibration characterization,
an endurance test, persistent offline spooling if required, shared event state
for multiworker deployments, managed certificate rotation, user-management UI,
and workload-based retention/aggregation. These are identified extensions rather
than completed features.

## 15. Primary references

- [Espressif ADC oneshot driver](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc_oneshot.html)
- [Espressif ADC calibration](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc_calibration.html)
- [ESP32-WROOM-32 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32_datasheet_en.pdf)
- [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/)
- [Mosquitto configuration](https://mosquitto.org/man/mosquitto-conf-5.html)
- [Node official downloads](https://nodejs.org/en/download)

Firmware API choices were also checked against installed ESP-IDF headers.

## 16. CAN statistics and BMS diagnostics update — 18 November 2026

This section supersedes earlier no-board-flashed/browser-unverified statements
for the CAN/BMS delivery. The original simulator measurements above remain
historical evidence and are not presented as new hardware benchmarks.

Added a separate CAN statistics section and a new BMS diagnostics page. The
local reference catalogue exposes 111 actual CDD services and 42 batch-script
workflows, with source-based codecs, image validation, temporary ESP32 ISO-TP
transmission, session/security handling, previews, decoded/raw responses and
persistent jobs/exchanges. Migration 0004 adds two BMS tables after a database
backup. Existing analog, GPIO2/GPIO0, CAN history and DBC features remain.

Verification: 58 backend tests, 25 frontend tests, firmware host tests, Ruff,
TypeScript/Vite and ESP-IDF builds passed. The 1,007,952-byte firmware was flashed
on COM5 with hash verification. MQTT, database and physical CAN reception are
live; both GUI additions were visually inspected and screenshots saved.

Live BMS read requests failed at CAN transmission; failed request history and
listen-only restoration were verified. Heavy repeated 0x06E traffic, bus errors
and substantial capture/publish losses are visible. Successful BMS hardware
responses, destructive workflows and lossless full-load capture are not claimed.
One script-referenced boot-updater image is missing and requires a replacement.

The [detailed work record](docs/development/CAN_BMS_IMPLEMENTATION.md) contains
AI work performed, source discrepancies, usage, test evidence, screenshots,
firmware hash, reference/image locations and outstanding physical checks.

### Superseding BE reference update — 18 November 2026

At the user's request, the active BMS reference is now `HVBEOSK/be_repo`.
AMP Client 15.0.4, 55 CDD services and all 44 BAT workflows were inspected;
the current CAN pair is 0x7E4/0x7EC, with 0x640/0x650 retained for the migration
scripts that explicitly select the old profile. All six supplied programming
images pass preparation, including relocated bootloader updater images.

The page adds one-click application-mode reads and automatic preparation,
session/security, bootloader authentication and programming steps. Existing
analog/GPIO/raw-CAN/DBC functionality remains. The new firmware is flashed and
hash verified on COM3. Validation passed: 75 backend tests, 27 frontend tests,
firmware host tests, Ruff, frontend production build and ESP-IDF build.

Live PCAN reads returned serial, QR and manufacturing-serial data. Original EXE
codec failures were identified and handled in the web decoder. ESP32 hardware
reads still fail to transmit and receive no frames despite PCAN bus activity;
the transceiver supply and wiring are being checked. No live BMS write, erase,
security unlock or programming is claimed. This update supersedes the previous
reference counts, missing-image note and COM5 firmware details for this task.
See [the BE report](docs/development/BE_CLIENT_IMPLEMENTATION.md) for evidence,
workflow details, observed timing and AI work attribution.

Firmware regression check: the flashed COM3 image matched the intended build;
CAN ID/data prints were still present. A temporary test of the pre-BMS Git
image also received zero frames while PCAN received 8,467 in 20 seconds.
The current firmware was restored with a build fingerprint and periodic CAN
status output; all three flash components verified. The final comparison still
received zero ESP32 frames versus 9,263 PCAN frames. MQTT, fresh analog database
delivery and the LAN dashboard remained working. The offline package was
refreshed to match the flashed application (`bd1af2db...`, 1,009,264 bytes).
See the BE report's firmware investigation and `output/testing/be-firmware-audit.json`.

### Software version 1.1.0 and restored CAN reception

Added shared `SW_VERSION` firmware macros and GUI constants, automatic patch
increments for changed source builds, matching/stale/missing device-version
display and release packaging checks. Version 1.1.0 (source build
`2e6876f40c71`) was flashed to COM3 and all component hashes verified. The
terminal and GUI both reported the intended version. A 20-second serial capture
contained 2,415 CAN lines; a separate six-second comparison captured 3,425
frames and persisted 674 new CAN database records. CAN reception is now live;
existing serial/MQTT delivery drops remain visible in statistics. The follow-up
read still failed to transmit, so BMS diagnostics are not claimed as working.
Validation: 3 versioning tests, 48 relevant backend tests, 30 frontend tests,
Ruff, production GUI/firmware builds and firmware host checks passed. Details,
screenshots and machine-readable evidence are linked in the BE report.

### CAN GUI current-value correction — software 1.1.3

Live inspection found that incoming CAN values were advancing, but yesterday's
inactive IDs appeared first and 79 DBC conflict notices preceded the table.
The corrected page defaults to the current ESP32 run, places the latest values
first, retains All saved IDs/history, and makes DBC details and longer signal
lists expandable. It shows refresh time and byte-change highlighting. Request
timeouts retry automatically, while frame ages keep advancing independently.
Server timestamps avoid remote-PC clock differences affecting freshness.
Sixteen CAN backend tests, 32 frontend tests, lint and production builds validate
the change. The shared release version is 1.1.3, source build `8097dcac11e0`.
Firmware capture, GPIO assignments, Wi-Fi credentials and DBC files were not
changed for this display correction. See the final live verification evidence
in the BE report for the deployed version and actual changing values.

The interrupted USB flash was recovered after reconnection on 18 November.
All three firmware components passed flash verification, and startup plus the
GUI confirmed version 1.1.3. Live checks found 31 current-run CAN IDs, retained
69 saved IDs, and verified advancing database records through both the backend
and the laptop's LAN dashboard address. A 20-second serial capture contained
2,806 CAN frame lines. Actual browser samples confirmed changing 0x06E bytes
and counts. COM3 is released; the offline package records this verified flash.
Existing delivery drops and the unresolved BMS diagnostic TX failure remain
documented in the BE report.

### Live CAN search and requested project commit — software 1.1.4

Added a search field above the live CAN table for hexadecimal IDs, message and
signal names, DBC filenames, and raw bytes. Searches are case-insensitive and
run across all latest IDs before pagination. Input is debounced; live polling,
history, current/all-run selection and whole-bus statistics remain available.
Clear search restores the full view and a no-match message explains empty results.

Validation: 18 CAN backend tests, 33 frontend tests, Ruff, the production GUI
build and the ESP32 firmware build passed. Live API tests through the direct
backend and laptop LAN address confirmed ID/name/raw searches, fresh database
timestamps while filtered, no-match results and clearing back to 31 current IDs.
The browser independently confirmed changing bytes/counts under `0x06E`.
Evidence is in `output/testing/can-search-live-verification.json`,
`output/testing/can-search-browser-verification.json` and
`output/testing/bms/can-search-live.jpg`.

GUI/source release 1.1.4 has build ID `2ae749ea5903`. The running ESP32 remains
on verified 1.1.3; search requires no device change. The compiled 1.1.4 firmware
is included offline but was not flashed, and its manifest records that fact.
The prior verified 1.1.3 source/firmware archive is preserved in `output/releases`.

At the user's request, the commit includes accumulated project work and a
temporary-work snapshot in `output/work_snapshot`. Its inventory accounts for
included files and items retained locally: credentials/NVS, database backups,
private reference security extraction, installed tools/dependencies and caches.
Included text copies have credential values redacted; original local files are
preserved. BMS diagnostic transmission remains unresolved as previously recorded.

### Application flash and GUI redeployment — 19 November 2026

Flashed application version **1.1.4**, build `2ae749ea5903`, to COM3 at
115200 baud, application offset `0x10000`. The flash hash verified and startup
reported the matching version/build. ESP32 MAC: `ec:62:60:9c:40:84`.
Application SHA-256:
`0af7b4d2a54b7c70838652a6b0bcb6914c9bd8e561ad3274bd059e5983c9e03c`.
Bootloader, partition table and provisioned NVS were not written during this
application-only flash. The production GUI build passed and the existing GUI
service was relaunched on port 5173 with LAN access.

The services were stopped at the start. Restarted the existing XAMPP MariaDB
database (`C:/xampp/mysql/data/navsphere`), MQTT broker, backend and frontend.
Mosquitto initially rejected its persisted state as an unrecognized format.
Preserved the remaining state file as
`.runtime/mqtt/mosquitto.db.unreadable-20261119-142547` and restarted the broker
with fresh state. Existing database history and credentials were preserved.

Initial CAN capture was empty. Once the bus was active, receive traffic became
dominated by repeated transmissions and dashboard delivery was delayed. A PCAN
comparison isolated missing acknowledgements: five seconds in listen-only mode
received **18,524 identical 0x06E frames** plus 17 error frames. Five seconds
with a normal-mode PCAN receiver received **2,640 frames across 29 CAN IDs**,
with zero error frames. No application CAN messages or BMS commands were sent.

Left a PCAN normal-mode receive helper running to supply acknowledgements for
this bench setup: `.runtime/run_pcan_receiver.py`, process record
`.runtime/pcan-receiver-process.json`, status `.runtime/pcan-receiver-status.json`.
Keep PCAN connected and this receiver running while the BMS and listen-only
ESP32 are the only other nodes. A normal-mode node on the real CAN network can
supply these acknowledgements instead. The ESP32 remains listen-only at
500 kbit/s, GPIO25 TX/GPIO26 RX.

After this correction, the direct backend and laptop LAN URL both returned
33 current-run IDs and retained 71 saved IDs. Four-second comparisons confirmed
advancing sequences and database receive timestamps for seven CAN IDs.
Browser samples showed 0x06E changing from `BB DB FF 03 00 81 16 00` to
`9E D3 FF 03 00 81 16 00`, with its saved count increasing. The GUI showed
matching **v1.1.4** versions and CAN logger online. The follow-up serial capture
contained **1,633 CAN lines in 12 seconds**. Analog records also continued to
persist. COM3 was released and an exclusive open/close check passed.

Existing bounded serial/MQTT delivery drops remain visible; this deployment
does not establish lossless logging. BMS diagnostic transmission was not retested.
The offline package now records the verified application as flashed.

Evidence: `output/testing/redeploy-20261119-verification.json`,
`output/testing/redeploy-20261119-can-live.json`,
`output/testing/redeploy-20261119-can-serial.json`,
`output/testing/redeploy-20261119-pcan-comparison.json`,
`output/testing/redeploy-20261119-browser.json`, and
`output/testing/bms/redeploy-20261119-gui.jpg`.

### Periodic CAN transmission — 19 November 2026

Added one CAN-page ON/OFF control for two fixed standard CAN messages at
500 kbit/s: `0x014`, payload `00 60 00`, every 100 ms; and `0x548`, payload
`00 00 00 00 00 00 00 08`, every 10 ms. The second identifier follows the
user's explicit payload instruction, superseding `0x584` in the screenshot.
Both messages start OFF after reboot. The GUI displays device-confirmed state,
successful-send counts and failures. Admin authentication, CSRF protection,
boot-bound expiring commands and audit records protect the new control route.
Transmission stops after MQTT disconnection or repeated send failures.
Existing CAN receive, DBC, GPIO, telemetry and diagnostic request behavior
remain in place; diagnostics and periodic transmission cannot own the bus
controller simultaneously.

After the transceiver voltage correction, PCAN received both exact payloads
from firmware v1.1.7 with no observed PCAN error frames. The 10-second capture
contained 100 frames for `0x014` (mean period 99.982 ms) and 813 frames for
`0x548` (mean period 12.301 ms). The timing check failed: ordinary arbitration
losses dropped single-shot attempts. Version **1.1.8**, build `8148c3afe9b8`,
adds bounded retries for arbitration losses only, retaining immediate failure
handling for bus/ACK errors. Firmware host tests and firmware/GUI builds passed.
The backend suite previously passed 89 tests, followed by 11 targeted tests;
the GUI suite passed 38 tests, followed by 14 targeted CAN/control tests.

**Hardware validation remains incomplete for v1.1.8.** Both USB devices
disconnected before this build could be flashed. The last verified device
version is v1.1.7; its final acknowledged transmission state was OFF. Flashing
v1.1.8 and repeating wire timing, GUI ON/OFF and persistence checks remain
pending. The packaged v1.1.8 manifest therefore records `hardware_flashed: false`.
Do not interpret earlier v1.1.4 deployment evidence as validation of v1.1.8.

Evidence: `output/testing/can-tx-voltage-corrected-before-arbitration-fix.json`,
`output/testing/can-tx-live.json`, and
`output/testing/can-tx-awaiting-flash.jpg`. Relevant temporary scripts/logs and
the built GUI are preserved in `output/work_snapshot/can_tx_20261119/`.

### Documentation reconciliation — 19 November 2026

Reviewed all maintained guides, READMEs, contracts, checklists and offline editions
against source commit `c272b05` (v1.1.8). Corrected stale control-pin references,
LAN and flashing instructions; documented CAN search/statistics, fixed periodic
TX behavior, ACK and transceiver supply requirements, storage semantics and the
separate unresolved BMS work. Added a documentation index, current release status
and detailed CAN TX operating/acceptance guide. Generated OpenAPI now covers 25
paths; the SQL schema reference contains all 11 application tables through migration
0004. These exports do not change the running database or application.

Refreshed four engineering PDFs, the project/AI report, five-slide stakeholder
presentation and source/docs ZIP. The audit covers 74 user-message records and
44 completed turns across two chats, totaling 6h 21m 22s of recorded session time.
The current documentation turn is excluded from completed time. Credits and billed
tokens remain unavailable. Dated screenshots and failed tests remain accurately
labeled. Documentation helpers and validation evidence are included. Application
version/source fingerprint remains v1.1.8 / 8148c3afe9b8; no firmware was flashed,
CAN control toggled or BMS diagnostic behavior changed during this review.

## Wi-Fi OTA addition — 20 November 2026

Added /ota, authenticated BIN/Intel HEX validation and staging, MQTT chunk
transfer, inactive-slot firmware writes, SHA-256 checks, startup rollback and
live chip version/hash confirmation. Existing control/CAN logic has only
maintenance gates required to prevent concurrent actuation during OTA. NVS
offsets are preserved. Added broker ACLs, migration backup helper, API schema,
release packaging and OTA operation/acceptance documentation. No serial device
was connected during implementation; physical migration and OTA acceptance
remain pending. See docs/RELEASE_STATUS.md for software-check results.

## Live OTA validation and screenshot gaps — 20 November 2026

Release v1.1.20 / 1fb9fadf201c was verified on the connected board. Added actual
IP/RSSI/uptime, drag/drop, limits, guidance and connection-security reporting.
Backed up flash and preserved provisioned credentials. BIN/HEX updates and startup
rollback passed; ADC/CAN persistence, existing pages and safe OFF controls were
checked. Fixed OTA deadline skew and isolated OTA network capacity/power handling.
See docs/RELEASE_STATUS.md and output/testing/ota-hardware-validation-20261120.json
for exact tests, evidence and remaining hardware limits.

## OTA file-selection correction — 20 November 2026

Release v1.1.21 / bd9ed0ad6a1b moves upload errors beside the picker, retains selected
filename feedback and blocks installing a stale staged image after rejection.
The user-selected standalone build was a pre-OTA application; both build roots
were rebuilt. Eight GUI tests and live rejection/acceptance checks passed.
The chip remained on v1.1.20; the new release is upload-validated, not flashed.
See docs/RELEASE_STATUS.md for current and historical evidence.

## OTA screenshot follow-up - 20 November 2026

Release v1.1.22 / 1e17f3d0dbcc hides previously staged image details after a rejected
selection and retains the chosen filename in the native picker. Both build
folders were refreshed. Eight OTA GUI tests and live old-file rejection/new-file
acceptance checks passed; the board remained on v1.1.21, with no flash started.
