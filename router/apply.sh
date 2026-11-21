#!/bin/sh
# miwifi-panel-i18n - boot-time apply (stock Xiaomi firmware; tested on RD15 1.0.87).
# Called every minute from cron; does its work once per boot.
#
# Nothing is written to the read-only firmware: pack files live in /data/panel/files and are
# bind-mounted over the originals (RAM mounts, gone after a reboot until re-applied).
# Fail-closed: if any original file's SHA-256 differs from the manifest (other firmware),
# nothing is mounted.
P=/data/panel
M=$P/manifest.txt
STATE=/tmp/panel_pack.state
MIRROR=/tmp/panel_mirror

[ -f "$STATE" ] && exit 0
[ -f "$P/enabled" ] && [ -f "$M" ] || exit 0
# cron and install.sh may start it at the same moment
mkdir /tmp/panel_pack.lock 2>/dev/null || exit 0
trap 'rmdir /tmp/panel_pack.lock' EXIT
[ -f "$STATE" ] && exit 0

log() { logger -t panel_pack "$*"; echo "$*" > "$STATE"; }
sum() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }

# 1. verify firmware and pack integrity before touching anything
while read -r orig new path; do
    [ "$(sum "$P/files$path")" = "$new" ] || { log "pack file corrupt: $path"; exit 1; }
    [ "$orig" = "-" ] && continue
    [ "$(sum "$path")" = "$orig" ] || { log "firmware changed (e.g. after an update): $path - not applied. Rebuild the pack"; exit 1; }
done < "$M"

# 2. new files: mirror their directory into RAM, add the file, bind the mirror over the dir
while read -r orig _ path; do
    [ "$orig" = "-" ] || continue
    dir=${path%/*}
    if ! grep -qs " $dir " /proc/mounts; then
        mkdir -p "$MIRROR$dir"
        cp -a "$dir/." "$MIRROR$dir/"
        mount --bind "$MIRROR$dir" "$dir" || { log "mount failed: $dir"; exit 1; }
    fi
    cp "$P/files$path" "$path"
done < "$M"

# 3. replaced files: bind each pack file over the original
while read -r orig _ path; do
    [ "$orig" = "-" ] && continue
    grep -qs " $path " /proc/mounts && continue
    mount --bind "$P/files$path" "$path" || { log "mount failed: $path"; exit 1; }
done < "$M"

rm -f /tmp/luci-indexcache

# 4. port_service already ran at boot with the stock (VLAN-unaware) WAN setup
[ "1" = "$(uci -q get port_service.wan.wantag)" ] && /usr/sbin/port_service restart wan >/dev/null 2>&1

log "applied $(wc -l < "$M") files"
exit 0
