"""Bounded, app-only ESP32 image validation. No device writes occur here."""

import hashlib
import struct

MAX_IMAGE = 0x1F0000
MAX_UPLOAD = 6 * 1024 * 1024
PROTOCOL_MARKER = b"NAVSPHERE_OTA_PROTOCOL_1\0"


def intel_hex(data: bytes) -> bytes:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise ValueError("HEX must contain ASCII Intel HEX records") from exc
    blocks = []
    base = 0
    eof = False
    total = 0
    for line in lines:
        if not line.strip():
            continue
        if eof or not line.startswith(":") or len(line) > 521:
            raise ValueError("Invalid Intel HEX record or data after EOF")
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise ValueError("Invalid Intel HEX encoding") from exc
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 255:
            raise ValueError("Intel HEX length/checksum mismatch")
        length, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        value = record[4:-1]
        if kind == 0:
            if address + length > 0x10000:
                raise ValueError("HEX record crosses its address window")
            if length:
                blocks.append((base + address, value))
                total += length
                if total > MAX_IMAGE:
                    raise ValueError("Firmware exceeds OTA slot size")
        elif kind == 1 and length == 0 and address == 0:
            eof = True
        elif kind in (2, 4) and length == 2 and address == 0:
            base = int.from_bytes(value, "big") << (4 if kind == 2 else 16)
        elif kind in (3, 5) and length == 4 and address == 0:
            pass  # Entry point is taken from the ESP image header.
        else:
            raise ValueError("Unsupported Intel HEX record")
    if not eof or not blocks:
        raise ValueError("HEX requires image data and EOF")
    blocks.sort()
    origin = blocks[0][0]
    if origin not in (0, 0x10000, 0x200000):
        raise ValueError("HEX must contain only an application at 0, 0x10000 or 0x200000")
    output = bytearray()
    for address, value in blocks:
        if address != origin + len(output):
            raise ValueError(
                "HEX contains gaps, overlaps or multiple flash regions; export app only"
            )
        output.extend(value)
    return bytes(output)


def inspect_image(filename: str, raw: bytes) -> tuple[bytes, dict]:
    if len(raw) > MAX_UPLOAD:
        raise ValueError("Upload exceeds 6 MiB")
    if filename.lower().endswith(".hex"):
        data = intel_hex(raw)
    elif filename.lower().endswith(".bin"):
        data = raw
    else:
        raise ValueError("Choose an application .bin or Intel .hex file")
    if not 288 <= len(data) <= MAX_IMAGE:
        raise ValueError("Application size is invalid for the OTA slot")
    if data[0] != 0xE9 or not 1 <= data[1] <= 16 or struct.unpack_from("<H", data, 12)[0] != 0:
        raise ValueError("Expected a classic ESP32 application image")
    if data[23] != 1 or data[32:36] != bytes.fromhex("3254cdab"):
        raise ValueError("Expected an ESP-IDF application with an appended SHA-256")

    def field(offset):
        try:
            return data[offset : offset + 32].split(b"\0", 1)[0].decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Invalid application descriptor") from exc

    version, project = field(48), field(80)
    if project != "firmware" or not version or PROTOCOL_MARKER not in data:
        raise ValueError(
            "Choose NavSphere firmware with OTA protocol 1 support; legacy images would remove OTA"
        )
    cursor, checksum = 24, 0xEF
    for _ in range(data[1]):
        if cursor + 8 > len(data):
            raise ValueError("Truncated segment header")
        length = struct.unpack_from("<I", data, cursor + 4)[0]
        cursor += 8
        if cursor + length > len(data):
            raise ValueError("Truncated image segment")
        for value in data[cursor : cursor + length]:
            checksum ^= value
        cursor += length
    checksum_at = cursor | 15
    image_end = checksum_at + 1
    if image_end + 32 != len(data) or data[checksum_at] != checksum:
        raise ValueError(
            "Image checksum/length mismatch; merged and signed flash bundles are not accepted"
        )
    digest = hashlib.sha256(data[:image_end]).digest()
    if digest != data[image_end:]:
        raise ValueError("Image SHA-256 mismatch")
    return data, {
        "filename": filename,
        "version": version,
        "project": project,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "image_sha256": digest.hex(),
        "elf_sha256": data[176:208].hex(),
    }
