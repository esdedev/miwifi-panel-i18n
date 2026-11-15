#!/usr/bin/env python3
"""Extract the squashfs root filesystem from an official Xiaomi HDR1 firmware image.

Usage: unpack_firmware.py <firmware.bin> <out_dir>

Writes <out_dir>/rootfs.squashfs and prints the firmware version. Unpack it with
`unsquashfs -d rootfs rootfs.squashfs` (squashfs-tools; dev/emulator.sh does it in Docker).

HDR1 layout: magic, u32 signed length, u32 CRC32, u16 type, u16 model, then 32 x u32 offsets of
sub-image headers (u16 0xbabe, u32 flash address, u32 size, name at +0x10, data at +0x30).
The `root.ubi` sub-image is a raw UBI image: volume 0 is the kernel, volume 1 the squashfs.
"""
import os
import re
import struct
import sys


def sub_images(fw: bytes):
    if fw[:4] != b"HDR1":
        sys.exit("error: not a Xiaomi HDR1 firmware image")
    for i in range(32):
        off = struct.unpack_from("<I", fw, 0x10 + 4 * i)[0]
        if not off or off + 0x30 > len(fw):
            continue
        size = struct.unpack_from("<I", fw, off + 8)[0]
        name = fw[off + 0x10:off + 0x30].split(b"\0")[0].decode("ascii", "replace")
        yield name, fw[off + 0x30:off + 0x30 + size]


def ubi_volumes(d: bytes) -> dict:
    """Rebuild UBI volumes; for duplicate logical blocks the highest sqnum wins."""
    pebs = [i for i in range(0, len(d), 0x1000) if d[i:i + 4] == b"UBI#"]
    if len(pebs) < 2:
        sys.exit("error: root.ubi has fewer than two UBI erase blocks")
    peb = pebs[1] - pebs[0]
    vols = {}
    for p in range(0, len(d), peb):
        if d[p:p + 4] != b"UBI#":
            continue
        vid_off, data_off = struct.unpack_from(">II", d, p + 16)
        v = p + vid_off
        if d[v:v + 4] != b"UBI!":
            continue
        vol_type = d[v + 5]
        vol_id, lnum = struct.unpack_from(">II", d, v + 8)
        data_size = struct.unpack_from(">I", d, v + 20)[0]
        sqnum = struct.unpack_from(">Q", d, v + 40)[0]
        if vol_id >= 0x7FFFEFFF:  # layout volume
            continue
        n = data_size if vol_type == 2 and data_size else peb - data_off
        blocks = vols.setdefault(vol_id, {})
        if lnum not in blocks or sqnum > blocks[lnum][0]:
            blocks[lnum] = (sqnum, d[p + data_off:p + data_off + n])
    return {vid: b"".join(b[i][1] for i in sorted(b)) for vid, b in vols.items()}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    fw = open(sys.argv[1], "rb").read()
    out = sys.argv[2]
    parts = dict(sub_images(fw))
    ver = parts.get("xiaoqiang_version", b"").decode("utf-8", "replace")
    info = dict(re.findall(r"option\s+(\w+)\s+'([^']*)'", ver))
    print(f"model {info.get('HARDWARE', '?')}, version {info.get('ROM', '?')}")
    if "root.ubi" not in parts:
        sys.exit("error: no root.ubi in this image")
    squash = [v for v in ubi_volumes(parts["root.ubi"]).values() if v[:4] == b"hsqs"]
    if not squash:
        sys.exit("error: no squashfs volume found")
    # trim to the size recorded in the squashfs superblock (bytes_used at +40)
    used = struct.unpack_from("<Q", squash[0], 40)[0]
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "rootfs.squashfs")
    open(path, "wb").write(squash[0][:used])
    print(f"{path}: {used} bytes")


if __name__ == "__main__":
    main()
