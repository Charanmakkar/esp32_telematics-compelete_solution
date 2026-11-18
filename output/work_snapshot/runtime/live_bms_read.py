import os,time,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import httpx

root=Path(__file__).resolve().parents[1]
with httpx.Client(base_url="http://127.0.0.1:8000",timeout=20) as client:
    login=client.post("/api/v1/auth/login",json={"username":"admin","password":os.environ["NAV_TEST_PASSWORD"]})
    login.raise_for_status()
    client.headers["X-CSRF-Token"]=login.json()["csrf_token"]
    catalog=client.get("/api/v1/bms/catalog").json()
    entry=next(s for s in catalog["services"] if s["request_prefix"]=="22F186")
    before=client.get("/api/v1/can/statistics").json()
    preview=client.post("/api/v1/bms/preview",json=dict(device_id="ESP32_001",kind="cdd",entry_id=entry["id"],instance=0))
    preview.raise_for_status()
    assert preview.json()["risk"]=="read"
    job=client.post("/api/v1/bms/jobs",json={"token":preview.json()["token"]})
    job.raise_for_status()
    job_id=job.json()["id"]
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        result=client.get("/api/v1/bms/jobs/"+job_id).json()
        if result["status"] not in ("queued","running"):break
        time.sleep(.25)
    time.sleep(2)
    after=client.get("/api/v1/can/statistics").json()
    health=client.get("/api/v1/health").json()
    report=dict(time=datetime.now(timezone.utc).isoformat(),
                firmware_sha256=hashlib.sha256((root/"build/firmware.bin").read_bytes()).hexdigest(),
                read_only_request="22F186",instance=0,job=result,
                stats_before=before,stats_after=after,health=health,
                destructive_tests_run=False)
    (root/"output/testing/bms-live-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(dict(job_id=job_id,status=result["status"],result=result["result"],
                         exchanges=len(result["exchanges"]),can_mode=after.get("device",{}).get("mode"),
                         hardware_fps=after.get("hardware_fps"),delivered_fps=after.get("received_fps"),
                         health=health["status"]),indent=2))
