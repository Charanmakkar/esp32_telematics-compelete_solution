"""Read the local reference, resolve CANdela services, never execute reference scripts."""

import hashlib
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.bms_client_reference import CLIENT_SHA256, CLIENT_VERSION

PROJECT = Path(__file__).resolve().parents[3]
DEFAULT_REFERENCE = PROJECT.parent / "HVBEOSK" / "be_repo"


def text(node, tag="NAME"):
    found = node.find(tag)
    return " ".join("".join(found.itertext()).split()) if found is not None else ""


def hex_bytes(value):
    value = re.sub(r"[\s,:_-]", "", str(value)).replace("0x", "").replace("0X", "")
    if len(value) % 2 or not re.fullmatch(r"[a-fA-F0-9]*", value):
        raise ValueError("Enter complete hexadecimal bytes")
    return bytes.fromhex(value)


def encode_fields(fields, values):
    result = bytearray()
    for field in fields:
        if "constant" in field:
            result.extend(bytes.fromhex(field["constant"]))
            continue
        value = values.get(field["key"], field.get("default", ""))
        size = field["bytes"]
        if field["kind"] == "hex":
            raw = hex_bytes(value)
            if len(raw) < field.get("min_bytes", size or 0) or (
                size is not None and len(raw) != size
            ):
                raise ValueError(f"{field['name']}: expected {size or 'variable'} bytes")
        else:
            try:
                numeric = (
                    float(value)
                    if field.get("float")
                    else Decimal(int(str(value), 16))
                    if str(value).lower().startswith("0x")
                    else Decimal(str(value))
                )
                if not math.isfinite(numeric):
                    raise ValueError("Nonfinite value")
                if field.get("float"):
                    numeric = (numeric - field.get("offset", 0)) / field.get("factor", 1)
                    raw = struct.pack(
                        ("<" if field["little"] else ">") + ("f" if size == 4 else "d"), numeric
                    )
                else:
                    numeric = (numeric - Decimal(str(field.get("offset", 0)))) / Decimal(
                        str(field.get("factor", 1))
                    )
                    if numeric != int(numeric):
                        raise ValueError("Value cannot be represented exactly")
                    raw = int(numeric).to_bytes(
                        size,
                        "little" if field["little"] else "big",
                        signed=field.get("signed", False),
                    )
            except (ValueError, OverflowError, TypeError, struct.error, InvalidOperation) as exc:
                raise ValueError(f"{field['name']}: invalid value for {size} bytes") from exc
        result.extend(raw)
    if not 1 <= len(result) <= 4095:
        raise ValueError("Diagnostic request must contain 1–4095 bytes")
    return bytes(result)


def decode_fields(fields, payload):
    decoded, warnings, offset = [], [], 0
    for field in fields:
        size = field["bytes"]
        if size is None:
            size = len(payload) - offset
        raw = payload[offset : offset + size]
        if len(raw) != size:
            warnings.append(f"{field['name']}: response is shorter than the CDD definition")
            break
        offset += size
        if "constant" in field:
            if raw.hex().upper() != field["constant"]:
                warnings.append(f"{field['name']}: response does not match the CDD constant")
            continue
        value, label = raw.hex().upper(), None
        if field["kind"] == "number":
            if field.get("float"):
                value = struct.unpack(
                    ("<" if field["little"] else ">") + ("f" if size == 4 else "d"), raw
                )[0]
            else:
                value = int.from_bytes(
                    raw, "little" if field["little"] else "big", signed=field.get("signed", False)
                )
            label = field.get("choices", {}).get(str(value))
            value = value * field.get("factor", 1) + field.get("offset", 0)
            if not math.isfinite(value):
                value = None
        decoded.append(dict(name=field["name"], value=value, label=label, hex=raw.hex().upper()))
    if offset < len(payload):
        warnings.append(
            f"{len(payload) - offset} additional response bytes retained in raw response"
        )
    return decoded, warnings


