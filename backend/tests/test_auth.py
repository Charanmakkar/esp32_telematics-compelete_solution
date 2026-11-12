from app.core.config import Settings
from app.core.security import hash_password
from app.database.models import User


def test_authentication_csrf_initial_password_and_logout(logged_in):
    app, client = logged_in
    assert client.get("/api/v1/auth/me").json()["user"]["must_change_password"]
    result = client.post(
        "/api/v1/commands", json={"device_id": "ESP32_001", "key": "A", "value": 1}
    )
    assert result.status_code == 403
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/auth/logout").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/telemetry/latest").status_code == 401


def test_password_rotation_revokes_other_sessions(admin):
    app, client = admin
    assert not client.get("/api/v1/auth/me").json()["user"]["must_change_password"]
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
        ).status_code
        == 401
    )
    with app.state.runtime.db.session() as db:
        user = db.query(User).filter_by(username="admin").one()
        assert "admin" not in user.password_hash
        assert user.password_hash.startswith("scrypt$")


def test_viewer_cannot_control(application):
    app, client = application
    with app.state.runtime.db.session() as db:
        db.add(
            User(
                username="viewer",
                password_hash=hash_password("viewer-password"),
                role="viewer",
                must_change_password=False,
            )
        )
        db.commit()
    auth = client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "viewer-password"}
    )
    response = client.post(
        "/api/v1/commands",
        json={"device_id": "ESP32_001", "key": "A", "value": 1},
        headers={"X-CSRF-Token": auth.json()["csrf_token"]},
    )
    assert response.status_code == 403


def test_login_rate_limit(application):
    app, client = application
    for _ in range(10):
        assert (
            client.post("/api/v1/auth/login", json={"username": "x", "password": "x"}).status_code
            == 401
        )
    assert (
        client.post("/api/v1/auth/login", json={"username": "x", "password": "x"}).status_code
        == 429
    )


def test_production_rejects_default_password():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_command_timeout_matches_device_ttl():
    import pytest
    from pydantic import ValidationError

    assert Settings(environment="test", command_timeout_seconds=30).command_timeout_seconds == 30
    with pytest.raises(ValidationError):
        Settings(environment="test", command_timeout_seconds=31)
