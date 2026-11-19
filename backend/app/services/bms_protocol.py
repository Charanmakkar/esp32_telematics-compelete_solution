"""Source-backed BMS script encoding and bounded Intel HEX loading."""

import hashlib
import re
import time
import zlib
from pathlib import Path

NRC = {
    0x10: "General reject",
    0x11: "Service not supported",
    0x12: "Subfunction not supported",
    0x13: "Incorrect length or format",
    0x21: "Busy, repeat request",
    0x22: "Conditions not correct",
    0x24: "Request sequence error",
    0x31: "Request out of range",
    0x33: "Security access denied",
    0x35: "Invalid key",
    0x36: "Exceeded security attempts",
    0x37: "Security delay not expired",
    0x70: "Upload/download not accepted",
    0x71: "Transfer suspended",
    0x72: "Programming failure",
    0x73: "Wrong block counter",
    0x78: "Response pending",
    0x7E: "Subfunction unavailable in session",
    0x7F: "Service unavailable in session",
}


def validate_response(request, response):
    if len(response) == 3 and response[0] == 0x7F and response[1] == request[0]:
        raise ValueError(f"NRC 0x{response[2]:02X}: {NRC.get(response[2], 'ECU rejected request')}")
    if not response or response[0] != request[0] + 0x40:
        raise ValueError("Response service ID does not match request")
    echo = (
        2
        if request[0] in (0x22, 0x2E)
        else 3
        if request[0] == 0x31
        else 1
        if request[0] in (0x10, 0x11, 0x27, 0x28, 0x36, 0x3E)
        else 0
    )
    if len(response) < 1 + echo or response[1 : 1 + echo] != request[1 : 1 + echo]:
        raise ValueError("Response identifier/subfunction does not match request")
    return response


def preset_request(preset, values):
    op, did = preset["operation"], preset["did"]
    if op == "read":
        return bytes([0x22]) + did.to_bytes(2, "big")
    if op == "clear_dtc":
        return bytes.fromhex("14FFFFFF")
    if op in ("mute", "unmute"):
        return bytes([0x28, 0x81 if op == "mute" else 0x80])
    if op in ("program", "erase_app"):
        return None
    raw = bytes.fromhex(preset["default_hex"]) if preset["default_hex"] else b""
    if did in (0xC000, 0xF18C):
        size = 60 if did == 0xC000 else 32
        raw = str(values.get("text", "")).encode("ascii")
        if not raw or len(raw) > size:
            raise ValueError(f"Enter 1–{size} ASCII characters")
        raw = raw.ljust(62 if did == 0xC000 else size, b"\x00")
    elif did == 0xF013:
        instance = int(values.get("instance", 0))
        if not 1 <= instance <= 15:
            raise ValueError("Instance must be 1–15")
        raw = instance.to_bytes(2, "big")
    elif did == 0xFD20:
        location = str(values.get("location", "")).encode("ascii")
        if len(location) != 2:
            raise ValueError("Location must contain two ASCII characters")
        raw = bytearray(32)
        raw[11:13] = location[::-1]
        for key, offset, size in (("build", 13, 4), ("date", 17, 5), ("part", 22, 10)):
            digits = str(values.get(key, ""))
            if not re.fullmatch(rf"[0-9]{{{size}}}", digits):
                raise ValueError(f"{key}: enter {size} digits")
            raw[offset : offset + size] = bytes(int(d) for d in reversed(digits))
        raw = bytes(raw)
    return bytes([0x2E]) + did.to_bytes(2, "big") + raw