class BmsCatalog:
    def __init__(self, reference_root=""):
        self.root = Path(reference_root) if reference_root else DEFAULT_REFERENCE
        self.release = self.root / "45_Release" / "abs_hv_bms_release"
        self.services = {}
        self.presets = {}
        self.metadata = {}
        self.error = None
        try:
            self._load()
        except (OSError, ValueError, ET.ParseError, KeyError) as exc:
            self.error = (
                f"Cannot load BMS reference: {type(exc).__name__}. Check BMS_REFERENCE_ROOT."
            )

    def _load(self):
        cdd = self.release / "documents" / "BMS.cdd"
        raw = cdd.read_bytes()
        if len(raw) > 8 * 1024 * 1024 or b"<!ENTITY" in raw:
            raise ValueError("Unsupported CDD")
        root = ET.fromstring(raw)
        self.ids = {e.get("id"): e for e in root.iter() if e.get("id")}
        for instance in root.findall(".//DIAGINST"):
            template = self.ids[instance.get("tmplref")]
            constants, proxies = {}, {}
            for value in instance.findall("STATICVALUE"):
                shared = self.ids[value.get("shstaticref")]
                for ref in shared.findall("STATICCOMPREF"):
                    constants[ref.get("idref")] = int(value.get("v"))
            for content in instance.findall("SIMPLECOMPCONT"):
                shared = self.ids[content.get("shproxyref")]
                for ref in shared.findall("PROXYCOMPREF"):
                    proxies[ref.get("idref")] = content
            for service in instance.findall("SERVICE"):
                protocol = self.ids[self.ids[service.get("tmplref")].get("tmplref")]
                request = self._fields(protocol.find("REQ"), constants, proxies)
                response = self._fields(protocol.find("POS"), constants, proxies)
                sid = int(request[0]["constant"], 16)
                prefix = "".join(f["constant"] for f in request if "constant" in f)
                identifier = int(prefix[2:6], 16) if sid in (0x22, 0x2E) else None
                risk = (
                    "read"
                    if sid in (0x22, 0x3E) or (sid == 0x31 and prefix[2:4] == "03")
                    else "change"
                )
                if (
                    sid in (0x11, 0x34, 0x36, 0x37)
                    or identifier in (0xCE00, 0xCE01, 0xCE02, 0xF16A, 0xFD06, 0xFD09)
                    or sid == 0x31
                ):
                    risk = "critical" if not (sid == 0x31 and prefix[2:4] == "03") else "read"
                notes = []
                if sid == 0x31:
                    notes.append(
                        (
                            "CDD routine IDs differ from the application F200–F205 table. "
                            "This entry sends the CDD definition exactly; use verified script "
                            "presets for programming."
                        )
                    )
                if identifier in (
                    0xFD06,
                    0xFD07,
                    0xFD0A,
                    0xFD0B,
                    0xFD0C,
                    0xFD0D,
                    0xFD0E,
                    0xFD0F,
                    0xF013,
                    0xE000,
                    0xD002,
                    0xD003,
                    0xD004,
                ):
                    notes.append(
                        (
                            "CDD layout may differ from the supplied firmware. Raw response is"
                            " authoritative; script presets also provide source-based "
                            "decoding."
                        )
                    )
                self.services[service.get("id")] = dict(
                    id=service.get("id"),
                    name=text(instance).replace("_", " "),
                    action=text(service),
                    group=text(template),
                    sid=sid,
                    identifier=identifier,
                    request_fields=request,
                    response_fields=response,
                    request_prefix=prefix,
                    risk=risk,
                    sensitive=sid == 0x27 or identifier == 0xF16A,
                    source="BMS.cdd",
                    notes=notes,
                )
        config_path = self.release / "client" / "config.json"
        config = json.loads(config_path.read_text())
        ecu = config["ecus"]["abs_hv"]
        targets = [
            dict(
                ecu=ecu_name,
                instance=int(k),
                name=v["name"],
                tx_id=int(v["request_id"], 16),
                rx_id=int(v["response_id"], 16),
            )
            for ecu_name, definition in config["ecus"].items()
            for k, v in definition["instance_id"].items()
        ]
        self.contracts = self._source_contracts()
        for path in sorted((self.release / "client" / "client_scripts").glob("*.bat")):
            self.presets[path.stem] = self._preset(path)
        self.metadata = dict(
            cdd_sha256=hashlib.sha256(raw).hexdigest(),
            cdd_instances=len(root.findall(".//DIAGINST")),
            services=len(self.services),
            scripts=len(self.presets),
            reference_root=str(self.root),
            targets=targets,
            bitrate=ecu["baud_rate"] * 1000,
            source_read_only=True,
            client_version=CLIENT_VERSION,
            client_sha256=CLIENT_SHA256,
        )

    def _source_contracts(self):
        folder = self.root / "15_Construction/projects/bms/hv_bms/abs/amp_config/uds"
        header = (folder / "app_uds_dids.h").read_text(errors="replace")
        source = (folder / "app_uds_dids.c").read_text(errors="replace")
        definitions = {
            name: int(value, 16)
            for name, value in re.findall(r"#define\s+(\w+)\s+\((0x[0-9a-fA-F]+)", header)
        }
        sessions = {"Default": 1, "Programming": 2, "Extended": 3, "Manufacturing": 4}
        result = {}
        for body in re.findall(r"static\s+const\s+TsUdsDID\s+\w+\s*=\s*\{([^}]+)\}", source):
            parts = [value.strip() for value in body.split(",")]
            if len(parts) < 10 or parts[1] not in definitions:
                continue

            def security(value):
                return 0 if value.endswith("_Locked") else int(value.rsplit("_", 1)[-1], 16)

            try:
                result[definitions[parts[1]]] = dict(
                    read_allowed=parts[2] == "true",
                    read_session=sessions[parts[3].replace("eUdsDiagnosticSession", "")],
                    read_security=security(parts[4]),
                    write_allowed=parts[5] == "true",
                    write_session=sessions[parts[6].replace("eUdsDiagnosticSession", "")],
                    write_security=security(parts[7]),
                    handler=parts[8],
                )
            except (KeyError, ValueError):
                continue
        return result

    def _field(self, node, name=None):
        dtype = self.ids.get(node.get("dtref"))
        val = dtype.find("CVALUETYPE") if dtype is not None else None
        kind, size = "hex", None
        info = {}
        if val is not None:
            bits = int(val.get("bl", 8))
            count = int(val.get("minsz", 1)) if val.get("qty") == "field" else 1
            size = bits * count // 8 if bits % 8 == 0 else None
            if val.get("qty") == "field" and val.get("minsz") != val.get("maxsz"):
                size = None
            if val.get("qty") != "field" and bits in (8, 16, 32, 64):
                kind = "number"
            info = dict(
                little=val.get("bo") == "12",
                signed=val.get("enc") == "sgn",
                float=val.get("enc") == "flt",
            )
            comp = dtype.find("COMP")
            if comp is not None:
                info.update(factor=float(comp.get("f", 1)), offset=float(comp.get("o", 0)))
            choices = {
                str(m.get("s")): text(m, "TEXT")
                for m in dtype.findall("TEXTMAP")
                if m.get("s") == m.get("e")
            }
            if choices:
                info["choices"] = choices
        return dict(
            name=name or text(node) or node.tag,
            kind=kind,
            bytes=size,
            default=node.get("def", ""),
            **info,
        )

    def _fields(self, container, constants, proxies):
        result = []

        def visit(node):
            if node.tag in ("NAME", "QUAL", "DESC"):
                return
            if node.tag == "CONSTCOMP" or node.get("id") in constants:
                val = int(node.get("v")) if node.tag == "CONSTCOMP" else constants[node.get("id")]
                size = int(node.get("bl", 0)) // 8 or self._field(node)["bytes"]
                result.append(
                    dict(
                        name=text(node),
                        bytes=size,
                        constant=val.to_bytes(size, "big").hex().upper(),
                    )
                )
            elif node.tag == "SIMPLEPROXYCOMP":
                content = proxies.get(node.get("id"))
                if content is not None:
                    for child in content:
                        visit(child)
                elif node.get("dest") != "resCode":
                    lo, hi = int(node.get("minbl", 0)) // 8, node.get("maxbl")
                    result.append(
                        dict(
                            name=text(node),
                            kind="hex",
                            bytes=int(hi) // 8 if hi and int(hi) // 8 == lo else None,
                            min_bytes=lo
                            if node.get("must") == "1" and node.get("mustAtRT") != "0"
                            else 0,
                            default="",
                        )
                    )
            elif node.tag == "DATAOBJ":
                result.append(self._field(node))
            elif node.tag in ("CONTENTCOMP", "SIMPLECOMPCONT", "STRUCT"):
                for child in node:
                    visit(child)

        for node in container:
            visit(node)
        for index, field in enumerate(result):
            field["key"] = f"field_{index}"
        # AMP transfer exit uses no optional parameter record.
        if result and result[0].get("constant") in ("37", "77"):
            for field in result[1:]:
                field["min_bytes"] = 0
        return result

    def _preset(self, path):
        content = path.read_text(errors="replace")
        read = re.search(r"--did_read\s+(0x[0-9a-fA-F]+)", content)
        write = re.search(r"--did_write\s+(0x[0-9a-fA-F]+)\s+([^\r\n]+)", content)
        program = re.search(r"--(app|cal)_download\s+([^\s]+)", content)
        application_mode = bool(re.search(r"--app(?:\s|$)", content))
        session = re.search(r"--diag_session\s+(\d+)", content)
        operation = (
            "write"
            if write
            else "read"
            if read
            else "program"
            if program
            else "erase_app"
            if "--app_erase" in content
            else "clear_dtc"
            if "--clear_dtc" in content
            else "unmute"
            if "--unmute" in content
            else "mute"
            if "--mute" in content
            else None
        )
        if operation is None:
            raise ValueError(f"Unsupported script: {path.name}")
        did = int((write or read).group(1), 16) if write or read else None
        defaults = write.group(2).strip().strip('"') if write else ""
        inputs = []
        if write:
            if did in (0xC000, 0xF18C):
                inputs = [
                    dict(
                        key="text",
                        label="QR code" if did == 0xC000 else "Serial number",
                        kind="text",
                        default="",
                    )
                ]
            elif did == 0xF013:
                inputs = [
                    dict(key="instance", label="New instance ID (1–15)", kind="number", default="")
                ]
            elif did == 0xFD20:
                inputs = [
                    dict(key=k, label=label, kind="text", default="")
                    for k, label in [
                        ("location", "Location (2 ASCII characters)"),
                        ("build", "Build number (4 digits)"),
                        ("date", "Julian date YYDDD (5 digits)"),
                        ("part", "Part number (10 digits)"),
                    ]
                ]
            else:
                raw = bytes(int(v.strip(), 0) for v in defaults.split(","))
                defaults = raw.hex().upper()
        image = None
        notes = []
        ecu_match = re.search(r"\b(abs_hv(?:_old)?)\s+--", content)
        if not ecu_match:
            raise ValueError(f"Cannot identify ECU profile in {path.name}")
        ecu_name = ecu_match.group(1)
        if "--transport docan %port%" in content:
            notes.append(
                "Script has an invalid transport/port argument. The GUI uses the configured "
                "500 kbit/s CAN transport and preserves its DID, payload and session defaults."
            )
        contract = self.contracts.get(did)
        if did == 0xF013 and write:
            notes.append(
                (
                    "Source uses two big-endian bytes and programming session 02, "
                    "unlike the script's extended session. Application firmware "
                    "ignores the supplied instance and learns its pack ID from ADC "
                    "straps; readback may differ. Bootloader behavior depends on its "
                    "version."
                )
            )
        if program:
            if "program_bootloader" in path.stem:
                notes.append(
                    "This bootloader image is staged at 0x01100000 by the matching boot "
                    "updater. Follow the release's 0.4.0/0.6.0 migration order; load the "
                    "matching updater first. This is not a direct installed-bootloader write."
                )
            image = (path.parent / program.group(2).replace("\\", "/")).resolve()
            if not image.is_relative_to(self.release.resolve()):
                raise ValueError("Programming path is outside reference release")
            if image.name == "abs_hv_bootloader_0_5_0.hex" and not image.exists():
                supplied = image.with_name("abs_hv_bootloader_v0_5_0.hex")
                if supplied.exists():
                    image = supplied
                    notes.append(
                        (
                            "Script filename omits 'v'; using the supplied "
                            "abs_hv_bootloader_v0_5_0.hex. Verify its fingerprint before "
                            "programming."
                        )
                    )
            image = str(image.relative_to(self.release.resolve()))
        return dict(
            id=path.stem,
            name=path.stem.replace("abs_hv_", "").replace("_", " "),
            source=path.name,
            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            ecu=ecu_name,
            operation=operation,
            did=did,
            default_hex=defaults if not inputs else "",
            inputs=inputs,
            session=int(session.group(1)) if session else None,
            app=application_mode,
            image=image,
            image_kind=program.group(1) if program else None,
            risk="read"
            if operation == "read" and application_mode
            else "critical"
            if not application_mode
            or operation in ("program", "erase_app", "mute", "unmute", "clear_dtc", "read")
            or did in (0xCE00, 0xCE01, 0xCE02, 0xFD06, 0xFD09)
            else "change",
            fixed_instance=0 if "abs_hv_string_00" in content else None,
            verify_instance=did == 0xF013 and bool(write),
            notes=notes,
            source_contract=contract,
        )

    def public(self):
        return dict(
            metadata=self.metadata,
            error=self.error,
            services=list(self.services.values()),
            presets=list(self.presets.values()),
        )

    def target(self, ecu="abs_hv", instance=1):
        for target in self.metadata["targets"]:
            if target["ecu"] == ecu and target["instance"] == instance:
                return target
        raise ValueError("Unknown BMS address profile or instance")

    def security_key(self, ecu="abs_hv"):
        config = json.loads((self.release / "client" / "config.json").read_text())
        value = config["ecus"][ecu]["security_key"]
        raw = bytes(value) if isinstance(value, list) else hex_bytes(value)
        if len(raw) != 16:
            raise ValueError("Local BMS security key must contain 16 bytes")
        return raw
