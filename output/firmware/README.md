# Compiled ESP32S-WROOM firmware

Built with ESP-IDF6.0.2 for classic `esp32`, six ADC1 inputs and GPIO25/26
controls. `manifest.json` records offsets, sizes and SHA256 hashes. This is the
development configuration:4MB flash, DIO40MHz, default navsphere topic prefix,
plaintext MQTT permitted for trusted development. Verify the actual module's
flash capacity and wiring before writing it. Production needs its own TLS and
device-security configuration build.

No Wi-Fi/MQTT credentials or NVS image are included. Provision the separate
private NVS image using `firmware/tools/provision_nvs.py`. No physical board
has been flashed or tested by the agent.

From an IDF terminal in this directory, after selecting the actual COM port:

```powershell
python -m esptool --chip esp32 --port COMx write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x1000 bootloader.bin 0x8000 partition-table.bin 0x10000 navsphere.bin
```

Back up any existing NVS before explicitly writing the provisioned image at
0x9000. Use the full firmware specification and physical hardware test plan
before interpreting readings or connecting output loads.
