import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from app.core.security import (
    COOKIE_NAME,
    LoginLimiter,
    authenticate,
    check_password,
    csrf_header,
    hash_password,
    token_hash,
    utcnow,
)
from app.database.models import LoginSession, User
from app.database.repository import audit

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
limiter = LoginLimiter()
# Equalize work when a username does not exist.
DUMMY_HASH = hash_password("unavailable-account-dummy-password")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserInfo(BaseModel):
    username: str
    role: str
    must_change_password: bool


class AuthResponse(BaseModel):
    user: UserInfo
    csrf_token: str


def result(user, session) -> dict:
    return {
        "user": {
            "username": user.username,
            "role": user.role,
            "must_change_password": user.must_change_password,
        },
        "csrf_token": session.csrf_token,
    }


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request, response: Response):
    rt = request.app.state.runtime
    origin = request.headers.get("origin")
    if origin and origin not in rt.settings.origins:
        raise HTTPException(403, "Origin is not allowed")
    limiter.check(request.client.host if request.client else "unknown")
    with rt.db.session() as db:
        user = db.scalar(select(User).where(User.username == body.username))
        valid = check_password(body.password, user.password_hash if user else DUMMY_HASH)
        if not valid or user is None or not user.active:
            audit(db, body.username, "login_failed", {})
            db.commit()
            raise HTTPException(401, "Invalid username or password")
        token = secrets.token_urlsafe(32)
        session = LoginSession(
            token_hash=token_hash(token),
            user_id=user.id,
            csrf_token=secrets.token_urlsafe(32),
            expires_at=utcnow() + timedelta(seconds=rt.settings.session_ttl_seconds),
        )
        # Bound active sessions per account and remove expired sessions.
        db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow()))
        old_sessions = db.scalars(
            select(LoginSession)
            .where(LoginSession.user_id == user.id)
            .order_by(LoginSession.expires_at.desc())
            .offset(9)
        ).all()
        for old in old_sessions:
            db.delete(old)
        db.add(session)
        audit(db, user.username, "login", {})
        db.commit()
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            secure=rt.settings.cookie_secure,
            samesite="strict",
            max_age=rt.settings.session_ttl_seconds,
            path="/",
        )
        return result(user, session)


@router.get("/me", response_model=AuthResponse)
def me(request: Request):
    return result(*authenticate(request))


@router.post("/logout", dependencies=[Depends(csrf_header)])
def logout(request: Request, response: Response):
    user, session = authenticate(request, mutation=True)
    with request.app.state.runtime.db.session() as db:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == session.token_hash))
        audit(db, user.username, "logout", {})
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"detail": "Logged out"}


@router.post("/password", response_model=AuthResponse, dependencies=[Depends(csrf_header)])
def password(body: PasswordRequest, request: Request):
    user, session = authenticate(request, mutation=True)
    if not check_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(400, "New password must differ from current password")
    with request.app.state.runtime.db.session() as db:
        current = db.get(User, user.id)
        current.password_hash = hash_password(body.new_password)
        current.must_change_password = False
        db.execute(
            delete(LoginSession).where(
                LoginSession.user_id == user.id, LoginSession.token_hash != session.token_hash
            )
        )
        audit(db, user.username, "password_changed", {})
        db.commit()
        return result(current, session)
