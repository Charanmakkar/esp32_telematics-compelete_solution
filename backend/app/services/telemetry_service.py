import asyncio
import json
import logging
from collections import deque
from contextlib import suppress
from queue import Empty, Full, Queue
from time import monotonic

from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.security import check_password, hash_password, utcnow
from app.database.connection import Database
from app.database.models import Base, Device, LoginSession, User
from app.database.repository import Repository, iso
from app.mqtt.client import MqttClient
from app.schemas.commands import CommandAck
from app.schemas.telemetry import Telemetry
from app.services.command_service import CommandService
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        self.db = Database(settings)
        self.repository = Repository(self.db)
        self.queue: Queue = Queue(maxsize=settings.ingest_queue_size)
        self.hub = WebSocketManager()
        self.mqtt = MqttClient(settings, self.enqueue)
        self.commands = CommandService(self)
        self.latest_received: dict[str, dict] = {}
        self.arrivals: deque[float] = deque(maxlen=1000)
        self.metrics = {
            "received": 0,
            "persisted": 0,
            "invalid": 0,
            "duplicates": 0,
            "dropped": 0,
            "database_errors": 0,
            "last_received_at": None,
            "last_persisted_at": None,
        }
        self.database_connected = False
        self.tasks: list[asyncio.Task] = []

    def initialize(self):
        if self.settings.auto_migrate:
            if self.settings.environment == "production":
                raise ValueError("Use Alembic migrations in production")
            Base.metadata.create_all(self.db.engine)
        with self.db.session() as db:
            if self.settings.environment == "production":
                # Stream hashes in bounded batches; do not log account names or stored hashes.
                statement = select(User.password_hash).where(User.active.is_(True))
                with db.execute(statement.execution_options(yield_per=100)) as rows:
                    for (stored_hash,) in rows:
                        if check_password("admin", stored_hash):
                            raise ValueError(
                                "Production startup refused: an active account uses the prohibited "
                                "default password. Change its password or disable the account "
                                "before deployment."
                            )
            user = db.scalar(
                select(User).where(User.username == self.settings.initial_admin_username)
            )
            if user is None:
                db.add(
                    User(
                        username=self.settings.initial_admin_username,
                        password_hash=hash_password(self.settings.initial_admin_password),
                        role="admin",
                        must_change_password=True,
                    )
                )
            for device_id in self.settings.allowed_devices:
                if db.get(Device, device_id) is None:
                    db.add(Device(device_id=device_id))
            db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow()))
            db.commit()
        self.database_connected = True

    async def start(self):
        await asyncio.to_thread(self.initialize)
        self.tasks = [asyncio.create_task(self.consume()), asyncio.create_task(self.maintenance())]
        self.mqtt.start()

    async def stop(self):
        await asyncio.to_thread(self.mqtt.stop)
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with suppress(asyncio.CancelledError):
                await task
        self.db.engine.dispose()

    def enqueue(self, topic: str, payload: bytes, retained: bool = False) -> bool:
        if len(payload) > 8192:
            self.metrics["invalid"] += 1
            return False
        try:
            self.queue.put_nowait((topic, payload, retained, utcnow()))
            return True
        except Full:
            self.metrics["dropped"] += 1
            return False

    def get_message(self):
        try:
            return self.queue.get(timeout=0.2)
        except Empty:
            return None

    async def consume(self):
        while True:
            item = await asyncio.to_thread(self.get_message)
            if item is None:
                continue
            try:
                await self.process_message(*item)
            except (ValidationError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                self.metrics["invalid"] += 1
                logger.warning("mqtt_message_rejected topic=%s", item[0])
            except Exception:
                self.metrics["database_errors"] += 1
                self.database_connected = False
                logger.exception("mqtt_processing_failed topic=%s", item[0])
            finally:
                self.queue.task_done()

    async def process_message(self, topic: str, payload: bytes, retained: bool, received_at):
        parts = topic.split("/")
        if (
            len(parts) != 3
            or parts[0] != self.settings.mqtt_topic_prefix
            or parts[1] not in self.settings.allowed_devices
        ):
            raise ValueError("Unregistered topic")
        device_id, kind = parts[1:]
        data = json.loads(payload)
        if kind == "telemetry":
            if retained:
                raise ValueError("Retained telemetry is not a fresh reading")
            reading = Telemetry.model_validate(data)
            if reading.device_id != device_id:
                raise ValueError("Topic and payload device IDs differ")
            self.metrics["received"] += 1
            self.metrics["last_received_at"] = iso(received_at)
            self.arrivals.append(monotonic())
            event = {
                **reading.model_dump(),
                "id": None,
                "received_at": iso(received_at),
                "persisted_at": None,
            }
            self.latest_received[device_id] = event
            self.hub.broadcast({"type": "telemetry", "stage": "received", "data": event})
            deadline = monotonic() + self.settings.database_retry_seconds
            while True:
                try:
                    persisted = await asyncio.to_thread(
                        self.repository.persist, reading, received_at
                    )
                    self.database_connected = True
                    break
                except Exception:
                    self.metrics["database_errors"] += 1
                    self.database_connected = False
                    if monotonic() >= deadline:
                        self.metrics["dropped"] += 1
                        logger.error("telemetry_dropped_after_database_retry device=%s", device_id)
                        return
                    await asyncio.sleep(0.25)
            if persisted is None:
                self.metrics["duplicates"] += 1
                return
            self.metrics["persisted"] += 1
            self.metrics["last_persisted_at"] = persisted["persisted_at"]
            self.hub.broadcast({"type": "telemetry", "stage": "persisted", "data": persisted})
        elif kind == "ack":
            if retained:
                raise ValueError("Retained acknowledgements are rejected")
            ack = CommandAck.model_validate(data)
            result = await asyncio.to_thread(self.commands.acknowledge, device_id, ack)
            if result is None:
                self.metrics["invalid"] += 1
            else:
                self.hub.broadcast({"type": "command", "data": result})
        elif kind == "status":
            await asyncio.to_thread(self.update_status, device_id, data)
        else:
            raise ValueError("Unsupported topic")

    def update_status(self, device_id, data):
        if not isinstance(data, dict) or type(data.get("online")) is not bool:
            raise ValueError("Status requires boolean online")
        controls = data.get("controls", {})
        if not isinstance(controls, dict):
            raise ValueError("Invalid controls")
        if any(
            k not in ("A", "B") or type(v) is not int or v not in (0, 1)
            for k, v in controls.items()
        ):
            raise ValueError("Invalid control state")
        with self.db.session() as db:
            device = db.get(Device, device_id)
            if device:
                device.online = data["online"]
                # A retained online announcement alone never makes stale hardware fresh.
                if not data["online"]:
                    device.control_a = None
                    device.control_b = None
                elif data.get("boot_id") == device.boot_id:
                    device.control_a = controls.get("A", device.control_a)
                    device.control_b = controls.get("B", device.control_b)
                db.commit()

    async def maintenance(self):
        while True:
            await asyncio.sleep(0.5)
            try:
                expired = await asyncio.to_thread(self.commands.expire)
                for command in expired:
                    self.hub.broadcast({"type": "command", "data": command})
            except Exception:
                self.database_connected = False
                self.metrics["database_errors"] += 1

    def health(self) -> dict:
        now = monotonic()
        # HTTP handlers and WebSocket heartbeats may read this concurrently.
        arrivals = [arrival for arrival in tuple(self.arrivals) if arrival >= now - 10]
        frequency = 0.0
        if len(arrivals) > 1 and now - arrivals[-1] < 2:
            frequency = (len(arrivals) - 1) / max(0.001, arrivals[-1] - arrivals[0])
        return {
            "status": "ok",
            "mqtt_connected": self.mqtt.connected,
            "database_connected": self.database_connected,
            "database_engine": self.db.engine.dialect.name,
            "metrics": {
                **self.metrics,
                "frequency_hz": round(frequency, 2),
                "queue_depth": self.queue.qsize(),
                "websocket_dropped": self.hub.dropped,
            },
        }
