# Hardware acceptance checklist

Host compilation and simulated telemetry cannot establish physical ADC accuracy,
RF reconnection behavior, output voltage or firmware endurance. Run this checklist
on the identified ESP32S-WROOM after provisioning. Record board revision, ESP-IDF
version, wiring, calibration source, instrument and test duration.

1. Confirm six sensor inputs connect in order to GPIO32, 33, 34, 35, 36, 39 and
   share ground. Leave ADC2 unused. Keep signals inside the calibrated ADC range;
   attenuation does not make an input 5 V tolerant.
2. Connect A's LED through a suitable resistor to GPIO2; observe GPIO0 as B
   with a meter or a logic-level compatible circuit. Never drive a high-current
   load directly. Measure both LOW at boot before Wi-Fi connection.
3. Build and flash the configured firmware and provision its separate NVS image.
   Verify serial log board target and calibration result. If calibration is
   unsupported, readings must remain invalid rather than report invented mV.
4. Apply measured 0.2, 0.8, 1.5 and 2.2 V to each input; compare raw ADC and
   calibrated millivolts with a calibrated meter. Characterize noise and offset.
   Recheck valid_mask=63 when all channels succeed; unplug a sensor only if its
   circuit establishes a defined voltage (floating inputs need not fault).
5. Capture at least 1,000 MQTT acquisition/publication timestamps. Evaluate
   nominal100ms timing, preserved acquisition timestamps for stale samples and
   boot/sequence deduplication across reboot. Record jitter, loss and heap/stack.
6. Disable Wi-Fi, then restore it. Repeat with the broker stopped. ADC acquisition
   must continue, outputs must reach LOW, and reconnect must remain bounded.
   Verify no unbounded telemetry backlog is replayed after recovery.
7. Send authorized A/B values1/0 and observe pins HIGH/LOW. Match command ID,
   accepted/applied messages, audit log and physical measurements. Publish
   malformed, duplicate, mismatched, expired and retained commands. Verify no
   unauthorized state transition and safe return after the inactivity watchdog.
8. Disconnect the broker while A/B are HIGH; measure safe-state delay. Delay SNTP
   and test the documented unsynchronized command rejection behavior.
9. Run at least24hours. Record minimum heap, task high-water marks, watchdog
   resets, ADC failures, publish drops and reconnection counts under load.

Earlier firmware was flashed and CAN/telemetry tested, but full electrical/calibration/soak acceptance is incomplete. See ../RELEASE_STATUS.md. integration-results.json is historical simulator evidence.


### Control pin update 12 November 2026

Control A uses GPIO2 and Control B uses GPIO0, active high. Both pins affect boot selection. Keep GPIO0 HIGH during reset for normal boot; do not add a Control B pull-down. GPIO2 must be LOW or floating for serial flashing. Firmware sets both outputs LOW after startup. An attached load must tolerate reset-time levels or use a separately enabled driver.

## Periodic CAN TX acceptance, v1.1.8

The v1.1.7 test delivered exact bytes after power correction but failed timing.
The arbitration retry correction was exercised in v1.1.18; the periodic TX test failed with an ESP-IDF TWAI assertion/reset. See docs/RELEASE_STATUS.md before further transmission tests. Follow the root
docs/firmware/CAN_TX_GUIDE.md: verify exact image/hash, supplies, bitrate and ACK;
OFF baseline with no duplicate source; 10 s ON with exact IDs/DLC/bytes;
mean periods within 5% of 100/10 ms, max below twice period, no new failures;
OFF plus 300 ms grace and 3 s without either ID. Exercise actual GUI controls,
verify RX/ADC persistence, reboot default OFF and MQTT disconnect stopping TX.
Reconnect must not re-enable it. Leave OFF and release COM. Diagnostic success
is a separate unresolved check; no BMS programming/erase/reset belongs here.

## OTA acceptance

- USB migration preserves provisioned NVS; OTA slots and rollback bootloader match the package.
- Upload valid BIN and Intel HEX; verify chip version, boot ID and exact image hash after reboot.
- Update in both slot directions; verify existing ADC/CAN/control/diagnostic behavior afterward.
- Reject corrupt, wrong-chip, oversized, merged, legacy, stale and unauthorized uploads/requests.
- Reject OTA while GPIO outputs, periodic CAN or diagnostic sessions are active.
- Interrupt Wi-Fi and power mid-transfer: old image boots, maintenance gates release, retry succeeds.
- Force new-image startup failure: rollback selects prior firmware and GUI never reports success.
- Measure heap/stack margins and CAN/ADC gaps during transfer; document observed limits.

20 November bench results: see `output/testing/ota-hardware-validation-20261120.json` and
`docs/RELEASE_STATUS.md`. BIN/HEX, both slots, invalid-file/permission checks,
incomplete-transfer recovery, active-CAN rejection and reset-before-confirmation
rollback were exercised. Physical power cuts and long-duration/electrical tests
remain separate acceptance items; do not mark the entire checklist complete.
