# NavSphere

Updated 19 November 2026 for **v1.1.8 / 8148c3afe9b8**. Last hardware-verified firmware: v1.1.7. Flashing v1.1.8 and final CAN timing/GUI ON/OFF checks remain pending. ESP32 BMS diagnostic success remains unverified. See the project `docs/RELEASE_STATUS.md` for current evidence.

**360° Visibility and Comprehensive Tracking**

An ESP32S-WROOM telemetry and control platform: six onboard ADC1 inputs ->
authenticated MQTT -> FastAPI -> existing MySQL/MariaDB -> React dashboard.
The project prompt has been updated to the user's final **six-channel, no extra
ADC hardware** requirement.

| Component | Location |
|---|---|
| Native ESP-IDF C/FreeRTOS firmware | [firmware/](firmware/README.md) |
| FastAPI, MQTT ingestion, authentication, REST and WebSocket | [backend/](backend/README.md) |
| React/TypeScript dashboard and six analytics pages | [frontend/](frontend/README.md) |
| SQL schema and Alembic migration guidance | [database/](database/schema.sql) |
| Broker configuration and scoped ACLs | [mqtt/](mqtt/acl.example) |
| Explicit synthetic device and A/B responder | [simulator/](simulator/telemetry_simulator.py) |
| Windows setup, start, stop and tests | [scripts/](scripts/setup_windows.ps1) |
| Reports, specifications and guides | [docs/](docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md) |

This laptop uses the existing XAMPP MariaDB server; ensure it is running before startup. Setup reuses that
database server and creates only the NavSphere database and a restricted local
application account. Secrets are generated into ignored local configuration.
No second MySQL instance is started.

```powershell
# From this repository. Process-scoped Bypass does not change machine policy.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_local.ps1
# Optional synthetic device, in another terminal:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_simulator.ps1
```

