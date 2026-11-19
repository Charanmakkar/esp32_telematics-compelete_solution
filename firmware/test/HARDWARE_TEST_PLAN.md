# ESP32-WROOM hardware verification

Status: earlier firmware was flashed and CAN/telemetry paths exercised on hardware. Full electrical/calibration/soak acceptance remains incomplete. v1.1.8 is built but not flashed; see docs/RELEASE_STATUS.md. Disconnect external loads while first verifying the GPIO map.

| Check | Procedure | Acceptance / evidence |
|---|---|---|
| Pin mapping | Confirm GPIO32,33,34,35,36,39 on the board's own schematic and silkscreen | All six inputs mapped in logical order; no ADC2 input configured |
| ADC calibration | Check startup logs, apply metered DC voltages within the specified ADC range to each channel | Calibration initialized; error and nonlinearity recorded against an agreed sensor accuracy requirement |
| ADC range | Sweep a protected source through the documented measurement range | Raw values remain 0..4095; valid_mask bits reflect read/calibration errors; no claim of 5V tolerance |
| Input error handling | Run a build with acquisition disabled; separately inject driver failures in a test fixture | All six fields present; invalid mask bits clear; dashboard shows unavailable, not measured zero |
| Period | Capture at least 10,000 unique device sequences with original uptime_ms | Target 10Hz nominal; report actual median/p95/p99/max period, gaps and reconnect boundaries |
| ADC independence | Disconnect broker for 60s while monitoring serial acquisition/resource counters | Acquisition continues; bounded queues; dropped count increases; no heap growth from offline samples |
| Wi-Fi recovery | Remove access point for 60s, restore it, repeat three times | Bounded backoff to 30s, automatic IP and MQTT recovery; original boot_id preserved |
| Broker recovery | Stop/restart broker with device powered | LWT reports offline; recovery restores subscription; old expired commands cannot actuate |
| A/B mapping | Place meter or high-impedance scope on GPIO2 and GPIO0 | Startup LOW; authorized A=1 drives only GPIO2 HIGH; B=1 drives only GPIO0 HIGH; zero clears corresponding output |
| Command rejection | Through an authorized test fixture send retained, expired, wrong-type, unknown-key and duplicate commands | No forbidden execution; correlated valid IDs receive rejection; duplicate never reapplies an old state |
| Disconnect safety | Set both HIGH then remove Wi-Fi or broker | LOW within one observed publisher cycle after disconnect event; report measured delay |
| Watchdog | Set HIGH and leave that control untouched for 60 seconds | LOW after configured monotonic watchdog; SNTP correction cannot extend it |
| Reset safety | Observe reset/brownout with actual driver/load; keep GPIO0 HIGH at reset and GPIO2 LOW or floating for serial flashing | Pads remain safe before firmware initialization; verify the actual external circuit |
| Memory | Collect free heap and stack high-water marks under telemetry plus command load | No monotonic heap loss; adequate stack margin (target at least 25% for each task) |
| Soak | Run 24 hours with repeated Wi-Fi/broker outages and protected input signals | Record reboot count, timing distribution, heap trend, stack margins and telemetry/command losses |

Store captures and measured results separately from simulated integration
results. The software's `applied` acknowledgement proves a successful GPIO
latch API call; a meter/scope or feedback input is needed to verify an actuator.

## Periodic CAN TX acceptance, v1.1.8

The v1.1.7 test delivered exact bytes after power correction but failed timing.
v1.1.8 arbitration retry correction needs a physical test. Follow the root
docs/firmware/CAN_TX_GUIDE.md: verify exact image/hash, supplies, bitrate and ACK;
OFF baseline with no duplicate source; 10 s ON with exact IDs/DLC/bytes;
mean periods within 5% of 100/10 ms, max below twice period, no new failures;
OFF plus 300 ms grace and 3 s without either ID. Exercise actual GUI controls,
verify RX/ADC persistence, reboot default OFF and MQTT disconnect stopping TX.
Reconnect must not re-enable it. Leave OFF and release COM. Diagnostic success
is a separate unresolved check; no BMS programming/erase/reset belongs here.
