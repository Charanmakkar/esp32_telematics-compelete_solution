import json
from types import SimpleNamespace

import pytest
from conftest import wait_for

from app.schemas.can import CanBatch
from app.services.bms_catalog import BmsCatalog, decode_fields, encode_fields
from app.services.bms_protocol import (
    decode_preset,
    load_hex,
    preset_request,
    program_image,
    validate_response,
)
from app.services.can_statistics import CanStatistics


def field(**overrides):
    return dict(key="value", name="Value", kind="number", bytes=2, little=False, **overrides)


def test_codec_precision_sign_scale_float_and_variable():
    assert encode_fields([field()], {"value": 4660}) == b"\x12\x34"
    f = field(signed=True)
    f["little"] = True
    assert encode_fields([f], {"value": -2}) == b"\xfe\xff"
    f = field(factor=0.1, offset=-40)
    assert encode_fields([f], {"value": "-39.9"}) == b"\x00\x01"
    f = field()
    f["bytes"] = 8
    assert encode_fields([f], {"value": "18446744073709551615"}) == b"\xff" * 8
    f = field(float=True)
    f["bytes"] = 4
    assert encode_fields([f], {"value": 1.5}) == b"\x3f\xc0\x00\x00"
    rows, warnings = decode_fields([f], b"\x3f\xc0\x00\x00")
    assert rows[0]["value"] == 1.5 and not warnings
    with pytest.raises(ValueError):
        encode_fields([field()], {"value": -1})
    with pytest.raises(ValueError):
        encode_fields([field()], {"value": "NaN"})
    with pytest.raises(ValueError):
        encode_fields([dict(key="value", name="X", kind="hex", bytes=2)], {"value": "AA"})


@pytest.mark.parametrize("response", ["6EF18601", "62F18701", "7F2231", ""])
def test_rejects_negative_and_mismatched_responses(response):
    with pytest.raises(ValueError):
        validate_response(bytes.fromhex("22F186"), bytes.fromhex(response))


def test_source_preset_encoding_and_decoding():
    preset = dict(operation="write", did=0xFD06, default_hex="0101" + "FF" * 23)
    assert preset_request(preset, {}) == bytes.fromhex("2EFD060101" + "FF" * 23)
    preset.update(did=0xF013, default_hex="")
    assert preset_request(preset, {"instance": 15}) == b"\x2e\xf0\x13\x00\x0f"
    for invalid in (0, 16):
        with pytest.raises(ValueError):
            preset_request(preset, {"instance": invalid})
    preset["did"] = 0xFD20
    request = preset_request(
        preset, dict(location="TC", build="0110", date="23202", part="0123456789")
    )
    assert (
        len(request) == 35
        and request[14:16] == b"CT"
        and request[-10:] == bytes([9, 8, 7, 6, 5, 4, 3, 2, 1, 0])
    )
    rows, warnings = decode_preset(
        dict(operation="read", did=0xFD20), b"\x62\xfd\x20" + request[3:]
    )
    assert rows[0]["value"] == "TC" and rows[3]["value"] == "0123456789" and warnings
    rows, _ = decode_preset(dict(operation="read", did=0xFD07), b"\x62\xfd\x07\x0c\xe4\x01")
    assert rows[0]["value"] == 3300 and rows[0]["label"] == "valid"
    assert preset_request(dict(operation="mute", did=None), {}) == b"\x28\x81"


def record(address, kind, data=b""):
    raw = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
    return ":" + (raw + bytes([-sum(raw) & 255])).hex().upper()


def test_hex_validation(tmp_path):
    path = tmp_path / "image.hex"
    text = "\n".join([record(0, 4, b"\x80\x00"), record(0, 0, bytes(range(16))), record(0, 1)])
    path.write_text(text)
    info, segments = load_hex(path)
    assert info["bytes"] == 16 and segments[0][0] == 0x80000000
    for invalid in (
        text.replace("00000001", "00000002"),
        text.replace(record(0, 1), record(0, 0, b"\x00" * 8) + "\n" + record(0, 1)),
        record(1, 0, b"\x00" * 8) + "\n" + record(0, 1),
        record(0, 0, b"\x00" * 8),
    ):
        path.write_text(invalid)
        with pytest.raises(ValueError):
            load_hex(path)


