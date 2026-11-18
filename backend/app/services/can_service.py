"""Bounded CAN ingestion is isolated from the existing analog ingest queue."""

import asyncio
import hashlib
import json
import logging
import math
from functools import lru_cache
from queue import Empty, Full, Queue

import cantools
from pydantic import ValidationError
from sqlalchemy import select

from app.core.security import utcnow
from app.database.models import CanDbc, CanFrame, CanLatest
from app.database.repository import iso
from app.schemas.can import CanBatch
from app.services.dbc_folder import DbcFolder

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def parse_dbc(content):
    database = cantools.database.load_string(content, database_format="dbc", strict=True)
    if not database.messages or len(database.messages) > 4096:
        raise ValueError("DBC must contain 1 to 4096 messages")
    keys = [(m.frame_id, m.is_extended_frame) for m in database.messages]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate message IDs in DBC")
    if any(m.is_fd or m.length > 8 for m in database.messages):
        raise ValueError("Only classic CAN DBC messages (0 to 8 bytes) are supported")
    return database


def decode_frame(frame, database):
    if frame["rtr"]:
        return {"decode_status": "remote_request", "signals": []}
    if database is None:
        return {"decode_status": "no_dbc", "signals": []}
    key = (frame["can_id"], frame["extended"])
    source = None
    if isinstance(database, dict):
        if key in database["conflicts"]:
            return {
                "decode_status": "dbc_conflict",
                "signals": [],
                "dbc_files": database["conflicts"][key],
            }
        message = database["messages"].get(key)
        source = database["sources"].get(key)
    else:
        message = next(
            (
                m
                for m in database.messages
                if m.frame_id == frame["can_id"] and m.is_extended_frame == frame["extended"]
            ),
            None,
        )
    if message is None:
        return {"decode_status": "unknown_id", "signals": []}
    try:
        values = message.decode(
            bytes.fromhex(frame["data"]),
            decode_choices=False,
            allow_truncated=False,
            allow_excess=False,
        )
        signals = []
        raw_choices = message.decode(bytes.fromhex(frame["data"]), decode_choices=True)
        for signal in message.signals:
            if signal.name not in values:
                continue  # inactive multiplexed signal
            value = values[signal.name]
            if isinstance(value, float) and not math.isfinite(value):
                value = None
            label = str(raw_choices[signal.name]) if signal.choices else None
            signals.append(
                {"name": signal.name, "value": value, "unit": signal.unit, "label": label}
            )
        return {
            "decode_status": "decoded",
            "message_name": message.name,
            "signals": signals,
            "dbc_file": source,
        }
    except (ValueError, cantools.database.errors.DecodeError):
        return {"decode_status": "decode_error", "message_name": message.name, "signals": []}


class CanService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.queue = Queue(maxsize=512)
        self.metrics = dict(
            persisted=0,
            duplicates=0,
            invalid=0,
            dropped_batches=0,
            database_errors=0,
            database_dropped_frames=0,
        )
        self.status = {}
        self.dbc_folder = DbcFolder()

    def enqueue(self, topic, payload, retained):
        if len(payload) > 8192:
            self.metrics["invalid"] += 1
            return False
        try:
            self.queue.put_nowait((topic, payload, retained, utcnow()))
            return True
        except Full:
            self.metrics["dropped_batches"] += 1
            return False

    def take(self):
        try:
            return self.queue.get(timeout=0.2)
        except Empty:
            return None

    async def consume(self):
        while True:
            item = await asyncio.to_thread(self.take)
            if item is None:
                continue
            try:
                topic, payload, retained, received = item
                batch = CanBatch.model_validate(json.loads(payload))
                expected = f"{self.runtime.settings.mqtt_topic_prefix}/{batch.device_id}/can"
                if (
                    retained
                    or topic != expected
                    or batch.device_id not in self.runtime.settings.allowed_devices
                ):
                    raise ValueError("Invalid CAN topic/device or retained batch")
                # Retry a bounded interval. A database outage must not block analog ingestion.
                for attempt in range(4):
                    try:
                        result = await asyncio.to_thread(self.persist, batch, received)
                        break
                    except Exception:
                        self.metrics["database_errors"] += 1
                        if attempt == 3:
                            self.metrics["database_dropped_frames"] += len(batch.frames)
                            raise
                        await asyncio.sleep(0.25)
                self.metrics["persisted"] += result
                self.metrics["duplicates"] += len(batch.frames) - result
                self.status[batch.device_id] = {
                    "boot_id": batch.boot_id,
                    "received_at": iso(received),
                    **batch.stats.model_dump(),
                }
            except (ValueError, ValidationError, UnicodeDecodeError):
                self.metrics["invalid"] += 1
            except Exception:
                logger.exception("CAN database ingestion failed")
            finally:
                self.queue.task_done()

    def persist(self, batch, received):
        count = 0
        with self.runtime.db.session() as db:
            existing = set(
                db.scalars(
                    select(CanFrame.sequence).where(
                        CanFrame.device_id == batch.device_id,
                        CanFrame.boot_id == batch.boot_id,
                        CanFrame.sequence.in_([f.sequence for f in batch.frames]),
                    )
                )
            )
            for frame in batch.frames:
                if frame.sequence in existing:
                    continue
                existing.add(frame.sequence)
                payload = {
                    **frame.model_dump(),
                    "device_id": batch.device_id,
                    "boot_id": batch.boot_id,
                    "received_at": iso(received),
                }
                db.add(
                    CanFrame(
                        device_id=batch.device_id,
                        boot_id=batch.boot_id,
                        sequence=frame.sequence,
                        can_id=frame.can_id,
                        extended=frame.extended,
                        rtr=frame.rtr,
                        received_at=received,
                        payload=payload,
                    )
                )
                key = (batch.device_id, frame.can_id, frame.extended, frame.rtr)
                latest = db.get(CanLatest, key)
                if latest is None:
                    latest = CanLatest(
                        device_id=batch.device_id,
                        can_id=frame.can_id,
                        extended=frame.extended,
                        rtr=frame.rtr,
                        received_at=received,
                        payload=payload,
                        frame_count=0,
                    )
                    db.add(latest)
                latest.frame_count += 1
                if latest.received_at <= received and (
                    latest.payload["boot_id"] != batch.boot_id
                    or latest.payload["sequence"] <= frame.sequence
                ):
                    latest.payload = payload
                    latest.received_at = received
                count += 1
            db.commit()
        return count

    def dbc(self, device_id):
        library, info = self.dbc_folder.read(parse_dbc)
        if library is not None or info["errors"]:
            return library, info
        with self.runtime.db.session() as db:
            row = db.get(CanDbc, device_id)
            if row is None:
                return None, None
            return parse_dbc(row.content), {
                "filename": row.filename,
                "sha256": row.sha256,
                "updated_at": iso(row.updated_at),
            }

    def save_dbc(self, device_id, filename, content):
        database = parse_dbc(content)
        with self.runtime.db.session() as db:
            db.merge(
                CanDbc(
                    device_id=device_id,
                    filename=filename,
                    content=content,
                    sha256=hashlib.sha256(content.encode()).hexdigest(),
                    updated_at=utcnow(),
                )
            )
            db.commit()
        return {"filename": filename, "messages": len(database.messages)}
