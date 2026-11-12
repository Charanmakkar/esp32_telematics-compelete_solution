from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from app.core.security import authenticate, csrf_header
from app.database.models import Command
from app.database.repository import command_dict
from app.schemas.commands import CommandRequest
from app.schemas.responses import CommandResponse, CommandsResponse

router = APIRouter(prefix="/api/v1/commands", tags=["Admin commands"])


@router.post(
    "", status_code=202, response_model=CommandResponse, dependencies=[Depends(csrf_header)]
)
async def submit(body: CommandRequest, request: Request):
    import asyncio

    user, _ = await asyncio.to_thread(authenticate, request, mutation=True, admin=True)
    if user.must_change_password:
        raise HTTPException(403, "Change the initial password before issuing commands")
    rt = request.app.state.runtime
    result = await asyncio.to_thread(rt.commands.submit, body, user)
    rt.hub.broadcast({"type": "command", "data": result})
    return result


@router.get("", response_model=CommandsResponse)
def recent(request: Request, device_id: str = "ESP32_001", limit: int = Query(30, ge=1, le=100)):
    authenticate(request)
    rt = request.app.state.runtime
    if device_id not in rt.settings.allowed_devices:
        raise HTTPException(404, "Unknown device")
    with rt.db.session() as db:
        rows = db.scalars(
            select(Command)
            .where(Command.device_id == device_id)
            .order_by(Command.created_at.desc())
            .limit(limit)
        ).all()
        return {"commands": [command_dict(r) for r in rows]}


@router.get("/{command_id}", response_model=CommandResponse)
def status(command_id: str, request: Request):
    authenticate(request)
    with request.app.state.runtime.db.session() as db:
        row = db.get(Command, command_id)
        if row is None:
            raise HTTPException(404, "Unknown command")
        return command_dict(row)
