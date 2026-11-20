import hashlib
import json
import struct
from time import monotonic
from uuid import uuid4

import pytest
from conftest import wait_for

from app.services.ota_image import PROTOCOL_MARKER, inspect_image, intel_hex


def image(version="9.0.1"):
    header = bytearray(24)
    header[0:2] = bytes([0xE9, 1])
    header[23] = 1
    segment = bytearray(256)
    segment[0:4] = bytes.fromhex("3254cdab")
    segment[16 : 16 + len(version)] = version.encode()
    segment[48:57] = b"firmware\0"
    segment.extend(PROTOCOL_MARKER)
    segment.extend(bytes(1800))
    data = header + struct.pack("<II", 0x3F400020, len(segment)) + segment
    checksum = 0xEF
    for value in segment:
        checksum ^= value
    data.extend(bytes(15 - len(data) % 16))
    data.append(checksum)
    return bytes(data) + hashlib.sha256(data).digest()


def record(kind, address, data=b""):
    raw = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
    return ":" + (raw + bytes([-sum(raw) & 255])).hex() + "\n"


def as_hex(data, origin=0x10000):
    result = record(4, 0, (origin >> 16).to_bytes(2, "big"))
    for offset in range(0, len(data), 32):
        result += record(0, offset, data[offset : offset + 32])
    return (result + record(1, 0)).encode()


def test_bin_and_hex_match():
    data = image()
    assert inspect_image("app.bin", data)[0] == data
    assert inspect_image("app.hex", as_hex(data))[0] == data
    assert inspect_image("app.bin", data)[1]["image_sha256"] == data[-32:].hex()


@pytest.mark.parametrize("damage", ["hash", "chip", "truncated", "merged", "legacy"])
def test_reject_invalid_images(damage):
    data = bytearray(image())
    if damage == "hash":
        data[-1] ^= 1
    elif damage == "chip":
        data[12] = 9
    elif damage == "truncated":
        data = data[:100]
    elif damage == "merged":
        data = bytearray(65536) + data
    else:
        data = data.replace(PROTOCOL_MARKER, bytes(len(PROTOCOL_MARKER)))
    with pytest.raises(ValueError):
        inspect_image("app.bin", bytes(data))


def test_hex_rejects_overlap_gap_bad_checksum_and_bad_origin():
    for content in (
        record(0, 0, b"ab") + record(0, 1, b"bc") + record(1, 0),
        record(0, 0, b"ab") + record(0, 4, b"bc") + record(1, 0),
        ":02000000616200\n:00000001ff\n",
        record(0, 0x1000, b"ab") + record(1, 0),
    ):
        with pytest.raises(ValueError):
            intel_hex(content.encode())


def chip(**values):
    return {
        "protocol": 1,
        "source": "hardware",
        "version": "1.1.9",
        "build": "abcd",
        "boot_id": str(uuid4()),
        "image_sha256": "a" * 64,
        "confirmed": True,
        "slot_size": 0x1F0000,
        "state": "idle",
        **values,
    }


def test_upload_requires_auth_csrf_and_changed_password(application, logged_in):
    app, client = logged_in
    response = client.post(
        "/api/v1/ota/image?device_id=ESP32_001&filename=app.bin", content=image()
    )
    assert response.status_code == 403
    client.headers.pop("X-CSRF-Token")
    assert (
        client.post(
            "/api/v1/ota/start", json={"device_id": "ESP32_001", "upload_id": str(uuid4())}
        ).status_code
        == 403
    )


def test_prepare_and_reject_legacy_device(admin):
    app, client = admin
    response = client.post(
        "/api/v1/ota/image?device_id=ESP32_001&filename=app.hex", content=as_hex(image())
    )
    assert response.status_code == 200
    assert (
        client.post(
            "/api/v1/ota/start",
            json={"device_id": "ESP32_001", "upload_id": response.json()["upload_id"]},
        ).status_code
        == 409
    )


@pytest.mark.parametrize("chunk_size", [None, 2048])
def test_transfer_requires_new_boot_matching_hash_and_health(admin, chunk_size):
    app, _ = admin
    service = app.state.runtime.ota
    app.state.runtime.mqtt.connected = True
    old = chip(**({"max_chunk_bytes": chunk_size} if chunk_size else {}))
    service.receive("navsphere/ESP32_001/ota/status", json.dumps(old))
    prepared = service.prepare("ESP32_001", "app.bin", image())
    received = bytearray()
    chunk_lengths = []

    def publish(device, packet):
        if packet["op"] == "chunk":
            assert packet["offset"] == len(received)
            chunk_lengths.append(len(bytes.fromhex(packet["data"])))
            received.extend(bytes.fromhex(packet["data"]))
        service.receive(
            f"navsphere/{device}/ota/response",
            json.dumps(
                {
                    "protocol": 1,
                    "source": "hardware",
                    "id": packet["id"],
                    "boot_id": packet["boot_id"],
                    "op": packet["op"],
                    "offset": packet.get("offset", 0),
                    "ok": True,
                }
            ),
        )
        if packet["op"] == "finish":
            assert bytes(received) == image()
            matching = {
                **old,
                "version": prepared["version"],
                "image_sha256": prepared["image_sha256"],
            }
            service.receive(f"navsphere/{device}/ota/status", json.dumps(matching))
            assert service.job["state"] == "rebooting"  # same boot cannot confirm
            matching.update(boot_id=str(uuid4()), confirmed=False)
            service.receive(f"navsphere/{device}/ota/status", json.dumps(matching))
            assert service.job["state"] == "rebooting"
            matching["confirmed"] = True
            service.receive(f"navsphere/{device}/ota/status", json.dumps(matching))
        return True

    app.state.runtime.mqtt.publish_ota = publish
    service.begin("ESP32_001", prepared["upload_id"], "admin")
    wait_for(lambda: service.job["state"] == "confirmed")
    service.worker.join(2)
    assert service.job["progress"] == 100
    assert chunk_lengths[0] == (chunk_size or 768)
    assert max(chunk_lengths) <= (chunk_size or 768)


