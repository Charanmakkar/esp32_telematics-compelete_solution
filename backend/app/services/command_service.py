from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import utcnow
from app.database.models import Command, Device
from app.database.repository import audit, command_dict, epoch_ms
from app.schemas.commands import CommandAck, CommandRequest


class CommandService:
    def __init__(self, runtime):
        self.runtime = runtime

    def submit(self, request: CommandRequest, user) -> dict:
        rt = self.runtime
        if request.device_id not in rt.settings.allowed_devices:
            raise HTTPException(404, "Unknown device")
        if not rt.mqtt.connected:
            raise HTTPException(503, "MQTT broker is disconnected")
        with rt.db.session() as db:
            device = db.get(Device, request.device_id)
            if (
                device is None
                or not device.online
                or device.last_seen is None
                or (utcnow() - device.last_seen).total_seconds() > rt.settings.device_stale_seconds
            ):
                raise HTTPException(409, "Device is offline or stale")
            now = utcnow()
            command = Command(
                command_id=str(uuid4()),
                device_id=request.device_id,
                key=request.key,
                value=request.value,
                status="pending",
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(seconds=rt.settings.command_timeout_seconds),
                user_id=user.id,
                boot_id=device.boot_id,
                reason="Awaiting device acknowledgement",
            )
            db.add(command)
            audit(
                db,
                user.username,
                "command_requested",
                {
                    "command_id": command.command_id,
                    **request.model_dump(),
                },
            )
            db.commit()
            sent = rt.mqtt.publish_command(
                request.device_id,
                {
                    "command_id": command.command_id,
                    "key": request.key,
                    "value": request.value,
                    "issued_at_ms": epoch_ms(now),
                    "expires_at_ms": epoch_ms(command.expires_at),
                },
            )
            if not sent:
                command.status = "rejected"
                command.reason = "MQTT publication failed"
                command.updated_at = utcnow()
                db.commit()
            return command_dict(command)

    def acknowledge(self, device_id: str, ack: CommandAck) -> dict | None:
        with self.runtime.db.session() as db:
            row = db.get(Command, ack.command_id)
            if (
                row is None
                or row.device_id != device_id
                or row.key != ack.key
                or row.value != ack.value
                or (row.boot_id and row.boot_id != ack.boot_id)
            ):
                return None
            if row.status in ("applied", "rejected", "timed_out"):
                return None
            if row.expires_at < utcnow():
                row.status = "timed_out"
                row.reason = "Device acknowledgement arrived after deadline"
            else:
                if row.status == "accepted" and ack.status == "accepted":
                    return None
                row.status = ack.status
                row.reason = ack.reason or f"Device {ack.status} command"
                if ack.status == "applied":
                    device = db.get(Device, device_id)
                    if device:
                        setattr(device, "control_a" if ack.key == "A" else "control_b", ack.value)
            row.updated_at = utcnow()
            audit(
                db,
                device_id,
                "command_ack",
                {"command_id": row.command_id, "status": row.status, "reason": row.reason},
            )
            db.commit()
            return command_dict(row)

    def expire(self) -> list[dict]:
        with self.runtime.db.session() as db:
            rows = db.scalars(
                select(Command)
                .where(Command.status.in_(("pending", "accepted")), Command.expires_at < utcnow())
                .limit(500)
            ).all()
            for row in rows:
                row.status = "timed_out"
                row.reason = "No final device acknowledgement before deadline"
                row.updated_at = utcnow()
                audit(db, "system", "command_timeout", {"command_id": row.command_id})
            db.commit()
            return [command_dict(r) for r in rows]
