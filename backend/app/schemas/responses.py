from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.telemetry import Telemetry


class Reading(Telemetry):
    id: int | None
    received_at: datetime
    persisted_at: datetime | None


class LatestResponse(BaseModel):
    received: Reading | None
    persisted: Reading | None


class HistoryPoint(BaseModel):
    timestamp_ms: int
    channels: dict[str, float | None]


class ChannelStatistics(BaseModel):
    min: float | None
    max: float | None
    avg: float | None
    count: int


class HistoryResponse(BaseModel):
    points: list[HistoryPoint]
    statistics: dict[str, ChannelStatistics]
    count: int
    aggregated: bool
    time_basis: str


class CommandResponse(BaseModel):
    command_id: str
    device_id: str
    key: Literal["A", "B"]
    value: Literal[0, 1]
    status: Literal["pending", "accepted", "applied", "rejected", "timed_out"]
    reason: str
    boot_id: str | None
    created_at: datetime
    expires_at: datetime
    updated_at: datetime


class CommandsResponse(BaseModel):
    commands: list[CommandResponse]


class ChannelMapping(BaseModel):
    channel: str
    label: str
    physical: str


class DeviceResponse(BaseModel):
    device_id: str
    online: bool
    last_seen: datetime | None
    source: str
    boot_id: str | None
    controls: dict[str, Literal[0, 1] | None]
    mapping: list[ChannelMapping]


class DevicesResponse(BaseModel):
    devices: list[DeviceResponse]
