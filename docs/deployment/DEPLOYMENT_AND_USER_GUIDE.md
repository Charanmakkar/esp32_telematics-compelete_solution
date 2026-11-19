# NavSphere deployment and user guide

Updated 19 November 2026 for **v1.1.8 / 8148c3afe9b8**. Last hardware-verified firmware: v1.1.7. Flashing v1.1.8 and final CAN timing/GUI ON/OFF checks remain pending. ESP32 BMS diagnostic success remains unverified. See the project `docs/RELEASE_STATUS.md` for current evidence.

## Prerequisites and local environment

Use Windows, Python 3.13+, Node 22.12+ or24 LTS, ESP-IDF 6.0.2 for firmware,
and an existing MySQL 8 or compatible MariaDB server. This laptop has XAMPP
MariaDB 10.4.32 on127.0.0.1:3306 and Apache on80; both are reused. Portable
Mosquitto 2.1.2 and Node 24.22.2 are stored in ignored `.tools/`.
No global PATH, Windows service, firewall or database-server setting is changed
by the native setup. The current Wi-Fi address observed during setup was
192.168.31.50 at initial setup; the last verified office Wi-Fi address on 19 November was 192.168.9.59.
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

Open http://localhost:5173. A new development database seeds admin/admin; the existing installation has a changed password.
The backend stores a salted password hash, not plaintext. The login response
sets an HttpOnly session cookie. Account lets you change the initial password;
commands remain blocked until that change is completed. Logout revokes the
database session. Browser checks and genuine dated screenshots are preserved under output/testing and output/reports; consult their actual firmware versions.

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
device is blocked. GPIO2/0 are active high; firmware resets them LOW after
network loss or a configurable 60second inactivity watchdog. Send another
valid command to refresh the corresponding output's watchdog. An applied ack
confirms software latch state; verify electrical behavior on the actual board.

## Broker and LAN configuration

The native frontend defaults to 0.0.0.0:5173; backend remains loopback:8000. MQTT1883 must be reachable from the physical ESP32. All
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
GPIO2 -> suitable series resistor -> LED -> GND is the selected A output.
GPIO0 is B. High-current loads require a suitable driver circuit.

Build with the existing IDF installation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/build.ps1 -ProjectDirectory .
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

For a NEW board only, check wiring, actual serial port and NVS backup, build the standalone configuration, then run from firmware in the IDF terminal:

```powershell
idf.py -p COMx flash
python -m esptool --chip esp32 --port COMx write-flash 0x9000 .local/nvs.bin
idf.py -p COMx monitor
```

Replace COMx with the detected port. Earlier firmware was verified on COM3; v1.1.8 flashing is pending. Use the application-only procedure below for the existing provisioned board.
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

### Office network access

The native frontend launcher listens on all local interfaces on port 5173.
Other PCs on the same office network can open `http://<laptop-Wi-Fi-IP>:5173`.
Add that exact URL to `FRONTEND_ORIGINS` in the private `backend/.env` file,
then restart the backend. The frontend proxies API and WebSocket traffic to
the backend on loopback; port 8000 does not need to be exposed.

Run `scripts/enable_office_access.ps1` in an Administrator PowerShell to allow
TCP 5173 from the local subnet through the Wi-Fi interface. The rule applies
even when Windows identifies office Wi-Fi as a Public network. Office client
isolation or VLAN policies may still prevent another PC from connecting.
For laptop-only access, launch `scripts/start_frontend.ps1 -BindAddress 127.0.0.1`.
This local development server is not an internet deployment.

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


### Control pin update 12 November 2026

Control A uses GPIO2 and Control B uses GPIO0, active high. Both pins affect boot selection. Keep GPIO0 HIGH during reset for normal boot; do not add a Control B pull-down. GPIO2 must be LOW or floating for serial flashing. Firmware sets both outputs LOW after startup. An attached load must tolerate reset-time levels or use a separately enabled driver.

## Current application update and CAN operation

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
