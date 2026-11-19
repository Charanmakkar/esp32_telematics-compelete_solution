"""Validate BE reference coverage without running scripts or sending CAN commands."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.bms_catalog import BmsCatalog  # noqa: E402
from app.services.bms_client_reference import client_reference  # noqa: E402
from app.services.bms_protocol import load_hex, preset_request, validate_image_region  # noqa: E402


def main():
    catalog = BmsCatalog()
    if catalog.error:
        raise SystemExit(catalog.error)
    profile = client_reference(catalog.release)
    values = dict(text="TEST", location="TC", build="0110", date="23202", part="0123456789")
    rows = []
    for entry in catalog.presets.values():
        target = catalog.target(entry["ecu"])
        result = {k: entry[k] for k in ("id", "operation", "ecu", "app", "risk", "source_sha256")}
        result.update(tx_id=target["tx_id"], rx_id=target["rx_id"])
        try:
            raw = preset_request(entry, values)
            result["request_hex"] = raw.hex().upper() if raw else None
            if entry["operation"] == "program":
                info, segments = load_hex(catalog.release / entry["image"], client_format=True)
                validate_image_region(entry, segments)
                result["image"] = info
            catalog.security_key(entry["ecu"])
            result["preparation"] = "passed"
        except (ValueError, OSError) as exc:
            result["preparation"] = str(exc)
        rows.append(result)
    report = dict(
        time_utc=datetime.now(timezone.utc).isoformat(),
        reference=catalog.metadata,
        client={k: profile[k] for k in ("version", "sha256")},
        scripts=rows,
        scope="Static preparation only; no CAN traffic, security unlock or programming performed.",
    )
    output = ROOT / "output/testing/be-command-coverage.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    failures = [r for r in rows if r["preparation"] != "passed"]
    print(f"{len(rows)-len(failures)}/{len(rows)} scripts prepared; {len(catalog.services)} CDD services.")
    print(output)
    if failures:
        print(json.dumps(failures, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
