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
for p in ['firmware/README.md','docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md']:
 if '-File firmware/tools/build.ps1\n' in read(p):rep(p,'-File firmware/tools/build.ps1\n','-File firmware/tools/build.ps1 -ProjectDirectory .\n')
 if 'no board was flashed automatically during this implementation.' in read(p):rep(p,'no board was flashed automatically during this implementation.','earlier firmware has been flashed on COM3. Current v1.1.8 flashing is pending; see docs/RELEASE_STATUS.md.')
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
