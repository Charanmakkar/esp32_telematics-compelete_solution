"""Exercise the running local MQTT -> FastAPI -> MySQL -> WS/REST pipeline.

Creates an isolated temporary admin account and leaves it disabled afterwards,
preserving command/audit evidence. Never changes the user's admin password.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import UTC, datetime
import json
from pathlib import Path
import secrets
import statistics
import sys
import threading
import time

import httpx
from sqlalchemy import delete, func, select
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "simulator")]

from app.core.config import Settings
from app.core.security import hash_password
from app.database.connection import Database
from app.database.models import LoginSession, TelemetryReading, User
from telemetry_simulator import SimulatedDevice, load_env


def wait_for(check, timeout: float = 12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for expected pipeline state")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not 10 <= args.duration <= 300:
        parser.error("--duration must be between 10 and 300 seconds")
    settings = Settings(_env_file=ROOT / "backend" / ".env")
    if str(settings.db_url).startswith("sqlite"):
        raise RuntimeError("Live acceptance test requires real MySQL/MariaDB")
    load_env(ROOT / ".runtime" / "device.env")
    database = Database(settings)
    username = "integration_" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    new_password = secrets.token_urlsafe(24)
    with database.session() as db:
        user = User(username=username, password_hash=hash_password(password),
                    role="admin", must_change_password=True, active=True)
        db.add(user)
        db.commit()
        user_id = user.id
    checks: list[str] = []
    samples: list[float] = []
    device = SimulatedDevice("ESP32_001", settings.mqtt_host, settings.mqtt_port)
    result: dict = {}
    worker = threading.Thread(target=lambda: result.update(device.run(args.duration)), daemon=True)
    ws = None
    socket_contexts = ExitStack()
    client = httpx.Client(base_url=args.base_url, timeout=10,
                          headers={"Origin": args.base_url.rstrip("/")})
    try:
        assert client.get("/api/v1/devices").status_code == 401
        checks.append("unauthenticated API blocked")
        response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        response.raise_for_status()
        csrf = response.json()["csrf_token"]
        assert "httponly" in response.headers["set-cookie"].lower()
        headers = {"X-CSRF-Token": csrf}
        body = {"device_id": "ESP32_001", "key": "A", "value": 1}
        assert client.post("/api/v1/commands", json=body).status_code == 403
        assert client.post("/api/v1/commands", json=body, headers=headers).status_code == 403
        checks.append("CSRF and first-login password-change gate enforced")
        response = client.post("/api/v1/auth/password", headers=headers,
            json={"current_password": password, "new_password": new_password})
        response.raise_for_status()
        worker.start()
        assert device.connected.wait(10)
        wait_for(lambda: (client.get("/api/v1/telemetry/latest", params={
            "device_id": device.device_id}).json().get("persisted") or {}).get("boot_id") == device.boot_id)
        checks.append("authenticated simulator telemetry persisted in MySQL")
        cookie_header = "; ".join(f"{key}={value}" for key, value in client.cookies.items())
        ws_url = args.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws/v1/telemetry"
        ws = socket_contexts.enter_context(connect(ws_url,
            additional_headers={"Cookie": cookie_header},
            origin=args.base_url.rstrip("/"), max_queue=16))
        seen = set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and seen != {"received", "persisted"}:
            message = json.loads(ws.recv(timeout=5))
            if (message.get("type") == "telemetry"
                    and message.get("data", {}).get("boot_id") == device.boot_id):
                assert set(message["data"]["channels"]) == {f"analog_{i}" for i in range(1, 7)}
                assert len(message["data"]["raw"]) == 6
                seen.add(message["stage"])
        assert seen == {"received", "persisted"}
        checks.append("authenticated WebSocket received and persisted stages delivered")
        ws.close()
        ws = None
        for key in ("A", "B"):
            for value in (1, 0):
                response = client.post("/api/v1/commands", headers=headers,
                    json={"device_id": device.device_id, "key": key, "value": value})
                response.raise_for_status()
                command_id = response.json()["command_id"]
                wait_for(lambda: client.get(f"/api/v1/commands/{command_id}").json().get("status") == "applied")
                assert device.controls[key] == value
        checks.append("A and B on/off commands acknowledged and verified through MQTT")
        assert client.post("/api/v1/commands", headers=headers,
            json={"device_id": device.device_id, "key": "C", "value": 1}).status_code == 422
        checks.append("invalid command rejected")
        latest = client.get("/api/v1/telemetry/latest", params={"device_id": device.device_id}).json()["persisted"]
        payload_keys = {"schema_version", "device_id", "boot_id", "sequence", "timestamp_ms",
            "time_valid", "uptime_ms", "channels", "raw", "valid_mask", "mqtt_connected",
            "dropped_samples", "source", "stale"}
        duplicate = {key: latest[key] for key in payload_keys}
        assert duplicate["boot_id"] == device.boot_id
        duplicates_before = client.get("/api/v1/health").json()["metrics"]["duplicates"]
        for _ in range(2):
            published = device.client.publish(device.topic("telemetry"), json.dumps(duplicate), qos=1)
            assert published.rc == 0
            published.wait_for_publish(timeout=3)
        wait_for(lambda: client.get("/api/v1/health").json()["metrics"]["duplicates"] >= duplicates_before + 2)
        invalid_before = client.get("/api/v1/health").json()["metrics"]["invalid"]
        device.client.publish(device.topic("telemetry"), b'{"broken":', qos=1)
        wait_for(lambda: client.get("/api/v1/health").json()["metrics"]["invalid"] > invalid_before)
        checks.append("malformed MQTT JSON counted without crashing")
        with database.session() as db:
            count = db.scalar(select(func.count()).select_from(TelemetryReading).where(
                TelemetryReading.device_id == duplicate["device_id"],
                TelemetryReading.boot_id == duplicate["boot_id"],
                TelemetryReading.sequence_number == duplicate["sequence"]))
            assert count == 1
        checks.append("QoS1 duplicate sample stored exactly once")
        while worker.is_alive():
            reading = client.get("/api/v1/telemetry/latest", params={"device_id": device.device_id}).json()["persisted"]
            if reading and reading["boot_id"] == device.boot_id:
                samples.append(time.time() * 1000 - reading["timestamp_ms"])
            time.sleep(0.1)
        worker.join(timeout=2)
        assert result.get("samples", 0) > 0, "Simulator did not finish successfully"
        def stored_this_boot():
            with database.session() as db:
                return db.scalar(select(func.count()).select_from(TelemetryReading).where(
                    TelemetryReading.device_id == device.device_id,
                    TelemetryReading.boot_id == device.boot_id))
        expected_stored = result["samples"] - result["dropped"]
        assert expected_stored > 0, "Simulator did not publish any samples"
        wait_for(lambda: stored_this_boot() == expected_stored)
        with database.session() as db:
            stored = db.scalar(select(func.count()).select_from(TelemetryReading).where(
                TelemetryReading.boot_id == device.boot_id))
            rows = db.scalars(select(TelemetryReading).where(TelemetryReading.boot_id == device.boot_id)).all()
            assert stored == result["samples"] - result["dropped"]
            assert all(len(row.payload["channels"]) == 6 and row.valid_mask == 63 for row in rows)
            insert_latencies = sorted((row.persisted_at - datetime.fromtimestamp(row.timestamp_ms / 1000, UTC).replace(tzinfo=None)).total_seconds()*1000 for row in rows)
        history = client.get("/api/v1/telemetry/history", params={"device_id":device.device_id,
            "start_ms":int(time.time()*1000-120000), "end_ms":int(time.time()*1000), "limit":100})
        history.raise_for_status()
        assert 0 < len(history.json()["points"]) <= 100
        assert len(history.json()["statistics"]) == 6
        for channel in range(1, 7):
            response = client.get(f"/api/v1/telemetry/channels/{channel}", params={"device_id":device.device_id,
                "start_ms":int(time.time()*1000-120000),"end_ms":int(time.time()*1000),"limit":100})
            response.raise_for_status()
        checks.append("six channel histories, statistics and bounded downsampling queried")
        for endpoint in ("/docs", "/redoc", "/openapi.json", "/api/v1/health/ready"):
            assert client.get(endpoint).status_code == 200
        checks.append("Swagger, ReDoc, OpenAPI and dependency readiness reachable")
        client.post("/api/v1/auth/logout", headers=headers).raise_for_status()
        assert client.get("/api/v1/auth/me").status_code == 401
        checks.append("logout invalidates session")
        sorted_samples = sorted(samples)
        result.update({"passed": True, "checks": checks, "database": "MariaDB / MySQL",
            "stored_rows": stored, "throughput_hz": round(stored / result["elapsed_seconds"], 3),
            "sample_to_insert_timestamp_ms": {"median":round(statistics.median(insert_latencies),2),
                "p95":round(insert_latencies[int((len(insert_latencies)-1)*0.95)],2), "max":round(max(insert_latencies),2)},
            "observed_latest_age_ms": {"median":round(statistics.median(samples),2) if samples else None,
                "p95":round(sorted_samples[int((len(sorted_samples)-1)*0.95)],2) if samples else None},
            "tested_at_utc":datetime.now(UTC).isoformat(), "hardware_tested":False, "timing_note":"persisted_at is assigned before INSERT/commit; latest age is observed after committed REST retrieval"})
        output = ROOT / "docs" / "testing" / "integration-results.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        if ws:
            ws.close()
        socket_contexts.close()
        device.stop.set()
        if worker.is_alive():
            worker.join(timeout=5)
        with database.session() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            user = db.get(User, user_id)
            user.active = False
            user.password_hash = hash_password(secrets.token_urlsafe(48))
            db.commit()
        database.engine.dispose()
        client.close()


if __name__ == "__main__":
    main()
