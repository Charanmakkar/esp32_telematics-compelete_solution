# NavSphere API reference

Updated 20 November 2026 for application v1.1.22 / 1e17f3d0dbcc. Existing interfaces are retained; OTA routes are additive.

All URLs are relative to the configured backend. Production uses HTTPS. The final hardware requirement is **six** channels, GPIO32, GPIO33, GPIO34, GPIO35, GPIO36, GPIO39 in that order. No external acquisition hardware is used.

## Authentication

- `POST /api/v1/auth/login` JSON `{ "username": "admin", "password": "admin" }` creates the development session. These credentials only seed a missing account in development. The password is hashed with scrypt.
- Login, `GET /api/v1/auth/me`, and `POST /api/v1/auth/password` return `{ "user": { "username": "admin", "role": "admin", "must_change_password": true }, "csrf_token": "..." }`.
- Send the HttpOnly `navsphere_session` cookie (`credentials: "include"` in fetch) and header `X-CSRF-Token` for every mutation after login.
- `POST /api/v1/auth/password`: `{ "current_password": "admin", "new_password": "a new password of at least 12 characters" }`. Password changes revoke other sessions. Commands are forbidden until the first password change.
- `POST /api/v1/auth/logout` revokes the session; no JSON body needed. Sessions expire after the configured TTL. At most ten sessions per account are retained.
- Login is limited to ten attempts per client IP per minute in the single backend process. Do not trust arbitrary proxy headers; terminate the service behind a correctly configured trusted reverse proxy in production.

Swagger `/docs` includes a header input for CSRF on each authenticated mutation. Execute login, copy the returned token, and enter it on password/logout/commands. The browser sends the session cookie automatically. `/redoc` and `/openapi.json` describe REST schemas; the MQTT schema is also available as `MqttTelemetry` in OpenAPI components.

## Telemetry and device APIs

- `GET /api/v1/devices` returns `{ "devices": [{ "device_id", "online", "last_seen", "source", "boot_id", "controls": { "A": null, "B": null }, "mapping": [{ "channel": "analog_1", "label": "Analog 1", "physical": "GPIO32 / ADC1" }] }] }`. The mapping contains six entries. `controls` are nullable until a verified state is known; stale/offline devices show null controls.
- `GET /api/v1/devices/{device_id}/status` returns one device object. `online` requires recent telemetry and no explicit offline announcement.
- `GET /api/v1/telemetry/latest?device_id=ESP32_001` returns `{ "received": reading|null, "persisted": reading|null }`. Reading contains all MQTT fields below plus `id`, `received_at` and `persisted_at`. A received event has no database ID or persistence time. Persisted values are loaded from the database, including after a server restart.
- `GET /api/v1/telemetry/history?device_id=ESP32_001&start_ms=...&end_ms=...&limit=600` returns `{ "points": [{ "timestamp_ms": 1790000000000, "channels": { "analog_1": 1200 } }], "statistics": { "analog_1": { "min": 1100, "max": 1300, "avg": 1200, "count": 20 } }, "count": 20, "aggregated": false, "time_basis": "device_epoch_or_server_receive" }`. Each ordinary history point has all six channels. Invalid channel values are null and excluded from statistics. An unsynchronized sample uses server receive time on the history axis.
- `GET /api/v1/telemetry/channels/{channel_id}` has the same parameters/shape, restricted to one channel. IDs accept `1` through `6`, `analog-1` through `analog-6`, or `analog_1` through `analog_6`.
- History defaults to five minutes. The query window is at most 31 days and `limit` is 2Ã¢â‚¬â€œ2000. Larger result sets are averaged in SQL time buckets; min/max/average statistics still cover all valid rows in the requested range. CSV exports made by the dashboard contain the returned points and may therefore be aggregated.
- `GET /api/v1/health` returns `status`, `mqtt_connected`, `database_connected`, `database_engine`, and `metrics`: `received`, `persisted`, `invalid`, `duplicates`, `dropped`, `database_errors`, `frequency_hz`, `queue_depth`, `websocket_dropped`, `last_received_at`, `last_persisted_at`. Counters cover the current backend process lifetime; frequency uses recent valid arrivals.
- `GET /api/v1/health/ready` performs a database check and returns HTTP 200 only if both the database and MQTT connection are ready; otherwise HTTP 503.

## Commands

- Admin `POST /api/v1/commands`: `{ "device_id": "ESP32_001", "key": "A", "value": 1 }`. Returns HTTP 202 and a command object: `command_id`, `device_id`, `key`, `value`, `status`, `reason`, `boot_id`, `created_at`, `expires_at`, `updated_at`.
- Status is `pending`, `accepted`, `applied`, `rejected`, or `timed_out`. A successful MQTT publish remains pending. Only the matching, timely, boot-bound device acknowledgement permits applied status.
- `GET /api/v1/commands/{command_id}` returns the command object. `GET /api/v1/commands?device_id=ESP32_001&limit=30` returns `{ "commands": [...] }` newest first; maximum limit 100.
- Commands require the admin role, changed initial password, CSRF token, connected broker, and fresh device. All requests/results are audited. Terminal results cannot regress on duplicate or reordered acknowledgements.
- Command lifetime is configurable from1Ã¢â‚¬â€œ30seconds (default10), matching the supplied firmware/simulator maximum30seconds. If firmware `CONFIG_NAV_COMMAND_MAX_TTL_MS` is reduced, reduce backend `COMMAND_TIMEOUT_SECONDS` accordingly. Output safety leases are separate from command delivery lifetime.

