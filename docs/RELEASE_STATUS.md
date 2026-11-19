# Current release and verification status

Documentation reviewed: **19 November 2026**. Application source commit:
`c272b057ccbc3c86b27d0bb96a545ee407c330bb`, branch `feature/add_CAN`.
This documentation revision does not change application behavior or source identity.

| Item | Current record |
|---|---|
| Source, built GUI and packaged application | v1.1.8 / 8148c3afe9b8 |
| Source SHA-256 | 8148c3afe9b8fa5a0046a5f4b05c47ce58531288b845d8e405aea63358d0038b |
| Application SHA-256 | 5f48790458c4f0903e2ce1249dd9ba49b8e5b3d0a625fd5781c3d88160166ced |
| Latest hardware-verified firmware | v1.1.7 / b323d1f42a84 |
| v1.1.8 hardware_flashed | false; USB disconnected before flash |
| Last acknowledged periodic TX state | OFF on v1.1.7; later offline state unknown |
| BMS diagnostic response through ESP32 | Still unverified; deferred, no new diagnostic test |

## Delivered features

- Six native ADC1 channels (GPIO32/33/34/35/36/39), nominal 10 Hz telemetry,
  authenticated MQTT, MariaDB history, six analytics pages and CSV export.
- Active-high A/B controls on GPIO2/GPIO0 with acknowledgement, expiry,
  safe startup/disconnect and inactivity watchdog behavior.
- Classic CAN RX at 500 kbit/s on GPIO25 TX/GPIO26 RX, bounded serial/MQTT
  logging, separate raw history/latest tables and loss counters.
- Multiple local `can_dbc/` definitions, decoded signals, conflict reporting,
  latest/history views, current-run filter, live search and CAN statistics.
- BMS page based on `HVBEOSK/be_repo`: 55 CDD services, 44 BAT workflows,
  five Quick reads, previews, guarded state changes, responses and job history.
  Offline preparation passes; ESP32 diagnostic hardware success is not established.
- One confirmed GUI ON/OFF control for standard 0x014 / 00 60 00 / 100 ms and
  0x548 / 00 00 00 00 00 00 00 08 / 10 ms. Both default OFF. v1.1.8 contains
  bounded arbitration-loss retries, still awaiting live timing acceptance.
- Shared firmware/GUI version display, local/LAN startup, release packaging,
  reports, screenshots, test evidence and temporary work snapshots.

## Evidence and limits

| Evidence | Result and scope |
|---|---|
| `output/testing/redeploy-20261119-verification.json` and related redeploy files | Earlier v1.1.4 flash, services, CAN/ADC storage and LAN/browser checks |
| `output/testing/can-tx-voltage-corrected-before-arbitration-fix.json` | v1.1.7 exact payloads received; 100/813 frames in 10 s; timing FAILED |
| `output/testing/can-tx-live.json` | Latest recorded wire test is the same failed v1.1.7 timing test, not a v1.1.8 pass |
| `output/testing/can-tx-pin-probe.json` | Earlier pin-routing observation; not proof of bus delivery |
| `output/testing/can-tx-verification.json` | Earlier deployment snapshot; does not certify v1.1.8 |
| `output/testing/can-tx-awaiting-flash.jpg` | Genuine GUI v1.1.8 screenshot, device last seen v1.1.7/offline |
| `output/work_snapshot/can_tx_20261119/runtime/` | Build/test logs and repeatable bench helper copies |

Software validation recorded during implementation: backend 89 tests passed,
then 11 targeted tests after clock-readiness handling; frontend 38 tests passed,
then 14 targeted CAN/control tests. These counts overlap and must not be added
as a unique test total. Firmware host tests and firmware/GUI builds passed.
This documentation update does not turn those host checks into hardware approval.

After transceiver supply correction, v1.1.7 PCAN capture had no observed error
frames and exact payloads, but mean 0x548 period was 12.301 ms rather than 10 ms.
The v1.1.8 retry correction remains unmeasured. Follow the
[CAN TX acceptance procedure](firmware/CAN_TX_GUIDE.md) after reconnecting both adapters.
Do not substitute simulator traffic for physical bus verification.

Full electrical calibration, output voltage/reset characterization, 24-hour soak,
production TLS deployment and lossless bus logging are not certified. No new
BMS destructive command or diagnostic implementation change was made.

## Artifact interpretation

`output/firmware/manifest.json` describes the current binary; `version.json`
describes source identity. `output/NavSphere_Source_and_Docs.zip` is the current
offline source/docs package. `output/releases/` and older work snapshots contain
dated historical versions. Preserve them as evidence; do not deploy an older
snapshot merely because it contains a binary. NVS, credentials, live databases,
private reference executables/keys, proprietary images and installed dependencies
remain local. Source and selected temporary work files are committed.
