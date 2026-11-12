from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"
    database_url: str | None = None
    db_host: str = "192.168.9.59"
    db_port: int = 3306
    db_name: str = "navsphere"
    db_user: str = "navsphere"
    db_password: str = ""
    mqtt_host: str = "192.168.9.59"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_enabled: bool = True
    mqtt_tls: bool = False
    mqtt_ca_file: str | None = None
    mqtt_topic_prefix: str = "navsphere"
    device_ids: str = "ESP32_001"
    frontend_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )
    cookie_secure: bool = False
    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin"
    auto_migrate: bool = False
    command_timeout_seconds: int = Field(default=10, ge=1, le=30)
    session_ttl_seconds: int = Field(default=28800, ge=60, le=604800)
    ingest_queue_size: int = Field(default=2048, ge=10, le=65536)
    database_retry_seconds: int = Field(default=10, ge=0, le=300)
    device_stale_seconds: int = Field(default=3, ge=1, le=300)

    @property
    def allowed_devices(self) -> tuple[str, ...]:
        return tuple(v.strip() for v in self.device_ids.split(",") if v.strip())

    @property
    def origins(self) -> list[str]:
        return [v.strip() for v in self.frontend_origins.split(",") if v.strip()]

    @property
    def db_url(self) -> str | URL:
        return self.database_url or URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )

    @model_validator(mode="after")
    def secure_production(self):
        import re

        if not self.allowed_devices or len(self.allowed_devices) > 128:
            raise ValueError("Configure between 1 and 128 device IDs")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", d) for d in self.allowed_devices):
            raise ValueError("Invalid device ID")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.mqtt_topic_prefix):
            raise ValueError("Invalid MQTT topic prefix")
        if self.environment == "production":
            if len(self.initial_admin_password) < 12 or self.initial_admin_password == "admin":
                raise ValueError(
                    "Production requires a nondefault initial admin password >=12 chars"
                )
            if not self.cookie_secure or not self.mqtt_tls:
                raise ValueError("Production requires secure cookies and MQTT TLS")
            if not self.mqtt_username or not self.mqtt_password or not self.db_password:
                raise ValueError("Production requires database and MQTT credentials")
            if self.database_url and self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is only supported for tests/development")
            if any(not x.startswith("https://") for x in self.origins):
                raise ValueError("Production frontend origins must use HTTPS")
        return self
