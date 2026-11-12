import asyncio
from contextlib import asynccontextmanager, suppress
from time import monotonic

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyCookie
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api import auth, commands, devices, health, telemetry
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.security import COOKIE_NAME, authenticate
from app.schemas.telemetry import Telemetry
from app.services.telemetry_service import Runtime

cookie_scheme = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()
    runtime = Runtime(settings)

    @asynccontextmanager
    async def lifespan(app):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="NavSphere API",
        version="1.0.0",
        lifespan=lifespan,
        description=(
            "Authenticate with POST /api/v1/auth/login. The browser receives an HttpOnly "
            "session cookie. Copy csrf_token from login/me into X-CSRF-Token for mutations. "
            "Change the initial password before controls. WebSocket: /ws/v1/telemetry, "
            "same session cookie; MQTT/WS protocols are documented in docs/api/."
        ),
    )
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    for router in (auth.router, commands.router, devices.router, telemetry.router):
        app.include_router(router, dependencies=[Depends(cookie_scheme)])
    app.include_router(health.router)

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request, exc):
        runtime.database_connected = False
        return JSONResponse({"detail": "Database unavailable; retry shortly"}, status_code=503)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.websocket("/ws/v1/telemetry")
    async def websocket(socket: WebSocket):
        origin = socket.headers.get("origin")
        if origin and origin not in settings.origins:
            await socket.close(code=1008)
            return
        try:
            await asyncio.to_thread(authenticate, socket)
        except HTTPException:
            await socket.close(code=1008)
            return
        if len(runtime.hub.clients) >= 100:
            await socket.close(code=1013)
            return
        queue = await runtime.hub.register(socket)

        async def sender():
            next_auth = monotonic() + 15
            while True:
                if monotonic() >= next_auth:
                    try:
                        await asyncio.to_thread(authenticate, socket)
                    except HTTPException:
                        await socket.close(code=1008)
                        return
                    next_auth = monotonic() + 15
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    await socket.send_json(event)
                except TimeoutError:
                    # Revalidate sessions so logout and expiry close idle streams.
                    try:
                        await asyncio.to_thread(authenticate, socket)
                    except HTTPException:
                        await socket.close(code=1008)
                        return
                    await socket.send_json({"type": "heartbeat", "health": runtime.health()})

        async def receiver():
            while True:
                message = await socket.receive_text()
                if len(message) > 1024:
                    await socket.close(code=1009)
                    return

        jobs = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
        try:
            done, _ = await asyncio.wait(jobs, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            runtime.hub.remove(socket)
            for job in jobs:
                job.cancel()
            for job in jobs:
                with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                    await job

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title, version=app.version, description=app.description, routes=app.routes
            )
            schema.setdefault("components", {}).setdefault("schemas", {})["MqttTelemetry"] = (
                Telemetry.model_json_schema()
            )
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    return app


app = create_app()
