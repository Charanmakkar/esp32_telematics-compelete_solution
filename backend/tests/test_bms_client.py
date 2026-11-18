"""Golden BE client sequences and failure paths; no hardware writes are performed."""

import json
import zlib

import pytest
from conftest import wait_for
from test_bms import record

from app.services.bms_catalog import BmsCatalog
from app.services.bms_client_reference import CLIENT_SHA256, client_reference
from app.services.bms_client_workflows import (
    authenticate_bootloader,
    cmac,
    prepare_mode,
    program_client_image,
    unlock,
)
from app.services.bms_protocol import decode_preset, load_hex


def test_cmac_known_vector_and_security_exchange():
    # NIST SP 800-38B Example 2; public test values, not a device credential.
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    seed = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
    expected = bytes.fromhex("070a16b46b4d4144f79bdd9dd04a287c")
    assert cmac(key, seed) == expected
    calls = []

    def exchange(raw):
        calls.append(raw)
        return b"\x67\x03" + seed if len(raw) == 2 else b"\x67\x04"

    unlock(exchange, 3, key)
    assert calls == [b"\x27\x03", b"\x27\x04" + expected]
    calls.clear()
    unlock(lambda raw: calls.append(raw) or b"\x67\x01" + bytes(16), 1, key)
    assert calls == [b"\x27\x01"]
    with pytest.raises(ValueError, match="16 bytes"):
        unlock(lambda _: b"\x67\x01\x01", 1, key)


def test_application_preparation_never_resets_or_unlocks():
    calls, pauses = [], []
    prepare_mode({"app": True}, lambda raw, **kw: calls.append((raw, kw)), pauses.append)
    assert calls == [(b"\x3e\x80", dict(timeout=4000, expect_response=False, repeat=20))]
    assert pauses == [0.6]


def test_bootloader_trap_is_bounded_and_stops_on_rejection():
    calls = []

    def exchange(raw, **kw):
        calls.append(raw)
        return b"\x62\xf0\x10\x02"

    with pytest.raises(ValueError, match="did not enter"):
        prepare_mode({"app": False}, exchange, lambda _: None)
    assert calls == [bytes.fromhex(x) for x in ["1101", "3E80", "22F010"]] * 2
    calls.clear()

    def rejected(raw, **kw):
        calls.append(raw)
        raise ValueError("NRC 0x22")

    with pytest.raises(ValueError, match="NRC"):
        prepare_mode({"app": False}, rejected)
    assert calls == [b"\x11\x01"]


def test_reverse_bootloader_authentication(monkeypatch):
    key, challenge = bytes(range(16)), bytes(range(16, 32))
    monkeypatch.setattr(
        "app.services.bms_client_workflows.secrets.token_bytes", lambda _: challenge
    )
    calls = []

    def exchange(raw):
        calls.append(raw)
        return b"\x67\x06" if raw[1] == 6 else b"\x67\x05" + cmac(key, challenge)

    authenticate_bootloader(exchange, key)
    assert calls == [b"\x27\x06" + challenge, b"\x27\x05"]
    with pytest.raises(ValueError, match="no erase"):
        authenticate_bootloader(lambda _: b"\x67\x05" + bytes(16), key)


@pytest.mark.parametrize(
    "kind,rids", [("app", (0xFF00, 0x0210, 0x0211)), ("cal", (0x0201, 0x0212, 0x0213))]
)
def test_client_download_golden_sequence(kind, rids):
    calls = []

    def exchange(raw, **kw):
        calls.append(raw)
        if raw[0] == 0x31:
            status = b"\x00" if int.from_bytes(raw[2:4], "big") == rids[2] else b"\x02\x01"
            return b"\x71" + raw[1:4] + status
        if raw[0] == 0x34:
            return b"\x74\x20\x00\x82"  # 130-byte blocks, includes SID/counter.
        return bytes([raw[0] + 0x40]) + raw[1:2]

    payload = bytes(range(256))
    program_client_image(
        exchange,
        [(0x1000000, payload)],
        kind,
        lambda _: None,
        lambda: False,
        image_id=2,
        pause=lambda _: None,
    )
    erase, verify, comp = [x.to_bytes(2, "big") for x in rids]
    assert calls == [
        b"\x31\x01" + erase + b"\x02",
        b"\x31\x03" + erase + b"\x02",
        bytes.fromhex("3400440100000000000100"),
        b"\x36\x01" + payload[:128],
        b"\x36\x02" + payload[128:],
        b"\x37",
        b"\x31\x01" + verify + b"\x02",
        b"\x31\x03" + verify + b"\x02",
        b"\x31\x01" + comp + b"\x02",
        b"\x11\x01",
    ]


