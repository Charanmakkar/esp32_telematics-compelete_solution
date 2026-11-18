"""Package source, documentation and the compiled ESP32 release without secrets."""
from datetime import UTC, datetime
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from sync_version import sync

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-directory', choices=['build', 'firmware/build'])
    parser.add_argument('--hardware-flashed', action='store_true',
                        help='Record that this exact firmware build was verified on hardware')
    args = parser.parse_args()
    release = sync(check=True)
    build = ROOT / args.build_directory if args.build_directory else (ROOT / "build" if (ROOT / "build" / "firmware.bin").is_file() else ROOT / "firmware" / "build")
    image = (build / "firmware.bin").read_bytes()
    descriptor = image.find(bytes.fromhex("3254CDAB"), 0, 1024)
    image_version = image[descriptor+16:descriptor+48].split(b"\0", 1)[0].decode("ascii") if descriptor >= 0 else ""
    if image_version != release["sw_version"] or release["source_sha256"][:12].encode() + b"\0" not in image:
        raise RuntimeError("Firmware does not match version.json. Rebuild before packaging.")
    gui = json.loads((ROOT / "frontend/dist/sw-version.json").read_text())
    if gui != {"sw_version": release["sw_version"], "sw_build": release["source_sha256"][:12]}:
        raise RuntimeError("GUI does not match version.json. Run npm run build before packaging.")
    output = ROOT / "output" / "firmware"
    output.mkdir(parents=True, exist_ok=True)
    sources = {"bootloader.bin":build/"bootloader/bootloader.bin",
               "partition-table.bin":build/"partition_table/partition-table.bin",
               "navsphere.bin":build/"firmware.bin"}
    files = {}
    for name, source in sources.items():
        destination = output / name
        shutil.copy2(source, destination)
        files[name] = {"bytes":destination.stat().st_size,
                       "sha256":hashlib.sha256(destination.read_bytes()).hexdigest()}
    manifest = {"sw_version":release["sw_version"], "sw_build":release["source_sha256"][:12],
        "version_prepared_at_utc":release["built_at_utc"],
        "target":"esp32", "module":"ESP32S-WROOM", "esp_idf":"6.0.2",
        "channels":6, "adc1_gpio":[32,33,34,35,36,39], "control_gpio":{"A":2,"B":0},
        "can":{"bitrate":500000,"tx_gpio":25,"rx_gpio":26,"mode":"listen_only","classic_only":True,
               "diagnostics":{"enabled":True,"transport":"ISO-TP","maximum_payload_bytes":4095,
                              "temporary_normal_mode":True,"request_ids":"0x640-0x64F, 0x7E4, 0x7DF",
                              "protocol_version":3,"be_request_id":"0x7E4","be_response_id":"0x7EC",
                              "tester_present_burst":{"count":20,"interval_ms":100},
                              "idle_return_to_listen_only_seconds":15}},
        "flash_mode":"dio", "flash_size":"4MB", "flash_frequency":"40m",
        "offsets":{"bootloader.bin":"0x1000","partition-table.bin":"0x8000","navsphere.bin":"0x10000"},
        "nvs_offset":"0x9000", "nvs_included":False,"hardware_flashed":args.hardware_flashed,
        "build_directory":build.relative_to(ROOT).as_posix(),
        "files":files, "packaged_at_utc":datetime.now(UTC).isoformat()}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    candidates = subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard"],
                                         cwd=ROOT,text=True).splitlines()
    allowed = {"firmware","backend","frontend","database","mqtt","simulator","scripts","docs","output",".vscode","can_dbc","bms_images"}
    top = {".gitignore",".clangd","README.md","IMPLEMENTATION_REPORT.md","MASTER DEVELOPMENT PROMPT.md","docker-compose.yml","NavSphere.code-workspace","CMakeLists.txt","sdkconfig.defaults","dependencies.lock","version.json"}
    editor_files = {".vscode/settings.json", ".vscode/tasks.json", ".vscode/c_cpp_properties.json", "firmware/.vscode/settings.json", "firmware/.vscode/c_cpp_properties.json"}
    destination = ROOT / "output" / "NavSphere_Source_and_Docs.zip"
    count = 0
    with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=8) as archive:
        for name in sorted(set(candidates)):
            path = Path(name)
            if path.suffix == ".zip" or (".vscode" in path.parts and path.as_posix() not in editor_files):
                continue
            if path.parts[0] not in allowed and name not in top:
                continue
            if any(part in {".env",".local",".runtime",".tools","node_modules",".venv","build","__pycache__",".pytest_cache"} for part in path.parts):
                raise RuntimeError("Unexpected private/runtime path in release candidates")
            source = ROOT / path
            if source.is_file():
                archive.write(source, "NavSphere/" + path.as_posix())
                count += 1
    print(f"Packaged {count} files: {destination.relative_to(ROOT)} ({destination.stat().st_size} bytes)")
    print("Firmware SHA256:", files["navsphere.bin"]["sha256"])


if __name__ == "__main__":
    main()
