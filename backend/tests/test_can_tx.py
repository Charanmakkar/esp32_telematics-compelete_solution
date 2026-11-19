from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import utcnow
from app.database.models import AuditEvent, User
from app.database.repository import iso
from app.schemas.can import CanStats
from app.services.can_tx_service import PROFILES


def ready(app, **changes):
    rt = app.state.runtime
    rt.mqtt.connected = True
    rt.latest_received["ESP32_001"] = {
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "time_valid": True,
    }
    rt.can.status["ESP32_001"] = {
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "received_at": iso(utcnow()),
        "mode": "listen_only",
        "periodic_tx": {
            "enabled": False,
            "command_id": "",
            "reason": "off",
            "sent_014": 0,
            "sent_548": 0,
            "failures": 0,
            "skipped": 0,
        },
        **changes,
    }
    return rt


def test_status_requires_auth_and_accepts_old_firmware(application):
    app, client = application
    assert client.get("/api/v1/can/tx").status_code == 401
    rt = ready(app, periodic_tx=None)
    assert not rt.can_tx.snapshot("ESP32_001")["supported"]


def test_on_waits_for_current_boot_clock(admin, monkeypatch):
    app, client = admin
    rt = ready(app)
    rt.latest_received["ESP32_001"]["time_valid"] = False
    monkeypatch.setattr(rt.mqtt, "publish_can_tx", lambda *_: pytest.fail("Must not publish"))
    result = client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": True})
    assert result.status_code == 409
    assert "clock" in result.json()["detail"]


def test_confirmed_toggle_and_audit(admin, monkeypatch):
    app, client = admin
    rt = ready(app)
    commands = []

    def publish(device, payload):
        commands.append(payload)
        status = rt.can.status[device]
        status["periodic_tx"] = {
            **status["periodic_tx"],
            "enabled": payload["enabled"],
            "command_id": payload["command_id"],
        }
        return True

    monkeypatch.setattr(rt.mqtt, "publish_can_tx", publish)
    for enabled in (True, False):
        result = client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": enabled})
        assert result.status_code == 200
        assert result.json()["state"]["enabled"] is enabled
    assert commands[1]["issued_at_ms"] > commands[0]["issued_at_ms"]
    assert commands[0]["boot_id"] == rt.can.status["ESP32_001"]["boot_id"]
    assert commands[0]["expires_at_ms"] - commands[0]["issued_at_ms"] == 4000
    with rt.db.session() as db:
        assert (
            len(db.scalars(select(AuditEvent).where(AuditEvent.action == "can_tx_toggle")).all())
            == 2
        )
    assert PROFILES[0] == {"can_id": 0x14, "data": "006000", "dlc": 3, "period_ms": 100}
    assert PROFILES[1] == {"can_id": 0x548, "data": "0000000000000008", "dlc": 8, "period_ms": 10}


@pytest.mark.parametrize(
    "changes",
    [
        {"received_at": iso(utcnow() - timedelta(seconds=20))},
        {"mode": "diagnostic"},
        {"mode": "unavailable"},
        {"periodic_tx": None},
    ],
)
def test_on_rejects_stale_busy_and_old_device(admin, monkeypatch, changes):
    app, client = admin
    rt = ready(app, **changes)
    monkeypatch.setattr(rt.mqtt, "publish_can_tx", lambda *_: pytest.fail("Must not publish"))
    assert (
        client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": True}).status_code
        == 409
    )


def test_off_is_available_with_stale_status(admin, monkeypatch):
    app, client = admin
    rt = ready(app, received_at=iso(utcnow() - timedelta(seconds=30)))

    def publish(device, command):
        assert command["enabled"] is False
        rt.can.status[device]["received_at"] = iso(utcnow())
        rt.can.status[device]["periodic_tx"]["command_id"] = command["command_id"]
        return True

    monkeypatch.setattr(rt.mqtt, "publish_can_tx", publish)
    assert (
        client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": False}).status_code
        == 200
    )


def test_timeout_does_not_report_optimistic_success(admin, monkeypatch):
    app, client = admin
    rt = ready(app)
    monkeypatch.setattr(rt.mqtt, "publish_can_tx", lambda *_: True)
    ticks = iter([0, 6])
    monkeypatch.setattr("app.services.can_tx_service.monotonic", lambda: next(ticks))
    result = client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": True})
    assert result.status_code == 504
    assert not rt.can_tx.snapshot("ESP32_001")["state"]["enabled"]


def test_csrf_role_and_payload_restrictions(admin):
    app, client = admin
    rt = ready(app)
    for extra in ({"can_id": 0x123}, {"data": "FF"}, {"enabled": "true"}):
        result = client.post(
            "/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": True, **extra}
        )
        assert result.status_code == 422
    assert client.get("/api/v1/can/tx?device_id=unknown").status_code == 404
    token = client.headers.pop("X-CSRF-Token")
    assert (
        client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": True}).status_code
        == 403
    )
    client.headers["X-CSRF-Token"] = token
    with rt.db.session() as db:
        db.scalar(select(User).where(User.username == "admin")).role = "viewer"
        db.commit()
    assert (
        client.post("/api/v1/can/tx", json={"device_id": "ESP32_001", "enabled": True}).status_code
        == 403
    )


def test_new_status_validates_without_changing_legacy_stats():
    legacy = dict(
        queue_drops=0, serial_drops=0, publish_drops=0, rx_missed=0, rx_overruns=0, bus_errors=0
    )
    assert CanStats.model_validate(legacy).periodic_tx is None
    assert (
        CanStats.model_validate(
            {
                **legacy,
                "mode": "periodic_tx",
                "periodic_tx": {
                    "enabled": True,
                    "command_id": "",
                    "reason": "on",
                    "sent_014": 2,
                    "sent_548": 20,
                    "failures": 0,
                    "skipped": 0,
                },
            }
        ).periodic_tx.sent_548
        == 20
    )
