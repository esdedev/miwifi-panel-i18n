#!/bin/sh
# Run a stock Xiaomi web panel in Docker, without a router (for development and screenshots).
#
#   sh dev/emulator.sh image  <firmware.bin>       build a Docker image from an official firmware
#   sh dev/emulator.sh rootfs <firmware.bin>       write ./rootfs for build.py (no router needed)
#   sh dev/emulator.sh run    <firmware.bin> [port] [--pack]
#                                                  web panel on http://127.0.0.1:<port> (8080);
#                                                  --pack installs ./build/pack first
#
# Needs Docker with arm64 emulation (Docker Desktop has it; on Linux: qemu-user-static/binfmt).
# The emulated panel has no hardware behind it: live data (clients, Wi-Fi, WAN) stays empty.
set -e
cmd=$1 fw=$2
[ -n "$cmd" ] && [ -f "$fw" ] || { sed -n '2,11p' "$0"; exit 2; }
REPO=$(cd "$(dirname "$0")/.." && pwd)
host_path() { (cd "$1" && pwd -W 2>/dev/null) || (cd "$1" && pwd); }   # Git Bash on Windows
dk() { MSYS_NO_PATHCONV=1 docker "$@"; }   # no Git Bash path rewriting for docker

WORK="$REPO/dev/.work"
mkdir -p "$WORK"
ver=$(python3 "$REPO/dev/unpack_firmware.py" "$fw" "$WORK" 2>/dev/null || python "$REPO/dev/unpack_firmware.py" "$fw" "$WORK")
echo "$ver"
tag=$(echo "$ver" | sed -n 's/^model \([^,]*\), version \(.*\)$/\1-\2/p' | tr 'A-Z' 'a-z')
IMAGE="miwifi-stock:${tag:-unknown}"

unsquash() {  # $@ = paths to extract (none = everything); tar on stdout
    dk run --rm -v "$(host_path "$WORK"):/work:ro" debian:stable-slim sh -c \
        "export DEBIAN_FRONTEND=noninteractive; apt-get -qq update >/dev/null 2>&1 && apt-get -qq install -y squashfs-tools >/dev/null 2>&1 &&
         unsquashfs -q -n -d /tmp/r /work/rootfs.squashfs $* >/dev/null && tar -C /tmp/r -cf - ."
}

case "$cmd" in
image)
    unsquash | dk import --platform linux/arm64 - "$IMAGE"
    echo "image $IMAGE ready" ;;
rootfs)
    rm -rf "$REPO/rootfs" && mkdir -p "$REPO/rootfs"
    unsquash www usr/lib/lua/luci/view lib/miwifi/arch/lib_arch_port_service.sh \
        usr/share/xiaoqiang/xiaoqiang_version | tar -C "$REPO/rootfs" -xf -
    echo "wrote $REPO/rootfs; next: python build.py" ;;
run)
    port=${3:-8080}; pack=0
    for a in "$@"; do [ "$a" = --pack ] && pack=1; done
    case "$port" in --pack) port=8080 ;; esac
    dk image inspect "$IMAGE" >/dev/null 2>&1 || "$0" image "$fw"
    pw=$(python3 -c 'import secrets; print(secrets.token_hex(6))' 2>/dev/null || python -c 'import secrets; print(secrets.token_hex(6))')
    dk rm -f miwifi-emulator >/dev/null 2>&1 || true
    dk run -d --name miwifi-emulator --privileged --platform linux/arm64 \
        -e WITH_PACK=$pack -e ADMIN_PW="$pw" -p "127.0.0.1:$port:80" \
        -v "$(host_path "$REPO"):/repo:ro" "$IMAGE" /bin/sh /repo/dev/emulator/serve.sh >/dev/null
    echo "web panel: http://127.0.0.1:$port  (admin password of this emulator: $pw)"
    echo "logs: docker logs miwifi-emulator    stop: docker rm -f miwifi-emulator" ;;
*)
    sed -n '2,11p' "$0"; exit 2 ;;
esac
