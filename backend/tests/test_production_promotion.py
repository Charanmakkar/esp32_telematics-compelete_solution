import pytest

import app.services.telemetry_service as service
from app.core.config import Settings
from app.core.security import hash_password
from app.database.models import User
from app.services.telemetry_service import Runtime


def test_production_promotion_rejects_existing_default_passwords(tmp_path, monkeypatch):
    development = Runtime(
        Settings(
            environment="test",
            database_url=f"sqlite:///{tmp_path}/promotion.db",
            auto_migrate=True,
            mqtt_enabled=False,
        )
    )
    development.initialize()
    production_settings = Settings(
        environment="production",
        database_url=None,
        db_password="test-database-password",
        mqtt_enabled=False,
        mqtt_username="test-backend",
        mqtt_password="test-mqtt-password",
        mqtt_tls=True,
        cookie_secure=True,
        initial_admin_password="strong-production-seed-password",
        frontend_origins="https://navsphere.example",
        auto_migrate=False,
    )
    # Configuration independently prohibits SQLite in production. Only this test injects an
    # isolated connection to exercise account-promotion policy against persisted development data.
    monkeypatch.setattr(service, "Database", lambda _: development.db)
    production = Runtime(production_settings)
    with development.db.session() as db:
        original = db.query(User).filter_by(username="admin").one().password_hash
    with pytest.raises(ValueError, match="Production startup refused"):
        production.initialize()
    with development.db.session() as db:
        administrator = db.query(User).filter_by(username="admin").one()
        assert administrator.password_hash == original  # No automatic credential rotation.
        administrator.password_hash = hash_password("changed-before-production")
        db.add(
            User(
                username="viewer",
                password_hash=hash_password("admin"),
                role="viewer",
                active=True,
                must_change_password=True,
            )
        )
        db.commit()
    with pytest.raises(ValueError, match="Production startup refused"):
        production.initialize()
    with development.db.session() as db:
        db.query(User).filter_by(username="viewer").one().active = False
        db.commit()
    production.initialize()  # Disabled weak accounts do not grant access.
    development.db.engine.dispose()
