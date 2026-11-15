#!/usr/bin/env python3
"""Regression check for inline <script> blocks of patched LuCI templates.

Usage: check_template_js.py <rootfs_dir> <build_dir>
Each <% ... %> block is replaced by an identifier, then every script block of the original
and of the patched template is run through `node --check`. A block that parses in the
original but not in the patched file is a regression introduced by the pack.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)


def blocks(path):
    src = open(path, encoding="utf-8", errors="ignore").read()
    src = re.sub(r"<%.*?%>", "X", src, flags=re.S)
    return [b for b in SCRIPT.findall(src) if b.strip()]


def ok(code, tmpdir):
    p = os.path.join(tmpdir, "b.js")
    open(p, "w", encoding="utf-8").write(code)
    return subprocess.run(["node", "--check", p], capture_output=True).returncode == 0


def main():
    root, build = sys.argv[1:3]
    regress = checked = 0
    with tempfile.TemporaryDirectory() as td:
        for e in json.load(open(os.path.join(build, "manifest.json"))):
            if not e["path"].endswith(".htm"):
                continue
            ob = blocks(root + e["path"])
            nb = blocks(os.path.join(build, "files") + e["path"])
            # blocks added by the panel pack are checked on their own
            for b in [b for b in nb if "miwifi-panel-i18n" in b]:
                checked += 1
                if not ok(b, td):
                    regress += 1
                    print("ADDED BLOCK FAILS", e["path"])
            nb = [b for b in nb if "miwifi-panel-i18n" not in b]
            if len(ob) != len(nb):
                print("BLOCK COUNT", e["path"])
                regress += 1
                continue
            for i, (o, n) in enumerate(zip(ob, nb)):
                if o == n:
                    continue
                checked += 1
                if ok(o, td) and not ok(n, td):
                    regress += 1
                    print("REGRESSION", e["path"], "script #", i)
    print(f"changed script blocks checked: {checked}, regressions: {regress}")
    sys.exit(1 if regress else 0)


if __name__ == "__main__":
    main()
