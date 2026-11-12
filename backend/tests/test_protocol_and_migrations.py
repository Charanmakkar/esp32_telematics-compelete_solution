import os
import subprocess
import sys
from datetime import timedelta

from conftest import ingest, payload, wait_for
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.core.config import Settings
from app.core.security import utcnow
from app.database.models import LoginSession
from app.main import create_app


def test_status_safe_state_and_retained_ack(admin):
    app, client = admin
    ingest(app, payload())
    wait_for(lambda: app.state.runtime.metrics["persisted"] == 1)
    ingest(
        app,
        {"online": True, "boot_id": "boot-1", "controls": {"A": 1, "B": 0}},
        kind="status",
        retained=True,
    )
    wait_for(lambda: client.get("/api/v1/devices").json()["devices"][0]["controls"]["A"] == 1)
    ingest(
        app,
        {"online": True, "boot_id": "boot-1", "controls": {"A": 0, "B": 0}},
        kind="status",
        retained=True,
    )
    wait_for(lambda: client.get("/api/v1/devices").json()["devices"][0]["controls"]["A"] == 0)
    ingest(app, {"online": False}, kind="status", retained=True)
    wait_for(lambda: not client.get("/api/v1/devices").json()["devices"][0]["online"])
    assert client.get("/api/v1/devices").json()["devices"][0]["controls"]["A"] is None
    ingest(
        app,
        {
            "command_id": "x",
            "key": "A",
            "value": 1,
            "status": "applied",
            "reason": "retained",
            "boot_id": "boot-1",
        },
        kind="ack",
        retained=True,
    )
    wait_for(lambda: app.state.runtime.metrics["invalid"] == 1)


def test_session_expiry_and_openapi_mutation_headers(logged_in):
    app, client = logged_in
    schema = client.get("/openapi.json").json()
    for path in ("/api/v1/auth/password", "/api/v1/auth/logout", "/api/v1/commands"):
        assert any(p["name"] == "X-CSRF-Token" for p in schema["paths"][path]["post"]["parameters"])
    assert "LatestResponse" in schema["components"]["schemas"]
    with app.state.runtime.db.session() as db:
        for session in db.query(LoginSession).all():
            session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_alembic_fresh_database_finishes_with_six_channels(tmp_path):
    url = f"sqlite:///{tmp_path}/migrations.db"
    env = {**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "test"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    analog = [
        c["name"]
        for c in inspect(engine).get_columns("telemetry_readings")
        if c["name"].startswith("analog_")
    ]
    assert analog == [f"analog_{i}" for i in range(1, 7)]
    engine.dispose()


def test_swagger_api_origins_allow_auth_and_commands_but_reject_untrusted(tmp_path):
    origins = Settings.model_fields["frontend_origins"].default
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite:///{tmp_path}/swagger.db",
            mqtt_enabled=False,
            auto_migrate=True,
            frontend_origins=origins,
        )
    )
    password = "admin"
    with TestClient(app) as client:
        for index, origin in enumerate(("http://localhost:8000", "http://127.0.0.1:8000")):
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "admin",
                    "password": password,
                },
                headers={"Origin": origin},
            )
            assert response.status_code == 200
            headers = {"Origin": origin, "X-CSRF-Token": response.json()["csrf_token"]}
            new_password = f"swagger-verified-password-{index}"
            assert (
                client.post(
                    "/api/v1/auth/password",
                    json={
                        "current_password": password,
                        "new_password": new_password,
                    },
                    headers=headers,
                ).status_code
                == 200
            )
            password = new_password
            body = {"device_id": "ESP32_001", "key": "A", "value": 1}
            # The disconnected broker is reached after origin/auth/CSRF checks.
            assert client.post("/api/v1/commands", json=body, headers=headers).status_code == 503
            untrusted = {**headers, "Origin": "https://untrusted.example"}
            assert client.post("/api/v1/commands", json=body, headers=untrusted).status_code == 403
            assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert (
            client.post(
                "/api/v1/auth/login",
                json={
                    "username": "admin",
                    "password": password,
                },
                headers={"Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
