from time import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.security import current_user
from app.schemas.responses import HistoryResponse, LatestResponse

router = APIRouter(
    prefix="/api/v1/telemetry", tags=["Telemetry"], dependencies=[Depends(current_user)]
)


def validate_device(request, device_id):
    if device_id not in request.app.state.runtime.settings.allowed_devices:
        raise HTTPException(404, "Unknown device")


@router.get("/latest", response_model=LatestResponse)
def latest(request: Request, device_id: str = "ESP32_001"):
    validate_device(request, device_id)
    rt = request.app.state.runtime
    persisted = rt.repository.latest(device_id)
    return {"received": rt.latest_received.get(device_id), "persisted": persisted}


def query_history(request, device_id, start_ms, end_ms, limit, channel=None):
    validate_device(request, device_id)
    end = end_ms if end_ms is not None else int(time() * 1000)
    start = start_ms if start_ms is not None else end - 300000
    if start > end or end - start > 31 * 86400000:
        raise HTTPException(422, "Time range must be ordered and at most 31 days")
    return request.app.state.runtime.repository.history(device_id, start, end, limit, channel)


@router.get("/history", response_model=HistoryResponse)
def history(
    request: Request,
    device_id: str = "ESP32_001",
    start_ms: int | None = Query(None, ge=0),
    end_ms: int | None = Query(None, ge=0),
    limit: int = Query(600, ge=2, le=2000),
):
    """Bounded points; averages are aggregated in SQL if raw rows exceed limit.

    Statistics cover all valid channel readings in the requested range, not just returned points.
    Unsynchronized readings use server receive time for the history axis.
    """
    return query_history(request, device_id, start_ms, end_ms, limit)


@router.get("/channels/{channel_id}", response_model=HistoryResponse)
def channel_history(
    channel_id: str,
    request: Request,
    device_id: str = "ESP32_001",
    start_ms: int | None = Query(None, ge=0),
    end_ms: int | None = Query(None, ge=0),
    limit: int = Query(600, ge=2, le=2000),
):
    numeric = channel_id.replace("analog-", "").replace("analog_", "")
    if not numeric.isdigit() or not 1 <= int(numeric) <= 6:
        raise HTTPException(404, "Channel must be 1 through 6")
    return query_history(request, device_id, start_ms, end_ms, limit, f"analog_{int(numeric)}")
