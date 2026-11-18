from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

UInt = Annotated[int, Field(strict=True, ge=0, le=4294967295)]


class CanSample(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sequence: UInt
    uptime_ms: Annotated[int, Field(ge=0, le=2**63 - 1)]
    timestamp_ms: Annotated[int, Field(ge=0, le=253402300799999)]
    can_id: Annotated[int, Field(ge=0, le=0x1FFFFFFF)]
    extended: bool
    rtr: bool
    dlc: Annotated[int, Field(ge=0, le=8)]
    data: Annotated[str, Field(pattern=r"^(?:[0-9a-fA-F]{2}){0,8}$")]

    @model_validator(mode="after")
    def validate_frame(self):
        if not self.extended and self.can_id > 0x7FF:
            raise ValueError("Standard CAN IDs are 11 bits")
        if len(self.data) != (0 if self.rtr else self.dlc * 2):
            raise ValueError("DLC and data length differ")
        self.data = self.data.upper()
        return self


class CanStats(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    queue_drops: UInt
    serial_drops: UInt
    publish_drops: UInt
    rx_missed: UInt
    rx_overruns: UInt
    bus_errors: UInt


class CanBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    device_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
    boot_id: Annotated[str, Field(min_length=1, max_length=64)]
    frames: Annotated[list[CanSample], Field(max_length=24)]
    stats: CanStats
