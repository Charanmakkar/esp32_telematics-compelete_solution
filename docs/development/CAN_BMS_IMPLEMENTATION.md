# CAN statistics and BMS diagnostics work record

Historical HVP work record. Current status is in ../RELEASE_STATUS.md and BE_CLIENT_IMPLEMENTATION.md. Preserve old counts and results as dated evidence, not current instructions.

> Historical HVP implementation record. On 18 November the user replaced the
> active reference with `HVBEOSK/be_repo`. See
> [BE client implementation and current verification](BE_CLIENT_IMPLEMENTATION.md).
> The old 111/42 catalogue counts and HVP address assumptions below are historical.

Started: 18 November 2026 (Asia/Calcutta). Baseline: `d7eb9c2`, branch
`feature/add_CAN`. Existing analog acquisition, GPIO2/GPIO0 controls, raw CAN
storage, DBC library and office-network access must retain their behavior.

## Agreed scope

- Add a separate CAN statistics section: traffic, frame types, DLC distribution,
  per-ID timing, estimated utilization, capture health and protocol details.
- Add a separate BMS page with request preview, decoded/raw responses, command
  presets, programming workflows, and persistent request history.
- Read `HVP/hv_core` only as reference; do not modify that repository.
- Use the existing ESP32/TJA1042, enabling transmission only during diagnostics
  and restoring listen-only on completion, disconnect or timeout (user confirmed).
- Implement all 111 services in the supplied BMS CDD and all 42 batch scripts.
  Record differences between CDD definitions, scripts and implemented ECU source.
- Never run erase, programming, balancing, reset, write or mute commands as part
  of automatic hardware verification. Those require a deliberate GUI action.

## Reference inventory

Release: `45_Release/abs_hv_bms_release` in the reference repository.
CDD: `documents/BMS.cdd`, 79 diagnostic instances / 111 concrete services.
Presets: `client/client_scripts`, 42 batch files.
Target configuration: `client/config.json`, 500 kbit/s, physical request IDs
0x640..0x64A and response IDs 0x650..0x65A; default `string_01`.
The security key stays in the local reference configuration and is never sent
to the browser, copied into tracked files, or written to request logs.

Initial discrepancies: the CDD routine identifiers differ from the application's
F200..F205 routine table; CDD balancing field labels differ from the script's
two control bytes plus cell mask; several CDD data lengths differ from firmware.
CDD requests must remain traceable; verified script workflows use source-backed
definitions and show discrepancies instead of silently changing definitions.

## Implementation / verification log

- [x] Baseline clean and reference locations verified.
- [x] User selected ESP32 diagnostics transport.
- [x] Reference catalogue, codecs and script-to-operation coverage.
- [x] CAN statistics collector, API and GUI.
- [x] ESP32 bounded ISO-TP transport and temporary diagnostic mode.
- [x] BMS command jobs, security/session handling, programming and audit trail.
- [x] BMS page, input validation, request previews and response/history views.
- [x] Backend/frontend/firmware regression and fault-path tests.
- [x] Firmware flashed on COM5; live CAN/MQTT/database and browser verified.
- [x] Read-only BMS request attempted; failed transmission and mode restoration recorded.
- [ ] Successful BMS response over the physical bus: blocked by CAN transmission failure.
- [x] Documentation, evidence and release packaging prepared.

