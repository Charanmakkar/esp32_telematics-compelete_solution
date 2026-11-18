# CAN capture and dashboard

The CAN feature is additive. Analog acquisition, existing MQTT telemetry,
GPIO2/GPIO0 controls and their existing pages are unchanged.

## Wiring and firmware

Classic CAN at 500 kbit/s, ESP32 GPIO25 to transceiver TXD, GPIO26 from RXD.
Use a common ground, CANH/CANL on the bus, and correct end-of-bus termination.
The TJA1042 must be in normal transceiver mode (STB LOW). Its logic interface
must be 3.3 V compatible: use a VIO variant supplied at 3.3 V or appropriate
level translation; a plain 5 V RXD must not drive an ESP32 pin.
See [NXP TJA1042 data sheet](https://www.nxp.com/docs/en/data-sheet/TJA1042.pdf).

The ESP32 TWAI controller runs in LISTEN_ONLY with an accept-all filter for
11-bit standard and 29-bit extended IDs, including remote requests. It sends
no CAN data or acknowledgements. Other active nodes must acknowledge traffic.
CAN FD is not supported by the classic ESP32 controller. The installed IDF 6.0.2
HAL includes the ESP32 listen-only dominant-error-bit erratum workaround.
The compatible legacy TWAI API is used with its deprecation warning suppressed.
See [Espressif TWAI documentation](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32/api-reference/peripherals/twai.html).

Serial console remains at 115200 baud. Each captured frame is queued for a line
containing sequence, hexadecimal ID, STD/EXT, DATA/RTR, DLC and hexadecimal bytes.
RX capture never blocks on serial output. On a busy bus the UART cannot print
every frame at 115200; serial_drops explicitly counts omitted serial lines.

Capture uses a 256-frame TWAI queue, a 256-frame MQTT queue and a separate
64-frame serial queue. Up to 24 frames are batched over QoS1 MQTT, draining queued
bursts immediately and waiting 20 ms when idle.
Offline and overloaded queues/outbox can lose frames; this is not a lossless
or durable offline logger. Monitor RX missed/overruns, queue/publish drops,
serial drops and bus errors on the CAN page. MQTT expiry losses are also
included in the existing aggregate firmware publish-drop diagnostic.
Sustained throughput depends on bus load, UART, Wi-Fi and database speed.

## MQTT and storage

Topic: `navsphere/<device_id>/can`, never retained. Existing device credentials
and device-scoped ACLs apply. Payload version 1 contains device_id, boot_id,
frames and stats. A frame has sequence, uptime_ms, timestamp_ms (0 before SNTP),
can_id (numeric), extended, rtr, dlc and data (hex string; empty for RTR).
The CAN queue/worker is separate from analog ingestion. Batches are limited to
8192 bytes and 24 classic frames, with strict field/range validation.

Alembic revision 0003 adds only `can_frames`, `can_latest` and `can_dbc`.
History deduplicates by device, boot and sequence. Latest rows are separated by
device, numeric ID, standard/extended format and DATA/RTR. Replayed frames do
not overwrite newer sequences from the same boot. Receive timestamps remain
available when the device clock is not synchronized.
CAN history has no automatic purge. Monitor disk use and define a retention
policy before sustained logging; existing analog retention does not delete CAN.

## Dashboard and DBC

Open `/can`. The selected device's latest values refresh every second, with
pagination, age/stale indication, message names, raw bytes, signal values,
units, choice labels and the last 50 stored frames for each ID/format.
Authenticated GET endpoints:

- `/api/v1/can/latest?device_id=ESP32_001&offset=0&limit=100`
- `/api/v1/can/history?device_id=ESP32_001&can_id=291&extended=false&limit=100`
  (use `before_id` from `next_before_id` for older history)

Place multiple `.dbc` files directly in the project's **can_dbc** folder. On
this laptop that is `C:\Users\charanpreet\Documents\ChatGPT\esp32_telematics-compelete_solution\can_dbc`.
The page displays the folder path, each file's status and any decoding conflicts.
It reloads additions, edits and removals within a few seconds; no restart or ESP32
reflash is needed. This library is shared by all devices. Subfolders and links
are not loaded. Limits: 128 files, 2 MiB per file, 32 MiB total, classic CAN only,
unique message ID/format pairs within each file. UTF-8 and Windows-1252 are supported.
An administrator can also select multiple files with **Add DBC files** to save
them into this same folder. Uploading the same filename replaces that file.
The files stay local and are ignored by Git.

DBC handling uses
[cantools](https://cantools.readthedocs.io/en/latest/), including signed signals,
Intel/Motorola byte order, scaling/offset, units, enums and multiplexing.
If multiple files define the same ID and format, that ID shows **DBC conflict**
with the filenames. Move unused definitions outside the folder to resolve it.
Other IDs continue decoding; an invalid file is reported without preventing valid
files from loading. Decode uses the current library, including stored latest frames;
raw history is never rewritten. Unknown IDs, RTR and invalid-length payloads
are displayed explicitly rather than inventing signal values.

POST `/api/v1/can/dbc/files` accepts JSON with filename and content, requires an
admin session and X-CSRF-Token, and bounds the streamed request body. Invalid
upload replacements leave the existing file intact. Existing clients can still
use `/api/v1/can/dbc?device_id=ESP32_001` for the legacy 512 KiB database-backed
per-device DBC. That is used only when the project folder contains no DBC files.

## Office network access

The frontend must listen on `0.0.0.0:5173` (the start script's default).
On another PC use `http://192.168.9.253:5173/can` for this laptop's Ethernet
address, or `http://192.168.9.59:5173/can` for Wi-Fi. Use the explicit HTTP scheme
and port; `localhost` on another PC refers to that PC. These DHCP addresses may change.
The backend stays on loopback and is reached through the frontend proxy.

`scripts/enable_office_access.ps1`, run as administrator, enables inbound TCP
5173 and 1883 from LocalSubnet on Ethernet and Wi-Fi. Keep each frontend URL in
`FRONTEND_ORIGINS` in `backend/.env` for login, protected actions and WebSockets,
then restart the backend. Clients on isolated office Wi-Fi or a different VLAN
may require an office-network rule; opening the laptop firewall cannot override
network isolation. Check the remote PC's IP/subnet if both addresses fail.

## Install and verify

Install backend requirements, run `alembic upgrade head` from backend, and
restart the broker/backend/frontend to load the updated ACL and subscription.
Build with `firmware/tools/build.ps1` and flash the firmware, retaining NVS.
Use `scripts/test_system.ps1 -Firmware` for regressions and CAN software tests.
An actual powered CAN bus with at least two active communicating nodes is
required to verify the physical receive path. Software-generated fixtures are
not evidence of hardware reception.
