# NavSphere project and AI work report

Updated 19 November 2026. Application source/package: **v1.1.8 / 8148c3afe9b8**.
This report replaces the earlier November 12 summary. Historical captures and
test records retain their actual date/version. See ../RELEASE_STATUS.md.

## Time, interaction and effort

| Measure | Recorded result |
|---|---|
| Completed work-session duration | 6 hours 21 minutes 22 seconds (22,882,384 ms) |
| Completed timed turns | 44 across the two project chats |
| Initial development/build fixes | 1 hour 8 minutes 6 seconds; 4 completed turns |
| Recovery, integration, CAN/BMS, reports and Git work | 5 hours 13 minutes 16 seconds; 40 completed turns |
| Calendar span between first start and last completion | 8 days 4 hours 59 minutes 27 seconds; includes gaps |
| Current documentation turn | Excluded from completed-time total; still in progress at audit |
| Human hands-on labor / AI compute time | Not separately measured |
| Time saved against manual development | No baseline; no percentage claimed |

Source: `output/reports/interaction-time.json`, refreshed from complete paginated
turn records for **Build NavSphere telemetry platform** and **Recover missing
project files**. The sum includes tool execution and waits within completed turns,
but excludes gaps, interrupted/non-completed turns and this ongoing documentation
turn. It is measured interaction-session time, not an invoice or engineering
labor estimate. The earlier 1h 46m 40s covered only nine completed turns through
November 12 and is superseded for the expanded audited scope.

## Prompt count, size and credits

| Measure | Audit result |
|---|---|
| User message records | 74 across two chats: 9 initial development, 65 recovery/follow-up |
| Current documentation requests | Included in message count; excluded from completed time |
| Exported message text | 1,313 whitespace-separated words; 7,791 Unicode characters |
| Original master prompt attachment | Historical audit: 4,338 words, 32,235 characters, 32,289 file bytes |
| Exact billed/model tokens | Unavailable |
| Total project credits used | Unavailable, not zero |

One user-message record counts as one input, including clarification answers or
image-bearing inputs; multi-answer replies remain one record. Text sizes use the
app-exported text and clarification answer text, with space entities normalized.
Any file-label text in the export is included; image pixels are not converted to
words. Attachment contents are excluded from message totals; the original master
attachment is reported separately from the historical audit. The edited current
repository prompt is not counted again as a user input. Counts of user messages,
completed turns and model-internal prompts are different measures.

No project billing ledger or reliable billed-token total is available. The old
account-wide 4% weekly-allowance snapshot is historical and cannot establish
project cost. This report does not extrapolate credits, rates or monetary savings.
Stored metric records contain counts and durations, not passwords or transcript text.

## Implemented capability inventory

| Area | Delivered behavior |
|---|---|
| Firmware | Native ESP-IDF 6.0.2/C/FreeRTOS, root and standalone build support, shared version macros |
| Analog | Six ADC1 inputs on GPIO32/33/34/35/36/39, nominal 10 Hz, calibrated mV/raw values and validity mask |
| Connectivity | Private NVS provisioning, Wi-Fi/SNTP, authenticated MQTT, reconnect handling, bounded queues and visible loss counters |
| Controls | A=GPIO2, B=GPIO0; acknowledgement, expiry, replay protection, startup/disconnect LOW and inactivity watchdog |
| Backend/database | FastAPI, authenticated REST/WebSocket, MariaDB, Alembic, deduplication, received versus persisted state and audit history |
| Dashboard | Live overview, six analytics pages, historical ranges, CSV export, health, roles, account and themes |
| CAN receive | 500 kbit/s, GPIO25 TX/GPIO26 RX, standard/extended/RTR, raw history/latest values and serial output |
| CAN analysis | Multiple local DBC files, decoded signals, conflicts, live search, current-run/all-saved views and statistics |
| BMS page | BE reference: 55 CDD services, 44 BAT workflows, five Quick reads, previews, state-change guards and saved responses |
| Periodic CAN TX | One ON/OFF control for fixed 0x014 at 100 ms and 0x548 at 10 ms; device-confirmed state and counters |
| Operations | Native Windows launch/stop, LAN access, application-only flash instructions, source/binary packages, reports and test records |