def test_erase_fail_and_invalid_image_stop_before_download():
    calls = []

    def failed(raw, **kw):
        calls.append(raw)
        return b"\x71" + raw[1:4] + b"\x03"

    with pytest.raises(ValueError, match="failed"):
        program_client_image(failed, [(0x1000000, bytes(8))], "app", lambda _: None, lambda: False)
    assert all(c[0] == 0x31 for c in calls)
    calls.clear()
    with pytest.raises(ValueError, match="before erasure"):
        program_client_image(
            failed, [(0, bytes(8)), (16, bytes(8))], "app", lambda _: None, lambda: False
        )
    assert not calls


def test_client_hex_span_padding_and_crc(tmp_path):
    path = tmp_path / "span.hex"
    path.write_text("\n".join([record(0, 0, b"abcd"), record(8, 0, b"xy"), record(0, 1)]))
    info, segments = load_hex(path, client_format=True)
    assert segments == [(0, b"abcd" + b"\xff" * 4 + b"xy" + b"\xff" * 6)]
    assert info["bytes"] == 16 and info["source_bytes"] == 6
    _, with_crc = load_hex(path, client_format=True, inject_crc=True)
    assert with_crc[0][1][:4] == zlib.crc32(segments[0][1][4:]).to_bytes(4, "big")
    assert with_crc[0][1][4:] == segments[0][1][4:]


def test_new_reference_fingerprint_and_targets():
    catalog = BmsCatalog()
    if catalog.error:
        pytest.skip("Local BE reference not available")
    profile = client_reference(catalog.release)
    assert profile["version"] == "15.0.4" and profile["sha256"] == CLIENT_SHA256
    assert len(profile["boot_auth_key"]) == 16
    assert catalog.target()["tx_id"] == 0x7E4
    assert catalog.target("abs_hv_old")["rx_id"] == 0x650
    assert catalog.presets["abs_hv_clear_faults"]["operation"] == "clear_dtc"
    assert catalog.presets["abs_hv_program_bootloader_0_6_0"]["ecu"] == "abs_hv_old"
    assert catalog.presets["abs_hv_read_sn"]["risk"] == "critical"
    assert "boot_auth_key" not in json.dumps(catalog.public())
    with pytest.raises(ValueError):
        catalog.target(instance=2)


def test_changed_executable_is_rejected_before_parsing(tmp_path):
    path = tmp_path / "client"
    path.mkdir()
    (path / "amp_uds_client.exe").write_bytes(b"not the audited client")
    with pytest.raises(ValueError, match="has changed"):
        client_reference(tmp_path)


def test_all_be_scripts_preview_without_transmission(admin, monkeypatch):
    app, _ = admin
    service = app.state.runtime.bms
    if service.catalog.error:
        pytest.skip("Local BE reference not available")
    monkeypatch.setattr(
        app.state.runtime.mqtt,
        "publish_diagnostic",
        lambda *_: pytest.fail("Preview must never transmit"),
    )
    values = dict(text="TEST", location="TC", build="0110", date="23202", part="0123456789")
    prepared = {}
    for entry in service.catalog.presets.values():
        prepared[entry["id"]] = service.prepare(
            dict(kind="preset", entry_id=entry["id"], device_id="ESP32_001", values=values), "admin"
        )
    assert len(prepared) == 44
    assert prepared["abs_hv_clear_faults"]["request_hex"] == "14FFFFFF"
    assert prepared["abs_hv_clear_faults"]["security"] == 3
    assert prepared["abs_hv_program_bootloader_0_6_0"]["tx_id"] == 0x640
    assert (
        prepared["abs_hv_program_bootloader_0_6_0"]["image"]["segments"][0]["address"] == 0x1100000
    )
    assert prepared["abs_hv_read_sn"]["confirmation"] == "CONFIRM"
    assert prepared["abs_hv_read_custom_1_did"]["security"] == 0
    assert prepared["abs_hv_read_custom_1_did"]["tx_id"] == 0x7E4


