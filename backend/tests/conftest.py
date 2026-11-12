import json
import time

import pytest
from fastapi.testclient import TestClient

from app.api.auth import limiter
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def application(tmp_path):
    limiter.attempts.clear()
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite:///{tmp_path}/test.db",
            mqtt_enabled=False,
            auto_migrate=True,
            database_retry_seconds=0,
        )
    )
    with TestClient(app) as client:
        yield app, client


@pytest.fixture
def logged_in(application):
    app, client = application
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = token
    return app, client


@pytest.fixture
def admin(logged_in):
    app, client = logged_in
    response = client.post(
        "/api/v1/auth/password",
        json={
            "current_password": "admin",
            "new_password": "navsphere-test-password-2026",
        },
    )
    assert response.status_code == 200
    return app, client


def payload(sequence=1, boot_id="boot-1", **overrides):
    return {
        "schema_version": 1,
        "device_id": "ESP32_001",
        "boot_id": boot_id,
        "sequence": sequence,
        "timestamp_ms": int(time.time() * 1000),
        "time_valid": True,
        "uptime_ms": sequence * 100,
        "channels": {f"analog_{i}": 1000 + i for i in range(1, 7)},
        "raw": [1200] * 6,
        "valid_mask": 63,
        "mqtt_connected": True,
        "dropped_samples": 0,
        "source": "simulator",
        "stale": False,
        **overrides,
    }


def ingest(app, body, kind="telemetry", retained=False):
    return app.state.runtime.enqueue(
        f"navsphere/ESP32_001/{kind}", json.dumps(body).encode(), retained
    )


def wait_for(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise AssertionError("Condition did not become true before timeout")
