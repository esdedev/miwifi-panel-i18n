#!/usr/bin/env python3
"""Build the language pack for the stock panel from the web files of your own router.

Usage:
  python build.py [--lang CODE] [--rootfs DIR] [--po FILE] [--extra FILE.json ...] [--out DIR]

  --lang CODE    panel language: en (default) or any translations/<CODE>.json, e.g. es
  --rootfs DIR   router files fetched with `python router.py fetch` (default: rootfs)
  --po FILE      xmir-patcher's base.en.po (default: base.en.po; downloaded if missing)
  --extra FILE   more translations {chinese: english}, e.g. your own *.local.json
  --out DIR      output directory (default: build)

Result: <out>/pack, ready for `python router.py install`. Needs Python 3.10+. With Node.js installed,
the inline scripts of every changed template are also syntax-checked.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")
sys.path.insert(0, TOOLS)
import build_panel  # noqa: E402

# Firmware the pack has been tested on, on real hardware. Anything else builds and installs
# as experimental.
TESTED = {("RD15", "1.0.87")}

# xmir-patcher's community English .po (no license declared, so it is downloaded, not bundled)
PO_URL = ("https://raw.githubusercontent.com/openwrt-xiaomi/xmir-patcher/"
          "25b01d3e50fa13842f02c4f51d6a73a9eb84d5f1/data/base.en.po")
PO_SHA256 = "ed76a6d29a84673dcd7bf6c475fd1e31bc59e7ed6514d72ef61957afa4e6c61a"


def firmware_info(root):
    p = os.path.join(root, "usr/share/xiaoqiang/xiaoqiang_version")
    info = {}
    if os.path.exists(p):
        for k, v in re.findall(r"option\s+(\w+)\s+'([^']*)'", open(p, encoding="utf-8").read()):
            info[k] = v
    return info.get("HARDWARE", "unknown"), info.get("ROM", "unknown")


def get_po(path):
    if os.path.exists(path):
        return
    print(f"Downloading xmir-patcher's base.en.po\n  {PO_URL}")
    data = urllib.request.urlopen(PO_URL, timeout=30).read()
    if hashlib.sha256(data).hexdigest() != PO_SHA256:
        sys.exit("error: the downloaded base.en.po does not have the expected SHA-256")
    open(path, "wb").write(data)


def language(code):
    """Returns (translation file or None for English, native name)."""
    if code == "en":
        return None, "English"
    if code.endswith(".json") and os.path.exists(code):  # a file of your own, e.g. while translating
        return code, json.load(open(code, encoding="utf-8")).get("@name") or code
    path = os.path.join(HERE, "translations", f"{code}.json")
    if not re.fullmatch(r"[a-z]{2,3}(_[a-z]{2,4})?", code) or not os.path.exists(path):
        have = sorted(f[:-5] for f in os.listdir(os.path.join(HERE, "translations")) if f.endswith(".json"))
        sys.exit(f"error: no translations/{code}.json. Available: {', '.join(have)}")
    name = json.load(open(path, encoding="utf-8")).get("@name") or code
    return path, name


def run_tool(name, *args):
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(TOOLS, name), *args],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"error in {name}:\n{r.stdout}{r.stderr}")
    return r.stdout


def main():
    for stream in (sys.stdout, sys.stderr):  # a console or pipe in a legacy code page
        stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lang", default="en")
    ap.add_argument("--rootfs", default="rootfs")
    ap.add_argument("--po", default="base.en.po")
    ap.add_argument("--extra", action="append", default=[])
    ap.add_argument("--out", default="build")
    a = ap.parse_args()

    for d in ("www", "usr/lib/lua/luci/view"):
        if not os.path.isdir(os.path.join(a.rootfs, d)):
            sys.exit(f"error: {a.rootfs}/{d} not found. Fetch the router files first:\n"
                     f"  python router.py fetch 192.168.31.1")
    lang_file, lang_name = language(a.lang)
    model, rom = firmware_info(a.rootfs)
    tested = (model, rom) in TESTED
    get_po(a.po)

    i18n_out = os.path.join(a.out, "i18n")
    pack_out = os.path.join(a.out, "pack")
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    translations = ",".join([os.path.join(HERE, "translations", "en.json"), *a.extra])
    extra = ["--templates", os.path.join(HERE, "src")]
    if lang_file:
        extra += ["--lang", lang_file]
    log = run_tool("build_pack.py", a.po, a.rootfs, translations, i18n_out, *extra)
    result = build_panel.build(a.rootfs, i18n_out, pack_out)

    missing = len(json.load(open(os.path.join(i18n_out, "untranslated.json"), encoding="utf-8")))
    used = len(json.load(open(os.path.join(i18n_out, "strings_en.json"), encoding="utf-8")))
    not_in_lang = len(json.load(open(os.path.join(i18n_out, "missing_lang.json"), encoding="utf-8")))
    js = "skipped (Node.js not found)"
    if shutil.which("node"):
        js = run_tool("check_template_js.py", a.rootfs, pack_out).strip().splitlines()[-1]

    status = "tested" if tested else "experimental"
    lines = [
        f"miwifi-panel-i18n pack, built {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"firmware: {model} {rom}",
        f"language: {a.lang} ({lang_name})" + (
            f", {used - not_in_lang}/{used} strings translated" + (", the rest in English" if not_in_lang else "")
            if lang_file else ""),
        f"status: {status}",
        f"files: {result['files']} ({result['new']} new)",
        *[f"{k}: {v}" for k, v in result["features"].items()],
        f"strings without translation: {missing}",
        f"inline script check: {js}",
    ]
    with open(os.path.join(pack_out, "info.txt"), "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(pack_out, "language.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(lang_name + "\n")

    print(log.rstrip())
    print()
    print("\n".join(lines))
    print()
    if not tested:
        print(f"EXPERIMENTAL: this pack has only been tested on RD15 1.0.87, not on {model} {rom}.\n"
              "It was built from your router's own files and checks them again before applying,\n"
              "and it can be removed at any time, but some screens may look wrong. Please report\n"
              "how it went in an issue.\n")
    print(f"Ready: {pack_out}\nInstall: python router.py install 192.168.31.1")


if __name__ == "__main__":
    main()
