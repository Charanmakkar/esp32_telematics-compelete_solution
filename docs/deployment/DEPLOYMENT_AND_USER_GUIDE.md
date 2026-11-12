# NavSphere deployment and user guide

Six onboard ADC channels, ESP32S-WROOM. Updated 11 November 2026.

## Prerequisites and local environment

Use Windows, Python 3.13+, Node 22.12+ or24 LTS, ESP-IDF 6.0.2 for firmware,
and an existing MySQL 8 or compatible MariaDB server. This laptop has XAMPP
MariaDB 10.4.32 on127.0.0.1:3306 and Apache on80; both are reused. Portable
Mosquitto 2.1.2 and Node 24.22.2 are stored in ignored `.tools/`.
No global PATH, Windows service, firewall or database-server setting is changed
by the native setup. The current Wi-Fi address observed during setup was
192.168.31.50, different from the original prompt's192.168.9.59 example.
Check the current adapter address before configuring an ESP32 on the LAN.

## Native Windows setup

Open PowerShell in the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

This installs portable tools in `.tools/`, creates `backend/.venv`, installs
dependencies, creates the `navsphere` database in the existing server, creates
the restricted `navsphere_app@localhost` account with a random password,
generates broker credentials, applies Alembic migrations and installs frontend
dependencies using the lock file. Existing `backend/.env` is preserved and no
existing application user's password is rotated. If database administration
requires a password, supply `MYSQL_ADMIN_PASSWORD` in the current process
environment before setup. Do not put it in a script or command history.

Generated secrets are in `backend/.env`, `.runtime/device.env`, and
`.runtime/mqtt/passwords`; all are gitignored. The broker file contains PBKDF2
password hashes. Restrict access to the workspace account and avoid sharing
these files. Deployment copies should supply their own secrets.

The local account can read/write only the NavSphere database and has schema
migration privileges. For production, use a separate migration account and
remove CREATE/ALTER/INDEX/REFERENCES from the runtime account after migrations.
The native helper intentionally does not create a remote MySQL user.

## Starting and stopping

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

This starts hidden, project-owned MQTT/backend/frontend processes and records
their identities in `.runtime/processes.json`. Logs are in `.runtime/`. The
backend applies pending migrations before starting one Uvicorn worker.

For a clearly labelled synthetic device:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_simulator.ps1
# Or start the stack and simulator together:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_local.ps1 -Simulator
```

Stop the simulator before connecting physical firmware under the same device
ID. Do not run two producers with `ESP32_001`: different boot IDs would make
their interleaved data distinct samples but their control identities conflict.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_local.ps1
```

The separate start_backend/start_frontend/start_mqtt scripts can be used in
interactive terminals instead. Close those terminals or press Ctrl+C to stop
their foreground processes. The stop helper manages only its recorded stack.

## Browser access and login

Open http://localhost:5173. The initial local development account is admin/admin.
The backend stores a salted password hash, not plaintext. The login response
sets an HttpOnly session cookie. Account lets you change the initial password;
commands remain blocked until that change is completed. Logout revokes the
database session. Browser visual QA could not be completed in the agent's
Computer Use session; automated component and integration tests are reported
separately.

The overview shows broker/backend/database health, live frequency, current-run
counters, receipt and persistence times, and six signal cards. Simulator
readings have an explicit banner. A stale or invalid reading is not a fresh
measurement. Persisted values confirm successful database storage.

Choose a channel card to open `/analytics/analog-1` through `analog-6`. Switch
between Live and Historical. Presets cover1,5,15 minutes,1hour and 24 hours;
custom ranges allow up to 31 days. Drag chart brush handles to zoom and slide
the brush to pan. Historical min/max/average use valid database rows. The CSV
button exports plotted points, which can be SQL bucket averages for large
queries. UTC and local timestamp columns are both included.

Controls lets an administrator set A/B to1 or0. Pending and accepted do not
mean applied. Wait for the matching device acknowledgement. A stale/offline
device is blocked. GPIO25/26 are active high; firmware resets them LOW after
network loss or a configurable 60second inactivity watchdog. Send another
valid command to refresh the corresponding output's watchdog. An applied ack
confirms software latch state; verify electrical behavior on the actual board.

## Broker and LAN configuration

Native development binds MQTT1883, API8000 and frontend5173 to loopback. All
ports and hosts are configurable. For a physical ESP32, edit the generated
broker config's listener address to the actual LAN IP, or a reviewed0.0.0.0
binding, and restart the broker. Keep anonymous access disabled. Grant device
topics by matching MQTT username to device ID, and reserve the backend username
for the service. Review `mqtt/acl.example`. No firewall rule was opened
automatically. Allow only the required TCP port from your trusted local subnet
through Windows Firewall when enabling LAN access. Keep MySQL loopback-only
when the backend runs on this laptop.

For a different topic namespace, set MQTT_TOPIC_PREFIX in the backend and
simulator, CONFIG_NAV_MQTT_TOPIC_PREFIX in firmware menuconfig, and update the
broker ACL topic roots to the same prefix. The default is navsphere. Keep the
backend command timeout (1-30 seconds, default 10) at or below the firmware's
configured maximum command delivery TTL.

