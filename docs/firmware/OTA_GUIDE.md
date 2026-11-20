# Wi-Fi firmware updates

The OTA page is `/ota` (Manage → OTA over Wi-Fi). The browser uploads a file to
the existing backend; the backend transfers it through the existing MQTT broker
over the ESP32's Wi-Fi connection. No additional listener or device IP is needed.
ADC, CAN receive, GPIO and diagnostic implementations retain their existing
behavior outside an update. Flash writes can delay acquisition; reboot creates
a telemetry gap. Schedule updates while measurement interruptions are acceptable.

## Initial installation on an existing board

The old factory-only partition layout cannot receive OTA. A USB migration is
required once. Connect the actual ESP32, close serial monitors, turn A/B and
periodic CAN transmission OFF, and close BMS diagnostic sessions. GPIO0/2 retain
their existing boot-strapping requirements. From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/migrate_ota.ps1 -Port COMx
```

Replace COMx with the connected port. This checks packaged file hashes, backs up
all flash to private `.runtime/ota-backups/`, then writes the bootloader,
partition table, application and initial OTA metadata. The backup includes
credentials; keep it private. NVS at 0x9000 (0x6000 bytes) and PHY at 0xF000
are preserved. Do not erase the whole flash or reprovision Wi-Fi credentials.
The former 0x10000 app-only command is insufficient for this initial migration.

The new 4 MiB layout:

| Region | Offset | Size |
|---|---|---|
| NVS | 0x9000 | 0x6000 |
| PHY | 0xF000 | 0x1000 |
| OTA slot 0 | 0x10000 | 0x1F0000 (1984 KiB) |
| OTA slot 1 | 0x200000 | 0x1F0000 (1984 KiB) |
| OTA metadata | 0x3F0000 | 0x2000 |

Both root and standalone builds use the same partition CSV and enable
`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`. For an existing independently edited
SDK configuration, check that option in menuconfig before building. Routine OTA
updates write only the inactive app slot. Partition, bootloader, NVS, and eFuse
updates are not exposed through the web page.

Restart the backend and reload/restart the broker to pick up the new OTA ACL
entries. Rebuild/reload the GUI. Restarting the broker briefly interrupts other
MQTT operations, so do this while the device is idle. The native generated broker
configuration points to `mqtt/acl.example`; copy the additional rules to any
separately managed broker, using your configured topic prefix.

## Install from the GUI

1. Select the intended device and open **OTA over Wi-Fi**. Wait for a live report.
2. Sign in as an administrator with a changed initial password.
3. Select or drag one NavSphere application `.bin`, or an Intel HEX file containing that
   application alone. Review the extracted target version, size and fingerprint.
4. Turn GPIO controls and periodic CAN transmission OFF and close diagnostics.
   The chip independently checks these conditions. It rejects an update if busy;
   it does not forcibly stop an active operation to start flashing.
5. Acknowledge the reboot notice and select **Install firmware over Wi-Fi**.
6. Wait for **Update confirmed by chip**. A 100% transfer alone is not success.

Allow several minutes on a weak or busy Wi-Fi link. The 20 November bench BIN
test with negotiated 2 KiB chunks took about 5 minutes 6 seconds for the roughly
1 MiB application, including startup confirmation (the earlier 768-byte run took
about 10 minutes 49 seconds). These are observed network results, not guaranteed speeds.
Keep the server and board powered for the full transfer and reboot check.

The running version comes from `esp_app_get_description()` on the chip. Its
image fingerprint comes from `esp_partition_get_sha256()` for the running
partition. Confirmation requires a new boot ID, matching version and image
fingerprint, plus successful startup validation. The uploaded file's version and
the GUI build are displayed separately. Stale reports are labelled last seen.
The existing GUI/firmware version strip remains available on every page.
Because that existing strip also uses CAN reports, it can become stale while
CAN uploads are paused for OTA. Use the OTA page's independent live chip report
and update result during the transfer; CAN reports resume afterward.

The four summary cards display the installed version, station IP address, Wi-Fi
signal in dBm and uptime reported by the chip. Older OTA builds omit network
fields and show **Not reported**; stale values are explicitly labelled. The
page shows the 1984 KiB application limit and 6 MiB upload limit before selection,
plus an upload guide. HEX conversion remains on the server, where both file
formats receive the same validation.

## If a BIN file does not load

Use `output/firmware/navsphere.bin` from the current release. The standalone
build writes `firmware/build/firmware.bin`; the root build writes
`build/firmware.bin`. These are separate build directories: rebuilding one does
not refresh the other. Confirm the target version displayed after selection.

The 20 November file-loading issue was caused by an old pre-OTA application in
`firmware/build/firmware.bin`. It was selected successfully but rejected because
installing it would remove OTA support. That directory has now been rebuilt.
The page keeps the selected filename visible and displays validation errors
beside the picker. A rejected selection hides the previous target metadata and
blocks installing an older staged file. Reopening the picker allows the same
filename to be selected again after rebuilding it.

Refresh the page, select the newly rebuilt application file and wait for
**File accepted** and the target version. Then acknowledge the maintenance
notice and install. If the chip already runs that exact image, the server
rejects a redundant installation. Do not select `bootloader.bin`, a partition
table, or a full-flash bundle.

## Accepted files

Use `output/firmware/navsphere.bin` from an OTA-enabled release. Both formats are
validated for classic ESP32, application descriptor/project, segment bounds,
checksum, appended SHA-256, slot size and the OTA protocol marker. The file must
contain OTA support so installing old firmware cannot silently remove the feature.
Same-image updates are rejected; different compatible images may be installed
even when they have the same human-readable version.

Intel HEX records require correct checksums, EOF and contiguous, non-overlapping
app data. Origins 0, 0x10000 and 0x200000 are accepted; the source address is
discarded and the chip chooses its inactive slot. Merged flash dumps, bootloader
files, partition tables, encrypted/signed bundles, other ESP families, and legacy
images without OTA are rejected. The upload limit is 6 MiB, decoded app limit
1984 KiB. Uploads expire after ten minutes and are held only in backend memory.

## Failure handling and security

The transfer uses non-retained, boot-bound MQTT requests, negotiated chunks and
per-chunk acknowledgements with bounded retries. Duplicate chunks are checked
against flash rather than written twice. A 30-second inactivity timeout or MQTT
loss aborts an incomplete transfer and releases the maintenance locks. Whole-file
SHA-256 and ESP-IDF image validation must pass before changing the boot target.
New firmware reports `max_chunk_bytes: 2048`; the server uses that capacity to
reduce acknowledgement round trips. Earlier OTA firmware continues to receive
768-byte chunks. This is compatible in both directions and does not change the
existing telemetry, GPIO or diagnostic payloads.
Allow at least 6 KiB per MQTT packet when using the larger chunks; the supplied
broker configuration already permits 12 KiB message payloads. The bounded OTA
worker uses a 16 KiB stack and two 4400-byte receive queue entries.
The server requests a 15-second start deadline, leaving clock-skew margin below
the chip's 30-second maximum. Both clocks must still be synchronized.

During an accepted update, GPIO commands are rejected with
`firmware_update_in_progress`; CAN normal-mode acquisition is blocked. Existing
ADC telemetry and passive CAN capture remain enabled, subject to flash-write
delays. Large CAN MQTT batches pause only while OTA owns the maintenance lock,
reserving network capacity for update acknowledgements; the existing CAN publish
drop counter records skipped batches. CAN uploads resume on abort or after reboot.
Wi-Fi modem sleep is temporarily disabled during an accepted transfer to reduce
per-chunk acknowledgement latency; abort restores the previous power policy and
reboot starts with the normal policy. This increases radio activity during OTA only.
The new boot must initialize the application successfully and stay MQTT-connected
for ten seconds before being marked valid. After 120 seconds without validation,
it requests rollback. Reset/crash before validation also enables bootloader
rollback. USB recovery remains necessary for partition/bootloader corruption or
hardware/network faults that also affect the previous application.

The backend waits up to 180 seconds for a new confirmed boot. Missing confirmation
is shown as **unconfirmed**, never success; a later matching live report can
resolve it. A different image after reboot is reported as failure/possible rollback.
Backend restart loses staged files and in-memory job progress; do not restart
during an update. Start/result metadata is recorded in the existing audit log.

Upload/start require the existing session, admin role, password-change gate and
CSRF token. Broker ACLs restrict request publication to the backend and scope
device responses to its username. This uses the existing MQTT transport security:
trusted LAN development may use the current plaintext broker; production requires
MQTT TLS and HTTPS for the browser. Hash checks detect corruption, not publisher
identity. This change does not provision signing keys, secure boot or eFuses.

The connection-security panel reports browser HTTPS/HTTP, configured server MQTT
TLS and chip-reported MQTT TLS independently. No second OTA password is introduced:
the existing changed-password administrator session authorizes uploads and starts.

## API and MQTT additions

- `GET /api/v1/ota?device_id=...`: live chip state, staged image, current job,
  `limits.max_application_bytes`, `limits.max_upload_bytes` and
  `transport.server_mqtt_tls`. Optional chip fields are `ip_address`,
  `wifi_rssi_dbm`, `uptime_ms`, `mqtt_tls` and `max_chunk_bytes` (absent on earlier OTA firmware).
- `POST /api/v1/ota/image?device_id=...&filename=...`: raw octet-stream upload;
  validates only, returns `upload_id` and extracted metadata.
- `POST /api/v1/ota/start`: JSON `{ "device_id": "ESP32_001", "upload_id": "..." }`.
- MQTT `{prefix}/{device}/ota/request`: start/chunk/finish, QoS 1, never retained.
- MQTT `{prefix}/{device}/ota/response`: correlated ACK/rejection.
- MQTT `{prefix}/{device}/ota/status`: live heartbeat every two seconds.

The API does not change existing telemetry, control, CAN or diagnostic schemas.
No database schema migration is required.

## Hardware acceptance before field use

Verify the USB migration, preserved NVS credentials, chip identity, BIN and HEX
updates in both slot directions, wrong-file rejection, active-control rejection,
Wi-Fi loss, power loss during transfer, and rollback after a failed startup.
Check that CAN/ADC reporting resumes and existing controls/diagnostics still work.
Measure capture delays and heap/stack margin on the actual board during transfer.
Software tests and compilation alone do not establish these hardware properties.

Reference: [Espressif OTA and rollback documentation](https://docs.espressif.com/projects/esp-idf/en/v6.0.2/esp32/api-reference/system/ota.html).
