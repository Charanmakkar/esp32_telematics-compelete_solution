import json
import time

import pytest
from conftest import ingest, payload, wait_for
from pydantic import ValidationError
from sqlalchemy import func, select

from app.database.models import TelemetryReading
from app.schemas.telemetry import Telemetry


@pytest.mark.parametrize(
    "changes",
    [
        {"channels": {"analog_1": 1}},
        {"raw": [1]},
        {"valid_mask": 64},
        {"sequence": True},
        {"schema_version": True},
        {"time_valid": False},
        {"timestamp_ms": int(time.time() * 1000) + 900000},
        {"channels": {f"analog_{i}": 5001 for i in range(1, 7)}},
    ],
)
def test_invalid_payloads(changes):
    with pytest.raises(ValidationError):
        Telemetry.model_validate(payload(**changes))


def test_ingest_duplicate_and_reboot_sequences(logged_in):
    app, client = logged_in
    message = payload()
    ingest(app, message)
    ingest(app, message)
    ingest(app, payload(boot_id="boot-2"))
    wait_for(lambda: app.state.runtime.metrics["persisted"] == 2)
    assert app.state.runtime.metrics["duplicates"] == 1
    with app.state.runtime.db.session() as db:
        assert db.scalar(select(func.count()).select_from(TelemetryReading)) == 2
    latest = client.get("/api/v1/telemetry/latest").json()
    assert latest["persisted"]["boot_id"] == "boot-2"
    assert latest["received"]["persisted_at"] is None
    assert latest["persisted"]["persisted_at"]
    assert latest["persisted"]["channels"]["analog_6"] == 1006


def test_malformed_json_retained_and_topic_spoofing(logged_in):
    app, client = logged_in
    app.state.runtime.enqueue("navsphere/ESP32_001/telemetry", b"{bad")
    ingest(app, payload(), retained=True)
    message = payload(device_id="attacker")
    ingest(app, message)
    wait_for(lambda: app.state.runtime.metrics["invalid"] == 3)
    assert client.get("/api/v1/telemetry/latest").json()["persisted"] is None


def test_history_downsampling_and_validity_statistics(logged_in):
    app, client = logged_in
    timestamp = int(time.time() * 1000) - 10000
    for i in range(30):
        body = payload(
            sequence=i,
            timestamp_ms=timestamp + i * 100,
            channels={f"analog_{n}": i for n in range(1, 7)},
            valid_mask=62 if i < 10 else 63,
        )
        ingest(app, body)
    wait_for(lambda: app.state.runtime.metrics["persisted"] == 30)
    response = client.get(
        "/api/v1/telemetry/history",
        params={
            "start_ms": timestamp,
            "end_ms": timestamp + 3000,
            "limit": 5,
        },
    )
    assert response.status_code == 200
    history = response.json()
    assert history["count"] == 30 and history["aggregated"]
    assert len(history["points"]) <= 5
    assert history["statistics"]["analog_1"] == {"min": 10, "max": 29, "avg": 19.5, "count": 20}
    assert history["statistics"]["analog_2"]["avg"] == 14.5
    assert client.get("/api/v1/telemetry/channels/analog-6").status_code == 200
    assert client.get("/api/v1/telemetry/channels/analog-7").status_code == 404
    assert (
        client.get(
            "/api/v1/telemetry/history", params={"start_ms": 0, "end_ms": 999999999999}
        ).status_code
        == 422
    )


def test_websocket_received_and_persisted_events(logged_in):
    app, client = logged_in
    with client.websocket_connect("/ws/v1/telemetry") as socket:
        ingest(app, payload())
        received = socket.receive_json()
        persisted = socket.receive_json()
        assert received["stage"] == "received" and received["data"]["persisted_at"] is None
        assert persisted["stage"] == "persisted" and persisted["data"]["id"] > 0


def test_database_failure_then_recovery(logged_in, monkeypatch):
    app, client = logged_in
    repo = app.state.runtime.repository
    original = repo.persist

    def fail(*args, **kwargs):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(repo, "persist", fail)
    ingest(app, payload(sequence=1))
    wait_for(lambda: app.state.runtime.metrics["dropped"] == 1)
    assert app.state.runtime.latest_received["ESP32_001"]["persisted_at"] is None
    monkeypatch.setattr(repo, "persist", original)
    ingest(app, payload(sequence=2))
    wait_for(lambda: app.state.runtime.metrics["persisted"] == 1)
    assert app.state.runtime.database_connected
    assert client.get("/api/v1/telemetry/latest").json()["persisted"]["sequence"] == 2


def test_bounded_queue(application):
    app, client = application
    # Use an independent runtime with no worker for deterministic overflow verification.
    from app.core.config import Settings
    from app.services.telemetry_service import Runtime

    rt = Runtime(
        Settings(
            environment="test", database_url="sqlite://", mqtt_enabled=False, ingest_queue_size=10
        )
    )
    for _ in range(11):
        rt.enqueue("navsphere/ESP32_001/telemetry", json.dumps(payload()).encode())
    assert rt.queue.qsize() == 10
    assert rt.metrics["dropped"] == 1
