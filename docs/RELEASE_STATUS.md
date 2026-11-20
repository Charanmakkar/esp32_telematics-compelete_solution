# Current release and verification status

Updated 20 November 2026. **v1.1.22 / 1e17f3d0dbcc** fixes firmware-file feedback.
The connected board remained on **v1.1.21** during the final upload validation; no flash
or reboot was requested by the upload-only test.

- Root and standalone ESP-IDF builds and the GUI production build passed.
- Eight focused OTA GUI tests passed, including visible validation errors,
  retained filename feedback and rejection of stale-image installation. Rejected
  selections now hide previous target details, and the native picker retains the
  chosen filename. These cases directly address the supplied screenshot.
- A real browser with normal administrator authentication reproduced the old
  BIN rejection (HTTP 400) and accepted the rebuilt `firmware/build/firmware.bin`
  (HTTP 200). Desktop/mobile checks passed with no page errors.
- The packaged `output/firmware/navsphere.bin` is the exact standalone image
  tested by the uploader. Application SHA-256: `787f925df445586d4003ac2aa1e17b45202500101c33e9e6fb18c0f6fc15b070`.
- This image is ready for the user to install. Its manifest records
  `hardware_flashed=false` and `hardware_ota_verified=false`; the earlier v1.1.20
  hardware results below are historical and do not claim a v1.1.22 flash.
- The temporary upload-test account was disabled and its sessions revoked.
  Existing login credentials and board settings were unchanged.

The user also completed a v1.1.21 OTA update successfully; the chip confirmed
the exact uploaded image. Evidence: `output/testing/ota-user-update-v1.1.21.json`.
This does not claim installation of the newer v1.1.22 image.

Evidence: `output/testing/ota-file-selection-20261120.json` and
`output/testing/screenshots/ota-file-*`. See the OTA guide's file-loading section.
The unresolved periodic CAN reset and other hardware limits from the previous
validation remain applicable; periodic CAN transmission remains OFF.

## Previous hardware verification — v1.1.20

Updated **20 November 2026**. Release **v1.1.20 / 1fb9fadf201c** was installed on the
connected ESP32 and matched the application packaged for that release.

| Item | Verified record |
|---|---|
| Source / GUI / firmware | v1.1.20 / 1fb9fadf201c |
| Source SHA-256 | 1fb9fadf201ce4deb40dca01d2c361fb96d03a147fe5534ba8d24244185a6194 |
| Application SHA-256 | 52183f74e964206809bcf01098c14d393813281d165eae8ccf8d008854ba030d |
| Running-image SHA-256 | 4ee0c99991718382bef53ab5762daf8b1d32e493750d4259caab40643c9285c9 |
| Application size / slot | 1038608 / 2031616 bytes |
| USB migration | Full 4 MiB private backup, preserved NVS, verified writes |
| Hardware OTA | BIN and Intel HEX confirmed by new boot, exact hash and version |
| Startup rollback | Reset pending boot; previous confirmed image restored |
| Current hardware flags | hardware_flashed=true, hardware_ota_verified=true |

### Screenshot comparison and delivered additions

The OTA page now has chip-reported installed version, IP, Wi-Fi signal and uptime;
single-file drag/drop; visible 1984 KiB application and 6 MiB upload limits; a
before-upload guide; progress, offline/stale reporting; and browser/server/device
transport-security information. It retains the existing administrator login and
server-side HEX conversion. No separate OTA password or browser HEX parser is required.

Transfers use the chip-advertised 2048-byte capacity, with a 768-byte fallback for
earlier OTA builds. Final USB restoration after the deliberate rollback test kept
the original NVS bytes identical and restored the packaged build.

