# Periodic CAN transmission

Updated 19 November 2026. Source/package: **v1.1.8 / 8148c3afe9b8**.
This build has not yet been flashed or accepted on hardware.

## Fixed messages

| Standard 11-bit CAN ID | DLC | Hexadecimal bytes | Requested period |
|---|---|---|---|
| `0x014` | 3 | `00 60 00` | 100 ms |
| `0x548` | 8 | `00 00 00 00 00 00 00 08` | 10 ms |

Both use classic CAN at 500 kbit/s on the ESP32's single physical CAN bus.
The user's explicit `0x548` supersedes `0x584` in the screenshot. Its CAN 2
label does not create a second ESP32 interface. Repeat these exact bytes;
there is no rolling counter, checksum calculation or arbitrary-frame editor.

## Wiring and prerequisites

GPIO25 connects to TXD and GPIO26 receives RXD. The identified TJA1042/3 uses
VCC pin 3 at 5 V, VIO pin 5 at 3.3 V, GND pin 2 shared with ESP32/bus, and
STB pin 8 LOW. TXD is pin 1 and RXD pin 4. Verify the actual module schematic:
pin 5 on a non-VIO variant has a different function. See the
[NXP datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1042.pdf).
Connect CANH/CANL with appropriate end-of-bus termination.

Keep another normal-mode CAN node present to acknowledge the ESP32 frames.
PCAN in active/normal receive mode supplies ACK without application messages;
a listen-only analyzer cannot. Reception alone does not prove TX power,
TXD continuity or acknowledgements are correct.

Start MariaDB, MQTT, backend and frontend using the
[deployment guide](../deployment/DEPLOYMENT_AND_USER_GUIDE.md). Load the matching
firmware/GUI build and updated `mqtt/acl.example`. Retain private NVS credentials.
Use a changed-password admin account and wait for Wi-Fi, MQTT and SNTP.

## GUI operation

1. Open `/can`, select the physical ESP32 and find **Periodic CAN transmission**.
2. Confirm fresh status, synchronized clock and idle diagnostics.
3. Click **Turn transmission ON**. Wait for **Transmission ON** and increasing
   successful-send counters for both IDs. The ESP32 schedules frames locally;
   the browser sends one enable command, not individual timed frames.
4. Click **Turn transmission OFF**, wait for confirmation and check an independent
   analyzer after allowing queued traffic to drain. Leave OFF after testing.

Closing the browser does not send OFF. Transmission continues while enabled
and connected to MQTT. Backend failure alone need not disconnect device MQTT.
Unknown/stale means the current state is unconfirmed, including OFF. OFF with
known stale state is best effort and still needs device acknowledgement.
If a response is lost, the command may have applied: refresh before retrying.

## Firmware and command behavior

`can_tx_rules.c` defines the two profiles and strict control parser. `can_tx.c`
has an eight-command queue and priority-5 task with 4096-byte stack. It starts
OFF, skips overdue slots instead of sending catch-up bursts, and resets counters
on reboot. Successful driver completions increment `sent_014`/`sent_548`;
`failures` counts failed sends and `skipped` counts missed schedule slots.
Three consecutive failures stop transmission with `transmit_failed`; a successful
send resets that consecutive count. MQTT disconnect cancels older queued controls
and stops active TX. Reconnect requires a fresh ON command.

Diagnostics and periodic TX cannot own normal mode simultaneously. Turn periodic
TX OFF before BMS work. OFF restores listen-only when diagnostics do not own it.
Existing analog, GPIO, RX/DBC and diagnostic request interfaces are retained.

v1.1.8 keeps hardware single-shot attempts and retries ordinary arbitration loss
only when neither bus errors nor the TX error counter increased. The budget is
5 ms and at most 16 attempts per scheduled send. Bus/ACK errors are not retried
by this loop. Requested periods are scheduling targets, not guaranteed wire
timing under arbitrary load. This correction still requires physical verification.

MQTT topic: `navsphere/<device_id>/can/tx/request`, QoS 1, never retained.
Its exact five fields are `command_id` (lowercase UUID), `boot_id`, `enabled`
(boolean), `issued_at_ms` and `expires_at_ms`. Backend lifetime is four seconds;
firmware rejects lifetimes over five seconds, expiry, issue times over one second
in the future, wrong boot, retained/fragmented messages, duplicate/out-of-order
timestamps, embedded NUL, extra fields and payloads of 384 bytes or more.
Confirmations arrive in `stats.periodic_tx` on the existing CAN batch topic,
including empty batches. See the [API reference](../api/API_REFERENCE.md).

## Database meaning

Received frames still use `can_frames` and `can_latest`; toggle submissions use
`audit_events` with action `can_tx_toggle`. There is no new migration or separate
durable per-transmitted-frame log. The receive table need not contain the ESP32's
own outgoing frames: normal transmission does not guarantee self-echo.
Use independent PCAN capture for bus delivery. TX counters and estimated bus
statistics are not lossless recording or electrical measurements.

## Evidence and remaining acceptance

After the user corrected the supplies, v1.1.7 delivered both exact payloads to
PCAN with zero observed PCAN error frames. Ten seconds contained 100 frames of
0x014 (mean 99.982 ms) and 813 of 0x548 (mean 12.301 ms). Timing acceptance
failed. Single-shot arbitration losses motivated v1.1.8. Host tests and both
builds passed; USB devices disconnected before flashing the correction.
Last acknowledged state was OFF on v1.1.7; current offline state is unknown.

1. Reconnect ESP32 USB and PCAN. Detect the actual serial port (previously COM3).
2. Close monitors, flash only the application at `0x10000`, baud 115200, preserve
   NVS, then verify flash hash and startup version/build.
3. Keep PCAN active at 500000 bit/s. Disable other transmitters of these two IDs.
   Only one helper/test should own PCAN at a time.
4. Capture three seconds OFF, then ten seconds ON after settling. Check exact
   ID/format/DLC/bytes, mean intervals within 5% of 100/10 ms, maximum interval
   below twice the period and no new send failures. Record bus-error frames.
5. After OFF and 300 ms grace, capture three seconds without either target ID.
   Exercise the actual GUI buttons as well as the API.
6. Confirm ordinary CAN RX and analog persistence still advance, final mode is
   listen-only, TX is OFF and the serial port is released.
7. Separately verify reboot defaults OFF and MQTT disconnect stops TX; reconnect
   must not re-enable it. Keep an independent ACK node throughout these tests.

Scripts/logs are preserved in `output/work_snapshot/can_tx_20261119/` and
results in `output/testing/can-tx-*.json`. Restore helper copies to `.runtime/`
before running from the repository root; some resolve paths relative to that
directory. The live test needs python-can, PCAN drivers and pyserial. Provide
`NAV_TEST_PASSWORD` privately in a temporary environment variable; do not commit
credentials. The script enables only the two approved profiles. Do not use
BMS erase/program/reset or diagnostic jobs as part of this test.

## Troubleshooting

| Symptom | Check |
|---|---|
| ON disabled | Admin, changed password, fresh CAN state, SNTP and idle diagnostics |
| HTTP 504 or unknown | Device acknowledgement timed out; inspect state before retry |
| TX_FAILED / rising TEC | VCC/VIO, TXD, STB, ground, termination and another ACK node |
| Timing gaps, arbitration loss only | Check actual flashed build, then measure bus timing |
| Repeated RX frames while OFF | Another normal-mode node must supply ACK |
| Serial CAN works; GUI stale | MQTT drops, backend persistence, device/run selection |
| COM unavailable | Close monitors/test handles, reconnect and enumerate; preserve NVS |
