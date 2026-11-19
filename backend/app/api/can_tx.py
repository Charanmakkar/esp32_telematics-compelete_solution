from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.core.security import authenticate, csrf_header

router = APIRouter(prefix="/api/v1/can/tx", tags=["CAN transmission"])


class ToggleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(max_length=64)
    enabled: StrictBool


@router.get("")
def status(request: Request, device_id: str = "ESP32_001"):
    authenticate(request)
    try:
        return request.app.state.runtime.can_tx.snapshot(device_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("", dependencies=[Depends(csrf_header)])
def toggle(body: ToggleRequest, request: Request):
    user, _ = authenticate(request, mutation=True, admin=True)
    if user.must_change_password:
        raise HTTPException(403, "Change the initial password before controlling CAN transmission")
    try:
        return request.app.state.runtime.can_tx.command(body.device_id, body.enabled, user.username)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(504, str(exc)) from exc
