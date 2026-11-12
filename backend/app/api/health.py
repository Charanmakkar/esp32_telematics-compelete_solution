from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


@router.get("")
def health(request: Request):
    return request.app.state.runtime.health()


@router.get("/ready")
def ready(request: Request):
    rt = request.app.state.runtime
    rt.database_connected = rt.db.health()
    status = rt.database_connected and rt.mqtt.connected
    return JSONResponse(
        {
            "ready": status,
            "database_connected": rt.database_connected,
            "mqtt_connected": rt.mqtt.connected,
        },
        status_code=200 if status else 503,
    )
