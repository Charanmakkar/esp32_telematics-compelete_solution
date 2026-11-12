"""Back up only the configured NavSphere database using mysqldump.

No password appears in command arguments. The temporary option file is removed
in finally. Output is ignored under .runtime/backups; protect and copy it off-host.
"""
from datetime import UTC, datetime
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings
from sqlalchemy.engine import make_url


def protect_file(path: Path) -> None:
    """Restrict temporary credentials and dumps before any sensitive bytes are written."""
    if os.name == "nt":
        identity = subprocess.check_output(
            ["whoami", "/user", "/fo", "csv", "/nh"], text=True, encoding="utf-8")
        sid = next(csv.reader(identity.strip().splitlines()))[1]
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    else:
        path.chmod(0o600)


def option_escape(value) -> str:
    result = str(value or "")
    for original, escaped in (("\\", "\\\\"), ('"', '\\"'), ("\n", "\\n"),
                              ("\r", "\\r"), ("\t", "\\t"), ("\b", "\\b")):
        result = result.replace(original, escaped)
    if "\x00" in result:
        raise ValueError("MySQL option values must not contain NUL bytes")
    return result


def main() -> None:
    settings = Settings(_env_file=ROOT / "backend" / ".env")
    url = make_url(settings.db_url) if isinstance(settings.db_url, str) else settings.db_url
    if not url.drivername.startswith("mysql"):
        raise RuntimeError("This helper backs up MySQL/MariaDB only")
    executable = os.getenv("MYSQLDUMP_PATH") or shutil.which("mysqldump")
    if not executable and Path("C:/xampp/mysql/bin/mysqldump.exe").exists():
        executable = "C:/xampp/mysql/bin/mysqldump.exe"
    if not executable:
        raise RuntimeError("Set MYSQLDUMP_PATH to your compatible mysqldump executable")
    output_dir = ROOT / ".runtime" / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    output = output_dir / f"navsphere_{stamp}.sql"
    options = {"host":url.host,"port":url.port or 3306,"user":url.username,"password":url.password}
    option_path = None
    partial_path = None
    try:
        descriptor, name = tempfile.mkstemp(dir=ROOT / ".runtime", suffix=".cnf")
        os.close(descriptor)
        option_path = Path(name)
        protect_file(option_path)
        option_path.write_text("[client]\n" + "".join(
            f'{key}="{option_escape(value)}"\n' for key,value in options.items()), encoding="utf-8")
        descriptor, name = tempfile.mkstemp(dir=output_dir, prefix=".navsphere-", suffix=".partial")
        os.close(descriptor)
        partial_path = Path(name)
        protect_file(partial_path)
        with partial_path.open("wb") as stream:
            subprocess.run([executable, f"--defaults-extra-file={option_path}",
                "--single-transaction", "--skip-lock-tables", "--triggers", "--hex-blob",
                url.database], stdout=stream, check=True)
        partial_path.replace(output)
        print(f"Backup written: {output.relative_to(ROOT)} ({output.stat().st_size} bytes)")
    finally:
        if option_path:
            option_path.unlink(missing_ok=True)
        if partial_path:
            partial_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
