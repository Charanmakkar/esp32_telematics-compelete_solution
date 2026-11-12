from datetime import timedelta

from conftest import ingest, payload, wait_for

from app.core.security import utcnow
from app.database.models import Command


def prepare_device(app):
    ingest(app, payload())
    wait_for(lambda: app.state.runtime.metrics["persisted"] == 1)
    app.state.runtime.mqtt.connected = True
    app.state.runtime.mqtt.publish_command = lambda device, body: True


def test_command_not_applied_until_matching_ack(admin):
    app, client = admin
    prepare_device(app)
    command = client.post(
        "/api/v1/commands", json={"device_id": "ESP32_001", "key": "A", "value": 1}
    )
    assert command.status_code == 202
    command = command.json()
    assert command["status"] == "pending"
    assert client.get("/api/v1/devices").json()["devices"][0]["controls"]["A"] is None
    ack = {
        "command_id": command["command_id"],
        "key": "A",
        "value": 1,
        "status": "accepted",
        "reason": "validated",
        "boot_id": "boot-1",
    }
    ingest(app, ack, kind="ack")
    wait_for(
        lambda: (
            client.get(f"/api/v1/commands/{command['command_id']}").json()["status"] == "accepted"
        )
    )
    ack["status"] = "applied"
    ingest(app, ack, kind="ack")
    wait_for(
        lambda: (
            client.get(f"/api/v1/commands/{command['command_id']}").json()["status"] == "applied"
        )
    )
    assert client.get("/api/v1/devices").json()["devices"][0]["controls"]["A"] == 1
    ack["status"] = "rejected"
    ingest(app, ack, kind="ack")
    wait_for(lambda: app.state.runtime.queue.empty())
    assert client.get(f"/api/v1/commands/{command['command_id']}").json()["status"] == "applied"


def test_command_timeout_and_mismatched_ack(admin):
    app, client = admin
    prepare_device(app)
    command = client.post(
        "/api/v1/commands", json={"device_id": "ESP32_001", "key": "B", "value": 0}
    ).json()
    ingest(
        app,
        {
            "command_id": command["command_id"],
            "key": "B",
            "value": 1,
            "status": "applied",
            "reason": "wrong-value",
            "boot_id": "boot-1",
        },
        kind="ack",
    )
    wait_for(lambda: app.state.runtime.metrics["invalid"] >= 1)
    assert client.get(f"/api/v1/commands/{command['command_id']}").json()["status"] == "pending"
    with app.state.runtime.db.session() as db:
        row = db.get(Command, command["command_id"])
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    wait_for(
        lambda: (
            client.get(f"/api/v1/commands/{command['command_id']}").json()["status"] == "timed_out"
        )
    )


def test_broker_disconnection_and_input_validation(admin):
    app, client = admin
    assert (
        client.post(
            "/api/v1/commands", json={"device_id": "ESP32_001", "key": "A", "value": 1}
        ).status_code
        == 503
    )
    assert (
        client.post(
            "/api/v1/commands", json={"device_id": "ESP32_001", "key": "C", "value": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/commands", json={"device_id": "ESP32_001", "key": "A", "value": True}
        ).status_code
        == 422
    )