The default 1883 development listener is plaintext. Protected deployments must
use a TLS listener (normally8883) with `cafile`, `certfile`, and `keyfile`,
backend `MQTT_TLS=true`, `MQTT_CA_FILE` for a private CA, and a matching
`mqtts://` firmware URI. Configure HTTPS for the browser, exact allowed
origins, secure cookies, nondefault admin credentials and `ENVIRONMENT=production`.
Production startup validates these settings. TLS certificates must match the
hostname, rather than relying on certificate-error bypasses.

## ESP32 wiring, provisioning and flashing

Connect signals and common ground. The logical order is:

| Channel | Input |
|---|---|
| analog_1 | GPIO32 / ADC1 |
| analog_2 | GPIO33 / ADC1 |
| analog_3 | GPIO34 / ADC1 |
| analog_4 | GPIO35 / ADC1 |
| analog_5 | GPIO36 / VP / ADC1 |
| analog_6 | GPIO39 / VN / ADC1 |

No ADC2 channels or extra acquisition hardware are used. ADC attenuation does
not make pins5V tolerant. Verify the usable calibrated voltage range in the
ESP32 documentation and protect/scale signals as needed. GPIO34/35/36/39
have no internal pulls. Floating inputs cannot be treated as valid sensor data.
GPIO25 -> suitable series resistor -> LED -> GND is the selected A output.
GPIO26 is B. High-current loads require a suitable driver circuit.

Build with the existing IDF installation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/test_host.ps1
```

On another machine activate an ESP-IDF terminal, set target esp32, review
menuconfig and run `idf.py build`. The firmware is classic ESP32, not S3.
In a private IDF terminal supply NAV_WIFI_SSID, NAV_WIFI_PASSWORD,
NAV_MQTT_URI, NAV_MQTT_USERNAME, NAV_MQTT_PASSWORD and NAV_DEVICE_ID as
environment variables. The device MQTT username must equal ESP32_001 under
the supplied ACL. Obtain its generated password privately from device.env.
Then run `python firmware/tools/provision_nvs.py`. The ignored NVS image
contains credentials; do not distribute it with source.

After checking the physical wiring, actual serial port and any existing NVS
backup, run from firmware in the IDF terminal:

```powershell
idf.py -p COMx flash
python -m esptool --chip esp32 --port COMx write-flash 0x9000 .local/nvs.bin
idf.py -p COMx monitor
```

Replace COMx with the detected port. Flashing was not performed by the agent.
Run the hardware acceptance plan before relying on measurements or outputs.

## API documentation

Open http://localhost:8000/docs, /redoc or /openapi.json. In Swagger, execute
login first; the browser stores the session cookie. Copy the returned csrf_token
into the X-CSRF-Token header field for password/logout/commands. Change the
default password before executing commands. Include the API documentation browser
origin (such as http://localhost:8000) in FRONTEND_ORIGINS, alongside the
dashboard origin; the generated local configuration includes both loopback
forms for ports5173/8000. For production use exact HTTPS origins.
Read the separate API reference
for MQTT and WebSocket examples and validation rules.

## Retention, backup and optional containers

At 10 Hz one device produces 864,000 rows/day regardless of channel count. The
default history query is bounded and downsampled, not a whole-table download.
Choose retention after measuring disk use and required history. Inspect a
30day purge with `python -m app.maintenance --days 30` from backend; the
`--execute` flag explicitly deletes eligible rows in10,000row batches. No
automatic purge or scheduler was installed. Back up the database before purge;
use `scripts/backup_database.py` and keep an off-machine protected copy.

Docker Compose is provided but was not run because Docker was unavailable.
It starts broker/backend/frontend only and reuses host MySQL through
host.docker.internal. Configure a separate restricted MySQL account allowed
from Docker's subnet before running `docker compose up --build`. Do not run
the native broker and container broker on1883 simultaneously. The supplied
Compose ports bind to loopback. Native Windows is the verified deployment path.

## Troubleshooting

Connection refused: check existing services, `.runtime` logs and listening
ports. MQTT authentication failed: match backend credentials/password hashes
and device username/ID; recheck ACLs. Avoid sharing the backend account with
firmware. Database denied: check the actual server endpoint and application
account host grant; phpMyAdmin is an administration UI, not a database port.

Blank charts: check the simulator banner or actual device, validity mask,
sample age, Wi-Fi/MQTT/SNTP logs and selected time range. A clock without SNTP
uses server receive time for history and rejects actuation commands. Stale
samples preserve their acquisition identity and cannot create new measurements.

Commands rejected: check admin role, password-change gate, CSRF, device
freshness, broker state, matching boot ID and delivery deadline. An expired
or retained command must not execute. A/B returning LOW after 60 seconds is
the configured safety watchdog. Physical LED behavior is a separate board test.

PowerShell scripts disabled: use the documented process-scoped Bypass command;
the helper does not change system execution policy. Native stop starts no
system-wide kills and does not stop Apache or MariaDB.
