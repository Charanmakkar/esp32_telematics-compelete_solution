from datetime import UTC, datetime
from math import ceil

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import utcnow
from app.database.models import AuditEvent, Command, Device, TelemetryReading
from app.schemas.telemetry import CHANNELS, Telemetry


def iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=UTC).isoformat() if value else None


def epoch_ms(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp() * 1000)


def reading_dict(row: TelemetryReading) -> dict:
    return {
        **row.payload,
        "id": row.id,
        "received_at": iso(row.received_at),
        "persisted_at": iso(row.persisted_at),
    }


def command_dict(row: Command) -> dict:
    return {
        "command_id": row.command_id,
        "device_id": row.device_id,
        "key": row.key,
        "value": row.value,
        "status": row.status,
        "reason": row.reason,
        "boot_id": row.boot_id,
        "created_at": iso(row.created_at),
        "expires_at": iso(row.expires_at),
        "updated_at": iso(row.updated_at),
    }


def audit(db, actor: str, action: str, details: dict) -> None:
    db.add(AuditEvent(actor=actor, action=action, details=details, created_at=utcnow()))


class Repository:
    def __init__(self, database):
        self.database = database

    def persist(self, payload: Telemetry, received_at: datetime) -> dict | None:
        with self.database.session() as db:
            row = TelemetryReading(
                device_id=payload.device_id,
                boot_id=payload.boot_id,
                sequence_number=payload.sequence,
                timestamp_ms=payload.timestamp_ms,
                observed_ms=payload.timestamp_ms or epoch_ms(received_at),
                received_at=received_at,
                persisted_at=utcnow(),
                valid_mask=payload.valid_mask,
                payload=payload.model_dump(),
                **payload.channels,
            )
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                existing = db.scalar(
                    select(TelemetryReading.id).where(
                        TelemetryReading.device_id == payload.device_id,
                        TelemetryReading.boot_id == payload.boot_id,
                        TelemetryReading.sequence_number == payload.sequence,
                    )
                )
                if existing is None:
                    raise
                return None
            device = db.get(Device, payload.device_id)
            if device is not None:
                if device.boot_id != payload.boot_id:
                    device.control_a = None
                    device.control_b = None
                device.boot_id = payload.boot_id
                device.last_seen = received_at
                device.online = True
                device.source = payload.source
            db.commit()
            return reading_dict(row)

    def latest(self, device_id: str) -> dict | None:
        with self.database.session() as db:
            row = db.scalar(
                select(TelemetryReading)
                .where(TelemetryReading.device_id == device_id)
                .order_by(TelemetryReading.id.desc())
                .limit(1)
            )
            return reading_dict(row) if row else None

    def history(
        self, device_id: str, start_ms: int, end_ms: int, limit: int, channel: str | None = None
    ) -> dict:
        keys = [channel] if channel else list(CHANNELS)
        filters = (
            TelemetryReading.device_id == device_id,
            TelemetryReading.observed_ms >= start_ms,
            TelemetryReading.observed_ms <= end_ms,
        )
        expressions = {}
        for key in keys:
            bit = 1 << (int(key.split("_")[1]) - 1)
            expressions[key] = case(
                (TelemetryReading.valid_mask.op("&")(bit) != 0, getattr(TelemetryReading, key)),
                else_=None,
            )
        with self.database.session() as db:
            count = db.scalar(select(func.count()).select_from(TelemetryReading).where(*filters))
            stats_expr = []
            for key, expression in expressions.items():
                stats_expr.extend(
                    [
                        func.min(expression).label(key + "_min"),
                        func.max(expression).label(key + "_max"),
                        func.avg(expression).label(key + "_avg"),
                        func.count(expression).label(key + "_count"),
                    ]
                )
            stats = db.execute(select(*stats_expr).where(*filters)).mappings().one()
            statistics = {
                key: {
                    name: (
                        float(stats[key + "_" + name])
                        if stats[key + "_" + name] is not None
                        else None
                    )
                    for name in ("min", "max", "avg", "count")
                }
                for key in keys
            }
            if count <= limit:
                rows = db.scalars(
                    select(TelemetryReading)
                    .where(*filters)
                    .order_by(TelemetryReading.observed_ms, TelemetryReading.id)
                    .limit(limit)
                ).all()
                points = [
                    {
                        "timestamp_ms": r.observed_ms,
                        "channels": {
                            k: getattr(r, k)
                            if r.valid_mask & (1 << (int(k.split("_")[1]) - 1))
                            else None
                            for k in keys
                        },
                    }
                    for r in rows
                ]
            else:
                width = max(1, ceil((end_ms - start_ms + 1) / limit))
                bucket = func.floor((TelemetryReading.observed_ms - start_ms) / width)
                rows = db.execute(
                    select(
                        func.min(TelemetryReading.observed_ms).label("timestamp_ms"),
                        *[func.avg(e).label(k) for k, e in expressions.items()],
                    )
                    .where(*filters)
                    .group_by(bucket)
                    .order_by(bucket)
                    .limit(limit)
                ).mappings()
                points = [
                    {
                        "timestamp_ms": int(r["timestamp_ms"]),
                        "channels": {k: float(r[k]) if r[k] is not None else None for k in keys},
                    }
                    for r in rows
                ]
        return {
            "points": points,
            "statistics": statistics,
            "count": count,
            "aggregated": count > limit,
            "time_basis": "device_epoch_or_server_receive",
        }
