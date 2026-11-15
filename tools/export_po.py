#!/usr/bin/env python3
"""Append our LuCI-template translations to an xmir-patcher style base.en.po.

Usage: export_po.py <base.en.po> <rootfs_dir> <translations.json> <header comment>

Only `<%: ... %>` msgids that the .po does not know yet (by text or hash) are appended, as
plain `msgid "<chinese>"` / `msgstr "<english>"` entries with a `#:` reference to one
template. SPA/raw-template strings are not .po material and are left out.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pack import safe_markup  # noqa: E402
from lmo import key_id, norm, parse_po  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")


def po_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def main():
    po, root, tr_path, header = sys.argv[1:5]
    text, hashed = parse_po(po)
    known = {key_id(k) for k in text} | set(hashed)
    tr = {norm(k): v for k, v in json.load(open(tr_path, encoding="utf-8")).items()}
    found = {}
    for f in sorted(glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True)):
        rel = "/" + os.path.relpath(f, root).replace(os.sep, "/")
        for m in re.findall(r"<%:(.*?)%>", open(f, encoding="utf-8", errors="ignore").read(), re.S):
            s = norm(m)
            if CJK.search(s) and key_id(s) not in known and s not in found and s in tr:
                found[s] = rel
    raw = open(po, "rb").read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    out = [nl, f"# {header}{nl}"]
    for s, rel in found.items():
        out.append(f"{nl}#: {rel}{nl}msgid {po_str(s)}{nl}msgstr {po_str(safe_markup(tr[s]))}{nl}")
    with open(po, "a", encoding="utf-8", newline="") as fh:
        fh.write("".join(out))
    print(f"appended {len(found)} entries to {po}")


if __name__ == "__main__":
    main()
