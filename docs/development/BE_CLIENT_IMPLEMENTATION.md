# BE reference implementation and verification

Updated 18 November 2026 (India Standard Time). This record supersedes the HVP
reference assumptions in `CAN_BMS_IMPLEMENTATION.md` for the active BMS page.

## Reference and scope

The user selected `C:\Users\charanpreet\Documents\ChatGPT\HVBEOSK\be_repo`.
The reference is read only. Active files are under
`45_Release\abs_hv_bms_release`: `client\client_scripts`, `client\config.json`,
`client\amp_uds_client.exe`, `documents\BMS.cdd`, programming images, and the
bootloader migration instructions. Corresponding ECU definitions are under
`15_Construction\projects\bms\hv_bms\abs\amp_config\uds`.

The catalogue contains **55 CDD services and 44 BAT workflows**. All 44 can be
prepared without transmitting, including all six supplied programming images.
See [machine-readable coverage](../../output/testing/be-command-coverage.json).

The executable is a 24,263,811-byte PyInstaller/Python 3.10 application,
AMP UDS Client **15.0.4**, SHA-256
`84b51a8589b89a337cff76587fa7155786001ab0962ea6e9f868d930b2fa0232`.
Its CLI and bundled `amp` bytecode were inspected as data. Command routines were
compared to the earlier client; their matching code does not imply matching
addresses, codecs, scripts or ECU source. The executable is not launched by the
web application. The backend implements the audited workflows; ESP32 implements
CAN and ISO-TP. Runtime security material is read locally, excluded from API
metadata and saved request/response traces. A changed executable fingerprint is
rejected until reviewed. No reference executable or key is bundled in the release.

## Addresses and one-button reads

| Profile | CAN request | CAN response | Use |
|---|---|---|---|
| `abs_hv` | `0x7E4` | `0x7EC` | Current BMS and most scripts |
| `abs_hv_old` | `0x640` | `0x650` | Specific legacy bootloader migration scripts |

Both use standard 11-bit classic CAN at 500 kbit/s. The GUI selects profiles
from the new configuration instead of deriving addresses from HVP string IDs.
Script profiles are selected automatically. Firmware protocol version 3 is
required before sending the new workflows.

Open `/bms`, keep **BMS · 0x7E4 → 0x7EC** selected, and click a Quick read:
QR (`C000`), serial (`F18C`), hardware part number (`F191`), manufacturing serial
(`FD20`), or mode (`F010`). The page opens the response section automatically.
Application-mode reads run preparation and display decoded values, raw bytes,
elapsed exchange times and saved history without a separate preview/submit step.
Application-mode read scripts also have **Read now**. State-changing workflows
retain review and typed confirmation, then run their entire sequence automatically.

## Executable behavior reproduced

| Workflow | Automatically executed sequence |
|---|---|
| Application read | 20 suppressed `3E80` messages, 100 ms cadence; 600 ms pause; `22 DID` |
| Non-application BAT | `1101` reset, bounded bootloader trap, TesterPresent burst, `22F010` mode check; at most two trap attempts |
| Application write | Application preparation; script session (default 02); security `2703/2704`; `2E DID payload` |
| Non-application write | Bootloader preparation; script/default session; security `2701/2702`; DID write |
| Clear faults | Application preparation; session 03; security level 03; `14FFFFFF` |
| Erase app | Bootloader preparation; session 02; security level 01; app erase start and status polling |
| Download | Preparation; session 02; security level 01; separate bootloader authentication; erase, download, transfer, exit, integrity, compatibility, prescribed reset |

Security access computes AES-CMAC over the 16-byte ECU seed using the selected
local configuration key. An all-zero seed means already unlocked. Download
authentication is separate: a fresh 16-byte challenge is sent in `2706`, `2705`
retrieves the bootloader MAC, and a constant-time comparison must pass before
erasure. Security bytes are redacted from persistent traces.

Executable routine IDs are app `FF00 / 0210 / 0211` and calibration
`0201 / 0212 / 0213` for erase/integrity/compatibility. Some ECU source routines
use different IDs; the script workflows match the executable and stop on a
rejection. CDD services retain their exact CDD definitions. No destructive
fallback to a different routine is attempted.

