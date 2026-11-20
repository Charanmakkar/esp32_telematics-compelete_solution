# Compiled ESP32S-WROOM firmware

Updated 20 November 2026 for **v1.1.22 / 1e17f3d0dbcc**. File-selection feedback is fixed and the rebuilt firmware passed live GUI upload validation. The connected chip reported v1.1.21; this new image has not been flashed. See `docs/RELEASE_STATUS.md` for evidence and limitations.

Built with ESP-IDF 6.0.2 for classic `esp32`, six ADC1 inputs, ControlA on
GPIO2 and ControlB on GPIO0. CAN uses GPIO25 TX / GPIO26 RX at 500 kbit/s.
It starts in listen-only; diagnostics or periodic ON temporarily enable transmission, with mutually exclusive ownership.
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

For the initial installation only, from an IDF terminal in this directory after
selecting the actual COM port (prefer the backup-and-migration helper below):

```powershell
python -m esptool --chip esp32 --port COMx --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x1000 bootloader.bin 0x8000 partition-table.bin 0x10000 navsphere.bin 0x3F0000 ota_data_initial.bin
```

Back up any existing NVS before explicitly writing the provisioned image at
0x9000. Use the full firmware specification and physical hardware test plan
before interpreting readings or connecting output loads.
The command above initializes OTA metadata. Do not use it for routine application
updates on an OTA-enabled board; use the OTA page instead.

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

## Existing provisioned board: first OTA installation

From the repository root, close monitors and use the detected port:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/migrate_ota.ps1 -Port COMx
```

The helper backs up flash and preserves NVS while installing the OTA layout.
Use `manifest.json` for the current application SHA-256 and release identity.
Future updates use /ota; writing only 0x10000 cannot select the active OTA slot.
The manifest records this new image as built and upload-validated, not yet hardware flashed. The periodic frames are 0x014/006000/100ms and
0x548/0000000000000008/10ms, switched together on /can. See the root
docs/firmware/CAN_TX_GUIDE.md for operation and pending acceptance.

## Wi-Fi OTA update

Open **Manage → OTA over Wi-Fi** (`/ota`) to upload an application BIN/Intel HEX,
review its target version and update the ESP32 through the existing MQTT connection.
The page reports the actual running chip version and image SHA-256; success requires
a new confirmed boot with the uploaded fingerprint. See the [OTA guide](../../docs/firmware/OTA_GUIDE.md)
for accepted files, permissions, recovery and the required initial USB migration.

The packaged firmware now uses two OTA slots. Earlier factory-only flashing
commands in this guide are historical: use `scripts/migrate_ota.ps1` for the first
installation. Future application updates use the OTA page. Never erase NVS.
