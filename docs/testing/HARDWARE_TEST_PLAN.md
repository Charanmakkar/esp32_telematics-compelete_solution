# Hardware acceptance checklist

Host compilation and simulated telemetry cannot establish physical ADC accuracy,
RF reconnection behavior, output voltage or firmware endurance. Run this checklist
on the identified ESP32S-WROOM after provisioning. Record board revision, ESP-IDF
version, wiring, calibration source, instrument and test duration.

1. Confirm six sensor inputs connect in order to GPIO32, 33, 34, 35, 36, 39 and
   share ground. Leave ADC2 unused. Keep signals inside the calibrated ADC range;
   attenuation does not make an input 5 V tolerant.
2. Connect A's LED through a suitable resistor to GPIO25; observe GPIO26 as B
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

These hardware checks are pending until a board, wiring and serial port are
available. See integration-results.json for the separately measured host path.
