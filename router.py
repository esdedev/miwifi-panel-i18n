#!/usr/bin/env python3
"""Talk to the router over SSH: fetch its web files, install, remove, restore or check the pack.

Usage:
  python router.py fetch   [IP]           copy the router's web files to ./rootfs
  python router.py install [IP] [--yes]  upload ./build/pack and turn it on
  python router.py remove  [IP]           back to the stock panel (the pack stays on the router)
  python router.py restore [IP]           undo everything: back to how the router was before
  python router.py status  [IP]

IP defaults to 192.168.31.1. Needs root SSH on the router and the `ssh` client
(built into Windows 10/11, macOS and Linux). Each command opens one SSH session, so a
password is asked at most once. Extra ssh options: MIWIFI_SSH_OPTS="-i key -p 22".
"""
import argparse
import io
import os
import shlex
import shutil
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACT_KW = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}

# Old dropbear builds on stock firmware only offer ssh-rsa host keys.
SSH_BASE = ["ssh", "-o", "HostKeyAlgorithms=+ssh-rsa", "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa"]

# Router paths the build reads (everything else on the router is left alone)
FETCH_PATHS = ["www", "usr/lib/lua/luci/view", "lib/miwifi/arch/lib_arch_port_service.sh",
               "usr/share/xiaoqiang/xiaoqiang_version"]
FETCH_REQUIRED = ["www", "usr/lib/lua/luci/view"]

PACK_ACTIVE_CHECK = (
    "if grep -qs '^applied' /tmp/panel_pack.state || grep -qs ' /usr/lib/lua/luci/view' /proc/mounts; then "
    "echo 'The pack is active: its files would be fetched instead of the originals.' >&2; "
    "echo 'Run: python router.py remove, then fetch again.' >&2; exit 3; fi"
)


def ssh_cmd(ip, remote):
    extra = shlex.split(os.environ.get("MIWIFI_SSH_OPTS", ""))
    return SSH_BASE + extra + [f"root@{ip}", remote]


def safe_members(tf):
    """Only plain files and directories, and only below the extraction directory."""
    for m in tf:
        name = m.name.replace("\\", "/")
        if (name.startswith("/") or ".." in name.split("/") or ":" in name.split("/")[0]
                or not (m.isfile() or m.isdir())):
            print(f"  skipped unexpected entry: {m.name}")
            continue
        yield m


def fetch(ip):
    dest = os.path.join(HERE, "rootfs")
    required = " ".join(f"[ -e {p} ] || {{ echo 'not found on the router: /{p}' >&2; exit 4; }};"
                        for p in FETCH_REQUIRED)
    present = "; ".join(f"[ -e {p} ] && set -- \"$@\" {p}" for p in FETCH_PATHS)
    remote = f"{PACK_ACTIVE_CHECK}; cd / && {required} set --; {present}; tar -cf - \"$@\""
    print(f"Fetching the web files from {ip}...")
    p = subprocess.Popen(ssh_cmd(ip, remote), stdout=subprocess.PIPE)
    tmp = dest + ".partial"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        with tarfile.open(fileobj=p.stdout, mode="r|") as tf:
            n = 0
            for m in safe_members(tf):
                tf.extract(m, tmp, **EXTRACT_KW)
                n += m.isfile()
    except tarfile.ReadError:
        n = 0
    rc = p.wait()
    if rc != 0 or n == 0:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"error: fetch failed (ssh exit code {rc})")
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(tmp, dest)
    ver = os.path.join(dest, "usr/share/xiaoqiang/xiaoqiang_version")
    print(f"{n} files in {dest}")
    if os.path.exists(ver):
        for line in open(ver, encoding="utf-8"):
            if "option ROM" in line or "option HARDWARE" in line:
                print("  " + line.strip())
    print("Next: python build.py")


def pack_tar(pack):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        def add(path, arc):
            ti = tf.gettarinfo(path, arc)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            if ti.isfile():
                ti.mode = 0o755 if arc.endswith(".sh") else 0o644
            with open(path, "rb") as fh:
                tf.addfile(ti, fh)
        for base, _, files in os.walk(os.path.join(pack, "files")):
            for f in sorted(files):
                full = os.path.join(base, f)
                add(full, os.path.relpath(full, pack).replace("\\", "/"))
        add(os.path.join(pack, "manifest.txt"), "manifest.txt")
        add(os.path.join(pack, "info.txt"), "info.txt")
        add(os.path.join(pack, "language.txt"), "language.txt")
        for s in ("apply.sh", "install.sh", "remove.sh"):
            add(os.path.join(HERE, "router", s), s)
    return buf.getvalue()


def install(ip, yes):
    pack = os.path.join(HERE, "build", "pack")
    if not os.path.exists(os.path.join(pack, "manifest.txt")):
        sys.exit("error: no pack in build/pack. Run: python build.py")
    info = open(os.path.join(pack, "info.txt"), encoding="utf-8").read()
    print(info)
    if "status: experimental" in info and not yes:
        print("This firmware has not been tested with the pack. It checks every file before\n"
              "applying and can be removed with `python router.py remove`.")
        if input("Install it anyway? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            sys.exit("Cancelled.")
    data = pack_tar(pack)
    remote = ("rm -rf /tmp/panel_upload && mkdir -p /tmp/panel_upload && "
              "tar -C /tmp/panel_upload -xf - && sh /tmp/panel_upload/install.sh")
    print(f"Uploading {len(data) // 1024} KiB to {ip}...")
    rc = subprocess.run(ssh_cmd(ip, remote), input=data).returncode
    if rc != 0:
        sys.exit(f"error: install failed (exit code {rc})")
    print(f"\nDone. Open http://{ip} and reload the page (Ctrl+F5).")


def remove(ip, restore=False):
    remote = ("if [ -f /data/panel/remove.sh ]; then sh /data/panel/remove.sh"
              + (" restore" if restore else "") + "; else echo 'pack not installed'; fi")
    sys.exit(subprocess.run(ssh_cmd(ip, remote)).returncode)


def status(ip):
    remote = ("cat /data/panel/info.txt 2>/dev/null || echo 'pack not installed'; "
              "echo; echo -n 'state: '; cat /tmp/panel_pack.state 2>/dev/null || echo 'not applied yet'; "
              "echo -n 'language: '; uci -q get luci.main.lang; "
              "echo -n 'WAN VLAN: '; [ \"$(uci -q get port_service.wan.wantag)\" = 1 ] && "
              "uci -q get port_service.wantag_attr.vid || echo off")
    sys.exit(subprocess.run(ssh_cmd(ip, remote)).returncode)


def main():
    for stream in (sys.stdout, sys.stderr):  # a console or pipe in a legacy code page
        stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["fetch", "install", "remove", "restore", "status"])
    ap.add_argument("ip", nargs="?", default="192.168.31.1")
    ap.add_argument("--yes", action="store_true", help="install: do not ask on experimental firmware")
    a = ap.parse_args()
    if not shutil.which("ssh"):
        sys.exit("error: the ssh command was not found")
    {"fetch": lambda: fetch(a.ip), "install": lambda: install(a.ip, a.yes),
     "remove": lambda: remove(a.ip), "restore": lambda: remove(a.ip, True), "status": lambda: status(a.ip)}[a.command]()


if __name__ == "__main__":
    main()
