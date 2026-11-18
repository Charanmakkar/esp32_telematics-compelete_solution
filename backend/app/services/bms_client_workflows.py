"""AMP 15.0.4 workflows, audited against the BE release's CLI/module bytecode."""

import hmac
import secrets
import time

from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.cmac import CMAC


def cmac(key, data):
    mac = CMAC(algorithms.AES(key))
    mac.update(data)
    return mac.finalize()


def unlock(exchange, level, key):
    seed = exchange(bytes([0x27, level]))[2:]
    if len(seed) != 16:
        raise ValueError("Security seed must contain 16 bytes")
    if any(seed):
        exchange(bytes([0x27, level + 1]) + cmac(key, seed))


def tester_present(exchange):
    # One ESP32-side burst preserves the client's 100 ms cadence despite MQTT latency.
    exchange(b"\x3e\x80", timeout=4000, expect_response=False, repeat=20)


def prepare_mode(entry, exchange, pause=time.sleep):
    if entry["app"]:
        tester_present(exchange)
        pause(0.6)
        return
    # CLI bootloader_trap: bounded two attempts, reset then suppressed tester-present.
    for _ in range(2):
        try:
            exchange(b"\x11\x01", timeout=2000)
        except ValueError as exc:
            if "timeout" not in str(exc).lower() and "timed out" not in str(exc).lower():
                raise
            exchange(b"\x11\x01", expect_response=False)
            pause(0.1)
        tester_present(exchange)
        mode = exchange(b"\x22\xf0\x10")
        if mode == b"\x62\xf0\x10\x01":
            return
        if mode != b"\x62\xf0\x10\x02":
            raise ValueError("Invalid BMS run-mode response")
    raise ValueError("BMS did not enter its bootloader; operation stopped before erasure")


def authenticate_bootloader(exchange, key):
    challenge = secrets.token_bytes(16)
    expected = cmac(key, challenge)
    exchange(b"\x27\x06" + challenge)
    actual = exchange(b"\x27\x05")[2:]
    if len(actual) != 16 or not hmac.compare_digest(actual, expected):
        raise ValueError("Bootloader authentication failed; no erase was sent")


def program_client_image(
    exchange,
    segments,
    image_kind,
    progress,
    cancelled,
    image_id=0,
    data_only_block_length=False,
    reset_after=True,
    pause=time.sleep,
):
    erase, integrity, compatibility = (
        (0x0201, 0x0212, 0x0213) if image_kind == "cal" else (0xFF00, 0x0210, 0x0211)
    )
    suffix = bytes([image_id]) if image_id else b""
    if segments and len(segments) != 1:
        raise ValueError("Client image must be prepared as one contiguous span before erasure")
    if cancelled():
        raise ValueError("Cancelled before erasure")

    def routine(rid, verify=False):
        request = rid.to_bytes(2, "big") + suffix
        exchange(b"\x31\x01" + request, timeout=60000)
        deadline = time.monotonic() + 60
        while True:
            if cancelled():
                raise ValueError("Cancelled; BMS programming may be incomplete")
            raw = exchange(b"\x31\x03" + request, timeout=10000)
            if len(raw) < 5:
                raise ValueError("Truncated routine status")
            if raw[4] == 2:
                if verify and (len(raw) < 6 or raw[5] != 1):
                    raise ValueError("Image integrity check failed; no reset sent")
                return
            if raw[4] != 1 or time.monotonic() >= deadline:
                raise ValueError("Routine failed or timed out")
            pause(0.2 if verify else 1)

    progress("Erasing calibration" if image_kind == "cal" else "Erasing application")
    routine(erase)
    if not segments:
        return
    address, data = segments[0]
    raw = exchange(b"\x34\x00\x44" + address.to_bytes(4, "big") + len(data).to_bytes(4, "big"))
    width = raw[1] >> 4 if len(raw) > 1 else 0
    if not 1 <= width <= 4 or len(raw) != width + 2:
        raise ValueError("Invalid download block limit")
    maximum = int.from_bytes(raw[2:], "big")
    if maximum < 128:
        raise ValueError("AMP client requires a transfer block limit of at least 128 bytes")
    block = min(4093, maximum if data_only_block_length else maximum - 2)
    sequence = 1
    for offset in range(0, len(data), block):
        if cancelled():
            raise ValueError("Cancelled; BMS programming may be incomplete")
        chunk = data[offset : offset + block]
        exchange(bytes([0x36, sequence]) + chunk, timeout=10000)
        sequence = (sequence + 1) & 255
        progress(f"Transferring {offset + len(chunk):,} / {len(data):,} bytes")
    exchange(b"\x37")
    progress("Checking image integrity")
    routine(integrity, verify=True)
    progress("Checking image compatibility")
    raw = exchange(b"\x31\x01" + compatibility.to_bytes(2, "big") + suffix)
    if len(raw) < 5 or int.from_bytes(raw[4:], "big") != 0:
        raise ValueError("Image compatibility check failed; no reset sent")
    if reset_after:
        progress("Restarting BMS after successful programming")
        exchange(b"\x11\x01")
        pause(0.2)