Dashboard: <http://localhost:5173> · API: <http://localhost:8000/docs> ·
[ReDoc](http://localhost:8000/redoc) · [OpenAPI](http://localhost:8000/openapi.json).
A new development database seeds `admin` / `admin`; the existing account has a changed password. Change the initial password in Account
before sending commands. Production configuration rejects these defaults.

With the repository root open in VS Code, use **ESP-IDF: Build your Project**
or **Ctrl+Shift+B**. The root `CMakeLists.txt` registers the existing
`firmware/main` component, so there is no need to switch folders or duplicate
firmware source. The board target is **esp32** (classic ESP32S-WROOM).

The root build uses `sdkconfig`, `build/`, the shared defaults from
`firmware/sdkconfig.defaults`, and a root defaults overlay that points to
`firmware/partitions.csv`. SDK Configuration Editor edits that root configuration.
The workspace uses `KCONFIG_REPORT_VERBOSITY=quiet` because extension 2.3 treats
ESP-IDF 6 informational notes as errors and brings the Output panel forward.
Actual configuration failures remain visible. After environment-setting changes,
run **Developer: Reload Window**, then reopen the gear icon / **ESP-IDF: SDK
Configuration Editor**. The project settings are under **NavSphere**.
The default build task selects the same project and configuration:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/build.ps1 -ProjectDirectory .
```

The root `.vscode/c_cpp_properties.json` selects the Xtensa ESP32 compiler and
`build/compile_commands.json` for Microsoft C/C++ IntelliSense. Build once to
generate that database. For previously cached C/C++1696 header errors, run
**C/C++: Reset IntelliSense Database** from the Command Palette. SDK include paths
come from the real compiler commands; no manual SDK header copies are needed.

Opening `firmware/` directly remains supported as a standalone ESP-IDF project,
with its own `firmware/sdkconfig` and `firmware/build/`. Those generated settings
are independent of root menuconfig edits. To build that standalone configuration,
omit `-ProjectDirectory`. The optional [NavSphere.code-workspace](NavSphere.code-workspace)
also exposes both project folders; choose the matching current project in ESP-IDF.

| Input / output | GPIO |
|---|---|
| Analog 1–6 | 32, 33, 34, 35, 36, 39, respectively |
| Control A, active high | 2; external LED with series resistor |
| Control B, active high | 0 |

Both outputs start LOW and return LOW after network loss or the configurable
60-second inactivity watchdog. An applied acknowledgement confirms the software
GPIO latch operation; no electrical feedback sensor is installed.

Initial simulator integration verification stored 300/300 simulated samples in MariaDB in
30.002 seconds (9.999Hz), and tested authenticated WebSocket delivery, six
histories and acknowledged A/B on/off commands. See the
[implementation report](IMPLEMENTATION_REPORT.md) and
[machine-readable results](docs/testing/integration-results.json) for scope and
measurement details. Firmware build and host tests are separate from physical
hardware validation. The later 18 November 2026 CAN/BMS delivery includes a
COM5 flash and browser verification; see the current work record below.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_system.ps1
# With broker/backend running; starts its own bounded-duration synthetic device:
backend/.venv/Scripts/python.exe scripts/integration_test.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_local.ps1
```

Detailed deliverables: [API reference](docs/api/API_REFERENCE.md),
[firmware specification](docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md),
[deployment/user guide](docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md), and
[PDF editions](output/pdf/). Docker Compose is optional, uses the existing host
database, and has not been executed on this laptop because Docker is unavailable.


### Control pin update 12 November 2026

Control A uses GPIO2 and Control B uses GPIO0, active high. Both pins affect boot selection. Keep GPIO0 HIGH during reset for normal boot; do not add a Control B pull-down. GPIO2 must be LOW or floating for serial flashing. Firmware sets both outputs LOW after startup. An attached load must tolerate reset-time levels or use a separately enabled driver.
# CAN bus support

The `feature/add_CAN` branch adds classic CAN capture at 500 kbit/s using
GPIO25 (TX) and GPIO26 (RX), starting in listen-only mode. Diagnostics or periodic TX temporarily enable normal mode. Open `/can` for the latest
raw frame per CAN ID, history, capture diagnostics and administrator DBC upload.
Raw CAN history is stored independently of analog telemetry. See the
[CAN setup and data guide](docs/firmware/CAN_GUIDE.md) for wiring, database
migration, DBC support and throughput limits.

Put all bus definition files in the project's [can_dbc folder](can_dbc/README.md).
The CAN page loads multiple files automatically and lists parsing or ID conflicts.
For another office PC, the active Wi-Fi dashboard URL on 18 November 2026 was
<http://192.168.9.59:5173/can>. The former Ethernet address 192.168.9.253 was
disconnected; see the CAN guide for firewall/network setup. DHCP addresses may change.

## CAN statistics and BMS diagnostics — 18 November 2026

Expand **CAN statistics & protocol details** on `/can` for capture/delivery
rates, utilization estimates, controller errors, drops, DLC distribution and
per-ID timing. The existing latest-frame, history and DBC views remain available.

The CAN page opens with **Current ESP32 run** selected and shows the latest
values with a **Search CAN messages** bar. Search by hexadecimal CAN ID (for
example `0x06E`), message/signal name, DBC filename, or raw bytes (`38 DE` or
`38DE`). Search is case-insensitive and applies before pagination, across all
IDs in the selected view. Live updates continue while searching; **Clear
search** restores the full list. CAN statistics continue to cover the whole bus.

The live table shows the latest
values before configuration details. Use **All saved IDs** for values retained
from earlier runs. The refresh time and each ID's age/count show activity; byte
changes are highlighted. DBC details and additional decoded signals can be
expanded without hiding the live table. Stalled update requests time out and
retry automatically.

Open **BMS diagnostics** at `/bms` for 55 CDD services and 44 script workflows
from the local `HVBEOSK/be_repo` reference, using AMP Client 15.0.4 behavior.
Quick reads provide one-button QR, serial, hardware-part, manufacturing-serial
and mode requests. The current BMS uses `0x7E4 → 0x7EC`; migration scripts select
their required current or legacy address automatically. The page provides
confirmation for state changes, decoded/raw responses and saved job history.
Diagnostic transmission is enabled during its job and returns to listen-only afterward. Periodic TX is a separate, mutually exclusive control. Optional replacement images go in `bms_images`.

Historical verification on 18 November: firmware was flashed on COM3; 75 backend and 27 frontend tests,
firmware host tests and builds passed. All 44 workflows and six programming
images pass offline preparation. PCAN successfully reads the physical BMS;
ESP32 CAN reception is now verified live with software version 1.1.0;
BMS diagnostic transmission remains under hardware verification.
Destructive BMS commands were not run on hardware. See the
[BE implementation report](docs/development/BE_CLIENT_IMPLEMENTATION.md)
for exact validation, executable codec discrepancies and remaining checks.

## Shared software version

`version.json` is the shared release record. ESP32 code uses the generated
`SW_VERSION`, `SW_BUILD_ID` and `SW_BUILD_UTC` macros in
`firmware/main/sw_version.h`; the GUI imports the corresponding constants from
`frontend/src/sw_version.ts`. Do not edit the generated files independently.
The GUI shows its own version and the version actually reported by the selected
ESP32, including missing, stale and differing versions.

ESP-IDF builds (both project entry points, including VS Code) and `npm run build`
automatically prepare the version. A source change advances the patch number
once; rebuilding or reflashing unchanged source keeps the same identity so
separately built firmware and GUI stay aligned. `SW_BUILD_UTC` is the release
preparation time in UTC. To deliberately create another release without source
changes, run `python scripts/sync_version.py --bump`, then rebuild both.

Build the GUI and firmware before packaging. `scripts/package_release.py`
rejects outdated source, firmware or GUI versions. The release manifest records
the shared version, source build ID and exact binary SHA-256. On serial at
115200 baud, look for `SW_VERSION=...` at startup and `CAN_BUILD` for the running
firmware identity. CAN data output and GPIO assignments remain unchanged.

## Current instructions and periodic transmission

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