HEX loading spans minimum through maximum address, fills gaps with `FF`, pads
to eight bytes, and optionally inserts a big-endian CRC32 in the first four
bytes. Download uses `34 00 44`, negotiated transfer size, modulo-256 block
counters, `37`, integrity and compatibility checks. Bad files, wrong component
regions, authentication failures and rejected checks stop the workflow.
Application/updater images use the application region. The two bootloader BATs
send relocated images at `0x01100000–0x01118000`; the supplied migration guide
requires the matching updater first. They are not direct writes to installed
bootloader memory at `0x00F98000`. Calibrations use their configured region.

CAN/ISO-TP frames use `55` padding, bounded flow control and response deadlines.
The ESP32 supports the new address pair while preserving the previous range.
Transmission is enabled only for a diagnostic job; completion, failure,
disconnect or expiry restores listen-only mode. Existing ADC, GPIO2/GPIO0,
raw CAN logging and DBC views were not replaced.

## Verified live behavior and intentional corrections

PCAN received valid BMS serial, QR and manufacturing-serial responses at
`0x7EC`. The board's serial payload is 32 bytes and hardware-part payload is
eight bytes. The original executable rejected valid replies due to its codec
definitions: F18C consumed 23 bytes then interpreted remaining bytes as another
DID; F191 expected more data; FD20 raised `bad char in struct format`.
The web decoder handles observed payloads and retains raw bytes. FD20's supplied
ECU implementation returns example data and does not persist writes; the GUI
discloses that limitation. Invalid BAT transport syntax is identified in its
preview rather than executed as a shell command.

The exact `abs_hv_read_sn.bat` lacks `--app` and therefore resets/traps the BMS.
Live serial testing used the executable's application-mode equivalent to avoid
a reset. Exact application-mode hardware-part and manufacturing-serial BATs
were executed. No BMS reset, security unlock, erase, write, balancing, NVM clear,
fault clear or programming was performed in the live tests.

The initial BE ESP32 firmware was flashed and hash-verified on **COM3**, then
reported protocol version 3 through MQTT. Its application image is 1,008,656
bytes, SHA-256 `06e13721e553d93acc9deef34e155f3606c1c9226414a53e98f703a30da64e76`.
The prior COM6 device was replaced during testing; the last verified flash is
the COM3 board. Wi-Fi/MQTT and database readiness passed.

**Outstanding physical check:** with PCAN and ESP32 both connected, PCAN
captured 2,831 frames with status OK while ESP32 captured zero. PCAN observed
zero ESP32 diagnostic frames; the ESP32 returned a TX failure, saved it and
restored listen-only. See [dual-interface evidence](../../output/testing/be-dual-interface-read.json).
This does not establish successful end-to-end ESP32 BMS reads.

After the user reported power corrected, another comparison at 18:51:10 IST
captured 3,212 PCAN frames but still zero ESP32 frames and zero observed ESP32
diagnostic requests. The latest evidence is also preserved in
`output/testing/be-dual-interface-after-power-correction.json`.

The user reported a 3.3 V transceiver supply. If this is connected to TJA1042
VCC, it is below the specified 4.5–5.5 V operating range and is a plausible
cause. VIO-capable variants can use 3.3 V logic separately; variants without
VIO use 5 V logic. Verify the exact module and voltage compatibility before
changing supplies. STB must be LOW for normal transmission/reception.
The reported chip marking is `A1042/3 B9 02`, indicating the VIO variant.
The chip pin assignment supplied for checking is VCC pin 3 = 5 V, VIO pin 5 =
3.3 V, STB pin 8 = LOW, GND pin 2 common, TXD pin 1 from GPIO25, RXD pin 4 to
GPIO26. This is chip pin numbering, not an unverified module header order.
Source: [NXP TJA1042 datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1042.pdf),
sections 7 and 10. A successful ESP32 read and physical programming remain
unverified; software and PCAN validation must not be presented as those tests.

## Work, timing and reproducibility

AI work: new-reference inventory, executable inspection, address/profile and
44-workflow mapping, CDD parsing, codecs, automatic preparation/security,
programming validation, firmware transport changes, one-click GUI, tests,
flashing, live PCAN/API tests, screenshots and this work record. User work:
reference selection, USB/bus connection and hardware supply confirmation.

Observed milestones on 18 November 2026:

- 18:31:55 IST: new-reference manufacturing-serial BAT completed its test.
- 18:36:56 IST: hardware-part BAT test completed.
- 18:37:05 IST: application-mode serial EXE test completed.
- 18:41:19 IST: ESP32 API read recorded TX failure and successful close.
- 18:46:47 IST: simultaneous PCAN/ESP32 comparison recorded.

