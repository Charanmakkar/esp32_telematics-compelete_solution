import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20) as client:
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": os.environ["NAV_TEST_PASSWORD"]})
    login.raise_for_status()
    checks = {}
    for name, url in {
        "health": "/api/v1/health",
        "ready": "/api/v1/health/ready",
        "statistics": "/api/v1/can/statistics",
        "can_history": "/api/v1/can/history?can_id=110&extended=false&limit=2",
        "analog_latest": "/api/v1/telemetry/latest",
        "bms_catalog": "/api/v1/bms/catalog",
    }.items():
        response = client.get(url)
        response.raise_for_status()
        checks[name] = response.json()
    catalog = checks.pop("bms_catalog")
    checks["catalog_counts"] = {"services": len(catalog["services"]), "presets": len(catalog["presets"])}
    assert checks["ready"]["ready"]
    assert checks["statistics"]["device"]["mode"] == "listen_only"
    assert checks["statistics"]["age_seconds"] < 5
    assert checks["can_history"]["frames"]
    assert checks["analog_latest"]["persisted"]
    checks["lan_pages"] = {}
    for page in ("can", "bms"):
        response = httpx.get("http://192.168.9.59:5173/" + page, timeout=10)
        response.raise_for_status()
        checks["lan_pages"][page] = response.status_code
    checks["lan_scope"] = "Requested through the laptop's LAN address from this laptop; remote PC not retested."
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "application_bytes": (root / "build/firmware.bin").stat().st_size,
        "application_sha256": hashlib.sha256((root / "build/firmware.bin").read_bytes()).hexdigest(),
        "flash": {"port": "COM5", "baud": 115200, "esptool_hash_verified": True},
        "diagnostic_requests_sent_by_this_check": 0,
        "software_checks": {"backend_pytest_passed": 58, "frontend_vitest_passed": 25, "ruff": "passed", "firmware_host_tests": "passed", "esp_idf_build": "passed", "typescript_vite_build": "passed"},
        "checks": checks,
    }
    (root / "output/testing/bms-post-flash-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ready": checks["ready"], "mode": checks["statistics"]["device"]["mode"], "catalog_counts": checks["catalog_counts"], "lan_pages": checks["lan_pages"], "time_utc": report["time_utc"]}))
