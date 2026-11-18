import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Full, Queue

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.security import utcnow
from app.database.models import BmsExchange, BmsJob
from app.database.repository import iso
from app.services.bms_catalog import PROJECT, BmsCatalog, decode_fields, encode_fields
from app.services.bms_client_reference import client_reference
from app.services.bms_client_workflows import (
    authenticate_bootloader,
    prepare_mode,
    program_client_image,
    unlock,
)
from app.services.bms_protocol import (
    decode_preset,
    load_hex,
    preset_request,
    validate_image_region,
    validate_response,
)


class BmsService:
    def __init__(self, runtime):
        self.rt = runtime
        self.catalog = BmsCatalog(runtime.settings.bms_reference_root)
        self.lock = threading.RLock()
        self.previews = {}
        self.pending = {}
        self.active = {}
        self.queue = Queue(maxsize=128)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bms")
        self.last_issued = 0
        self.stopping = False

    def initialize(self):
        with self.rt.db.session() as db:
            db.execute(
                update(BmsJob)
                .where(BmsJob.status.in_(["queued", "running"]))
                .values(
                    status="interrupted",
                    updated_at=utcnow(),
                    result={
                        "message": (
                            "Server restarted; request was not replayed. ESP32 returns to "
                            "listen-only after its lease expires."
                        )
                    },
                )
            )
            db.commit()

    def enqueue(self, topic, payload, retained):
        if retained or len(payload) > 9000:
            return False
        try:
            self.queue.put_nowait((topic, payload))
            return True
        except Full:
            return False

    async def consume(self):
        while True:
            try:
                topic, payload = self.queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.01)
                continue
            try:
                message = json.loads(payload)
                if not isinstance(message, dict):
                    continue
                with self.lock:
                    item = self.pending.get(message.get("id"))
                    if item and topic == item["topic"] and message.get("boot_id") == item["boot"]:
                        item["reply"] = message
                        item["event"].set()
            except (ValueError, TypeError):
                pass
            finally:
                self.queue.task_done()

    def quick_read(self, body, actor):
        command = body["command"]
        if command not in ("qr", "serial", "hardware", "manufacturing", "mode"):
            raise ValueError("Unknown quick read")
        prepared = self.prepare(
            dict(
                device_id=body["device_id"],
                instance=body["instance"],
                ecu=body.get("ecu", "abs_hv"),
                kind="preset",
                entry_id="abs_cust_hw_part_number_read",
            ),
            actor,
            quick_command=command,
        )
        return self.submit(prepared["token"], "", actor)

    def prepare(self, body, actor, quick_command=None):
        if self.catalog.error:
            raise ValueError(self.catalog.error)
        device = body["device_id"]
        if device not in self.rt.settings.allowed_devices:
            raise ValueError("Unknown device")
        kind = body["kind"]
        entry = (self.catalog.services if kind == "cdd" else self.catalog.presets).get(
            body["entry_id"]
        )
        if entry is None:
            raise ValueError("Unknown reference command")
        if quick_command:
            did, name = {
                "qr": (0xC000, "Read QR code"),
                "serial": (0xF18C, "Read serial number"),
                "hardware": (0xF191, "Read hardware part number"),
                "manufacturing": (0xFD20, "Read manufacturing serial"),
                "mode": (0xF010, "Read BMS mode"),
            }[quick_command]
            entry = {
                **entry,
                "id": "quick_" + quick_command,
                "did": did,
                "name": name,
                "app": True,
                "operation": "read",
                "risk": "read",
                "notes": [],
                "fixed_instance": None,
                "ecu": body.get("ecu", "abs_hv"),
                "source": "AMP 15.0.4 application-mode read",
            }
        profile = client_reference(self.catalog.release) if kind == "preset" else None
        values = body.get("values", {})
        target = entry.get("fixed_instance")
        if target is None:
            target = body.get("instance", 1)
        if not 0 <= target <= 15:
            raise ValueError("Instance must be 0–15")
        ecu = entry["ecu"] if kind == "preset" else body.get("ecu", "abs_hv")
        address = self.catalog.target(ecu, target)
        request = (
            encode_fields(entry["request_fields"], values)
            if kind == "cdd"
            else preset_request(entry, values)
        )
        image, segments = None, None
        if kind == "preset" and entry["operation"] == "program":
            override = body.get("image_filename", "").strip()
            if override:
                if any(c in override for c in ("/", "\\", ":")) or not override.lower().endswith(
                    ".hex"
                ):
                    raise ValueError("Choose a .hex filename inside bms_images")
                path = (PROJECT / "bms_images" / override).resolve()
                if path.parent != (PROJECT / "bms_images").resolve():
                    raise ValueError("Invalid image path")
            else:
                path = self.catalog.release / entry["image"]
            image, segments = load_hex(
                path, client_format=True, inject_crc=body.get("inject_crc", False)
            )
            validate_image_region(entry, segments)
        session = body.get("session", 0)
        security = body.get("security", 0)
        if kind == "preset":
            if entry["operation"] in ("program", "erase_app"):
                session, security = 2, 1
            elif entry["operation"] in ("write", "mute", "unmute", "clear_dtc"):
                session, security = entry["session"] or 2, 3 if entry["app"] else 1
            else:
                session, security = 0, 0  # The EXE does not switch sessions for DID reads.
        if session not in (0, 1, 2, 3) or security not in (0, 1, 3, 5):
            raise ValueError("Unsupported session/security level")
        if security and not session:
            raise ValueError("Choose the session required by the security level")
        risk = entry["risk"]
        if kind == "preset" and not entry["app"]:
            risk = "critical"  # Even a non--app read performs a reset/bootloader trap.
        if risk == "read" and (session == 2 or security):
            risk = "change"
        sensitive = entry.get("sensitive", False)
        notes = list(entry["notes"])
        if kind == "preset":
            if entry["operation"] in ("mute", "unmute"):
                risk = "critical"
                notes.append(
                    (
                        "Original client broadcasts setup and 28 81 / 28 80 using CAN ID"
                        " 0x7DF. This can affect every BMS on the bus; only the selected"
                        " response ID is observed. Positive command response is suppressed."
                    )
                )
            if entry["did"] == 0xFD20:
                notes.append(
                    (
                        "Reference FD20 is a placeholder: reads return example values and "
                        "writes do not persist. Bytes 0–10 are zero; remaining digit "
                        "groups use reversed unpacked BCD."
                    )
                )
            if entry["operation"] in ("program", "erase_app"):
                notes.append(
                    (
                        "AMP 15.0.4: programming session 02, security level 01; downloads"
                        " additionally verify the bootloader using a challenge/response."
                        " Uses FF00/0210/0211 for app or 0201/0212/0213 for calibration."
                        " These differ from the supplied ECU source. A rejection stops the job."
                    )
                )
            if entry["app"]:
                notes.append(
                    (
                        "Application-mode preparation sends a two-second TesterPresent"
                        " burst and waits 600 ms, matching the original client."
                    )
                )
            else:
                notes.append(
                    "This exact script resets the BMS and traps its bootloader before the "
                    "command. Use Quick reads to read without resetting."
                )
            if entry["operation"] == "program":
                reset_after = not entry["app"] or entry["image_kind"] == "cal"
                notes.append(
                    "BMS resets after successful programming."
                    if reset_after
                    else "This application-mode image workflow does not reset after programming."
                )
            if security:
                self.catalog.security_key(ecu)  # Validate before queuing any state change.
        summary = dict(
            name=entry["name"],
            action=entry.get("action", entry.get("operation")),
            source=entry["source"],
            kind=kind,
            entry_id=entry["id"],
            device_id=device,
            instance=target,
            ecu=ecu,
            tx_id=0x7DF
            if kind == "preset" and entry["operation"] in ("mute", "unmute")
            else address["tx_id"],
            rx_id=address["rx_id"],
            session=session,
            security=security,
            risk=risk,
            sensitive=sensitive,
            request_hex="[redacted]" if sensitive else request.hex().upper() if request else None,
            image=image,
            notes=notes,
            cdd_sha256=self.catalog.metadata["cdd_sha256"],
            client_version=profile["version"] if profile else None,
            client_sha256=profile["sha256"] if profile else None,
            image_id=body.get("image_id", 0),
        )
        token = str(uuid.uuid4())
        with self.lock:
            self.previews = {
                k: v for k, v in self.previews.items() if v["expires"] > time.monotonic()
            }
            if len(self.previews) >= 128:
                raise ValueError("Too many previews; wait briefly")
            self.previews[token] = dict(
                actor=actor,
                expires=time.monotonic() + 300,
                entry=entry,
                summary=summary,
                request=request,
                segments=segments,
                values=values,
            )
        return dict(
            token=token,
            expires_seconds=300,
            confirmation="CONFIRM" if risk != "read" else "",
            **summary,
        )

    def submit(self, token, confirmation, actor):
        with self.lock:
            preview = self.previews.get(token)
            if not preview or preview["actor"] != actor or preview["expires"] <= time.monotonic():
                raise ValueError("Preview expired; preview the request again")
            summary = preview["summary"]
            device = summary["device_id"]
            if summary["risk"] != "read" and confirmation != "CONFIRM":
                raise ValueError("Type CONFIRM after reviewing the request")
            if self.stopping or device in self.active:
                raise ValueError("Another diagnostic job is active for this device")
            stats = self.rt.can.statistics.snapshot(device)
            if (
                not self.rt.mqtt.connected
                or not stats.get("available")
                or stats["age_seconds"] > 5
                or not stats["device"].get("diag_supported")
            ):
                raise ValueError(
                    (
                        "Connect an ESP32 running diagnostic-enabled firmware and wait for"
                        " fresh CAN status"
                    )
                )
            if (stats["device"].get("diag_version") or 0) < 3:
                raise ValueError("Flash the updated ESP32 firmware for automatic AMP workflows")
            job_id = str(uuid.uuid4())
            stop = threading.Event()
            with self.rt.db.session() as db:
                db.add(
                    BmsJob(
                        id=job_id,
                        device_id=device,
                        actor=actor,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                        status="queued",
                        summary=summary,
                        result={"message": "Waiting to start"},
                    )
                )
                db.commit()
            del self.previews[token]
            self.active[device] = (job_id, stop)
            self.executor.submit(self._run, job_id, preview, stats["boot_id"], stop)
            return self.detail(job_id)

    def _update(self, job_id, status, result):
        with self.rt.db.session() as db:
            row = db.get(BmsJob, job_id)
            row.status = status
            row.result = result
            row.updated_at = utcnow()
            db.commit()

    def _send(
        self,
        job_id,
        summary,
        boot,
        data=None,
        timeout=5000,
        close=False,
        expect_response=True,
        repeat=1,
    ):
        command = str(uuid.uuid4())
        with self.lock:
            self.last_issued = max(int(time.time() * 1000), self.last_issued + 1)
            issued = self.last_issued
            waiter = dict(
                event=threading.Event(),
                reply=None,
                boot=boot,
                topic=f"{self.rt.settings.mqtt_topic_prefix}/{summary['device_id']}/diagnostic/response",
            )
            self.pending[command] = waiter
        body = dict(
            id=command,
            lease=job_id,
            boot_id=boot,
            op="close" if close else "request",
            issued_ms=issued,
            expires_ms=issued + 5000,
            tx_id=summary["tx_id"],
            rx_id=summary["rx_id"],
            expect_response=expect_response,
            repeat=repeat,
            timeout_ms=timeout,
            data=data.hex().upper() if data else "",
        )
        started = time.monotonic()
        sensitive = bool(data and (data[0] == 0x27 or data[:3] == b"\x2e\xf1\x6a"))
        trace = dict(
            command_id=command,
            tx_id=summary["tx_id"],
            rx_id=summary["rx_id"],
            request_hex="[redacted]" if sensitive else body["data"],
            operation=body["op"],
            expect_response=expect_response,
            repeat=repeat,
        )
        try:
            if not self.rt.mqtt.publish_diagnostic(summary["device_id"], body):
                raise ValueError("MQTT publication failed; request not retried")
            if not waiter["event"].wait(timeout / 1000 + 3):
                raise ValueError("ESP32 response timed out; request not retried")
            reply = waiter["reply"]
            trace.update(
                response_hex="[redacted]" if sensitive else reply.get("response_hex", ""),
                pending_count=reply.get("pending_count", 0),
            )
            if reply.get("status") != "completed":
                reason = str(reply.get("error", "Diagnostic transport failed"))[:200]
                messages = {
                    "can_transmit_failed": (
                        "CAN transmission failed. Check TXD wiring, STB, power, termination "
                        "and an acknowledging node. No request retry was sent."
                    ),
                    "response_timeout": (
                        "No complete BMS response before the timeout. Check target instance, "
                        "BMS power and CAN errors. No request retry was sent."
                    ),
                }
                raise ValueError(messages.get(reason, reason))
            raw = bytes.fromhex(reply.get("response_hex", ""))
            if not close and expect_response:
                validate_response(data, raw)
            trace["status"] = "completed"
            return raw
        except Exception as exc:
            trace.update(status="failed", error=str(exc)[:200])
            raise
        finally:
            with self.lock:
                self.pending.pop(command, None)
            trace["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            with self.rt.db.session() as db:
                db.add(BmsExchange(job_id=job_id, created_at=utcnow(), details=trace))
                db.commit()

    def _run(self, job_id, preview, boot, stop):
        summary, entry = preview["summary"], preview["entry"]
        result = {"message": "Starting diagnostic job"}
        status = "failed"

        def progress(message):
            self._update(job_id, "running", dict(message=message))

        def exchange(data, timeout=5000, expect_response=True, repeat=1):
            if stop.is_set():
                raise ValueError("Cancelled before next request")
            return self._send(
                job_id, summary, boot, data, timeout, expect_response=expect_response, repeat=repeat
            )

        def pause(seconds):
            if stop.wait(seconds):
                raise ValueError("Cancelled before next request")

        try:
            progress("Preparing diagnostic session")
            if summary["kind"] == "preset":
                prepare_mode(entry, exchange, pause)
            if summary["session"]:
                exchange(bytes([0x10, summary["session"]]))
            if summary["security"]:
                unlock(exchange, summary["security"], self.catalog.security_key(summary["ecu"]))
            if summary["kind"] == "preset" and entry["operation"] in ("program", "erase_app"):
                if entry["operation"] == "program":
                    progress("Authenticating the BMS bootloader before erasure")
                    authenticate_bootloader(
                        exchange, client_reference(self.catalog.release)["boot_auth_key"]
                    )
                config = json.loads((self.catalog.release / "client" / "config.json").read_text())
                reset_after = not entry["app"] or entry.get("image_kind") == "cal"
                program_client_image(
                    exchange,
                    preview["segments"] or [],
                    entry.get("image_kind") or "app",
                    progress,
                    stop.is_set,
                    image_id=summary["image_id"],
                    data_only_block_length=bool(
                        config["ecus"][summary["ecu"]].get("use_data_only_block_length", False)
                    ),
                    reset_after=reset_after,
                    pause=pause,
                )
                result = (
                    {
                        "message": "Programming checks passed; BMS reset acknowledged"
                        if reset_after
                        else "Programming checks passed; script does not request a final reset"
                    }
                    if preview["segments"]
                    else {"message": "Erase completed"}
                )
            else:
                progress("Waiting for BMS response")
                expect = not (
                    summary["kind"] == "preset" and entry["operation"] in ("mute", "unmute")
                )
                raw = exchange(preview["request"], timeout=10000, expect_response=expect)
                if summary["sensitive"]:
                    decoded, warnings = [], ["Sensitive response is not stored or shown."]
                elif summary["kind"] == "cdd":
                    decoded, warnings = decode_fields(entry["response_fields"], raw)
                else:
                    decoded, warnings = decode_preset(entry, raw)
                result = dict(
                    message="BMS returned a positive response"
                    if expect
                    else (
                        "CAN transmission confirmed. This client command suppresses a positive "
                        "response; execution cannot be confirmed from an acknowledgement."
                    ),
                    response_expected=expect,
                    response_hex="[redacted]" if summary["sensitive"] else raw.hex().upper(),
                    decoded=decoded,
                    warnings=warnings,
                )
                if entry.get("verify_instance"):
                    summary = {
                        **summary,
                        "tx_id": 0x640 + int(preview["values"]["instance"]),
                        "rx_id": 0x650 + int(preview["values"]["instance"]),
                    }
                    prepare_mode({"app": True}, exchange, pause)
                    verified = exchange(b"\x22\xf0\x13")
                    if int.from_bytes(verified[3:], "big") != int(preview["values"]["instance"]):
                        raise ValueError(
                            (
                                "Instance write acknowledged, but readback did not match; "
                                "application may have learned its ADC strap ID"
                            )
                        )
                    result["message"] = "Instance write and readback verified"
            status = "completed"
        except Exception as exc:
            result = {"message": str(exc)[:300]}
            status = "cancelled" if stop.is_set() else "failed"
        finally:
            try:
                self._send(job_id, summary, boot, close=True, timeout=1000)
                result["listen_only_restored"] = True
            except Exception:
                result["listen_only_restored"] = False
                result["restore_note"] = (
                    "Close was not acknowledged. Firmware returns to listen-only on "
                    "disconnect or after 15 seconds idle; check CAN statistics."
                )
            try:
                self._update(job_id, status, result)
            finally:
                with self.lock:
                    self.active.pop(summary["device_id"], None)

    def cancel(self, job_id):
        with self.lock:
            for ident, event in self.active.values():
                if ident == job_id:
                    event.set()
                    return {
                        "message": "Cancellation requested; current bounded exchange will finish"
                    }
        raise ValueError("Job is no longer active")

    def detail(self, job_id, offset=0):
        with self.rt.db.session() as db:
            row = db.get(BmsJob, job_id)
            if row is None:
                raise HTTPException(404, "Unknown BMS job")
            exchanges = db.scalars(
                select(BmsExchange)
                .where(BmsExchange.job_id == job_id)
                .order_by(BmsExchange.id)
                .offset(offset)
                .limit(200)
            ).all()
            return dict(
                id=row.id,
                device_id=row.device_id,
                actor=row.actor,
                created_at=iso(row.created_at),
                updated_at=iso(row.updated_at),
                status=row.status,
                summary=row.summary,
                result=row.result,
                exchanges=[dict(created_at=iso(r.created_at), **r.details) for r in exchanges],
                offset=offset,
            )

    def recent(self, device):
        with self.rt.db.session() as db:
            rows = db.scalars(
                select(BmsJob)
                .where(BmsJob.device_id == device)
                .order_by(BmsJob.created_at.desc())
                .limit(50)
            ).all()
            return [
                dict(id=r.id, name=r.summary["name"], status=r.status, created_at=iso(r.created_at))
                for r in rows
            ]

    def stop(self):
        self.stopping = True
        with self.lock:
            for _, event in self.active.values():
                event.set()
        self.executor.shutdown(wait=True, cancel_futures=False)