The first upload test exposed a clock-skew boundary, fixed by using a 15-second
deadline below the chip's 30-second maximum. Wi-Fi/MQTT timeouts occurred under
heavy CAN traffic and weak signal. Large CAN MQTT batches now pause only during
OTA, and modem sleep is disabled only during transfer. ADC telemetry and passive
CAN capture remain enabled, subject to flash delays. Abort releases the locks
and restores the power policy; reboot briefly interrupts all device reporting.
No previous GPIO, ADC, periodic CAN or BMS behavior was changed outside OTA.

An earlier run with the final chunk configuration stopped when the board reset
unexpectedly at 53% transfer. The previous confirmed image survived; the cause
was not captured and remains unassigned. The subsequent fully logged BIN and
HEX runs passed. These successful runs do not establish long-duration reliability.
See `output/testing/ota-live-bin-large-reset.json` for the failed attempt.

### Verification evidence

- 116 backend tests, 45 frontend tests, 3 version tests, firmware host checks,
  ESP-IDF build and GUI production build passed. The 26 targeted OTA tests overlap
  the backend total. One existing Starlette/httpx deprecation warning remains.
- Live BIN and HEX page uploads, both slot directions, mobile/desktop rendering,
  chip hash/version confirmation, reset mid-transfer and reset-before-confirmation
  rollback passed.
  BIN installed v1.1.20; drag/drop HEX installed v1.1.19 from the same final source
  revision. Confirmation took about 306 and 305 seconds respectively. The board
  was restored to v1.1.20 after the deliberate rollback test.
- Live server authentication/CSRF, bad BIN/HEX, bootloader and oversize rejection;
  chip size/hash/image checks; duplicate/conflicting/out-of-order chunks;
  interrupted-transfer timeout and maintenance control rejection passed.
- After OTA, six ADC channels persisted, WebSocket received/persisted events arrived,
  all six history APIs returned data, CAN capture/storage resumed, both safe OFF
  commands received applied hardware acknowledgements, and existing pages loaded.
- CAN wire test: FAILED: the ESP-IDF TWAI transmit-count assertion reset the device during periodic transmission; PCAN observed error frames and timing could not be evaluated. The cleanup OFF request timed out during reboot; subsequent live status independently confirmed listen-only mode, periodic TX OFF and both controls OFF. Periodic-transmit code was unchanged by OTA; root cause remains unresolved.
- Active periodic CAN causes OTA rejection while CAN remains enabled. All bench
  testing ends with periodic CAN OFF and both GPIO controls OFF.
- A read-only BMS hardware-number query completed with a positive response and
  restored listen-only mode. This does not establish all diagnostic workflows.
- The temporary test administrator was used through normal login/password-change
  flows, then disabled and its sessions revoked. The user's password was unchanged.

Machine-readable summary: `output/testing/ota-hardware-validation-20261120.json`.
Individual `ota-live-*.json` files and `output/testing/screenshots/ota-live-*`
contain measured results. Earlier failed attempts retain their failure labels.
The flash backup remains private under `.runtime/ota-backups/` and is excluded
from the release ZIP, along with credentials and live database files.

### Remaining acceptance limits

Reset-triggered rollback is verified; a physical power-cut test was not performed.
Output voltages, ADC accuracy, 24-hour stability, production TLS and lossless CAN
logging are not certified. CAN/ADC drop counters can increase during flash writes.
The transfer serial captures contain truncated characters/numeric fields, so their
raw resource minima cannot certify heap/stack margin. OTA worker stack margin and
reliable worst-case heap measurements remain unverified.
BMS catalog/jobs, page access and one read-only hardware-number response were
checked; destructive BMS operations were not performed. Other BMS workflows
remain outside this hardware acceptance result. Periodic CAN transmission has
the unresolved driver assertion described above; leave it OFF pending investigation.

### Artifact interpretation

`output/firmware/manifest.json` records exact binary hashes and verification flags.
`output/NavSphere_Source_and_Docs.zip` contains current source and documentation.
Earlier PDFs, reports, snapshots and screenshots remain historical evidence;
use the current Markdown OTA guide and this record for deployment decisions.
No Git commit or remote publication is implied by this package.
