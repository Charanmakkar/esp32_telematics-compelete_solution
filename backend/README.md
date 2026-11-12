# Backend

Python3.13 was used for the executed tests. From this directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
Copy-Item .env.example .env
# Configure the existing MySQL/MariaDB account and authenticated MQTT broker in .env.
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open `/docs`, `/redoc`, or `/openapi.json` on that server. [API_CONTRACT.md](API_CONTRACT.md) describes REST, MQTT, WebSocket, CSRF, exact JSON shapes and six-channel mapping.

Use one Uvicorn worker: MQTT ingestion, rate limiting, latest received values and WebSocket fanout are process local. Multiple workers require a shared event bus and rate limiter. SQLAlchemy sessions are short lived and each database operation runs independently; no database writes occur in the Paho network callback. Telemetry ingestion uses a bounded2048-message RAM queue by default. While a database write fails, the head sample retries for up to10seconds and later samples remain queued. After the deadline that sample is dropped and counted. Queue overflow drops arriving messages and counts them. No disk spool is implemented; restart loses buffered samples. Database constraints deduplicate QoS1 repeats. The worker continues processing after errors and later messages can persist after recovery.

The MySQL connection must succeed on startup and migrations must have been applied. Startup fails clearly if those prerequisites are missing. `/health/ready` distinguishes dependency readiness. Telemetry counters cover this backend run. Device freshness is computed from server receipt time and explicit status messages; dashboard acquisition freshness additionally uses the original sample timestamp/uptime and stale flag. `persisted_at` records the time immediately before insert work begins; a persisted event is emitted only after commit succeeds. A receipt-to-`persisted_at` measurement therefore measures time to the insertion stage, not full commit latency.

Tests are isolated in temporary SQLite databases with MQTT disabled. They do not claim real MySQL/MQTT verification; the root integration script covers those live services separately.

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app tests migrations
```

The tested dependency set is pinned in `requirements.lock`; `requirements.txt` expresses compatible version ranges for intentional upgrades. Lock regeneration should occur in a clean environment and exclude documentation generation dependencies. The current upstream Starlette TestClient emits one deprecation warning about future `httpx2`; the executed tests still pass.

Sessions are random tokens whose hashes are stored in the database, with HttpOnly/SameSite cookies and per-session CSRF tokens. Passwords use salted scrypt. Production configuration prohibits default credentials, insecure cookies, plaintext MQTT, SQLite, or HTTP frontend origins. Production startup also checks every active stored account for the default password, in bounded batches; changing the seed environment variable does not replace existing passwords. Change those passwords or disable those accounts before promoting a development database. Put HTTPS in front of backend/frontend and configure origins to the exact browser origins. The application trusts authenticated per-device MQTT ACLs; it does not implement cryptographic signing of individual payloads. Protect the broker network and credentials. Login, password changes, command submissions, acknowledgements and timeouts are audited.

Dockerfile migrates and starts one worker. It does not start another database. Supply deployment environment variables and configure MySQL/MQTT endpoints from the host or Compose network. The production TLS settings require certificates and a trusted HTTPS reverse proxy.