def test_new_workflows_reject_old_firmware_before_publication(admin, monkeypatch):
    app, client = admin
    rt = app.state.runtime
    if rt.bms.catalog.error:
        pytest.skip("Local BE reference not available")
    monkeypatch.setattr(
        rt.can.statistics,
        "snapshot",
        lambda _: dict(
            available=True,
            age_seconds=0,
            boot_id="old",
            device=dict(diag_supported=True, diag_version=2),
        ),
    )
    rt.mqtt.connected = True
    monkeypatch.setattr(rt.mqtt, "publish_diagnostic", lambda *_: pytest.fail("Wrong firmware"))
    result = client.post("/api/v1/bms/read", json=dict(device_id="ESP32_001", command="serial"))
    assert result.status_code == 400 and "Flash" in result.json()["detail"]


def test_observed_be_payload_lengths_are_decoded_without_exe_codec_errors():
    for did, data in [(0xF18C, b"02345678901234567890123456789012"), (0xF191, b"00000000")]:
        rows, warnings = decode_preset(
            dict(operation="read", did=did), b"\x62" + did.to_bytes(2, "big") + data
        )
        assert rows[0]["value"] == data.decode() and not warnings


def test_download_counter_wrap_integrity_failure_and_cancellation():
    calls = []

    def exchange(raw, **kw):
        calls.append(raw)
        if raw[0] == 0x31:
            return b"\x71" + raw[1:4] + (b"\x02\x00" if raw[2:4] == b"\x02\x10" else b"\x02")
        if raw[0] == 0x34:
            return b"\x74\x20\x00\x80"
        return bytes([raw[0] + 0x40]) + raw[1:2]

    with pytest.raises(ValueError, match="integrity"):
        program_client_image(
            exchange,
            [(0x1000000, bytes(128 * 256))],
            "app",
            lambda _: None,
            lambda: False,
            data_only_block_length=True,
        )
    transfers = [c for c in calls if c[0] == 0x36]
    assert len(transfers) == 256 and transfers[-1][1] == 0
    assert not any(c[0] == 0x11 or c[2:4] == b"\x02\x11" for c in calls)
    calls.clear()
    with pytest.raises(ValueError, match="before erasure"):
        program_client_image(exchange, [], "app", lambda _: None, lambda: True)
    assert not calls


@pytest.mark.parametrize("command,did", [("serial", "F18C"), ("qr", "C000"), ("hardware", "F191")])
def test_one_click_read_routes_only_reads_and_saves_response(admin, monkeypatch, command, did):
    app, client = admin
    rt = app.state.runtime
    if rt.bms.catalog.error:
        pytest.skip("Local BE reference not available")
    monkeypatch.setattr(
        rt.can.statistics,
        "snapshot",
        lambda _: dict(
            available=True,
            age_seconds=0,
            boot_id="be",
            device=dict(diag_supported=True, diag_version=3),
        ),
    )
    rt.mqtt.connected = True
    sent = []
    payload = "SERIAL".encode().ljust(62 if command == "qr" else 32, b"\0")

    def publish(device, body):
        sent.append(body)
        reply = "62" + did + payload.hex() if body["data"] == "22" + did else ""
        rt.bms.enqueue(
            f"navsphere/{device}/diagnostic/response",
            json.dumps(
                dict(id=body["id"], boot_id="be", status="completed", response_hex=reply)
            ).encode(),
            False,
        )
        return True

    monkeypatch.setattr(rt.mqtt, "publish_diagnostic", publish)
    response = client.post("/api/v1/bms/read", json=dict(device_id="ESP32_001", command=command))
    assert response.status_code == 202
    ident = response.json()["id"]
    result = wait_for(
        lambda: r if (r := rt.bms.detail(ident))["status"] in ("completed", "failed") else None
    )
    assert result["status"] == "completed" and result["result"]["listen_only_restored"]
    assert result["result"]["decoded"][0]["value"] == "SERIAL"
    assert [s["data"] for s in sent] == ["3E80", "22" + did, ""]
    assert sent[0]["repeat"] == 20 and not sent[0]["expect_response"]
    assert all(s["tx_id"] == 0x7E4 and s["rx_id"] == 0x7EC for s in sent)
    assert (
        client.post(
            "/api/v1/bms/read", json=dict(device_id="ESP32_001", command="erase")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/bms/read",
            json=dict(device_id="ESP32_001", command=command),
            headers={"X-CSRF-Token": "bad"},
        ).status_code
        == 403
    )
