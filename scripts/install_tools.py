"""Fetch portable, workspace-local Node and Mosquitto from their publishers.

Uses archive extraction, never runs installers or changes Windows services/PATH.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
NODE_VERSION = "24.22.2"


def download(url: str, target: Path) -> None:
    if target.exists() and target.stat().st_size:
        return
    temporary = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
        expected_size = response.headers.get("Content-Length")
        actual_size = 0
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            actual_size += len(chunk)
    if actual_size == 0 or (expected_size is not None and actual_size != int(expected_size)):
        raise RuntimeError("Incomplete portable-tool download; rerun setup to retry")
    os.replace(temporary, target)


def main() -> None:
    TOOLS.mkdir(exist_ok=True)
    archive_name = f"node-v{NODE_VERSION}-win-x64.zip"
    node_dir = TOOLS / f"node-v{NODE_VERSION}-win-x64"
    if not (node_dir / "node.exe").exists():
        archive = TOOLS / archive_name
        download(f"https://nodejs.org/dist/v{NODE_VERSION}/{archive_name}", archive)
        with urllib.request.urlopen(f"https://nodejs.org/dist/v{NODE_VERSION}/SHASUMS256.txt", timeout=30) as response:
            lines = response.read().decode().splitlines()
        expected = next(line.split()[0] for line in lines if line.endswith(" " + archive_name))
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Node publisher SHA256 verification failed; remove corrupt archive")
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if not (TOOLS / member.filename).resolve().is_relative_to(TOOLS.resolve()):
                    raise RuntimeError("Archive member escapes workspace-local tools directory")
            source.extractall(TOOLS)
    if not (TOOLS / "mosquitto" / "mosquitto.exe").exists():
        download("https://mosquitto.org/files/binary/win64/mosquitto-2.1.2-install-windows-x64.exe",
                 TOOLS / "mosquitto-installer.exe")
        download("https://www.7-zip.org/a/7zr.exe", TOOLS / "7zr.exe")
        download("https://www.7-zip.org/a/7z2301-x64.exe", TOOLS / "7zip-installer.exe")
        subprocess.run([str(TOOLS / "7zr.exe"), "x", str(TOOLS / "7zip-installer.exe"),
                        f"-o{TOOLS / '7zip'}", "-y"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(TOOLS / "7zip" / "7z.exe"), "x", str(TOOLS / "mosquitto-installer.exe"),
                        f"-o{TOOLS / 'mosquitto'}", "-y"], check=True, stdout=subprocess.DEVNULL)
    print(f"Portable tools ready: {node_dir.name}; Mosquitto 2.1.2")


if __name__ == "__main__":
    main()
