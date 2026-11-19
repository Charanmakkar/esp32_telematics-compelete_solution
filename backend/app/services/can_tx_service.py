"""Fixed cyclic frames, controlled independently of GPIO and UDS commands."""

from datetime import UTC, datetime
from threading import Lock
from time import monotonic, sleep, time
from uuid import uuid4

from app.core.security import utcnow
from app.database.repository import audit

PROFILES = (
    {"can_id": 0x014, "data": "006000", "dlc": 3, "period_ms": 100},
    {"can_id": 0x548, "data": "0000000000000008", "dlc": 8, "period_ms": 10},
)


class CanTxService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = Lock()
        self.last_issued = 0

    def snapshot(self, device_id):
        if device_id not in self.runtime.settings.allowed_devices:
            raise ValueError("Unknown device")
        status = self.runtime.can.status.get(device_id) or {}
        state = status.get("periodic_tx")
        telemetry = self.runtime.latest_received.get(device_id) or {}
        clock_ready = (
            telemetry.get("boot_id") == status.get("boot_id")
            and telemetry.get("time_valid") is True
        )
        age = None
        if status.get("received_at"):
            observed = datetime.fromisoformat(status["received_at"]).astimezone(UTC)
            age = max(0, (utcnow().replace(tzinfo=UTC) - observed).total_seconds())
        return {
            "profiles": PROFILES,
            "supported": state is not None,
            "clock_ready": clock_ready,
            "fresh": state is not None
            and age is not None
            and age < 5
            and self.runtime.mqtt.connected,
            "age_seconds": age,
            "boot_id": status.get("boot_id"),
            "mode": status.get("mode"),
            "state": state,
        }

    def command(self, device_id, enabled, actor):
        # One outstanding toggle; status is always device-confirmed, never optimistic.
        if not self.lock.acquire(blocking=False):
            raise ValueError("A transmission command is already awaiting confirmation")
        try:
            before = self.snapshot(device_id)
            if not before["supported"] or not before["boot_id"]:
                raise ValueError("ESP32 firmware with periodic transmission support is required")
            if enabled and (
                not before["fresh"] or before["mode"] not in ("listen_only", "periodic_tx")
            ):
                raise ValueError(
                    "ESP32 must be online with diagnostics idle before turning transmission ON"
                )
            if enabled and not before["clock_ready"]:
                raise ValueError("Waiting for the ESP32 clock to synchronize; retry shortly")
            issued = max(int(time() * 1000), self.last_issued + 1)
            self.last_issued = issued
            command = {
                "command_id": str(uuid4()),
                "boot_id": before["boot_id"],
                "enabled": enabled,
                "issued_at_ms": issued,
                "expires_at_ms": issued + 4000,
            }
            if not self.runtime.mqtt.publish_can_tx(device_id, command):
                raise ValueError("MQTT is unavailable; transmission state was not confirmed")
            with self.runtime.db.session() as db:
                audit(db, actor, "can_tx_toggle", {"device_id": device_id, **command})
                db.commit()
            deadline = monotonic() + 5
            while monotonic() < deadline:
                current = self.snapshot(device_id)
                if (
                    current["fresh"]
                    and current["boot_id"] == command["boot_id"]
                    and current["state"].get("command_id") == command["command_id"]
                ):
                    return current
                sleep(0.05)
            raise TimeoutError(
                "ESP32 confirmation timed out. Check the displayed state before retrying."
            )
        finally:
            self.lock.release()
