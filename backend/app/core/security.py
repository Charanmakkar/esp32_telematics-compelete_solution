import base64
import hashlib
import hmac
import secrets
from collections import OrderedDict, deque
from datetime import UTC, datetime
from threading import Lock
from time import monotonic

from fastapi import Header, HTTPException, Request
from sqlalchemy import select

from app.database.models import LoginSession, User

COOKIE_NAME = "navsphere_session"


def csrf_header(x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")):
    """Expose the anti-CSRF header in OpenAPI; authenticate() verifies its session binding."""
    return x_csrf_token


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt + digest).decode()


def check_password(password: str, encoded: str) -> bool:
    try:
        packed = base64.b64decode(encoded.split("$", 1)[1], validate=True)
        expected = hashlib.scrypt(password.encode(), salt=packed[:16], n=16384, r=8, p=1)
        return hmac.compare_digest(expected, packed[16:])
    except (ValueError, IndexError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class LoginLimiter:
    """Per-client bounded process-local limiter; run one backend worker."""

    def __init__(self) -> None:
        self.attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = Lock()

    def check(self, key: str) -> None:
        with self.lock:
            now = monotonic()
            entries = self.attempts.setdefault(key, deque(maxlen=10))
            self.attempts.move_to_end(key)
            while entries and entries[0] < now - 60:
                entries.popleft()
            if len(self.attempts) > 2048:
                self.attempts.popitem(last=False)
            if len(entries) >= 10:
                raise HTTPException(429, "Too many login attempts; retry in one minute")
            entries.append(now)


def authenticate(request: Request, mutation: bool = False, admin: bool = False):
    token = request.cookies.get(COOKIE_NAME, "")
    with request.app.state.runtime.db.session() as db:
        session = db.scalar(
            select(LoginSession).where(LoginSession.token_hash == token_hash(token))
        )
        if not token or session is None or session.expires_at <= utcnow():
            raise HTTPException(401, "Authentication required")
        user = db.get(User, session.user_id)
        if user is None or not user.active:
            raise HTTPException(401, "Account disabled")
        if mutation:
            supplied = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(supplied, session.csrf_token):
                raise HTTPException(403, "CSRF token missing or invalid")
            origin = request.headers.get("origin")
            if origin and origin not in request.app.state.runtime.settings.origins:
                raise HTTPException(403, "Origin is not allowed")
        if admin and user.role != "admin":
            raise HTTPException(403, "Administrator role required")
        return user, session


def current_user(request: Request):
    return authenticate(request)[0]