def test_stale_retained_and_wrong_hash_never_confirm(admin):
    app, _ = admin
    service = app.state.runtime.ota
    app.state.runtime.mqtt.connected = True
    status = chip()
    assert not service.enqueue("navsphere/ESP32_001/ota/status", json.dumps(status).encode(), True)
    service.devices["ESP32_001"] = (monotonic() - 10, status)
    assert not service.snapshot("ESP32_001")["fresh"]
    service.job = {
        "device_id": "ESP32_001",
        "state": "rebooting",
        "boot_id": str(uuid4()),
        "image": {"image_sha256": "b" * 64, "version": "2"},
    }
    service.receive("navsphere/ESP32_001/ota/status", json.dumps(status))
    assert service.job["state"] == "failed"


def test_disconnect_does_not_report_success(admin):
    app, _ = admin
    service = app.state.runtime.ota
    app.state.runtime.mqtt.connected = True
    service.receive("navsphere/ESP32_001/ota/status", json.dumps(chip()))
    info = service.prepare("ESP32_001", "app.bin", image())
    app.state.runtime.mqtt.publish_ota = lambda *_: False
    service.begin("ESP32_001", info["upload_id"], "admin")
    wait_for(lambda: service.job["state"] == "failed")


def test_device_rejection_at_finish_is_failure_not_unconfirmed(admin):
    app, _ = admin
    service = app.state.runtime.ota
    app.state.runtime.mqtt.connected = True
    service.receive("navsphere/ESP32_001/ota/status", json.dumps(chip()))
    info = service.prepare("ESP32_001", "app.bin", image())

    def publish(device, packet):
        service.receive(
            f"navsphere/{device}/ota/response",
            json.dumps(
                {
                    "protocol": 1,
                    "source": "hardware",
                    "id": packet["id"],
                    "boot_id": packet["boot_id"],
                    "op": packet["op"],
                    "offset": packet.get("offset", 0),
                    "ok": packet["op"] != "finish",
                    "error": "Image validation failed",
                }
            ),
        )
        return True

    app.state.runtime.mqtt.publish_ota = publish
    service.begin("ESP32_001", info["upload_id"], "admin")
    wait_for(lambda: service.job["state"] == "failed")
    assert service.job["message"] == "Image validation failed"


def test_network_status_and_upload_limits(admin):
    app, client = admin
    status = chip(ip_address="192.168.10.60", wifi_rssi_dbm=-63, uptime_ms=5408000, mqtt_tls=False)
    app.state.runtime.ota.receive("navsphere/ESP32_001/ota/status", json.dumps(status))
    response = client.get("/api/v1/ota").json()
    assert response["chip"]["ip_address"] == "192.168.10.60"
    assert response["chip"]["wifi_rssi_dbm"] == -63
    assert response["chip"]["uptime_ms"] == 5408000
    assert response["limits"]["max_application_bytes"] == 1984 * 1024
    assert response["transport"]["server_mqtt_tls"] is False


@pytest.mark.parametrize(
    "invalid",
    [
        {"ip_address": "not-an-ip"},
        {"wifi_rssi_dbm": True},
        {"wifi_rssi_dbm": -200},
        {"uptime_ms": -1},
        {"uptime_ms": 1.5},
        {"mqtt_tls": "false"},
        {"max_chunk_bytes": True},
        {"max_chunk_bytes": "2048"},
        {"max_chunk_bytes": 767},
        {"max_chunk_bytes": 2049},
    ],
)
def test_invalid_network_status_rejected(admin, invalid):
    app, _ = admin
    with pytest.raises(ValueError):
        app.state.runtime.ota.receive("navsphere/ESP32_001/ota/status", json.dumps(chip(**invalid)))


def test_start_deadline_allows_small_server_chip_clock_skew(admin, monkeypatch):
    app, _ = admin
    service = app.state.runtime.ota
    app.state.runtime.mqtt.connected = True
    service.receive("navsphere/ESP32_001/ota/status", json.dumps(chip()))
    info = service.prepare("ESP32_001", "app.bin", image())
    monkeypatch.setattr("app.services.ota_service.time", lambda: 1800000000)
    packets = []

    def publish(device, packet):
        packets.append(packet)
        return False

    app.state.runtime.mqtt.publish_ota = publish
    service.begin("ESP32_001", info["upload_id"], "admin")
    service.worker.join(2)
    expiry = packets[0]["expires_at_ms"]
    for skew in (-1000, 0, 1000):
        chip_now = 1800000000000 + skew
        assert 0 < expiry - chip_now <= 30000
