import pytest
from conftest import ingest, wait_for
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.security import utcnow
from app.database.models import CanFrame
from app.schemas.can import CanBatch, CanSample
from app.services.can_service import decode_frame, parse_dbc
from app.services.dbc_folder import DbcFolder

DBC = """VERSION ""
NS_ :
BS_:
BU_: ECU
BO_ 291 Engine: 4 ECU
 SG_ Speed : 0|16@1+ (0.1,0) [0|6553.5] "km/h" ECU
 SG_ Temp : 23|8@0- (1,-40) [-168|87] "degC" ECU
BO_ 2147483939 ExtendedEngine: 1 ECU
 SG_ State : 0|8@1+ (1,0) [0|255] "" ECU
VAL_ 2147483939 State 1 "Running" 0 "Stopped";
BO_ 512 Mux: 2 ECU
 SG_ Selector M : 0|8@1+ (1,0) [0|255] "" ECU
 SG_ A m1 : 8|8@1+ (1,0) [0|255] "V" ECU
 SG_ B m2 : 8|8@1+ (1,0) [0|255] "A" ECU
"""


def frame(sequence=1, **overrides):
    return dict(
        sequence=sequence,
        uptime_ms=100,
        timestamp_ms=0,
        can_id=291,
        extended=False,
        rtr=False,
        dlc=4,
        data="D204FE00",
        **overrides,
    )


def batch(frames=None):
    return dict(
        schema_version=1,
        device_id="ESP32_001",
        boot_id="can-boot-1",
        frames=frames if frames is not None else [frame()],
        stats=dict(
            queue_drops=0, serial_drops=0, publish_drops=0, rx_missed=0, rx_overruns=0, bus_errors=0
        ),
    )


def test_can_persist_deduplicate_and_latest(admin):
    app, client = admin
    can = app.state.runtime.can
    body = batch([frame(2), frame(1)])
    assert can.persist(CanBatch.model_validate(body), utcnow()) == 2
    assert can.persist(CanBatch.model_validate(body), utcnow()) == 0
    result = client.get("/api/v1/can/latest").json()
    assert result["frames"][0]["sequence"] == 2
    assert result["frames"][0]["frame_count"] == 2
    assert result["frames"][0]["decode_status"] == "no_dbc"
    with app.state.runtime.db.session() as db:
        assert db.scalar(select(func.count()).select_from(CanFrame)) == 2
    history = client.get("/api/v1/can/history?limit=1").json()
    assert history["next_before_id"] is not None
    assert (
        len(
            client.get(f"/api/v1/can/history?before_id={history['next_before_id']}").json()[
                "frames"
            ]
        )
        == 1
    )


def test_dbc_decode_signed_endian_scale_extended_and_mux():
    db = parse_dbc(DBC)
    decoded = decode_frame(frame(), db)
    assert decoded["message_name"] == "Engine"
    assert [s["value"] for s in decoded["signals"]] == [123.4, -42]
    extended = {**frame(), "extended": True, "dlc": 1, "data": "01"}
    decoded = decode_frame(extended, db)
    assert decoded["message_name"] == "ExtendedEngine"
    assert decoded["signals"][0]["label"] == "Running"
    mux = decode_frame({**frame(), "can_id": 512, "dlc": 2, "data": "020A"}, db)
    assert [s["name"] for s in mux["signals"]] == ["Selector", "B"]
    assert decode_frame({**frame(), "data": "00"}, db)["decode_status"] == "decode_error"
    assert decode_frame({**frame(), "can_id": 100}, db)["decode_status"] == "unknown_id"
    assert decode_frame({**frame(), "rtr": True, "data": ""}, db)["signals"] == []


@pytest.mark.parametrize(
    "change",
    [dict(can_id=2048), dict(data="AB"), dict(dlc=9), dict(extended="false"), dict(sequence=-1)],
)
def test_can_validation(change):
    with pytest.raises(ValidationError):
        CanSample.model_validate({**frame(), **change})


def test_dbc_upload_auth_and_decodes_existing_frames(admin):
    app, client = admin
    app.state.runtime.can.persist(CanBatch.model_validate(batch()), utcnow())
    response = client.post("/api/v1/can/dbc", json=dict(filename="engine.dbc", content=DBC))
    assert response.status_code == 200
    result = client.get("/api/v1/can/latest").json()
    assert result["dbc"]["filename"] == "engine.dbc"
    assert result["frames"][0]["decode_status"] == "decoded"
    assert (
        client.post("/api/v1/can/dbc", json=dict(filename="bad.dbc", content="bad")).status_code
        == 422
    )
    assert client.get("/api/v1/can/latest").json()["dbc"]["filename"] == "engine.dbc"
    assert (
        client.post("/api/v1/can/dbc", json=dict(filename="../x.dbc", content=DBC)).status_code
        == 422
    )
    assert client.post("/api/v1/can/dbc", content=b"x" * 700001).status_code == 413
    client.headers.pop("X-CSRF-Token")
    assert (
        client.post("/api/v1/can/dbc", json=dict(filename="x.dbc", content=DBC)).status_code == 403
    )


