from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.security import authenticate, current_user
from app.database.models import CanFrame, CanLatest
from app.services.can_service import decode_frame, parse_dbc
from app.services.dbc_folder import MAX_FILE_BYTES

router = APIRouter(prefix="/api/v1/can", tags=["CAN"], dependencies=[Depends(current_user)])


def service(request, device_id):
    rt = request.app.state.runtime
    if device_id not in rt.settings.allowed_devices:
        raise HTTPException(404, "Unknown device")
    return rt.can


@router.get("/latest")
def latest(
    request: Request,
    device_id: str = "ESP32_001",
    offset: int = Query(0, ge=0, le=1000000),
    limit: int = Query(100, ge=1, le=500),
):
    can = service(request, device_id)
    database, dbc = can.dbc(device_id)
    with can.runtime.db.session() as db:
        rows = db.scalars(
            select(CanLatest)
            .where(CanLatest.device_id == device_id)
            .order_by(CanLatest.can_id, CanLatest.extended, CanLatest.rtr)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        return {
            "frames": [
                {**r.payload, "frame_count": r.frame_count, **decode_frame(r.payload, database)}
                for r in rows[:limit]
            ],
            "has_more": len(rows) > limit,
            "dbc": dbc,
            "dbc_library": can.dbc_folder.read(parse_dbc)[1],
            "status": can.status.get(device_id),
            "metrics": dict(can.metrics),
        }


@router.get("/history")
def history(
    request: Request,
    device_id: str = "ESP32_001",
    can_id: int | None = Query(None, ge=0, le=0x1FFFFFFF),
    extended: bool | None = None,
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=1000),
):
    can = service(request, device_id)
    query = select(CanFrame).where(CanFrame.device_id == device_id)
    if can_id is not None:
        query = query.where(CanFrame.can_id == can_id)
    if extended is not None:
        query = query.where(CanFrame.extended == extended)
    if before_id is not None:
        query = query.where(CanFrame.id < before_id)
    with can.runtime.db.session() as db:
        rows = db.scalars(query.order_by(CanFrame.id.desc()).limit(limit)).all()
        return {
            "frames": [{"id": r.id, **r.payload} for r in rows],
            "next_before_id": rows[-1].id if len(rows) == limit else None,
        }


class DbcUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=128, pattern=r"^[^/\\]+\.[dD][bB][cC]$")
    content: str = Field(min_length=1, max_length=524288)


class FolderDbcUpload(DbcUpload):
    content: str = Field(min_length=1, max_length=MAX_FILE_BYTES)


@router.post("/dbc/files")
async def upload_file(request: Request):
    authenticate(request, mutation=True, admin=True)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 3 * MAX_FILE_BYTES:
            raise HTTPException(413, "DBC upload is too large (2 MiB maximum file)")
    import asyncio

    try:
        upload = FolderDbcUpload.model_validate_json(bytes(body))
        return await asyncio.to_thread(
            request.app.state.runtime.can.dbc_folder.save,
            upload.filename,
            upload.content,
            parse_dbc,
        )
    except OSError as exc:
        raise HTTPException(503, "Cannot save to the project can_dbc folder") from exc
    except Exception as exc:
        raise HTTPException(
            422, "Invalid DBC or filename. Use a classic CAN DBC up to 2 MiB with unique IDs."
        ) from exc


@router.post("/dbc")
async def upload(request: Request, device_id: str = "ESP32_001"):
    # Bound the HTTP body before JSON decoding, including chunked requests.
    authenticate(request, mutation=True, admin=True)
    can = service(request, device_id)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 700000:
            raise HTTPException(413, "DBC upload is too large (512 KiB maximum file)")
    import asyncio

    try:
        upload = DbcUpload.model_validate_json(bytes(body))
        if len(upload.content.encode()) > 524288:
            raise ValueError("DBC exceeds 512 KiB")
        return await asyncio.to_thread(can.save_dbc, device_id, upload.filename, upload.content)
    except Exception as exc:
        # Never expose uploaded content or parser internals in HTTP errors.
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(exc, SQLAlchemyError):
            raise
        raise HTTPException(
            422, "Invalid DBC. Use a valid classic CAN DBC, up to 512 KiB, with unique IDs."
        ) from exc