Protocol references: [ISO-TP transport](https://docs.kernel.org/networking/iso15765-2.html),
[Espressif TWAI](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32/api-reference/peripherals/twai.html).
Bus utilization is an estimate from captured valid frames; voltage, termination,
ACK-slot state and individual bit/stuff/CRC error classification are not exposed
by this setup and must never be fabricated.

## Delivered behavior

### CAN statistics

Open **CAN data → CAN statistics & protocol details**. The separate section
refreshes every two seconds and includes:

- Hardware capture rate versus server delivery rate, payload throughput, and
  estimated bus-utilization bounds over a ten-second window.
- Standard/extended/RTR counts, controller mode/state, RX/TX error counters,
  bus errors, arbitration losses, successful diagnostic frames and TX failures.
- RX overruns/misses, capture/MQTT/UART drops and mode-switch gaps.
- Delivered DLC distribution, per-ID frame counts, rate, mean/minimum/maximum
  interval, interval jitter, payload changes and age.
- Classic-CAN framing, arbitration, identifiers, fault confinement, pinout and
  DBC/UDS/ISO-TP reference information.

Statistics use bounded memory rather than repeatedly scanning raw history.
They reset on server restart or ESP32 boot as labeled. Per-ID timing is based
on the last 64 delivered intervals, so capture losses affect it. Rates and
estimated utilization are not oscilloscope measurements; error-frame wire time
is excluded. Full-rate lossless recording is not claimed.

### BMS diagnostics

Open **BMS diagnostics** from the navigation, or `/bms`.

1. Select a script workflow or CDD service; search by command name, group or
   request. The library currently contains **42 scripts and 111 CDD services**.
2. Choose the target instance and fill the generated fields. Instances 0–15
   map to request IDs 0x640–0x64F and response IDs 0x650–0x65F. The reference
   configuration originally lists instances 0–10. Recovery presets can fix
   their target to instance 0.
3. Preview the exact request, session/security requirements, source notes and
   image fingerprint. Selection and preview do not transmit.
4. Send the request. State-changing operations additionally require typing
   `CONFIRM`. Only an administrator with a changed initial password can send.
5. Read decoded values, raw response bytes, timing and errors. Job history and
   individual exchanges are saved in the database. Cancellation stops between
   bounded exchanges; partially programmed memory is not rolled back.

Script workflows cover identity/QR/serial-number reads and writes, instance
configuration, event testing, CAN debug controls, balancing, open-wire data,
histograms and their resets, SOC/NVM operations, communication mute/unmute,
application erasure and the supplied image-programming procedures. CDD services
remain available individually with their declared request/response fields.

Programming validates Intel HEX checksums, address overlap, component address
ranges and 8-byte alignment before any request is sent. The workflow checks
BMS mode, enters the requested session, unlocks once, erases, downloads with
negotiated block size, exits transfer, and checks integrity/compatibility.
It stops on failure, never automatically retries writes, and sends no automatic
ECU reset. The supplied source does not support every security level in every
mode; a rejected unlock stops before erase.

## Reference locations and differences

Default reference root on this laptop:
`C:\Users\charanpreet\Documents\ChatGPT\HVP\hv_core`.
Set `BMS_REFERENCE_ROOT` in `backend/.env` to use a different local root, then
restart the backend. The reference project is read only and is not bundled in
the source release. If absent, only the BMS reference catalogue becomes
unavailable; existing telemetry/CAN pages continue working.

CDD SHA-256:
`5fc254d6f8240ad3e4cbf85b8473cf8eee29d6ed71f82f1f1d0dc3f76ab0d463`.
The catalogue counts actual instances and service references, excluding unused
generic templates. Source analysis records 60 DID contracts. Full command and
image inventory: [bms-command-coverage.json](../../output/testing/bms-command-coverage.json).

| Reference discrepancy | Implemented handling |
|---|---|
| CDD routine IDs differ from application F200–F205 | CDD sends its exact definition; script workflows use the verified source routine table and show notes. |
| F013 instance is two-byte big-endian; application learns ADC straps and ignores written value | Source size/session/security are used; GUI warns and the write workflow verifies readback at the requested target. An acknowledgement alone is not reported as a verified change. |
| FD20 handler is a placeholder | Encode the source's 32-byte format, including reversed unpacked BCD groups; warn that reference reads are examples and writes do not persist. |
| FD06 balancing labels differ | Presets use two control flags and 23 mask bytes; CDD fields remain independently accessible. |
| FD07 has 180 voltage/validity records | Decode the 540-byte source format. |
| Histogram dimensions/lengths differ | Decode big-endian uint32 bins using source dimensions 6, 6×6 or 6×8. |
| D002/D003/D004 and E000 lengths differ from CDD | Preserve raw data and display decoding warnings/source notes. |
| Communication control is custom AMP behavior | Use two-byte `28 01` / `28 00` for the selected BMS; the script's “all” is not a broadcast to all instances. |
| Application supports security level 03; programming requires 05 | Select source-backed access conditions, perform one unlock attempt, and stop if rejected. |
| F204/F205 compatibility routines return status in start response | Validate that response without sending an unsupported results query. |
| Bootloader script omits `v` in image filename | Resolve the actual supplied `abs_hv_bootloader_v0_5_0.hex` and show a note. |
| `abs_hv_boot_updater_ff_4_0.hex` is missing | Keep its workflow visible but block preview until a valid replacement is provided. |

Seven supplied images passed local parsing/range checks; one named image is
missing. For a replacement, place the file in the project's **bms_images**
folder and enter its filename in the selected programming workflow. Images
remain local and excluded from Git. Existing DBC files remain in **can_dbc**.

## Transport, storage and preservation

- ESP32 retains classic CAN at 500 kbit/s, GPIO25 TX and GPIO26 RX. It boots in
  listen-only mode and enters normal mode only for a diagnostic job. Normal
  mode also acknowledges other valid CAN frames.
- Bounded ISO-TP supports payloads up to 4,095 bytes, sequence/block handling,
  flow control, separation times, response-pending and absolute timeouts.
  Successful TX means a controller TX-success alert, not just an enqueue.
- Requests are bound to device boot, unique request/job IDs and short expiry;
  retained/replayed requests are rejected. One job per device runs at a time.
- Completion/error/disconnect restores listen-only. A 15-second idle watchdog
  covers lost close messages. Mode changes briefly interrupt capture; discarded
  queued frames are counted. Diagnostic responses reserve MQTT outbox space;
  any resulting CAN publish drops are counted.
- New `bms_jobs` and `bms_exchanges` tables are added by migration **0004**.
  Existing telemetry and CAN tables are preserved. Startup marks interrupted
  jobs instead of replaying them.
- Security seed/key exchanges and key writes are redacted in previews/history.
  The local AES-CMAC key is neither sent to the browser nor copied into this repo.
- Existing ADC channels, GPIO2/GPIO0 control handlers, DBC ingestion and raw CAN
  history remain in place. Existing regression tests passed. Physical control
  outputs were not toggled during this task.

Before migration, the live database was backed up to the ignored local file
`.runtime/backups/navsphere_20261118T095813_830597Z.sql`
(2,039,631,109 bytes). No existing database records were deleted.

The Ethernet address 192.168.9.253 was absent during this session. The active
Wi-Fi address was **192.168.9.59**. The broker was restarted on loopback and that
active address; ESP32 NVS broker URI was updated to match. Wi-Fi credentials
were preserved. Full prior NVS is backed up under
`firmware/.local/nvs-before-bms-20261118.bin`; the adjusted private image is
`firmware/.local/nvs-bms-wifi.bin`. Neither is included in Git/release archives.
DHCP addresses can change; check the active interface before future provisioning.

## Verification and outstanding hardware work

Verification on 18 November 2026:

| Check | Result and scope |
|---|---|
| Backend | **58 passed**, including existing regression tests, CDD codecs, source contracts, image validation, mocked programming/cancellation, replay/CSRF/roles, response binding, history, statistics and security redaction. |
| Backend lint | Ruff passed for app, tests and migrations. |
| Frontend | **25 passed**, including preview without transmission, typed confirmation, stale-preview invalidation and unavailable-device behavior. |
| Production frontend build | TypeScript/Vite passed; final CSS correction was rebuilt. |
| Firmware host tests | Existing command-rule/parser/watchdog tests and new ISO-TP transfer, timeout and malformed-frame tests passed. |
| ESP-IDF build and COM5 flash | ESP-IDF 6.0.2; **1,007,952 bytes**; flash hash verified at 115200 baud. |
| Live services | MQTT/database healthy; physical CAN frames and analog telemetry persisted after flashing. |
| Browser | Both new sections inspected; response history and restored listen-only status visible; new statistics width corrected for narrow screens; no browser console errors observed. |
| BMS hardware request | Read-only `22 F1 86` at instance 0 failed with a physical CAN TX failure; close acknowledged and listen-only restored. Earlier F010 reads also failed. |
| Destructive hardware operations | Not run. Programming, erasure, resets, balancing and writes were exercised with software fixtures only. |

The post-flash check at 10:22:48 UTC (15:52:48 IST) found fresh analog and CAN
records from the same new ESP32 boot, an observed analog rate of 10.04 Hz,
zero backend database errors and no backend ingest drops. ESP32-side analog
dropped-sample and CAN-drop counters were nonzero under the heavy bus load;
the short check is not a lossless or endurance benchmark. Both `/can` and `/bms`
returned HTTP 200 through 192.168.9.59:5173 from this laptop. A separate remote PC
was not retested during this feature task.

Final flashed application SHA-256:
`5c8e29e622356d3a69a6891b62e12e27528ed0f0acce7a7d0e68a26942d95957`.
The recorded diagnostic attempt used the immediately preceding TX-confirming
build (hash retained in its evidence file). The final build adds response-outbox
reservation and rejects premature ISO-TP positive responses; it was flashed,
and its receive/data path was checked without repeating CAN requests blindly.

At the diagnostic attempt, the controller reported one failed TX and no
arbitration loss; mode changes were recorded and listen-only restoration was
acknowledged. Traffic repeatedly contained ID **0x06E** at roughly 3,600–3,700
captured frames/s, with substantial queue/MQTT/UART drops and bus errors.
The counters distinguish those losses from successfully stored frames. Possible
TX-path, transceiver or acknowledgement issues need electrical verification;
the software cannot identify the physical cause conclusively.

Outstanding: verify GPIO25→TXD, GPIO26←RXD, TJA1042 STB LOW, transceiver supply,
common ground, bus termination and a normal-mode node capable of acknowledging.
Then repeat one read-only request and a multi-frame read. A successful live BMS
response and physical programming validation are **not yet demonstrated**.

Evidence:

- [Live diagnostic attempt](../../output/testing/bms-live-verification.json)
- [Post-flash service checks](../../output/testing/bms-post-flash-verification.json)
- [BMS page screenshot](../../output/testing/bms/bms-diagnostics.jpg)
- [CAN statistics screenshot](../../output/testing/bms/can-statistics.jpg)
- [Firmware manifest](../../output/firmware/manifest.json)

## AI work and reproducibility

### Follow-up: original Windows client inspection

After the user's question about the executable, its bundled contents were
inspected statically, without running the executable or transmitting CAN data.
The batch files invoke
`45_Release/abs_hv_bms_release/client/amp_uds_client.exe`.
It is a 15,874,413-byte PyInstaller package containing Python 3.10,
`amp-uds-client` version 13.0.4, `PCANBasic.dll`, `PCAN-ISO-TP.dll`, and a readable
91,785-byte `amp.py` module. Executable SHA-256:
`83a99276c52d77e9a286ce5823a1d2afe58f8b5a101ac0212061edba1c9d5af5`.

The module implements DID codecs/reads/writes, AES-CMAC security, PCAN ISO-TP,
erase/download/integrity/compatibility procedures, bootloader trapping,
tester-present, communication control and ECU reset. The batch `--port` selects
the PCAN channel; it does not refer to the ESP32 flashing port COM5.

**Validation correction:** the earlier implementation examined batch arguments,
CDD and ECU source, but did not inspect the executable internals. The 42-script
and 111-service counts establish catalogue coverage, not complete behavioral
equivalence to this client. The new web application does not launch this EXE;
it implements requests through the selected ESP32 transport.

Initial client/source differences needing reconciliation before full parity is
claimed include:

- Embedded `prepare_download` selects programming session and security level 1;
  the current web programming workflow selects level 5 based on ECU source.
  Bootloader authentication is a separate conditional client operation.
- Embedded programming supports bootloader trapping, optional CRC insertion,
  transfer-size compatibility options and a final hard reset by default. The
  web workflow currently checks mode and does not reset automatically.
- Embedded mute/unmute performs session/security setup and sends `28 81` /
  `28 80` with positive response suppressed. The web implementation uses
  response-requesting `28 01` / `28 00` based on the server's custom service.

These are findings, not newly validated changes. CLI dispatch/defaults and
each affected workflow still need comparison with the embedded implementation
and actual target bootloader. No firmware or command behavior was changed
during this follow-up inspection. Previous passing tests remain valid for the
implemented behavior; they do not establish original-client parity.

Receiving valid CAN frames confirms the receive path only. The recorded
diagnostic attempt had one TX failure and zero arbitration losses; it does
not prove a broken TX wire or distinguish missing acknowledgement from other
transmit/bus faults. Listen-only nodes do not acknowledge frames. A protocol
response failure and a CAN transmission failure are different observations.

### Work attribution

AI work covered reference/source analysis, catalogue and codecs, firmware
transport, backend/API/database changes, GUI implementation, regression and
fault-path tests, live service recovery, COM5 flashing, browser verification,
screenshots and this work record. User input selected the existing ESP32
transport and confirmed USB connection; physical wiring remains user-operated.
No reference repository changes or Git push were made for this feature task.

This record's initial creation was 09:30:47 UTC (15:00:47 IST). Test evidence
and the release manifest contain later timestamps. These are workflow
milestones, not a measurement of continuous human/AI attention. Exact model
token consumption, interaction duration and account credits are not exposed
by the project or build tools and are not inferred from elapsed wall time.

Reproduce software checks from the project root:

```powershell
Push-Location backend
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check app tests migrations
Pop-Location
Push-Location frontend
. ../scripts/common.ps1
npm test -- --run
npm run build
Pop-Location
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/test_host.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/build.ps1 -ProjectDirectory .
backend/.venv/Scripts/python.exe scripts/package_release.py --build-directory build
```

Use a configured compiler for the host C tests. Install updated backend
requirements and run `alembic upgrade head` before restarting the stack on
another machine. Do not run the old same-device simulator integration script
against this connected live ESP32.