## MQTT v1

Topics: `navsphere/{device_id}/telemetry`, `/command`, `/ack`, `/status`; prefix and allowed device IDs are configurable. Use QoS1. Command, acknowledgement and telemetry messages are not retained. Retained telemetry and acknowledgements are rejected. Broker ACLs and TLS bind each device to its own topics. Payload device IDs must match topic IDs.

```json
{
  "schema_version": 1,
  "device_id": "ESP32_001",
  "boot_id": "a-new-id-each-boot",
  "sequence": 1,
  "timestamp_ms": 1790000000000,
  "time_valid": true,
  "uptime_ms": 100,
  "channels": {"analog_1": 1200, "analog_2": 1300, "analog_3": 1400, "analog_4": 1500, "analog_5": 1600, "analog_6": 1700},
  "raw": [1489, 1613, 1737, 1861, 1985, 2109],
  "valid_mask": 63,
  "mqtt_connected": true,
  "dropped_samples": 0,
  "source": "simulator",
  "stale": false
}
```

Example values are illustrative. Values are millivolts, 0Ã¢â‚¬â€œ5000; raw fields are unsigned16. Firmware may enforce tighter physical voltage limits. Exactly six values are required. Bit0 of `valid_mask` represents channel1; all valid is63. Sequence is unsigned32. Deduplication is unique `(device_id, boot_id, sequence)`, preserving sequence reuse after reboot. If time is unsynchronized, set `time_valid:false` and `timestamp_ms:null`. Synchronized timestamps must be year2000Ã¢â‚¬â€œ2100 and at most five minutes into the future. `stale:true` preserves the original sequence and timestamp, so repeats cannot create new database measurements.

Commands published by the backend:

```json
{"command_id":"550e8400-e29b-41d4-a716-446655440000","key":"A","value":1,"issued_at_ms":1790000000000,"expires_at_ms":1790000010000}
```

Acknowledgements publish accepted then applied, or rejected:

```json
{"command_id":"550e8400-e29b-41d4-a716-446655440000","key":"A","value":1,"status":"applied","reason":"GPIO2 set high","boot_id":"a-new-id-each-boot"}
```

Status example (retained): `{"online":true,"boot_id":"a-new-id-each-boot","controls":{"A":0,"B":0}}`. Configure device Last Will as `{"online":false}`. An online announcement alone does not refresh stale telemetry. Report control states only after the corresponding physical state has been set. Firmware A maps to GPIO2 and B to GPIO0, active high; safe startup/disconnection level is0.

## WebSocket

`/ws/v1/telemetry` authenticates using the same cookie and validates browser Origin. Maximum100 clients; each client has a32-event queue. Slow consumers lose oldest events, counted in metrics. Connections revalidate session revocation/expiry within15seconds.

- `{ "type": "telemetry", "stage": "received", "data": reading }`
- `{ "type": "telemetry", "stage": "persisted", "data": reading }`
- `{ "type": "command", "data": command }`
- `{ "type": "heartbeat", "health": health }` during idle periods.

Reconnect with bounded backoff, then retrieve latest/history to fill gaps. WebSocket delivery is a live view, not a durable event log.

Errors use FastAPI `{ "detail": "message" }`, or a validation error list. Typical statuses:401 unauthenticated,403 role/CSRF/password restriction,404 unknown device/channel/command,409 stale device,422 invalid input/range,429 login limit,503 dependency unavailable.

## CAN, DBC and statistics APIs (v1.1.8)

GET routes require a session; DBC writes require admin and CSRF.

| Route | Parameters and behavior |
|---|---|
| GET /api/v1/can/latest | device_id; offset 0..1000000; limit 1..500 (100 default); current_boot_only (API false, GUI true); search up to 128 chars. Returns frames, has_more, dbc/library, status, current_boot_id, server_time and metrics |
| GET /api/v1/can/history | device_id; optional numeric can_id and extended; before_id cursor; limit 1..1000 (100 default). Returns frames and next_before_id |
| GET /api/v1/can/statistics | device_id; bounded process/device statistics and server ingestion metrics |
| POST /api/v1/can/dbc/files | JSON filename/content; project folder file up to 2 MiB; replacement only after valid parse |
| POST /api/v1/can/dbc | Legacy per-device DBC up to 512 KiB; fallback when project folder is empty |

Query can_id is decimal: can_id=20 selects 0x014. Search accepts hex spelling.
History is newest first. The folder library supports 128 files/32 MiB total.

## Periodic CAN control

