from time import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

CHANNELS = tuple(f"analog_{i}" for i in range(1, 7))
Unsigned = Annotated[int, Field(strict=True, ge=0)]


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    device_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    boot_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    sequence: Annotated[int, Field(strict=True, ge=0, le=4294967295)]
    timestamp_ms: Annotated[int, Field(strict=True, ge=946684800000, le=4102444800000)] | None
    time_valid: StrictBool
    uptime_ms: Annotated[int, Field(strict=True, ge=0, le=18446744073709551615)]
    channels: dict[str, Annotated[int, Field(strict=True, ge=0, le=5000)]]
    raw: list[Annotated[int, Field(strict=True, ge=0, le=65535)]] = Field(
        min_length=6, max_length=6
    )
    valid_mask: Annotated[int, Field(strict=True, ge=0, le=63)]
    mqtt_connected: StrictBool
    dropped_samples: Unsigned
    source: Literal["hardware", "simulator"]
    stale: StrictBool

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_schema_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def invariants(self):
        if set(self.channels) != set(CHANNELS):
            raise ValueError("Exactly analog_1 through analog_6 are required")
        if self.time_valid != (self.timestamp_ms is not None):
            raise ValueError("timestamp_ms must be null exactly when time_valid is false")
        if self.timestamp_ms is not None and self.timestamp_ms > int(time() * 1000) + 300000:
            raise ValueError("Device timestamp is more than five minutes in the future")
        return self