def test_programming_sequence_checks_and_cancellation():
    calls = []

    def exchange(data, timeout=5000):
        calls.append(data)
        if data[0] == 0x31:
            result = b"\x71" + data[1:]
            if data[2:] == b"\xf2\x04":
                return result + b"\x00"
            return result + (
                b"\x01" if data[1] == 1 else b"\x02\x01" if data[2:] == b"\xf2\x01" else b"\x02"
            )
        if data[0] == 0x34:
            return b"\x74\x20\x00\x12"
        if data[0] == 0x36:
            return b"\x76" + data[1:2]
        return b"\x77"

    program_image(exchange, [(0x80000000, bytes(range(32)))], "app", lambda _: None, lambda: False)
    assert calls[:2] == [b"\x31\x01\xf2\x00", b"\x31\x03\xf2\x00"]
    assert [x[1] for x in calls if x[0] == 0x36] == [1, 2]
    assert calls[-1] == b"\x31\x01\xf2\x04" and b"\x37" in calls
    calls.clear()
    with pytest.raises(ValueError, match="Cancelled"):
        program_image(exchange, [(0x80000000, b"\x00" * 16)], "app", lambda _: None, lambda: True)
    assert not any(x[0] in (0x34, 0x36) for x in calls)
    with pytest.raises(ValueError, match="refused"):
        program_image(
            lambda data, **kw: b"\x71" + data[1:] + b"\x00",
            [],
            "app",
            lambda _: None,
            lambda: False,
        )


def test_actual_reference_inventory_when_present():
    catalog = BmsCatalog()
    if catalog.error:
        pytest.skip("Local proprietary reference is not bundled")
    assert len(catalog.services) == 55 and len(catalog.presets) == 44
    assert "security_key" not in json.dumps(catalog.public())
    for entry in catalog.services.values():
        values = {
            f["key"]: "00" * (f["bytes"] or f.get("min_bytes", 0)) if f.get("kind") == "hex" else 0
            for f in entry["request_fields"]
            if "constant" not in f
        }
        raw = encode_fields(entry["request_fields"], values)
        assert raw[0] == entry["sid"]
    assert {p["operation"] for p in catalog.presets.values()} == {
        "read",
        "write",
        "program",
        "erase_app",
        "clear_dtc",
    }


