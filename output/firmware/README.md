# Compiled ESP32S-WROOM firmware

Built with ESP-IDF 6.0.2 for classic `esp32`, six ADC1 inputs, ControlA on
GPIO2 and ControlB on GPIO0. CAN uses GPIO25 TX / GPIO26 RX at 500 kbit/s.
It starts in listen-only; BMS diagnostics temporarily enable transmission.
`manifest.json` records offsets, sizes and SHA256 hashes. This is the
development configuration:4MB flash, DIO40MHz, default navsphere topic prefix,
plaintext MQTT permitted for trusted development. Verify the actual module's
flash capacity and wiring before writing it. Production needs its own TLS and
device-security configuration build.

No Wi-Fi/MQTT credentials or NVS image are included. Provision the separate
private NVS image using `firmware/tools/provision_nvs.py` for a new board.
Keep existing provisioned NVS when updating an already configured board.
The manifest records whether this exact build was flashed and verified.
Flash verification does not establish successful physical CAN/BMS operation;
see `docs/development/BE_CLIENT_IMPLEMENTATION.md` for the live test results.

From an IDF terminal in this directory, after selecting the actual COM port:

```powershell
python -m esptool --chip esp32 --port COMx --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x1000 bootloader.bin 0x8000 partition-table.bin 0x10000 navsphere.bin
```

Back up any existing NVS before explicitly writing the provisioned image at
0x9000. Use the full firmware specification and physical hardware test plan
before interpreting readings or connecting output loads.

At 115200 baud the terminal prints every received CAN frame as `CAN seq=...`
with ID, DLC and data. `CAN_BUILD` identifies the running build at startup;
`CAN_STATUS` prints counters every five seconds, including when no frames
arrive. The separate `resources: ... publish_drops=...` line describes
analog/MQTT delivery, not CAN reception.

`manifest.json` contains the authoritative SW_VERSION and source build ID for
this package. Rebuilding after source changes
automatically advances the patch version in both firmware and GUI; unchanged
reflashes retain it. The dashboard compares its version with the connected
ESP32's actual MQTT report. See the project README for the release workflow.
