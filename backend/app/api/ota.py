from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.security import authenticate, csrf_header
from app.services.ota_image import MAX_UPLOAD

router = APIRouter(prefix="/api/v1/ota", tags=["Firmware OTA"])


def administrator(request):
    user, _ = authenticate(request, mutation=True, admin=True)
    if user.must_change_password:
        raise HTTPException(403, "Change the initial password before updating firmware")
    return user


@router.get("")
def status(request: Request, device_id: str = "ESP32_001"):
    authenticate(request)
    try:
        return request.app.state.runtime.ota.snapshot(device_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/image",
    dependencies=[Depends(csrf_header)],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary", "maxLength": MAX_UPLOAD}
                }
            },
        }
    },
)
async def upload(request: Request, device_id: str, filename: str = Query(max_length=128)):
    administrator(request)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD:
            raise HTTPException(413, "Upload exceeds 6 MiB")
        data.extend(chunk)
    try:
        return request.app.state.runtime.ota.prepare(device_id, filename, bytes(data))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(max_length=64)
    upload_id: str = Field(max_length=36)


@router.post("/start", dependencies=[Depends(csrf_header)])
def start(body: StartRequest, request: Request):
    user = administrator(request)
    try:
        return request.app.state.runtime.ota.begin(body.device_id, body.upload_id, user.username)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
