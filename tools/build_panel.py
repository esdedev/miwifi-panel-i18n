#!/usr/bin/env python3
"""Assemble the pack: translated UI (output of build_pack.py) + WAN VLAN feature + language menu.

Usage: build_panel.py <rootfs_dir> <i18n_build_dir> <out_dir>

Output: <out_dir>/files/<router path>, <out_dir>/manifest.json and manifest.txt
  manifest entries: {path, orig_sha256 (null = new file), new_sha256}
  manifest.txt lines: "<orig_sha256|-> <new_sha256> <path>" for the router-side scripts

Every patch is an exact text replacement that must match exactly once. On a firmware where an
anchor is missing or ambiguous, the feature that needs it is left out (with a warning) instead
of producing a broken file. The translated UI is built regardless.
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class AnchorError(Exception):
    pass


def replace_once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        raise AnchorError(f"'{what}': anchor found {n} times (expected 1)")
    return text.replace(old, new)


# --- arch_ps_setup_wan(): honour port_map <port>.dial_ifname (set by ps_setup_wan when
#     port_service.<service>.wantag=1). Stock only reads it for IPTV bridge mode.
ARCH = "lib/miwifi/arch/lib_arch_port_service.sh"
ARCH_OLD = """    wan_ifname=$(port_map iface port "$wan_port")
    wan6_ifname="$wan_ifname"
"""
ARCH_NEW = """    wan_ifname=$(port_map iface port "$wan_port")
    # miwifi-panel-i18n: use the 802.1Q device (e.g. eth0.1.20) when a WAN tag is set
    dial_ifname="$wan_ifname"
    [ "1" = "$(uci -q get port_service."$service".wantag)" ] && {
        dial_ifname=$(port_map config get "$wan_port" dial_ifname)
        [ -n "$dial_ifname" ] || dial_ifname="$wan_ifname"
    }
    wan6_ifname="$dial_ifname"
"""
ARCH_OLD2 = """        set network."$service".ifname="$wan_ifname"
"""
ARCH_NEW2 = """        set network."$service".ifname="$dial_ifname"
"""
ARCH_OLD3 = """        set network."macv_${service/n/n6}".ifname="$wan_ifname"
"""
ARCH_NEW3 = """        set network."macv_${service/n/n6}".ifname="$dial_ifname"
"""

WAN = "usr/lib/lua/luci/view/web/setting/wan.htm"
WAN_SECTION_ANCHOR = '        <div class="mod-set mod-macclone">\n'
WAN_SCRIPT_ANCHOR = '<%include("web/inc/netmod.js")%>\n'

SYSINFO = "usr/lib/lua/luci/view/web/inc/sysinfo.htm"
SYSINFO_OLD = 'romChannel == "release" and features["system"]["i18n"] == "1"'
SYSINFO_NEW = 'romChannel == "release"'

CONTROLLER = "usr/lib/lua/luci/controller/api/xqwanvlan.lua"


def build(root: str, i18n_build: str, out: str) -> dict:
    """Build the pack. Returns {"files": n, "features": {name: "ok" | reason}}."""
    files = os.path.join(out, "files")
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(i18n_build, "files"), files)
    manifest = {e["path"]: e for e in json.load(open(os.path.join(i18n_build, "manifest.json")))}
    features = {"translated_ui": "ok"}

    def current(rel):
        p = os.path.join(files, rel)
        src = p if os.path.exists(p) else os.path.join(root, rel)
        if not os.path.exists(src):
            raise AnchorError(f"{rel} not found in the rootfs")
        return open(src, encoding="utf-8").read()

    def write(rel, text, new_file=False):
        p = os.path.join(files, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        data = text.encode("utf-8")
        open(p, "wb").write(data)
        orig = None if new_file else sha(open(os.path.join(root, rel), "rb").read())
        manifest["/" + rel] = {"path": "/" + rel, "orig_sha256": orig, "new_sha256": sha(data)}

    # WAN VLAN: all patches or none
    try:
        arch = current(ARCH)
        arch = replace_once(arch, ARCH_OLD, ARCH_NEW, "arch wan ifname")
        arch = replace_once(arch, ARCH_OLD2, ARCH_NEW2, "arch network.wan.ifname")
        arch = replace_once(arch, ARCH_OLD3, ARCH_NEW3, "arch macv_wan6.ifname")
        wan = current(WAN)
        section = open(os.path.join(SRC, "wan_vlan_section.htm"), encoding="utf-8").read()
        script = open(os.path.join(SRC, "wan_vlan_script.htm"), encoding="utf-8").read()
        wan = replace_once(wan, WAN_SECTION_ANCHOR, section + WAN_SECTION_ANCHOR, "wan.htm section")
        wan = replace_once(wan, WAN_SCRIPT_ANCHOR, script + WAN_SCRIPT_ANCHOR, "wan.htm script")
    except AnchorError as e:
        features["wan_vlan"] = f"left out: {e}"
    else:
        write(ARCH, arch)
        write(WAN, wan)
        write(CONTROLLER, open(os.path.join(SRC, CONTROLLER), encoding="utf-8").read(), new_file=True)
        features["wan_vlan"] = "ok"

    try:
        t = replace_once(current(SYSINFO), SYSINFO_OLD, SYSINFO_NEW, "sysinfo language menu")
    except AnchorError as e:
        features["language_menu"] = f"left out: {e}"
    else:
        write(SYSINFO, t)
        features["language_menu"] = "ok"

    entries = sorted(manifest.values(), key=lambda e: e["path"])
    json.dump(entries, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    with open(os.path.join(out, "manifest.txt"), "w", newline="\n") as fh:
        for e in entries:
            fh.write(f"{e['orig_sha256'] or '-'} {e['new_sha256']} {e['path']}\n")
    return {"files": len(entries), "new": sum(1 for e in entries if e["orig_sha256"] is None),
            "features": features}


def main():
    root, i18n_build, out = sys.argv[1:4]
    r = build(root, i18n_build, out)
    print(f"pack: {r['files']} files ({r['new']} new)")
    for name, state in r["features"].items():
        print(f"  {name}: {state}")


if __name__ == "__main__":
    main()
