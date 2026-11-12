"""Create isolated NavSphere credentials using the existing local MySQL server.

Run with backend/.venv/Scripts/python.exe. MYSQL_ADMIN_PASSWORD may be supplied
in the environment; its value and generated secrets are never printed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import os
from pathlib import Path
import secrets

import pymysql

ROOT = Path(__file__).resolve().parents[1]


def password_entry(user: str, password: str) -> str:
    # Mosquitto's documented v2 password-file scheme: SHA512 PBKDF2, 12-byte salt.
    salt = secrets.token_bytes(12)
    iterations = 210000
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, iterations, 64)
    b64 = lambda value: base64.b64encode(value).decode("ascii")
    return f"{user}:$7${iterations}${b64(salt)}${b64(digest)}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--admin-user", default="root")
    parser.add_argument("--mqtt-bind", default="127.0.0.1")
    parser.add_argument("--db-client-host", help="MySQL account host for the backend; required for a remote DB")
    args = parser.parse_args()
    ipaddress.ip_address(args.mqtt_bind)
    if args.db_client_host is None and args.db_host not in ("localhost", "127.0.0.1", "::1"):
        parser.error("For a remote database, specify --db-client-host with the backend machine's exact host/IP")
    account_host = args.db_client_host or "localhost"
    if not account_host or any(character in account_host for character in ("%", "_", "\n", "\r", "\x00")):
        parser.error("--db-client-host must be an exact MySQL account host without wildcard characters")
    backend_env = ROOT / "backend" / ".env"
    if backend_env.exists():
        expected = (ROOT / ".runtime/device.env", ROOT / ".runtime/mqtt/passwords", ROOT / ".runtime/mqtt/mosquitto.conf")
        if not all(path.is_file() for path in expected):
            raise RuntimeError("backend/.env exists but local broker/device files are missing; restore them or configure manually. Existing secrets were preserved.")
        print("Existing backend/.env preserved. Setup already configured; no credentials rotated.")
        return
    runtime = ROOT / ".runtime"
    broker_dir = runtime / "mqtt"
    broker_dir.mkdir(parents=True, exist_ok=True)
    db_password, backend_password, device_password = [secrets.token_urlsafe(32) for _ in range(3)]
    connection = pymysql.connect(host=args.db_host, port=args.db_port, user=args.admin_user,
        password=os.getenv("MYSQL_ADMIN_PASSWORD", ""), connect_timeout=5, autocommit=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS navsphere CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute("SELECT COUNT(*) FROM mysql.user WHERE User='navsphere_app' AND Host=%s", (account_host,))
            if cursor.fetchone()[0]:
                raise RuntimeError("The navsphere_app account already exists for this host. Configure backend/.env manually to preserve its password.")
            cursor.execute("CREATE USER 'navsphere_app'@%s IDENTIFIED BY %s", (account_host, db_password))
            cursor.execute("GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES ON navsphere.* TO 'navsphere_app'@%s", (account_host,))
    finally:
        connection.close()
    backend_env.write_text(
        f"ENVIRONMENT=development\nDB_HOST={args.db_host}\nDB_PORT={args.db_port}\n"
        f"DB_NAME=navsphere\nDB_USER=navsphere_app\nDB_PASSWORD={db_password}\n"
        "MQTT_ENABLED=true\nMQTT_HOST=127.0.0.1\nMQTT_PORT=1883\n"
        f"MQTT_USERNAME=navsphere_backend\nMQTT_PASSWORD={backend_password}\n"
        "DEVICE_IDS=ESP32_001\nAUTO_MIGRATE=false\nCOOKIE_SECURE=false\n"
        "FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000\n"
        "INITIAL_ADMIN_USERNAME=admin\nINITIAL_ADMIN_PASSWORD=admin\n", encoding="utf-8")
    (runtime / "device.env").write_text("MQTT_HOST=127.0.0.1\nMQTT_PORT=1883\n"
        f"MQTT_DEVICE_USER=ESP32_001\nMQTT_DEVICE_PASSWORD={device_password}\n", encoding="utf-8")
    (broker_dir / "passwords").write_text(password_entry("navsphere_backend", backend_password)
        + password_entry("ESP32_001", device_password), encoding="ascii")
    posix = lambda path: path.resolve().as_posix()
    (broker_dir / "mosquitto.conf").write_text(
        f"listener 1883 {args.mqtt_bind}\nallow_anonymous false\n"
        f"password_file {posix(broker_dir / 'passwords')}\n"
        f"acl_file {posix(ROOT / 'mqtt' / 'acl.example')}\n"
        "persistence true\n"
        f"persistence_location {posix(broker_dir)}/\n"
        "max_queued_messages 100\nmax_inflight_messages 20\nmessage_size_limit 8192\n"
        "log_dest stdout\nlog_type error\nlog_type warning\nlog_type notice\n", encoding="utf-8")
    print("Created NavSphere database, restricted application user and ignored local credential files.")
    print("Default development login: admin / admin (password change required before commands).")


if __name__ == "__main__":
    main()
