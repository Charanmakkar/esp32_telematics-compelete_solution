from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

UInt = Annotated[int, Field(strict=True, ge=0, le=4294967295)]


class CanTxState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool
    command_id: str = Field(max_length=36)
    reason: Literal[
        "off", "on", "connection_lost", "transmit_failed", "controller_busy_or_unavailable"
    ]
    sent_014: UInt
    sent_548: UInt
    failures: UInt
    skipped: UInt


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
    # Optional fields preserve compatibility with deployed listen-only firmware.
    uptime_ms: int | None = Field(default=None, ge=0)
    rx_total: int | None = Field(default=None, ge=0)
    rx_bytes: int | None = Field(default=None, ge=0)
    standard_frames: int | None = Field(default=None, ge=0)
    extended_frames: int | None = Field(default=None, ge=0)
    rtr_frames: int | None = Field(default=None, ge=0)
    wire_bits_min: int | None = Field(default=None, ge=0)
    wire_bits_max: int | None = Field(default=None, ge=0)
    tx_frames: int | None = Field(default=None, ge=0)
    tx_failed: int | None = Field(default=None, ge=0)
    arb_lost: int | None = Field(default=None, ge=0)
    rx_error_counter: int | None = Field(default=None, ge=0, le=65535)
    tx_error_counter: int | None = Field(default=None, ge=0, le=65535)
    controller_state: int | None = Field(default=None, ge=0, le=3)
    mode: Literal["listen_only", "diagnostic", "periodic_tx", "unavailable"] | None = None
    periodic_tx: CanTxState | None = None
    mode_changes: int | None = Field(default=None, ge=0)
    mode_switch_drops: int | None = Field(default=None, ge=0)
    diag_supported: bool = False
    diag_version: int | None = Field(default=None, ge=1, le=100)
    sw_version: str | None = Field(default=None, max_length=31, pattern=r"^\d+\.\d+\.\d+$")
    sw_build: str | None = Field(default=None, pattern=r"^[0-9a-f]{12}$")


class CanBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    device_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
    boot_id: Annotated[str, Field(min_length=1, max_length=64)]
    frames: Annotated[list[CanSample], Field(max_length=24)]
    stats: CanStats
