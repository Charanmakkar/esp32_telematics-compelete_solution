"""Reload the project's DBC library without blocking CAN capture or mutating history."""

import hashlib
import os
import re
import tempfile
from pathlib import Path
from threading import Lock
from time import monotonic

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 128
MAX_TOTAL_BYTES = 32 * 1024 * 1024
DEFAULT_FOLDER = Path(__file__).resolve().parents[3] / "can_dbc"


class DbcFolder:
    def __init__(self, folder=DEFAULT_FOLDER):
        self.folder = Path(folder)
        self.lock = Lock()
        self.checked = 0.0
        self.fingerprint = None
        self.result = (None, {})

    def read(self, parser, force=False):
        with self.lock:
            now = monotonic()
            if not force and now - self.checked < 2:
                return self.result
            self.checked = now
            info = {
                "folder": str(self.folder.resolve()),
                "files": [],
                "errors": [],
                "conflicts": [],
                "messages": 0,
                "source": "project_folder",
            }
            try:
                paths = sorted(
                    (p for p in self.folder.iterdir() if p.suffix.lower() == ".dbc"),
                    key=lambda p: p.name.lower(),
                )
                if len(paths) > MAX_FILES:
                    raise ValueError("At most 128 DBC files may be loaded at once")
                fingerprint = tuple(
                    (p.name, p.stat().st_mtime_ns, p.stat().st_size, p.is_symlink()) for p in paths
                )
                if not force and fingerprint == self.fingerprint:
                    return self.result
                if sum(p.stat().st_size for p in paths) > MAX_TOTAL_BYTES:
                    raise ValueError("DBC library exceeds 32 MiB")
            except FileNotFoundError:
                paths, fingerprint = [], ()
            except (OSError, ValueError) as exc:
                info["errors"].append(
                    str(exc) if isinstance(exc, ValueError) else "Cannot read the can_dbc folder"
                )
                self.result = (None, info)
                self.fingerprint = None
                return self.result
            messages, owners, conflicts = {}, {}, {}
            for path in paths:
                record = {"filename": path.name, "messages": 0, "status": "error"}
                try:
                    if path.is_symlink() or path.resolve().parent != self.folder.resolve():
                        raise ValueError("Links outside the DBC folder are not supported")
                    with path.open("rb") as stream:
                        raw = stream.read(MAX_FILE_BYTES + 1)
                    if len(raw) > MAX_FILE_BYTES:
                        raise ValueError("File exceeds 2 MiB")
                    try:
                        content = raw.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        content = raw.decode("cp1252")
                    database = parser(content)
                    record.update(
                        status="loaded",
                        messages=len(database.messages),
                        sha256=hashlib.sha256(raw).hexdigest(),
                    )
                    for message in database.messages:
                        key = (message.frame_id, message.is_extended_frame)
                        if key in owners:
                            conflicts.setdefault(key, [owners[key]]).append(path.name)
                            messages.pop(key, None)
                        else:
                            owners[key] = path.name
                            messages[key] = message
                except Exception as exc:
                    record["error"] = (
                        str(exc) if type(exc) is ValueError else "Invalid or unreadable DBC"
                    )
                info["files"].append(record)
            info["messages"] = len(messages)
            info["conflicts"] = [
                {"can_id": k[0], "extended": k[1], "files": files}
                for k, files in sorted(conflicts.items())
            ]
            library = {"messages": messages, "sources": owners, "conflicts": conflicts}
            self.result = (library if paths else None, info)
            self.fingerprint = fingerprint
            return self.result

    def save(self, filename, content, parser):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.()-]{0,122}\.[dD][bB][cC]", filename):
            raise ValueError("Use a simple .dbc filename without path separators")
        if filename.split(".")[0].upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            raise ValueError("Reserved filename")
        raw = content.encode("utf-8")
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("DBC exceeds 2 MiB")
        database = parser(content)
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.folder / filename
        if target.is_symlink() or target.resolve().parent != self.folder.resolve():
            raise ValueError("Invalid destination")
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.folder, suffix=".tmp", delete=False) as f:
                temp = f.name
                f.write(raw)
            os.replace(temp, target)
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
        self.read(parser, force=True)
        return {"filename": filename, "messages": len(database.messages), "saved_to": str(target)}