def test_can_ingest_rejects_retained_and_wrong_device(logged_in):
    app, client = logged_in
    ingest(app, batch(), kind="can", retained=True)
    wait_for(lambda: app.state.runtime.can.metrics["invalid"] == 1)
    wrong = {**batch(), "device_id": "OTHER"}
    ingest(app, wrong, kind="can")
    wait_for(lambda: app.state.runtime.can.metrics["invalid"] == 2)
    ingest(app, batch(), kind="can")
    wait_for(lambda: app.state.runtime.can.metrics["persisted"] == 1)
    assert client.get("/api/v1/can/latest?device_id=OTHER").status_code == 404
    assert client.get("/api/v1/can/latest").json()["status"]["boot_id"] == "can-boot-1"


def test_can_routes_require_login(application):
    _, client = application
    assert client.get("/api/v1/can/latest").status_code == 401
    assert client.get("/api/v1/can/history").status_code == 401


def test_formats_and_rtr_have_distinct_latest_rows(admin):
    app, client = admin
    frames = [frame(), {**frame(2), "extended": True}, {**frame(3), "rtr": True, "data": ""}]
    app.state.runtime.can.persist(CanBatch.model_validate(batch(frames)), utcnow())
    assert len(client.get("/api/v1/can/latest").json()["frames"]) == 3


def test_folder_multiple_files_reload_conflict_and_remove(tmp_path):
    folder = DbcFolder(tmp_path)
    engine = DBC.split("BO_ 2147483939")[0]
    other = engine.replace("291 Engine", "292 Gearbox")
    (tmp_path / "engine.dbc").write_text(engine)
    (tmp_path / "gearbox.DBC").write_text(other)
    library, info = folder.read(parse_dbc)
    assert info["messages"] == 2
    assert decode_frame(frame(), library)["dbc_file"] == "engine.dbc"
    assert decode_frame({**frame(), "can_id": 292}, library)["message_name"] == "Gearbox"

    # Changed and invalid files are picked up on the next scan without a restart.
    (tmp_path / "engine.dbc").write_text(engine.replace("Engine", "EngineUpdated"))
    (tmp_path / "invalid.dbc").write_text("not a dbc")
    folder.checked = 0
    library, info = folder.read(parse_dbc)
    assert decode_frame(frame(), library)["message_name"] == "EngineUpdated"
    assert next(f for f in info["files"] if f["filename"] == "invalid.dbc")["status"] == "error"

    (tmp_path / "duplicate.dbc").write_text(engine)
    folder.checked = 0
    library, info = folder.read(parse_dbc)
    assert len(info["conflicts"]) == 1
    assert decode_frame(frame(), library)["decode_status"] == "dbc_conflict"
    assert decode_frame({**frame(), "can_id": 292}, library)["decode_status"] == "decoded"
    (tmp_path / "duplicate.dbc").unlink()
    (tmp_path / "gearbox.DBC").unlink()
    folder.checked = 0
    library, info = folder.read(parse_dbc)
    assert not info["conflicts"]
    assert decode_frame(frame(), library)["decode_status"] == "decoded"
    assert decode_frame({**frame(), "can_id": 292}, library)["decode_status"] == "unknown_id"


def test_folder_upload_survives_restart_and_invalid_replacement(admin):
    app, client = admin
    can = app.state.runtime.can
    can.persist(CanBatch.model_validate(batch()), utcnow())
    response = client.post("/api/v1/can/dbc/files", json=dict(filename="engine.dbc", content=DBC))
    assert response.status_code == 200
    file = can.dbc_folder.folder / "engine.dbc"
    assert file.read_text() == DBC
    can.dbc_folder = DbcFolder(can.dbc_folder.folder)  # simulate a new process
    result = client.get("/api/v1/can/latest").json()
    assert result["dbc_library"]["files"][0]["filename"] == "engine.dbc"
    assert result["frames"][0]["dbc_file"] == "engine.dbc"
    assert (
        client.post(
            "/api/v1/can/dbc/files", json=dict(filename="engine.dbc", content="invalid")
        ).status_code
        == 422
    )
    assert file.read_text() == DBC
    for name in ["../escape.dbc", "C:escape.dbc", "CON.dbc"]:
        assert (
            client.post("/api/v1/can/dbc/files", json=dict(filename=name, content=DBC)).status_code
            == 422
        )
    assert (
        client.post("/api/v1/can/dbc/files", content=b"x" * (6 * 1024 * 1024 + 1)).status_code
        == 413
    )
    client.headers.pop("X-CSRF-Token")
    assert (
        client.post("/api/v1/can/dbc/files", json=dict(filename="x.dbc", content=DBC)).status_code
        == 403
    )


def test_folder_size_and_encoding(tmp_path):
    engine = DBC.split("BO_ 2147483939")[0].replace("km/h", "°C")
    (tmp_path / "legacy.dbc").write_bytes(engine.encode("cp1252"))
    (tmp_path / "large.dbc").write_bytes(b" " * (2 * 1024 * 1024 + 1))
    folder = DbcFolder(tmp_path)
    library, info = folder.read(parse_dbc)
    assert decode_frame(frame(), library)["signals"][0]["unit"] == "°C"
    assert next(f for f in info["files"] if f["filename"] == "large.dbc")["status"] == "error"
