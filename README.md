# NavSphere

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

On this laptop, Apache and MariaDB are already running. Setup reuses that
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
Local development login is `admin` / `admin`; change the password in Account
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
| Control A, active high | 25; external LED with series resistor |
| Control B, active high | 26 |

Both outputs start LOW and return LOW after network loss or the configurable
60-second inactivity watchdog. An applied acknowledgement confirms the software
GPIO latch operation; no electrical feedback sensor is installed.

Live integration verification stored 300/300 simulated samples in MariaDB in
30.002 seconds (9.999Hz), and tested authenticated WebSocket delivery, six
histories and acknowledged A/B on/off commands. See the
[implementation report](IMPLEMENTATION_REPORT.md) and
[machine-readable results](docs/testing/integration-results.json) for scope and
measurement details. Firmware build and host tests are separate from physical
hardware validation. No board has been flashed. Browser visual QA is incomplete
because the available Computer Use session stopped on URL-verification policy.

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
