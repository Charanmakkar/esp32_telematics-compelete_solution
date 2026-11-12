"""Explicit synthetic device: six channels at 10 Hz and logical A/B commands."""
from __future__ import annotations

import argparse
from collections import OrderedDict
import json
import math
import os
from pathlib import Path
import re
import signal
import threading
import time
import uuid

import paho.mqtt.client as mqtt


def strict_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_command(payload: bytes, retained: bool, now_ms: int) -> tuple[dict, str | None]:
    if not 0 < len(payload) < 512:
        raise ValueError("Invalid command payload size")
    command = json.loads(payload, object_pairs_hook=strict_object)
    required = {"command_id", "key", "value", "issued_at_ms", "expires_at_ms"}
    if (not isinstance(command, dict) or set(command) != required
            or command["key"] not in ("A", "B")
            or type(command["value"]) is not int or command["value"] not in (0, 1)
            or not isinstance(command["command_id"], str)
            or not re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", command["command_id"])
            or type(command["issued_at_ms"]) is not int
            or type(command["expires_at_ms"]) is not int
            or not 0 <= command["issued_at_ms"] <= 9007199254740991
            or not 0 <= command["expires_at_ms"] <= 9007199254740991):
        raise ValueError("Invalid command schema")
    if retained:
        return command, "retained_command_forbidden"
    if command["issued_at_ms"] > now_ms + 2000:
        return command, "future_command"
    if command["expires_at_ms"] <= now_ms or command["expires_at_ms"] <= command["issued_at_ms"]:
        return command, "expired"
    if command["expires_at_ms"] - command["issued_at_ms"] > 30000:
        return command, "ttl_exceeded"
    return command, None


def load_env(path: Path) -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value.strip().strip('"'))