GET `/api/v1/can/tx?device_id=ESP32_001` returns profiles, supported,
clock_ready, fresh, age_seconds, boot_id, mode and nullable state. Profiles
contain numeric can_id, hex data, dlc and period_ms. State contains enabled,
command_id, reason, sent_014, sent_548, failures and skipped. Reasons are off,
on, connection_lost, transmit_failed and controller_busy_or_unavailable.
Modes include listen_only, diagnostic, periodic_tx and unavailable. Fresh
requires supported status under five seconds old and backend MQTT connected;
clock_ready requires synchronized telemetry matching the CAN boot ID.

POST `/api/v1/can/tx` accepts exactly:

```json
{"device_id":"ESP32_001","enabled":true}
```

Set enabled false for OFF. Numeric/string booleans and extra fields are rejected.
Admin, changed initial password, cookie and X-CSRF-Token are required. ON needs
fresh state, valid clock and idle diagnostics. OFF with known stale state is
best effort. The backend waits up to five seconds for matching device state.
HTTP 200 can still contain enabled=false with a refusal reason: check the state.
409 covers conflicts/unavailability; 504 acknowledgement timeout; 422 validation;
401/403 auth restrictions; unknown-device GET is 404. Only one toggle may wait
for confirmation at a time. Submissions are audited as can_tx_toggle.

The fixed profiles are standard 0x014/006000/100ms and
0x548/0000000000000008/10ms. No arbitrary transmit API exists. Counter/status
state is not a durable per-frame TX log. See docs/firmware/CAN_TX_GUIDE.md from root.

## BMS diagnostics API

Active catalogue: HVBEOSK/be_repo, 55 CDD services and 44 BAT workflows.
ESP32 diagnostic responses remain unverified. GET requires session; all POST
routes require changed-password admin and CSRF.

| Route | Request / result |
|---|---|
| GET /api/v1/bms/catalog | Catalogue and reference status; no keys |
| POST /api/v1/bms/preview | device_id, kind cdd/preset, entry_id, values; optional instance, ecu, session, security, image_filename, image_id, inject_crc; returns preview/token |
| POST /api/v1/bms/jobs | token and confirmation from preview; HTTP 202 job |
| POST /api/v1/bms/read | device_id; command qr/serial/hardware/manufacturing/mode; optional instance and ecu; HTTP 202 job |
| GET /api/v1/bms/jobs | device_id; recent saved jobs |
| GET /api/v1/bms/jobs/{job_id} | optional offset >=0; job and exchanges |
| POST /api/v1/bms/jobs/{job_id}/cancel | Cancel requested job |

Profile abs_hv uses 0x7E4/0x7EC; abs_hv_old uses 0x640/0x650. State-changing
workflows require preview confirmation; Quick reads execute documented preparation.
Turn periodic TX OFF first. See docs/development/BE_CLIENT_IMPLEMENTATION.md.

## CAN and diagnostic MQTT extensions

`navsphere/<device_id>/can` carries non-retained schema-v1 batches, at most 24
classic frames and 8192 bytes at backend, plus CAN stats. Optional software
version, mode and periodic_tx fields preserve earlier firmware compatibility.
`can/tx/request` is backend-write/device-read, QoS1 and never retained. Its exact
five-field schema and TTL rules are in the CAN TX guide; confirmations arrive
in CAN stats, not GPIO ack. Diagnostic transport uses diagnostic/request and
diagnostic/response separately. Existing ADC/GPIO MQTT interfaces remain unchanged.

## Firmware OTA API

`GET /api/v1/ota?device_id=ESP32_001` returns live chip identity, freshness,
prepared image and job state. Authenticated viewers may read it. It also returns
`limits.max_application_bytes` (2031616), `limits.max_upload_bytes` (6291456),
and `transport.server_mqtt_tls`. Optional chip fields `ip_address`,
`wifi_rssi_dbm`, `uptime_ms` and `mqtt_tls` come from the running ESP32;
older OTA firmware can omit them.
`POST /api/v1/ota/image?device_id=ESP32_001&filename=app.bin` accepts a raw
`application/octet-stream` body (6 MiB maximum); BIN or app-only Intel HEX is
validated and staged for ten minutes. It returns `upload_id`, version, size,
whole-file SHA-256 and image SHA-256. `POST /api/v1/ota/start` takes
`{"device_id":"ESP32_001","upload_id":"..."}`. Both POSTs require admin,
changed password, session and CSRF token. Busy/stale/migration-required state
returns 409; invalid image returns 400; oversized upload returns 413.

MQTT adds `{prefix}/{device}/ota/request`, `ota/response`, and `ota/status`.
All are non-retained QoS 1. Requests are start/chunk/finish, bound to a UUID
and boot ID. Start includes size, full-file SHA-256 and a 15-second deadline
(chip maximum 30 seconds, leaving clock-skew margin); chunks contain offset
and up to the chip's optional `max_chunk_bytes` (768â€“2048) encoded as hex.
Absent that field, the server uses the original 768-byte chunks. Responses
echo id/op/offset/boot_id, protocol=1, source=hardware, ok and optional error.
Status contains protocol/source, boot_id, version, build, running image SHA-256,
partition, slot_size, confirmed and state. Success requires a matching image
and new confirmed boot. See docs/firmware/OTA_GUIDE.md for full operation.
