"""OTA over the existing authenticated MQTT connection; stop-and-wait chunks."""

import json
import logging
import re
import threading
from ipaddress import IPv4Address
from queue import Empty, Full, Queue
from time import monotonic, time
from uuid import uuid4

from app.database.repository import audit
from app.services.ota_image import MAX_IMAGE, MAX_UPLOAD, inspect_image

logger = logging.getLogger(__name__)


class DeviceRejected(ValueError):
    pass


class OtaService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.queue = Queue(maxsize=64)
        self.acks = Queue(maxsize=16)
        self.devices = {}
        self.prepared = None
        self.job = None
        self.worker = None
        self.receiver = None

    def start(self):
        self.receiver = threading.Thread(target=self.consume, daemon=True, name="ota-status")
        self.receiver.start()

    def stop(self):
        self.stopping.set()
        for thread in (self.worker, self.receiver):
            if thread:
                thread.join(timeout=5)

    def enqueue(self, topic, payload, retained):
        if retained or len(payload) > 2048:
            return False
        try:
            self.queue.put_nowait((topic, payload))
            return True
        except Full:
            return False

    def consume(self):
        while not self.stopping.is_set():
            try:
                topic, payload = self.queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                self.receive(topic, payload)
            except (ValueError, TypeError, KeyError, UnicodeError):
                logger.warning("Invalid OTA status rejected")

    def receive(self, topic, payload):
        parts = topic.split("/")
        if (
            len(parts) != 4
            or parts[0] != self.runtime.settings.mqtt_topic_prefix
            or parts[2] != "ota"
        ):
            raise ValueError("Invalid OTA topic")
        device = parts[1]
        self.check_device(device)
        data = json.loads(payload)
        if (
            not isinstance(data, dict)
            or data.get("protocol") != 1
            or data.get("source") != "hardware"
        ):
            raise ValueError("Invalid OTA payload")
        if parts[3] == "status":
            if not isinstance(data.get("boot_id"), str) or len(data["boot_id"]) != 36:
                raise ValueError("Invalid boot identity")
            if (
                not isinstance(data.get("image_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", data["image_sha256"])
                or type(data.get("confirmed")) is not bool
                or type(data.get("slot_size")) is not int
                or not 0 <= data["slot_size"] <= 0x1F0000
                or not isinstance(data.get("version"), str)
                or len(data["version"]) > 31
                or data.get("state") not in ("idle", "transferring")
            ):
                raise ValueError("Invalid chip status")
            if "ip_address" in data:
                if not isinstance(data["ip_address"], str):
                    raise ValueError("Invalid IP address")
                IPv4Address(data["ip_address"])
            if "wifi_rssi_dbm" in data and (
                type(data["wifi_rssi_dbm"]) is not int or not -127 <= data["wifi_rssi_dbm"] <= 0
            ):
                raise ValueError("Invalid Wi-Fi signal")
            if "uptime_ms" in data and (
                type(data["uptime_ms"]) is not int or not 0 <= data["uptime_ms"] < 2**53
            ):
                raise ValueError("Invalid uptime")
            if "mqtt_tls" in data and type(data["mqtt_tls"]) is not bool:
                raise ValueError("Invalid transport status")
            if "max_chunk_bytes" in data and (
                type(data["max_chunk_bytes"]) is not int
                or not 768 <= data["max_chunk_bytes"] <= 2048
            ):
                raise ValueError("Invalid OTA chunk capacity")
            with self.lock:
                self.devices[device] = (monotonic(), data)
                job = self.job
                if (
                    job
                    and job["device_id"] == device
                    and job["state"] in ("rebooting", "unconfirmed")
                ):
                    if data["boot_id"] != job["boot_id"] and data.get("confirmed") is True:
                        if (
                            data.get("image_sha256") == job["image"]["image_sha256"]
                            and data.get("version") == job["image"]["version"]
                        ):
                            job.update(
                                state="confirmed",
                                message="The chip rebooted and confirmed the uploaded image",
                                progress=100,
                            )
                        else:
                            job.update(
                                state="failed",
                                message="The chip is running a different image; possible rollback",
                            )
        elif parts[3] == "response":
            with self.lock:
                if (
                    not self.job
                    or device != self.job["device_id"]
                    or data.get("id") != self.job["id"]
                    or data.get("boot_id") != self.job["boot_id"]
                ):
                    return
            try:
                self.acks.put_nowait(data)
            except Full:
                pass

    def check_device(self, device):
        if device not in self.runtime.settings.allowed_devices:
            raise ValueError("Unknown device")

    def snapshot(self, device):
        self.check_device(device)
        with self.lock:
            seen, chip = self.devices.get(device, (0, None))
            age = monotonic() - seen if chip else None
            prepared = self.prepared
            return {
                "device_id": device,
                "chip": chip,
                "age_seconds": age,
                "fresh": chip is not None and age < 6 and self.runtime.mqtt.connected,
                "prepared": prepared["info"]
                if prepared
                and prepared["device_id"] == device
                and monotonic() < prepared["expires"]
                else None,
                "job": json.loads(json.dumps(self.job))
                if self.job and self.job["device_id"] == device
                else None,
                "busy": bool(self.worker and self.worker.is_alive()),
                "limits": {"max_application_bytes": MAX_IMAGE, "max_upload_bytes": MAX_UPLOAD},
                "transport": {"server_mqtt_tls": self.runtime.settings.mqtt_tls},
            }

    def prepare(self, device, filename, raw):
        self.check_device(device)
        data, info = inspect_image(filename, raw)
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("An update is already running")
            info["upload_id"] = str(uuid4())
            self.prepared = {
                "info": info,
                "data": data,
                "device_id": device,
                "expires": monotonic() + 600,
            }
            return info

    def begin(self, device, upload_id, actor):
        with self.lock:
            status = self.snapshot(device)
            chip = status["chip"] or {}
            if status["busy"]:
                raise ValueError("An update is already running")
            if not status["fresh"] or chip.get("confirmed") is not True:
                raise ValueError(
                    "Waiting for OTA-ready firmware from the chip; install the USB migration first"
                )
            if chip.get("state") != "idle":
                raise ValueError("The device is still processing an update; wait for idle status")
            prepared = self.prepared
            if not status["prepared"] or status["prepared"]["upload_id"] != upload_id:
                raise ValueError("Upload expired or replaced; select the file again")
            info = prepared["info"]
            if info["size"] > chip.get("slot_size", 0):
                raise ValueError("Image exceeds the chip's OTA slot")
            if info["image_sha256"] == chip.get("image_sha256"):
                raise ValueError("The chip is already running this exact image")
            self.job = {
                "id": str(uuid4()),
                "device_id": device,
                "boot_id": chip["boot_id"],
                "image": info,
                "state": "starting",
                "progress": 0,
                "message": "Waiting for the chip to accept the update",
                "actor": actor,
                "chunk_bytes": chip.get("max_chunk_bytes", 768),
            }
            with self.runtime.db.session() as db:
                audit(db, actor, "ota_start", self.job)
                db.commit()
            self.worker = threading.Thread(
                target=self.transfer, args=(prepared["data"],), daemon=True, name="ota-transfer"
            )
            self.worker.start()
            return dict(self.job)

    def exchange(self, op, **values):
        job = self.job
        packet = {"id": job["id"], "boot_id": job["boot_id"], "op": op, **values}
        for _ in range(3):
            if self.stopping.is_set():
                raise ValueError("Backend stopped; device will discard the incomplete transfer")
            if not self.runtime.mqtt.publish_ota(job["device_id"], packet):
                raise ValueError("MQTT disconnected")
            deadline = monotonic() + 5
            while monotonic() < deadline and not self.stopping.is_set():
                try:
                    response = self.acks.get(timeout=0.2)
                except Empty:
                    continue
                if response.get("op") != op or response.get("offset") != values.get("offset", 0):
                    continue
                if not response.get("ok"):
                    raise DeviceRejected(response.get("error", "Device rejected the update"))
                return response
        raise TimeoutError("No acknowledgement from the chip; incomplete transfer will time out")

    def transfer(self, data):
        try:
            self.exchange(
                "start",
                size=len(data),
                sha256=self.job["image"]["sha256"],
                # Leave clock-skew margin below the chip's 30-second maximum.
                expires_at_ms=int(time() * 1000) + 15000,
            )
            with self.lock:
                self.job.update(state="transferring", message="Writing the inactive firmware slot")
            chunk_bytes = self.job.get("chunk_bytes", 768)
            for offset in range(0, len(data), chunk_bytes):
                chunk = data[offset : offset + chunk_bytes]
                self.exchange("chunk", offset=offset, data=chunk.hex())
                with self.lock:
                    self.job["progress"] = round((offset + len(chunk)) * 100 / len(data), 1)
            with self.lock:
                self.job.update(
                    state="rebooting",
                    message="Waiting for the chip to reboot and confirm its running image",
                )
            try:
                self.exchange("finish")
            except DeviceRejected:
                raise
            except (TimeoutError, ValueError):
                # The device can reboot before the final ACK reaches the backend.
                pass
            deadline = monotonic() + 180
            while monotonic() < deadline and not self.stopping.wait(0.2):
                with self.lock:
                    if self.job["state"] != "rebooting":
                        break
            with self.lock:
                if self.job["state"] == "rebooting":
                    self.job.update(
                        state="unconfirmed",
                        message="Not confirmed. Check device power/Wi-Fi before retrying.",
                    )
        except Exception as exc:
            with self.lock:
                self.job.update(state="failed", message=str(exc))
        finally:
            with self.lock:
                self.prepared = None
                result = dict(self.job)
            try:
                with self.runtime.db.session() as db:
                    audit(db, result["actor"], "ota_result", result)
                    db.commit()
            except Exception:
                logger.exception("Could not record OTA result")
