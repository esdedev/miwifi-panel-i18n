#!/bin/sh
# miwifi-panel-i18n - take the pack down.
#   remove.sh            stock panel again; the pack stays in /data/panel for a later install
#   remove.sh restore    everything back as it was before the first install: language and
#                        WAN VLAN settings, cron line; /data/panel and the backup are deleted
P=/data/panel
B=/data/panel_backup
M=$P/manifest.txt
MIRROR=/tmp/panel_mirror
busy=0

if [ -f "$M" ]; then
    # replaced files first, then mirrored directories
    while read -r orig _ path; do
        [ "$orig" = "-" ] && continue
        if grep -qs " $path " /proc/mounts; then umount "$path" || busy=1; fi
    done < "$M"
    while read -r orig _ path; do
        [ "$orig" = "-" ] || continue
        dir=${path%/*}
        if grep -qs " $dir " /proc/mounts; then umount "$dir" || busy=1; fi
    done < "$M"
fi
rm -f "$P/enabled" /tmp/luci-indexcache
if [ "$busy" = 1 ]; then
    # a mirror still mounted over a stock directory: deleting it would empty that directory
    echo "warning: some files are still in use and stay mounted until the next reboot"
else
    rm -rf "$MIRROR" /tmp/panel_pack.state
fi

put() {  # put <uci path>: the saved value, or delete it if it did not exist
    if [ -s "$B/$1" ]; then uci set "$1=$(cat "$B/$1")"; else uci -q delete "$1"; fi
}

if [ "$1" = "restore" ]; then
    [ -f "$B/complete" ] || { echo "no backup in $B: nothing to restore"; exit 1; }
    wantag_now=$(uci -q get port_service.wan.wantag)
    put luci.main.lang
    put luci.languages.en
    put port_service.wantag_attr
    [ -s "$B/port_service.wantag_attr" ] && put port_service.wantag_attr.vid
    put port_service.wan.wantag
    uci commit luci
    uci commit port_service
    sed -i '/\/data\/panel\/apply.sh/d' /etc/crontabs/root
    [ -f /data/ssh/boot.sh ] && sed -i '/\/data\/panel\/apply.sh/d' /data/ssh/boot.sh  # older installs
    /etc/init.d/cron restart >/dev/null 2>&1
    # rebuild the WAN if the VLAN setting changed
    [ "$wantag_now" != "$(uci -q get port_service.wan.wantag)" ] && /usr/sbin/port_service restart wan >/dev/null 2>&1
    rm -rf "$P" "$B"
    echo "panel pack removed; settings are back to how they were before the first install"
    exit 0
fi

# plain remove: language settings as before; a VLAN setting is kept but ignored until the
# pack is back
if [ -f "$B/complete" ]; then
    put luci.main.lang
    put luci.languages.en
else
    uci set luci.main.lang=zh_cn  # installed by an older version, without a backup
fi
uci commit luci
[ "1" = "$(uci -q get port_service.wan.wantag)" ] && /usr/sbin/port_service restart wan >/dev/null 2>&1
echo "panel pack removed (files kept in $P)"