BMS workflow preparation is implemented and tested offline; successful ESP32
diagnostic responses remain unverified. CAN TX payload delivery was measured
on v1.1.7, while the corrected v1.1.8 timing build remains unflashed.

## AI work and user contributions

| Work area | AI contribution | User contribution |
|---|---|---|
| Scope and recovery | Inspected files/reference projects, restored required work and mapped implementation | Defined six-channel scope and priorities; supplied original location |
| Software | Firmware, database, backend, GUI, DBC, search/statistics and periodic TX implementation | Confirmed GPIOs, IDs/payloads, transport and BE reference |
| BMS reference | Analysed BAT/executable behavior; reproduced workflows and documented discrepancies | Selected reference repository and connected BMS/PCAN |
| Deployment | Built/flashed earlier firmware, launched services, checked DB/MQTT/LAN and versions | Connected/reconnected adapters, supplied local network access and login |
| Hardware diagnosis | Compared PCAN/ESP32 captures, isolated ACK/power/arbitration symptoms | Checked wiring and corrected transceiver supplies |
| Verification | Host/component tests, independent bus captures, fault checks and evidence | Confirmed physical bus activity and remote-PC access |
| Handoff | Git commits/pushes, offline artifacts, screenshots, instructions and usage audit | Reviewed outcomes and requested additional functionality/documentation |

AI work did not physically measure voltages or change wiring. The user performed
those actions. Historical flashing is not evidence that the latest image is
running. No claims of production certification, lossless logging or measured
human-hour savings are made.

## Current tests and remaining effort

| Check | Recorded result |
|---|---|
| Backend software | 89-test suite passed; 11 targeted tests passed after clock-readiness handling |
| GUI software | 38-test suite passed; 14 targeted CAN/control tests passed afterward |
| Firmware host checks/builds | Passed, including arbitration retry policy; GUI production build also passed |
| Earlier v1.1.4 deployment | Flash, CAN/ADC storage and browser/LAN evidence saved on November 19 |
| v1.1.7 periodic TX after supply fix | Correct bytes on PCAN; 100 frames of 0x014 and 813 of 0x548 in 10 seconds; no observed PCAN errors |
| Timing result | FAILED: 0x014 mean 99.982 ms; 0x548 mean 12.301 ms |
| v1.1.8 correction | Bounded arbitration-only retries built; not flashed or wire-tested yet |
| BMS live ESP32 response | Unverified and deferred; periodic frames do not prove diagnostic completion |

Suite and targeted counts overlap; do not add them into a unique-test count.
Remaining immediate work is to reconnect both adapters, flash the exact v1.1.8
application while preserving NVS, measure timing, verify GUI ON/OFF and ongoing
CAN/ADC storage, then leave TX OFF and release COM. Reboot/disconnect behavior
also needs hardware confirmation. Electrical calibration, long soak and production
security remain separate acceptance work. No completion time is estimated without
the connected hardware. Full procedure: docs/firmware/CAN_TX_GUIDE.md.

## Screenshots and evidence

The following offline report pages use genuine stored captures. The CAN page
capture on November 19 shows GUI v1.1.8 with the last-seen v1.1.7 device offline;
it proves the displayed controls, not successful current transmission. The
November 19 earlier CAN capture and November 12 overview/analytics/controls
screenshots illustrate features at their recorded dates. None is a synthetic
image or a claim that the device is presently online.

Evidence paths: output/testing/can-tx-awaiting-flash.jpg,
output/testing/bms/redeploy-20261119-gui.jpg, output/reports/telematics-overview.png,
output/reports/telematics-analytics.png, output/reports/telematics-controls.png,
output/testing/can-tx-voltage-corrected-before-arbitration-fix.json and
output/work_snapshot/can_tx_20261119/runtime/. Raw records retain failed outcomes.
