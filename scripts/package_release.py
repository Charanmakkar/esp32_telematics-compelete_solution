"""Package source, documentation and the compiled ESP32 release without secrets."""
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    build = ROOT / "build" if (ROOT / "build" / "firmware.bin").is_file() else ROOT / "firmware" / "build"
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
    manifest = {"target":"esp32", "module":"ESP32S-WROOM", "esp_idf":"6.0.2",
        "channels":6, "adc1_gpio":[32,33,34,35,36,39], "control_gpio":{"A":25,"B":26},
        "flash_mode":"dio", "flash_size":"4MB", "flash_frequency":"40m",
        "offsets":{"bootloader.bin":"0x1000","partition-table.bin":"0x8000","navsphere.bin":"0x10000"},
        "nvs_offset":"0x9000", "nvs_included":False,"hardware_flashed":False,
        "build_directory":build.relative_to(ROOT).as_posix(),
        "files":files, "packaged_at_utc":datetime.now(UTC).isoformat()}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    candidates = subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard"],
                                         cwd=ROOT,text=True).splitlines()
    allowed = {"firmware","backend","frontend","database","mqtt","simulator","scripts","docs","output",".vscode"}
    top = {".gitignore",".clangd","README.md","IMPLEMENTATION_REPORT.md","MASTER DEVELOPMENT PROMPT.md","docker-compose.yml","NavSphere.code-workspace","CMakeLists.txt","sdkconfig.defaults","dependencies.lock"}
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
            if any(part in {".env",".runtime",".tools","node_modules",".venv","build","__pycache__",".pytest_cache"} for part in path.parts):
                raise RuntimeError("Unexpected private/runtime path in release candidates")
            source = ROOT / path
            if source.is_file():
                archive.write(source, "NavSphere/" + path.as_posix())
                count += 1
    print(f"Packaged {count} files: {destination.relative_to(ROOT)} ({destination.stat().st_size} bytes)")
    print("Firmware SHA256:", files["navsphere.bin"]["sha256"])


if __name__ == "__main__":
    main()