These are recorded test milestones, not continuous effort or interaction-time
measurements. EXE process durations included startup/teardown (~9–10 seconds);
the direct PCAN serial request received its first response about 3 ms after
transmission and completed its multi-frame reply in about 53 ms, following
~2.6 seconds of client preparation. No ESP32 success timing is claimed.
Exact token use, prompt count across hidden history, account credits and total
interaction time are not supplied by the runtime and have not been invented.

Reproduce from the project root:

```powershell
backend/.venv/Scripts/python.exe scripts/verify_bms_reference.py
Push-Location backend
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check app tests migrations
Pop-Location
Push-Location frontend
. ../scripts/common.ps1
npm test -- --run
npm run build
Pop-Location
./firmware/tools/test_host.ps1
./firmware/tools/build.ps1 -ProjectDirectory .
```

Live programming is not part of these tests. Inspect the current physical setup
and choose the correct migration workflow before a deliberate programming job.

Final software validation: **75 backend tests and 27 frontend tests passed**;
Ruff, TypeScript/Vite production build, firmware host tests and ESP-IDF build
passed. The one-click UI test covers automatic submission and decoded display;
it uses a simulated transport and is not a physical BMS success claim.

## Firmware and missing serial-message investigation

On 18 November the user reported that the terminal only showed `resources`
lines and asked whether CAN prints had been removed or the wrong firmware
flashed. The original `CAN seq=... ID=... DLC=... DATA=...` statement and its
per-frame formatting were retained. Neither the 500,000 bit/s rate nor GPIO25
TX / GPIO26 RX nor the accept-all filter had changed. The `resources`
`publish_drops` value is an analog/MQTT delivery counter; it is separate from
CAN receive counts and CAN publishing/serial drops. A stable value of 126
does not mean 126 additional frames were lost on each line.

COM3 was identified as ESP32 MAC `ec:62:60:9c:40:84`. Before making any new
firmware changes, esptool verified all three installed components against the
current build: bootloader at 0x1000, partition table at 0x8000, and application
at 0x10000. All digests matched. The application SHA-256 was the `06e137...`
image recorded above. The offline `output/firmware/navsphere.bin` was still an
earlier diagnostics build (`5c8e29...`); this packaging discrepancy did not
describe the firmware on COM3.

Controlled comparison on the same board, wiring and 500 kbit/s bus:

| Image / observation | Window | PCAN frames | ESP32 serial CAN frames |
| --- | ---: | ---: | ---: |
| Current BE firmware, before reset | 12 seconds | 4,900 | 0 |
| Current BE firmware, after reset | 12 seconds | 6,094 | 0 |
| Saved pre-BMS CAN-only image from commit d7eb9c2 | 20 seconds | 8,467 | 0 |

The original Git image was extracted without changing the working source,
checked against its committed manifest (SHA-256
`4e2df9c13970fde83d1fdc57b93ac7ec8e1de25880e48dde6e8c4fb5fdc6c85d`), then
temporarily flashed to the application partition only. Its startup explicitly
confirmed listen-only, 500 kbit/s, TX25/RX26 and accept-all IDs. PCAN reported
OK with no error frames in each comparison. These were passive captures;
no BMS requests, resets, unlocks or programming commands were transmitted.
The ESP32 itself was restarted/flashed; BMS firmware was not modified.

Evidence: [current image](../../output/testing/be-current-firmware-passive.json),
[after reset](../../output/testing/be-current-after-reset.json),
[pre-BMS image](../../output/testing/be-original-can-baseline.json).
This comparison does not reproduce a BMS-code regression and does not establish
the precise electrical fault. It establishes that reverting the BMS changes
alone did not restore reception on the currently connected COM3 board.

The added terminal visibility consists of a `CAN_BUILD` startup line with the
build date and ELF fingerprint, plus `CAN_STATUS` every five seconds showing
mode, controller state, RX/TX counts, bus errors, receive/transmit error counters,
serial drops and the instantaneous GPIO26 input level. `RXD26_now` is only a
point sample, not an oscilloscope measurement. Logging occurs outside the driver
lock; per-frame CAN output is retained. Analog acquisition, ControlA GPIO2,
ControlB GPIO0, Wi-Fi credentials and NVS are unchanged.

Firmware changes since the pre-BMS release are: CAN statistics; temporary
normal-mode transmission for diagnostic requests and automatic listen-only
restoration; ISO-TP framing/flow control; restricted request/reply CAN IDs;
diagnostic MQTT request/response handling; and the terminal visibility above.
CAN captures are still forwarded to both the serial and database paths.

