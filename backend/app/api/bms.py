from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.security import authenticate, csrf_header

router = APIRouter(prefix="/api/v1/bms", tags=["BMS diagnostics"])


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(max_length=64)
    kind: Literal["cdd", "preset"]
    entry_id: str = Field(max_length=128)
    instance: int = Field(default=1, ge=0, le=15)
    ecu: Literal["abs_hv", "abs_hv_old"] = "abs_hv"
    values: dict[str, str | int | float] = Field(default_factory=dict, max_length=512)
    session: int = Field(default=0, ge=0, le=3)
    security: int = Field(default=0, ge=0, le=5)
    image_filename: str = Field(default="", max_length=128)
    image_id: int = Field(default=0, ge=0, le=15)
    inject_crc: bool = False


class QuickReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(max_length=64)
    instance: int = Field(default=1, ge=0, le=15)
    ecu: Literal["abs_hv", "abs_hv_old"] = "abs_hv"
    command: Literal["qr", "serial", "hardware", "manufacturing", "mode"]


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(max_length=36)
    confirmation: str = Field(default="", max_length=16)


def admin(request):
    user, _ = authenticate(request, mutation=True, admin=True)
    if user.must_change_password:
        raise HTTPException(403, "Change the initial password before issuing diagnostics")
    return user


def call(function, *args):
    try:
        return function(*args)
    except (ValueError, KeyError, UnicodeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/catalog")
def catalog(request: Request):
    authenticate(request)
    return request.app.state.runtime.bms.catalog.public()


@router.post("/preview", dependencies=[Depends(csrf_header)])
def preview(body: PreviewRequest, request: Request):
    user = admin(request)
    if len(str(body.values)) > 18000:
        raise HTTPException(413, "Request values too large")
    return call(request.app.state.runtime.bms.prepare, body.model_dump(), user.username)


@router.post("/jobs", status_code=202, dependencies=[Depends(csrf_header)])
def submit(body: SubmitRequest, request: Request):
    user = admin(request)
    return call(request.app.state.runtime.bms.submit, body.token, body.confirmation, user.username)


@router.post("/read", status_code=202, dependencies=[Depends(csrf_header)])
def quick_read(body: QuickReadRequest, request: Request):
    user = admin(request)
    return call(request.app.state.runtime.bms.quick_read, body.model_dump(), user.username)


@router.get("/jobs")
def recent(request: Request, device_id: str = "ESP32_001"):
    authenticate(request)
    if device_id not in request.app.state.runtime.settings.allowed_devices:
        raise HTTPException(404, "Unknown device")
    return {"jobs": request.app.state.runtime.bms.recent(device_id)}


@router.get("/jobs/{job_id}")
def detail(job_id: str, request: Request, offset: int = Query(0, ge=0)):
    authenticate(request)
    return request.app.state.runtime.bms.detail(job_id, offset)


@router.post("/jobs/{job_id}/cancel", dependencies=[Depends(csrf_header)])
def cancel(job_id: str, request: Request):
    admin(request)
    return call(request.app.state.runtime.bms.cancel, job_id)
