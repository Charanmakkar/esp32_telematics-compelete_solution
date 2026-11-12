from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.core.security import current_user, utcnow
from app.database.models import Device
from app.database.repository import iso
from app.schemas.responses import DeviceResponse, DevicesResponse

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"], dependencies=[Depends(current_user)])


def device_dict(row, settings):
    fresh = (
        row.last_seen
        and (utcnow() - row.last_seen).total_seconds() <= settings.device_stale_seconds
    )
    pins = (32, 33, 34, 35, 36, 39)
    return {
        "device_id": row.device_id,
        "online": bool(row.online and fresh),
        "last_seen": iso(row.last_seen),
        "source": row.source,
        "boot_id": row.boot_id,
        "controls": {
            "A": row.control_a if fresh and row.online else None,
            "B": row.control_b if fresh and row.online else None,
        },
        "mapping": [
            {
                "channel": f"analog_{i}",
                "label": f"Analog {i}",
                "physical": f"Synthetic CH{i}"
                if row.source == "simulator"
                else (
                    f"GPIO{pins[i - 1]} / ADC1"
                    if i <= len(pins)
                    else "Unavailable - external ADC/multiplexer required"
                ),
            }
            for i in range(1, 7)
        ],
    }


@router.get("", response_model=DevicesResponse)
def devices(request: Request):
    rt = request.app.state.runtime
    with rt.db.session() as db:
        rows = db.scalars(
            select(Device).where(Device.device_id.in_(rt.settings.allowed_devices))
        ).all()
        return {"devices": [device_dict(row, rt.settings) for row in rows]}


@router.get("/{device_id}/status", response_model=DeviceResponse)
def device_status(device_id: str, request: Request):
    rt = request.app.state.runtime
    if device_id not in rt.settings.allowed_devices:
        raise HTTPException(404, "Unknown device")
    with rt.db.session() as db:
        row = db.get(Device, device_id)
        return device_dict(row, rt.settings)