def decode_preset(preset, response):
    if preset["operation"] != "read":
        return [], []
    did, raw = preset["did"], response[3:]
    rows, warnings = [], []
    if did == 0xC000:
        rows = [
            dict(name="QR code", value=raw[:60].rstrip(b"\x00").decode("ascii", errors="replace"))
        ]
        if len(raw) == 62:
            rows += [
                dict(name="QR CRC", value=f"0x{raw[60]:02X}"),
                dict(name="QR locked", value=raw[61] == 1),
            ]
        else:
            warnings.append(f"Expected 62 QR bytes; received {len(raw)}")
    elif did in (0xF18C, 0xF191):
        rows = [
            dict(
                name="Serial number" if did == 0xF18C else "Customer hardware part number",
                value=raw.rstrip(b"\x00").decode("ascii", errors="replace"),
            )
        ]
    elif did == 0xF010:
        value = int.from_bytes(raw, "big")
        rows = [
            dict(
                name="BMS mode",
                value=value,
                label={1: "Bootloader", 2: "Application"}.get(value, "Unknown"),
            )
        ]
    elif did in (0xD001, 0xD002, 0xD003, 0xD004, 0xD005, 0xFD08):
        rows = [dict(name=f"DID 0x{did:04X}", value=int.from_bytes(raw, "big"))]
    elif did == 0xFD07:
        if len(raw) != 540:
            warnings.append(f"Expected 540 open-wire bytes; received {len(raw)}")
        rows = [
            dict(
                name=f"Cell {i // 3 + 1}",
                value=int.from_bytes(raw[i : i + 2], "big"),
                unit="mV",
                label="valid" if raw[i + 2] & 1 else "invalid",
            )
            for i in range(0, len(raw) - 2, 3)
        ]
    elif 0xFD0A <= did <= 0xFD0F:
        dimensions = {
            0xFD0A: (6, 1),
            0xFD0B: (6, 6),
            0xFD0C: (6, 8),
            0xFD0D: (6, 8),
            0xFD0E: (6, 8),
            0xFD0F: (6, 8),
        }
        height, width = dimensions[did]
        if len(raw) != height * width * 4:
            warnings.append(f"Expected {height * width * 4} histogram bytes; received {len(raw)}")
        rows = [
            dict(
                name=f"Bin {i // 4 // width + 1}, {i // 4 % width + 1}",
                value=int.from_bytes(raw[i : i + 4], "big"),
                row=i // 4 // width,
                column=i // 4 % width,
            )
            for i in range(0, len(raw) - 3, 4)
        ]
        warnings.append(
            "Histogram values are source-defined counters; bin order follows the BMS array."
        )
    elif did == 0xFD06 and len(raw) >= 2:
        rows = [
            dict(name="Algorithm enabled", value=raw[0]),
            dict(name="Override enabled", value=raw[1]),
        ]
        rows += [
            dict(name=f"Cell {i + 1}", value=bool(raw[2 + i // 8] & (1 << (i % 8))))
            for i in range(min(180, (len(raw) - 2) * 8))
        ]
    elif did == 0xFD20 and len(raw) == 32:
        rows = [dict(name="Location", value=raw[11:13][::-1].decode("ascii", errors="replace"))]
        rows += [
            dict(name=key, value="".join(format(x, "X") for x in raw[offset : offset + size][::-1]))
            for key, offset, size in (
                ("Build", 13, 4),
                ("Julian date", 17, 5),
                ("Part number", 22, 10),
            )
        ]
        warnings.append(
            (
                "The supplied application source has a placeholder FD20 handler: "
                "example reads and no persistent write."
            )
        )
    elif did == 0xF013:
        rows = [dict(name="Instance / learned pack ID", value=int.from_bytes(raw, "big"))]
        if len(raw) != 2:
            warnings.append("Source defines a two-byte instance ID.")
    else:
        rows = [dict(name=f"DID 0x{did:04X}", value=raw.hex().upper())]
    return rows, warnings


def load_hex(path: Path, client_format=False, inject_crc=False):
    if not path.is_file():
        raise ValueError(
            f"Image is missing: {path.name}. "
            "Place a replacement in bms_images and select its filename."
        )
    raw = path.read_bytes()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("HEX image exceeds 8 MB")
    memory, base, eof = {}, 0, False
    for line_no, line in enumerate(raw.decode("ascii").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if eof or not line.startswith(":"):
            raise ValueError(f"Invalid HEX record at line {line_no}")
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise ValueError(f"Invalid HEX at line {line_no}") from exc
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 255:
            raise ValueError(f"HEX checksum/length error at line {line_no}")
        size, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        data = record[4:-1]
        if kind == 0:
            for offset, value in enumerate(data):
                loc = base + address + offset
                if loc > 0xFFFFFFFF or loc in memory:
                    raise ValueError("Overlapping or overflowing HEX addresses")
                memory[loc] = value
        elif kind == 1:
            if size or address:
                raise ValueError("Invalid HEX EOF")
            eof = True
        elif kind in (2, 4):
            if size != 2 or address:
                raise ValueError("Invalid HEX address record")
            base = int.from_bytes(data, "big") << (4 if kind == 2 else 16)
        elif kind in (3, 5):
            if size != 4:
                raise ValueError("Invalid HEX entry point")
        else:
            raise ValueError("Unsupported HEX record type")
    if not eof or not memory:
        raise ValueError("HEX image must contain data and EOF")
    segments = []
    for address in sorted(memory):
        if not segments or address != segments[-1][0] + len(segments[-1][1]):
            segments.append((address, bytearray()))
        segments[-1][1].append(memory[address])
    if len(segments) > 256:
        raise ValueError("Image has more than 256 disjoint segments")
    if client_format:
        start, end = min(memory), max(memory) + 1
        length = (end - start + 7) // 8 * 8
        if length > 8 * 1024 * 1024:
            raise ValueError("Prepared image span exceeds 8 MB")
        image = bytearray([0xFF]) * length
        for address, byte in memory.items():
            image[address - start] = byte
        if inject_crc:
            if len(image) < 4:
                raise ValueError("Image is too short for CRC insertion")
            image[:4] = zlib.crc32(image[4:]).to_bytes(4, "big")
        segments = [(start, image)]
    for address, data in segments:
        if address % 8 or len(data) % 8:
            raise ValueError("AMP download requires 8-byte aligned segments")
    return dict(
        name=path.name,
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=sum(len(d) for _, d in segments),
        source_bytes=len(memory),
        crc_injected=inject_crc,
        download_sha256=hashlib.sha256(b"".join(d for _, d in segments)).hexdigest(),
        segments=[dict(address=a, length=len(d)) for a, d in segments],
    ), segments


def validate_image_region(entry, segments):
    # BE bootloader BATs use relocated updater images, not the installed BL address.
    if "bootloader" in entry["id"]:
        low, high = 0x1100000, 0x1118000
    elif entry["image_kind"] == "cal":
        low, high = 0xFD0000, 0xFF0000
    else:
        low, high = 0x1000000, 0x1100000
    if any(address < low or address + len(data) > high for address, data in segments):
        raise ValueError(
            "Image addresses do not belong to the selected BMS component; no erase permitted"
        )


def program_image(exchange, segments, image_kind, progress, cancelled):
    """Stop immediately on failed erase/download/check; never retry a write."""
    base = 0xF202 if image_kind == "cal" else 0xF200

    def routine(rid, check=None):
        header = rid.to_bytes(2, "big")
        result = exchange(b"\x31\x01" + header, timeout=60000)
        if check == "compatibility":
            if len(result) != 5 or result[4] != 0:
                raise ValueError("Image compatibility check failed")
            return
        if len(result) < 5 or result[4] not in (1, 2):
            raise ValueError("BMS refused to start routine")
        deadline = time.monotonic() + 60
        while True:
            if cancelled():
                raise ValueError("Cancelled; BMS programming may be incomplete")
            result = exchange(b"\x31\x03" + header, timeout=10000)
            if len(result) < 5:
                raise ValueError("Truncated routine result")
            if result[4] == 2:
                if check == "integrity" and (len(result) < 6 or result[5] != 1):
                    raise ValueError("Image integrity check failed")
                break
            if result[4] in (0, 3) or time.monotonic() > deadline:
                raise ValueError("Routine failed or timed out")
            time.sleep(0.1)

    progress("Erasing application" if image_kind != "cal" else "Erasing calibration")
    routine(base)
    if not segments:
        return
    done, total = 0, sum(len(data) for _, data in segments)
    for address, data in segments:
        result = exchange(
            b"\x34\x00\x44" + address.to_bytes(4, "big") + len(data).to_bytes(4, "big")
        )
        width = result[1] >> 4 if len(result) > 1 else 0
        if not 1 <= width <= 4 or len(result) != width + 2:
            raise ValueError("Invalid download block length response")
        maximum = int.from_bytes(result[2:], "big") - 2
        block = min(1024, maximum) // 8 * 8
        if block < 8:
            raise ValueError("ECU block limit is too small")
        sequence = 1
        for offset in range(0, len(data), block):
            if cancelled():
                raise ValueError("Cancelled; BMS programming may be incomplete")
            chunk = data[offset : offset + block]
            exchange(bytes([0x36, sequence]) + chunk, timeout=10000)
            done += len(chunk)
            sequence = (sequence + 1) & 255
            progress(f"Transferring {done:,} / {total:,} bytes")
        exchange(b"\x37")
    progress("Checking image integrity")
    routine(base + 1, "integrity")
    progress("Checking image compatibility")
    routine(0xF205 if image_kind == "cal" else 0xF204, "compatibility")
