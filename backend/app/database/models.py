from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, MEDIUMTEXT, SMALLINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


BIG = BigInteger().with_variant(BIGINT(unsigned=True), "mysql")
SERIAL = BIG.with_variant(Integer, "sqlite")
UINT = Integer().with_variant(INTEGER(unsigned=True), "mysql")
USHORT = Integer().with_variant(SMALLINT(unsigned=True), "mysql")
TIME = DateTime().with_variant(DATETIME(fsp=3), "mysql")


class CanFrame(Base):
    __tablename__ = "can_frames"
    id: Mapped[int] = mapped_column(SERIAL, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64))
    boot_id: Mapped[str] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(BIG)
    can_id: Mapped[int] = mapped_column(UINT)
    extended: Mapped[bool] = mapped_column(Boolean)
    rtr: Mapped[bool] = mapped_column(Boolean)
    received_at: Mapped[datetime] = mapped_column(TIME)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        Index("uq_can_frame_sequence", "device_id", "boot_id", "sequence", unique=True),
        Index("ix_can_history", "device_id", "can_id", "extended", "id"),
        Index("ix_can_received", "received_at"),
    )


class CanLatest(Base):
    __tablename__ = "can_latest"
    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    can_id: Mapped[int] = mapped_column(UINT, primary_key=True)
    extended: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    rtr: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(TIME)
    payload: Mapped[dict] = mapped_column(JSON)
    frame_count: Mapped[int] = mapped_column(BIG, default=0)


class CanDbc(Base):
    __tablename__ = "can_dbc"
    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"))
    sha256: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(TIME)


class TelemetryReading(Base):
    __tablename__ = "telemetry_readings"
    id: Mapped[int] = mapped_column(SERIAL, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64))
    boot_id: Mapped[str] = mapped_column(String(64))
    sequence_number: Mapped[int] = mapped_column(BIG)
    timestamp_ms: Mapped[int | None] = mapped_column(BIG, nullable=True)
    observed_ms: Mapped[int] = mapped_column(BIG)
    received_at: Mapped[datetime] = mapped_column(TIME)
    persisted_at: Mapped[datetime] = mapped_column(TIME)
    analog_1: Mapped[int] = mapped_column(UINT)
    analog_2: Mapped[int] = mapped_column(UINT)
    analog_3: Mapped[int] = mapped_column(UINT)
    analog_4: Mapped[int] = mapped_column(UINT)
    analog_5: Mapped[int] = mapped_column(UINT)
    analog_6: Mapped[int] = mapped_column(UINT)
    valid_mask: Mapped[int] = mapped_column(USHORT)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        Index("uq_device_boot_sequence", "device_id", "boot_id", "sequence_number", unique=True),
        Index("ix_device_timestamp", "device_id", "timestamp_ms"),
        Index("ix_device_observed", "device_id", "observed_ms"),
        Index("ix_device_received", "device_id", "received_at", "id"),
        Index("ix_received_retention", "received_at"),
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(TIME, index=True)


class Device(Base):
    __tablename__ = "devices"
    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen: Mapped[datetime | None] = mapped_column(TIME, nullable=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(16), default="unknown")
    boot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    control_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    control_b: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Command(Base):
    __tablename__ = "commands"
    command_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(1))
    value: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reason: Mapped[str] = mapped_column(String(255), default="Awaiting device acknowledgement")
    boot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIME)
    expires_at: Mapped[datetime] = mapped_column(TIME, index=True)
    updated_at: Mapped[datetime] = mapped_column(TIME)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(SERIAL, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(TIME, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON)


class BmsJob(Base):
    __tablename__ = "bms_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TIME, index=True)
    updated_at: Mapped[datetime] = mapped_column(TIME)
    status: Mapped[str] = mapped_column(String(24))
    summary: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class BmsExchange(Base):
    __tablename__ = "bms_exchanges"
    id: Mapped[int] = mapped_column(SERIAL, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("bms_jobs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(TIME)
    details: Mapped[dict] = mapped_column(JSON)
