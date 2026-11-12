"""Generate a secret NVS image from environment without printing credentials.

Run using ESP-IDF Python. Flashing is deliberately a separate manual operation.
The image replaces the nvs partition; preserve an existing device's NVS first.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    idf = Path(os.environ.get("IDF_PATH", r"C:\esp\v6.0.2\esp-idf"))
    generator = idf / "components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py"
    values = {
        "wifi_ssid": ("NAV_WIFI_SSID", 32),
        "wifi_pass": ("NAV_WIFI_PASSWORD", 64),
        "mqtt_uri": ("NAV_MQTT_URI", 159),
        "mqtt_user": ("NAV_MQTT_USERNAME", 64),
        "mqtt_pass": ("NAV_MQTT_PASSWORD", 128),
        "device_id": ("NAV_DEVICE_ID", 64),
    }
    rows = [["key", "type", "encoding", "value"], ["navsphere", "namespace", "", ""]]
    for key, (environment, maximum) in values.items():
        if environment not in os.environ:
            raise SystemExit(f"Missing {environment}")
        value = os.environ[environment]
        if (len(value.encode("utf-8")) > maximum) or ((not value) and key != "wifi_pass") or ("\x00" in value):
            raise SystemExit(f"Invalid length/value for {environment}")
        if key == "device_id" and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            raise SystemExit("Device ID may contain letters, digits, underscores and hyphens only")
        if key == "mqtt_uri" and not value.startswith(("mqtt://", "mqtts://")):
            raise SystemExit("MQTT URI must start mqtt:// or mqtts://")
        rows.append([key, "data", "string", value])
    destination = root / ".local/nvs.bin"
    destination.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="navsphere-nvs-") as temp:
        source = Path(temp) / "credentials.csv"
        with source.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)
        result = subprocess.run([sys.executable, str(generator), "generate", str(source), str(destination), "0x6000"],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise SystemExit("NVS generator failed; verify IDF installation and partition size")
    print("NVS image created in firmware/.local/nvs.bin; keep it private. No device was flashed.")


if __name__ == "__main__":
    main()