class SimulatedDevice:
    def __init__(self, device_id: str, host: str, port: int) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", device_id):
            raise ValueError("Invalid device ID")
        self.device_id = device_id
        self.topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "navsphere")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.topic_prefix):
            raise ValueError("Invalid MQTT topic prefix")
        self.host, self.port = host, port
        self.boot_id = str(uuid.uuid4())
        self.start = time.monotonic()
        self.connected = threading.Event()
        self.stop = threading.Event()
        self.controls = {"A": 0, "B": 0}
        self.control_deadlines = {"A": 0.0, "B": 0.0}
        self.state_lock = threading.Lock()
        self.control_timeout = float(os.getenv("SIMULATOR_CONTROL_TIMEOUT_SECONDS", "60"))
        if not math.isfinite(self.control_timeout) or not 1 <= self.control_timeout <= 3600:
            raise ValueError("Simulator control watchdog must be 1..3600 seconds")
        self.commands: OrderedDict[str, dict] = OrderedDict()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"sim-{device_id}-{self.boot_id[:8]}")
        self.client.username_pw_set(os.getenv("MQTT_DEVICE_USER", device_id),
                                    os.environ["MQTT_DEVICE_PASSWORD"])
        if os.getenv("MQTT_TLS", "false").lower() == "true":
            self.client.tls_set(ca_certs=os.getenv("MQTT_CA_CERT") or None)
        self.client.reconnect_delay_set(1, 30)
        self.client.max_queued_messages_set(20)
        self.client.max_inflight_messages_set(10)
        self.client.will_set(self.topic("status"), json.dumps({"online": False,
            "boot_id": self.boot_id, "source": "simulator"}), qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def topic(self, leaf: str) -> str:
        return f"{self.topic_prefix}/{self.device_id}/{leaf}"

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            return
        client.subscribe(self.topic("command"), qos=1)
        self.connected.set()
        self.publish_status(True)

    def publish_status(self, online: bool) -> None:
        with self.state_lock:
            controls = dict(self.controls)
        payload = {"online": online, "boot_id": self.boot_id, "source": "simulator"}
        if online:
            payload["controls"] = controls
        self.client.publish(self.topic("status"), json.dumps(payload), qos=1, retain=True)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.connected.clear()
        self.safe_reset()

    def safe_reset(self) -> None:
        with self.state_lock:
            self.controls = {"A": 0, "B": 0}
            self.control_deadlines = {"A": 0.0, "B": 0.0}

    def expire_controls(self, monotonic_now: float) -> None:
        with self.state_lock:
            for key in ("A", "B"):
                if self.control_deadlines[key] <= monotonic_now:
                    self.controls[key] = 0

    def acknowledge(self, command: dict, status: str, reason: str) -> dict:
        ack = {"command_id": command["command_id"], "key": command["key"],
               "value": command["value"], "status": status, "reason": reason,
               "boot_id": self.boot_id}
        self.client.publish(self.topic("ack"), json.dumps(ack), qos=1)
        return ack

    def on_message(self, client, userdata, message) -> None:
        try:
            if message.topic != self.topic("command"):
                return
            now = time.time_ns() // 1_000_000
            command, reason = parse_command(message.payload, bool(message.retain), now)
            if reason:
                self.acknowledge(command, "rejected", reason)
                return
            # Keep live replay guards rather than evicting them under a flood.
            expired = [identifier for identifier, entry in self.commands.items() if entry["retain_until"] < now]
            for identifier in expired:
                del self.commands[identifier]
            if command["command_id"] in self.commands:
                self.acknowledge(command, "rejected", "duplicate_command_no_reexecution")
                return
            if len(self.commands) >= 64:
                self.acknowledge(command, "rejected", "dedupe_cache_full")
                return
            self.acknowledge(command, "accepted", "validated by simulator")
            with self.state_lock:
                self.controls[command["key"]] = command["value"]
                self.control_deadlines[command["key"]] = time.monotonic() + self.control_timeout
            ack = self.acknowledge(command, "applied", "logical simulator state applied; no physical output")
            self.commands[command["command_id"]] = {"ack": ack, "retain_until": command["expires_at_ms"] + 60000}
            self.publish_status(True)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return

    def run(self, duration: float, interval: float = 0.1) -> dict:
        if not math.isfinite(duration) or duration < 0 or not math.isfinite(interval) or interval <= 0:
            raise ValueError("Duration must be finite and nonnegative; interval must be positive")
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()
        if not self.connected.wait(10):
            self.client.loop_stop()
            raise RuntimeError("Simulator could not authenticate to MQTT broker")
        sequence, dropped = 0, 0
        started = time.monotonic()
        deadline = started
        last_status = started
        try:
            while not self.stop.is_set() and (duration <= 0 or time.monotonic() - started < duration):
                now = time.monotonic()
                self.expire_controls(now)
                if self.connected.is_set() and now - last_status >= 1:
                    self.publish_status(True)
                    last_status = now
                values = [round(1650 + 1100 * math.sin((now - started) * 0.6 + i * 0.5)) for i in range(6)]
                payload = {"schema_version": 1, "device_id": self.device_id,
                    "boot_id": self.boot_id, "sequence": sequence,
                    "timestamp_ms": time.time_ns() // 1_000_000, "time_valid": True,
                    "uptime_ms": round((now - self.start) * 1000),
                    "channels": {f"analog_{i+1}": v for i, v in enumerate(values)},
                    "raw": [round(v * 4095 / 3300) for v in values], "valid_mask": 63,
                    "mqtt_connected": self.connected.is_set(), "dropped_samples": dropped,
                    "source": "simulator", "stale": False}
                if self.connected.is_set():
                    info = self.client.publish(self.topic("telemetry"), json.dumps(payload), qos=1)
                    if info.rc != mqtt.MQTT_ERR_SUCCESS:
                        dropped += 1
                else:
                    dropped += 1
                sequence += 1
                deadline += interval
                self.stop.wait(max(0, deadline - time.monotonic()))
        finally:
            self.safe_reset()
            self.publish_status(False)
            self.client.disconnect()
            self.client.loop_stop()
        return {"source": "simulator", "boot_id": self.boot_id, "samples": sequence,
                "dropped": dropped, "elapsed_seconds": round(time.monotonic()-started, 3)}


def main() -> None:
    load_env(Path(__file__).resolve().parents[1] / ".runtime" / "device.env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", default="ESP32_001")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--duration", type=float, default=0, help="seconds; zero runs until Ctrl+C")
    args = parser.parse_args()
    device = SimulatedDevice(args.device_id, args.host, args.port)
    signal.signal(signal.SIGINT, lambda *_: device.stop.set())
    print("SIMULATOR: synthetic readings and logical controls only", flush=True)
    print(json.dumps(device.run(args.duration)), flush=True)


if __name__ == "__main__":
    main()
