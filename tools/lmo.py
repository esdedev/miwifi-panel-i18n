"""LuCI .lmo helpers: SuperFastHash key ids, reader and writer (own implementation).

LMO layout (big-endian):
  values ...            each value padded to a 4-byte boundary
  index[]               (key_id, val_id, offset, length) u32 x4, sorted by key_id
  u32 index_offset      last 4 bytes of the file
Keys are hashed after whitespace normalisation (collapse runs, strip), as LuCI does.
"""
from __future__ import annotations

import re
import struct

M32 = 0xFFFFFFFF


def _s8(b: int) -> int:
    return b - 256 if b > 127 else b


def sfh(data: bytes) -> int:
    """Paul Hsieh's SuperFastHash as implemented in LuCI (signed-char tail bytes)."""
    n = len(data)
    if n == 0:
        return 0
    h = n & M32
    rem, i = n & 3, 0
    for _ in range(n >> 2):
        h = (h + (data[i] | data[i + 1] << 8)) & M32
        tmp = (((data[i + 2] | data[i + 3] << 8) << 11) ^ h) & M32
        h = ((h << 16) ^ tmp) & M32
        h = (h + (h >> 11)) & M32
        i += 4
    if rem == 3:
        h = (h + (data[i] | data[i + 1] << 8)) & M32
        h ^= (h << 16) & M32
        h ^= (_s8(data[i + 2]) << 18) & M32
        h = (h + (h >> 11)) & M32
    elif rem == 2:
        h = (h + (data[i] | data[i + 1] << 8)) & M32
        h ^= (h << 11) & M32
        h = (h + (h >> 17)) & M32
    elif rem == 1:
        h = (h + _s8(data[i])) & M32
        h ^= (h << 10) & M32
        h = (h + (h >> 1)) & M32
    h ^= (h << 3) & M32
    h = (h + (h >> 5)) & M32
    h ^= (h << 4) & M32
    h = (h + (h >> 17)) & M32
    h ^= (h << 25) & M32
    h = (h + (h >> 6)) & M32
    return h


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def key_id(msgid: str) -> int:
    return sfh(norm(msgid).encode("utf-8"))


def read_lmo(path: str) -> dict[int, str]:
    with open(path, "rb") as fh:
        d = fh.read()
    idx = struct.unpack(">I", d[-4:])[0]
    out = {}
    for o in range(idx, len(d) - 4, 16):
        k, _v, off, ln = struct.unpack_from(">IIII", d, o)
        out[k] = d[off:off + ln].decode("utf-8", errors="replace")
    return out


def write_lmo(path: str, entries: dict[int, str]) -> None:
    """entries: {key_id: translated text}."""
    blob, index = bytearray(), []
    for k in sorted(entries):
        val = entries[k].encode("utf-8")
        index.append((k, sfh(val), len(blob), len(val)))
        blob += val
        blob += b"\x00" * (-len(blob) % 4)
    idx_off = len(blob)
    for e in index:
        blob += struct.pack(">IIII", *e)
    blob += struct.pack(">I", idx_off)
    with open(path, "wb") as fh:
        fh.write(bytes(blob))


def parse_po(path: str) -> tuple[dict[str, str], dict[int, str]]:
    """Return ({text msgid: msgstr}, {hash msgid: msgstr}) from an xmir-style .po.

    Supports `msgid "text"` and xmir's `msgid 0xHASH` form, multi-line strings, CRLF.
    """
    text, hashed = {}, {}
    cur_id, cur_str, key = None, "", None

    def unesc(s: str) -> str:
        return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")

    def flush():
        if cur_id is None:
            return
        if isinstance(cur_id, int):
            hashed[cur_id] = cur_str
        elif cur_id:
            text[cur_id] = cur_str

    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\r\n")
        m = re.match(r"^msgid 0x([0-9A-Fa-f]{8})\s*$", line)
        if m:
            flush()
            cur_id, cur_str, key = int(m.group(1), 16), "", "id"
            continue
        m = re.match(r'^(msgid|msgstr) "(.*)"$', line)
        if m:
            if m.group(1) == "msgid":
                flush()
                cur_id, cur_str, key = unesc(m.group(2)), "", "id"
            else:
                cur_str, key = unesc(m.group(2)), "str"
            continue
        if line.startswith('"') and key:
            if key == "id" and isinstance(cur_id, str):
                cur_id += unesc(line[1:-1])
            elif key == "str":
                cur_str += unesc(line[1:-1])
    flush()
    return text, hashed