def test_statistics_deduplicate_rates_stale_and_reboot(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.services.can_statistics.monotonic", lambda: clock[0])
    statistics = CanStatistics()

    def batch(seq, uptime, boot="boot1"):
        return CanBatch.model_validate(
            dict(
                schema_version=1,
                device_id="ESP32_001",
                boot_id=boot,
                frames=[
                    dict(
                        sequence=seq,
                        uptime_ms=uptime,
                        timestamp_ms=0,
                        can_id=1,
                        extended=False,
                        rtr=False,
                        dlc=1,
                        data="AA",
                    )
                ],
                stats=dict(
                    queue_drops=0,
                    serial_drops=0,
                    publish_drops=0,
                    rx_missed=0,
                    rx_overruns=0,
                    bus_errors=0,
                    uptime_ms=uptime,
                    rx_total=seq,
                    rx_bytes=seq,
                    wire_bits_min=seq * 55,
                    wire_bits_max=seq * 65,
                ),
            )
        )

    statistics.observe(batch(1, 1000))
    statistics.observe(batch(1, 1000))
    clock[0] = 101
    statistics.observe(batch(3, 2000))
    result = statistics.snapshot("ESP32_001")
    assert result["totals"]["frames"] == 2 and result["hardware_fps"] == 2
    assert result["ids"][0]["mean_interval_ms"] == 1000
    clock[0] = 107
    assert statistics.snapshot("ESP32_001")["hardware_fps"] is None
    statistics.observe(batch(1, 10, "boot2"))
    assert statistics.snapshot("ESP32_001")["totals"]["frames"] == 1


def install_catalog(service):
    entry = dict(
        id="read",
        name="Read session",
        action="Read",
        group="Identification",
        source="test.cdd",
        risk="read",
        sensitive=False,
        notes=[],
        request_fields=[
            dict(key="a", name="SID", bytes=1, constant="22"),
            dict(key="b", name="DID", bytes=2, constant="F186"),
        ],
        response_fields=[
            dict(key="a", name="SID", bytes=1, constant="62"),
            dict(key="b", name="DID", bytes=2, constant="F186"),
            dict(key="c", name="Session", bytes=1, kind="number", little=False),
        ],
    )
    change = {**entry, "id": "write", "name": "Write", "risk": "critical"}
    service.catalog = SimpleNamespace(
        error=None,
        services={"read": entry, "write": change},
        presets={},
        metadata={"cdd_sha256": "test"},
        target=lambda ecu, instance: dict(tx_id=0x7E4, rx_id=0x7EC),
        public=lambda: {"services": [entry, change]},
    )


def test_preview_no_transmit_confirmation_and_replay(admin, monkeypatch):
    app, client = admin
    rt = app.state.runtime
    install_catalog(rt.bms)
    sent = []
    monkeypatch.setattr(rt.mqtt, "publish_diagnostic", lambda *args: sent.append(args) or True)
    body = dict(kind="cdd", entry_id="read", device_id="ESP32_001")
    preview = client.post("/api/v1/bms/preview", json=body)
    assert preview.status_code == 200 and not sent
    assert (
        client.post("/api/v1/bms/jobs", json={"token": preview.json()["token"]}).status_code == 400
    )
    change = client.post("/api/v1/bms/preview", json={**body, "entry_id": "write"}).json()
    assert change["confirmation"] == "CONFIRM"
    assert client.post("/api/v1/bms/jobs", json={"token": change["token"]}).status_code == 400
    assert not sent
    assert (
        client.post("/api/v1/bms/preview", json=body, headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )


def test_job_mqtt_response_history_and_close(admin, monkeypatch):
    app, client = admin
    rt = app.state.runtime
    install_catalog(rt.bms)
    monkeypatch.setattr(
        rt.can.statistics,
        "snapshot",
        lambda _: dict(
            available=True,
            age_seconds=0,
            boot_id="testboot",
            device={"diag_supported": True, "diag_version": 3},
        ),
    )
    rt.mqtt.connected = True
    published = []

    def publish(device, body):
        published.append(body)
        reply = dict(
            id=body["id"],
            boot_id="testboot",
            status="completed",
            response_hex="62F18601" if body["op"] == "request" else "",
        )
        assert rt.bms.enqueue(
            "navsphere/" + device + "/diagnostic/response", json.dumps(reply).encode(), False
        )
        return True

    monkeypatch.setattr(rt.mqtt, "publish_diagnostic", publish)
    preview = client.post(
        "/api/v1/bms/preview", json=dict(kind="cdd", entry_id="read", device_id="ESP32_001")
    ).json()
    response = client.post("/api/v1/bms/jobs", json={"token": preview["token"]})
    assert response.status_code == 202
    job_id = response.json()["id"]
    result = wait_for(
        lambda: (
            r
            if (r := client.get("/api/v1/bms/jobs/" + job_id).json())["status"] == "completed"
            else None
        )
    )
    assert result["result"]["decoded"][0]["value"] == 1
    assert result["result"]["listen_only_restored"]
    assert len(result["exchanges"]) == 2 and [x["op"] for x in published] == ["request", "close"]
    assert published[1]["issued_ms"] > published[0]["issued_ms"]
    assert client.post("/api/v1/bms/jobs", json={"token": preview["token"]}).status_code == 400
    assert not rt.bms.enqueue("topic", b"{}", True)


def test_diagnostic_responses_are_bound_to_device_boot_and_command(admin):
    import threading

    app, _ = admin
    service = app.state.runtime.bms
    item = dict(
        event=threading.Event(),
        reply=None,
        boot="current",
        topic="navsphere/ESP32_001/diagnostic/response",
    )
    service.pending["command"] = item
    for topic, boot, command in [
        ("navsphere/another/diagnostic/response", "current", "command"),
        (item["topic"], "old", "command"),
        (item["topic"], "current", "other"),
    ]:
        service.enqueue(topic, json.dumps(dict(id=command, boot_id=boot)).encode(), False)
    wait_for(lambda: service.queue.empty())
    assert not item["event"].is_set()
    service.enqueue(
        item["topic"], json.dumps(dict(id="command", boot_id="current")).encode(), False
    )
    assert item["event"].wait(1)
    service.pending.pop("command")


def test_viewer_cannot_preview_bms_requests(admin):
    from sqlalchemy import select

    from app.database.models import User

    app, client = admin
    install_catalog(app.state.runtime.bms)
    with app.state.runtime.db.session() as db:
        user = db.scalar(select(User).where(User.username == "admin"))
        user.role = "viewer"
        db.commit()
    response = client.post(
        "/api/v1/bms/preview", json=dict(kind="cdd", entry_id="read", device_id="ESP32_001")
    )
    assert response.status_code == 403


def test_program_image_region_checked_before_erasing():
    from app.services.bms_protocol import validate_image_region

    entry = dict(id="program_app", image_kind="app")
    validate_image_region(entry, [(0x1000000, b"\0" * 8)])
    with pytest.raises(ValueError, match="no erase"):
        validate_image_region(entry, [(0x800000, b"\0" * 8)])


def test_automatic_security_exchange_redacts_seed_and_key(admin, monkeypatch):
    app, client = admin
    rt = app.state.runtime
    install_catalog(rt.bms)
    rt.bms.catalog.security_key = lambda ecu="abs_hv": bytes(range(16))
    monkeypatch.setattr(
        rt.can.statistics,
        "snapshot",
        lambda _: dict(
            available=True,
            age_seconds=0,
            boot_id="boot",
            device={"diag_supported": True, "diag_version": 3},
        ),
    )
    rt.mqtt.connected = True
    published = []

    def publish(device, body):
        raw = bytes.fromhex(body["data"])
        published.append(raw)
        if body["op"] == "close":
            response = b""
        elif raw[0] == 0x10:
            response = b"\x50\x03"
        elif raw[:2] == b"\x27\x03":
            response = b"\x67\x03" + b"\xaa" * 16
        elif raw[:2] == b"\x27\x04":
            assert len(raw) == 18
            response = b"\x67\x04"
        else:
            response = b"\x62\xf1\x86\x03"
        rt.bms.enqueue(
            "navsphere/ESP32_001/diagnostic/response",
            json.dumps(
                dict(id=body["id"], boot_id="boot", status="completed", response_hex=response.hex())
            ).encode(),
            False,
        )
        return True

    monkeypatch.setattr(rt.mqtt, "publish_diagnostic", publish)
    preview = client.post(
        "/api/v1/bms/preview",
        json=dict(kind="cdd", entry_id="read", device_id="ESP32_001", session=3, security=3),
    ).json()
    assert preview["confirmation"] == "CONFIRM"
    job = client.post(
        "/api/v1/bms/jobs", json=dict(token=preview["token"], confirmation="CONFIRM")
    ).json()
    result = wait_for(
        lambda: r if (r := rt.bms.detail(job["id"]))["status"] == "completed" else None
    )
    assert len(published) == 5
    for exchange in result["exchanges"][1:3]:
        assert exchange["request_hex"] == exchange["response_hex"] == "[redacted]"
    assert "AAAAAAAA" not in json.dumps(result)
