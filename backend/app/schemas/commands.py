from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    key: Literal["A", "B"]
    value: Annotated[int, Field(strict=True, ge=0, le=1)]


class CommandAck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=1, max_length=36)
    key: Literal["A", "B"]
    value: Annotated[int, Field(strict=True, ge=0, le=1)]
    status: Literal["accepted", "applied", "rejected"]
    reason: str = Field(default="", max_length=255)
    boot_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