GUI evidence includes the [quick-read page](../../output/testing/bms/be-quick-reads.jpg)
and [actual failed read with saved trace](../../output/testing/bms/be-read-response.jpg).
The latter is a failure record, not a successful BMS response.

Final restored image: **1,009,264 bytes**, SHA-256
`bd1af2dbacbd46179170cad830d8e9716c3b6c79bdf058282b1eda865f2d6a7c`.
All three flash components were hash-verified. The running firmware printed
ELF fingerprint `fe42bcd4b`, matching the local ELF SHA-256. The IDF application
description's compile date can remain from an earlier incremental build;
the ELF fingerprint and verified binary digest identify the current image.
The final 20-second comparison recorded **9,263 PCAN frames and zero ESP32
frames**. The new serial task printed `CAN_STATUS` with controller running,
listen-only, RX=0, TX=0, bus errors=0, serial drops=0 and instantaneous RXD26=1.
That pin sample alone cannot establish whether RXD is switching.
See the [complete firmware audit](../../output/testing/be-firmware-audit.json).

After restoration, MQTT and database readiness passed, fresh hardware analog
samples were persisted with the new boot ID, and both dashboard pages returned
HTTP 200 through the laptop's LAN address. The firmware build and host tests
passed again after the logging additions. COM3 was released after capture so
the user's ESP-IDF monitor can reopen it at 115200 baud. The offline firmware
and source/document package were refreshed from this verified build.

## Shared software version release — 18 November 2026

The next release is **SW_VERSION 1.1.0**, source build ID `2e6876f40c71`.
Its firmware image is **1,009,440 bytes**, SHA-256
`20763b850373c610628167ecce0a05732f48e6ac1ed9141c648bae695b2b0a8a`.
The user reported CAN reception had resumed before this versioning update.

`version.json` owns the shared release identity. Generated firmware macros in
`firmware/main/sw_version.h` and GUI constants in `frontend/src/sw_version.ts`
use `SW_VERSION`, `SW_BUILD_ID` and `SW_BUILD_UTC`. The last field records release
preparation in UTC, not a possibly cached compiler timestamp. The firmware
reports the version at startup and through CAN/MQTT status; the GUI displays
the actual device report alongside its own version on every signed-in page.
Legacy firmware shows "Not reported"; stale observations show "Last seen";
matching and differing version/build pairs are explicit.

Both ESP-IDF entry points run the shared generator, including direct VS Code
builds, and watch source changes. The GUI runs it before development startup
and production builds. A changed source tree increments the patch version;
unchanged rebuilds/reflashes retain it so separately built GUI and firmware
remain aligned. `python scripts/sync_version.py --bump` starts a deliberate new
release without source changes. Generated outputs must not be edited separately.
Generation is locked across simultaneous builds and writes files atomically.
Packaging now rejects stale source, an old compiled firmware identity, or an
old GUI build; the manifest includes version and source build ID.

Validation for this change: **3 versioning tests**, **48 CAN/BMS backend tests**,
**30 frontend tests**, Ruff, TypeScript/Vite production build, ESP-IDF build
and firmware host tests passed. The backend test verifies version metadata
survives real ingestion alongside persisted CAN data and resets to unknown for
a legacy boot. Version tests cover automatic increments, stable rebuilds,
missing generated files, stale-source rejection and explicit release bumps.

Live verification completed at approximately **22:23 IST, 18 November 2026**:
COM3 MAC `ec:62:60:9c:40:84`, all three flash components hash-verified, startup
`SW_VERSION=1.1.0 BUILD=2e6876f40c71`, and both GUI/ESP32 versions displayed as
matching. The serial capture contained **2,415 CAN ID/data lines in 20 seconds**.
A separate six-second API comparison recorded **3,425 additional captured CAN
frames and 674 additional database records**; analog hardware samples were
also persisted from the same new boot. This establishes live reception and
database delivery, not lossless delivery: the existing bounded MQTT and serial
queues reported drops at this bus rate. No throughput-policy change was made
as part of versioning.

The earlier zero-reception result is superseded for this setup. A single
follow-up application serial-number read still failed during the initial
TesterPresent transmission, before the DID read was sent (TX successes 0,
TX failures 1). The firmware restored listen-only and CAN reception continued.
Thus the version/flash/CAN receive checks passed; successful BMS diagnostic
transmission remains unverified. No live write, unlock, erase or BMS reset ran.

