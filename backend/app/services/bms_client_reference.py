"""Read the audited BE client as data; never import or execute its bundled code."""

import hashlib
import io
import marshal
import struct
import zlib
from functools import lru_cache
from pathlib import Path

from xdis import magics, unmarshal

CLIENT_SHA256 = "84b51a8589b89a337cff76587fa7155786001ab0962ea6e9f868d930b2fa0232"
CLIENT_VERSION = "15.0.4"


def client_reference(release):
    path = Path(release) / "client" / "amp_uds_client.exe"
    if not path.is_file():
        raise ValueError("Original AMP client is missing from the local reference project")
    return _read(str(path), path.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _read(filename, modified):
    del modified
    path = Path(filename)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Unsupported AMP client package size")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != CLIENT_SHA256:
        raise ValueError("AMP client has changed; its workflow must be reviewed before use")
    pos = data.rfind(b"MEI\x0c\x0b\x0a\x0b\x0e")
    _, size, offset, length, _, _ = struct.unpack("!8sIIII64s", data[pos : pos + 88])
    base = pos + 88 - size
    toc, end = base + offset, base + offset + length
    while toc < end:
        count, start, packed, _, compressed, _ = struct.unpack("!iIIIBc", data[toc : toc + 18])
        name = data[toc + 18 : toc + count].rstrip(b"\0")
        toc += count
        if name != b"PYZ-00.pyz":
            continue
        pyz = data[base + start : base + start + packed]
        pyz = zlib.decompress(pyz) if compressed else pyz
        index = dict(marshal.loads(pyz[struct.unpack("!I", pyz[8:12])[0] :]))
        _, start, length = index["amp"]
        code = unmarshal.load_code(
            io.BytesIO(zlib.decompress(pyz[start : start + length])),
            magics.magic2int(pyz[4:8]),
        )
        client = next(c for c in code.co_consts if getattr(c, "co_name", "") == "AmpClient")
        auth = next(
            c for c in client.co_consts if getattr(c, "co_name", "") == "authenticate_bootloader"
        )
        keys = [
            bytes(c)
            for c in auth.co_consts
            if isinstance(c, tuple)
            and len(c) == 16
            and all(isinstance(v, int) and 0 <= v <= 255 for v in c)
        ]
        if len(keys) != 1:
            raise ValueError("Invalid local bootloader authentication material")
        # Private mapping: only version/hash may be used in API metadata or saved reports.
        return {"boot_auth_key": keys[0], "sha256": CLIENT_SHA256, "version": CLIENT_VERSION}
    raise ValueError("AMP client authentication definition was not found")