Evidence: [serial version and CAN capture](../../output/testing/sw-version-serial.json),
[live version/database checks](../../output/testing/sw-version-live-verification.json),
[diagnostic read result](../../output/testing/sw-version-bms-read.json),
and [matching GUI versions with live CAN](../../output/testing/bms/sw-version-can-live.jpg).

## CAN latest-value display correction — software 1.1.3

The user reported that the GUI was not updating. Before changing the code,
two live API snapshots four seconds apart showed fresh database records and
changing payloads for 0x06E and 0x06F. However, the table was sorted by ID and
began with inactive IDs 0x001/0x002/0x014 last received on 17 November. It was
also below a long list of **79 DBC conflicts**. No ingestion stall was reproduced
in that check; the UI mixed historical and current-run values and put the live
table below configuration output. Evidence: `output/testing/can-gui-before-fix.json`.

The page now defaults to IDs received in the current ESP32 boot, with
**All saved IDs** preserving the previous view. The filter is applied on the
server before pagination; legacy API callers retain the original default.
The latest-value table appears first, followed by expandable DBC information
and statistics. Two decoded signals are visible per row, with all remaining
signals available by expanding the row. No DBC files or historical rows were
removed. Refresh time, per-ID age/count, and changed-byte highlighting make
activity visible. Ages use server time to avoid a remote PC's clock skew.

The polling loop now has an eight-second timeout, retries after errors and
keeps displayed ages advancing even while a request is stalled. This behavior
was tested; an actual stalled browser request was not established as the
original cause. Browser requests explicitly bypass cache.

Validation: **16 CAN backend tests**, **32 frontend tests**, Ruff and the
production GUI build passed. New tests cover current-boot filtering before
pagination, preserved old IDs/history, visible repeated value changes, timeout
recovery and continuously advancing ages. Final software version is **1.1.3**,
source build ID `8097dcac11e0`; firmware CAN capture, pins and bus settings were
not changed for this GUI correction. Firmware receives the matching release
identity through the existing generated macros.

Browser verification before flashing confirmed actual changes in row 0x06E:
`38 DE FF 03 00 81 16 00` / 2,205,798 frames at 17:15:41 UTC became
`BB DB FF 03 00 81 16 00` / 2,206,341 frames at 17:16:40 UTC. The All saved IDs
view retained 0x001 with its old timestamp and an explicit Previous run label.

**Deployment recovered on 18 November 2026:** the first flash lost its USB
connection during the application write, and the second connection timed out.
After the user unplugged and reconnected USB, a complete retry at 115200 baud
succeeded on COM3 (ESP32 MAC `ec:62:60:9c:40:84`). The bootloader, partition
table and application all passed the flash tool's hash verification. NVS was
not written. The application SHA-256 is
`6dc913faf334c11229077318780b2d11552694bd8806c8b5bb04689e128336f0`.

The startup log reported **SW_VERSION=1.1.3**, build `8097dcac11e0`. A
20-second serial capture contained **2,806 CAN frame lines**, with the device
in listen-only mode. Both the direct backend and LAN dashboard address returned
31 current-run IDs; the all-saved view retained 69 IDs. Four-second comparisons
confirmed advancing sequence numbers and database receive timestamps for 21
IDs through the direct backend and 25 through the LAN address. The LAN request
was made from this laptop, not a separate remote PC.

The actual browser showed matching GUI/ESP32 versions and CAN logger online.
For ID 0x06E, the visible raw bytes changed from `BB DB FF 03 00 81 16 00`
at 17:29:06 UTC to `72 D5 FF 03 00 81 16 00` at 17:29:23 UTC; the saved-frame
count advanced from 2,208,252 to 2,208,442. Existing serial and MQTT delivery
drops remain visible in the statistics; this verification does not establish
lossless logging. BMS diagnostic transmission was not retested in this recovery
and its previously recorded failure remains unresolved.

COM3 was closed after capture and an exclusive open/close check passed without
changing the serial control lines. The offline firmware manifest is updated
to `hardware_flashed=true` for this verified build.

Evidence: [flash receipt](../../output/testing/can-gui-flash-verification.json),
[serial capture summary](../../output/testing/can-gui-fix-serial.json),
[backend and LAN comparisons](../../output/testing/can-gui-live-verification.json),
[actual browser value changes](../../output/testing/can-gui-browser-verification.json),
and [live dashboard screenshot](../../output/testing/bms/can-gui-current-run.jpg).
