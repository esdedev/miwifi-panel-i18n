#!/bin/sh
# miwifi-panel-i18n - install from /tmp/panel_upload (sent by `python router.py install`).
#
# Before the first install it saves everything it is about to change in /data/panel_backup:
# the panel language settings, the WAN VLAN settings, the automatic update settings and the
# crontab. `remove.sh restore` puts those back exactly. The firmware itself is never written.
#
# Persistent changes:
#   /data/panel, /data/panel_backup
#   one cron line            runs /data/panel/apply.sh every minute (it works once per boot)
#   uci luci.main.lang=en, luci.languages.en=<language name>
#   automatic firmware updates off, unless AUTO_UPDATE=keep: the otapredownload cron line is
#   removed and otapred.settings.auto/plugin are set to 0. An automatic update would replace
#   the firmware: the pack stops, root access may be lost, and anti-rollback prevents going
#   back to the previous version.
set -e
U=/tmp/panel_upload
P=/data/panel
B=/data/panel_backup
CRON=/etc/crontabs/root
HOOK='* * * * * /data/panel/apply.sh >/dev/null 2>&1'
[ -f "$U/manifest.txt" ] || { echo "no upload in $U"; exit 1; }
[ -d /data ] || { echo "/data not found: is this a stock Xiaomi firmware?"; exit 1; }

save() {  # save <uci path>: its value, or an empty file when it does not exist
    uci -q get "$1" > "$B/$1" || : > "$B/$1"
}
if [ ! -f "$B/complete" ]; then
    rm -rf "$B" && mkdir -p "$B"
    save luci.main.lang
    save luci.languages.en
    save port_service.wan.wantag
    save port_service.wantag_attr
    save port_service.wantag_attr.vid
    if [ -f "$CRON" ]; then cp "$CRON" "$B/crontab.root"; fi
    date > "$B/complete"
fi
if [ ! -e "$B/otapred.settings.auto" ]; then  # first install, or a backup made by version 0.1.0
    save otapred.settings.auto
    save otapred.settings.plugin
    src=$CRON
    [ -f "$B/crontab.root" ] && src=$B/crontab.root  # the crontab before the first install
    grep otapredownload "$src" > "$B/cron.ota" 2>/dev/null || : > "$B/cron.ota"
fi

# upgrade: take the old version down first
if [ -x "$P/remove.sh" ]; then "$P/remove.sh" >/dev/null; fi

rm -rf "$P.new" && mv "$U" "$P.new"
rm -rf "$P" && mv "$P.new" "$P"
chmod 755 "$P/apply.sh" "$P/remove.sh" "$P/install.sh"
touch "$P/enabled"

# start at every boot: cron (persistent on stock firmware)
mkdir -p /etc/crontabs
touch "$CRON"
grep -qF '/data/panel/apply.sh' "$CRON" || echo "$HOOK" >> "$CRON"
/etc/init.d/cron restart >/dev/null 2>&1 || { killall crond 2>/dev/null; crond -c /etc/crontabs -b; } || echo "warning: could not restart cron; the pack starts after the next reboot"

if ! "$P/apply.sh"; then
    echo "panel pack NOT applied: $(cat /tmp/panel_pack.state 2>/dev/null || echo 'unknown error')"
    "$P/remove.sh" >/dev/null
    exit 1
fi

# The pack always uses the stock international (English) code path; the menu shows its name.
name=$(head -n 1 "$P/language.txt" 2>/dev/null || true)
uci set luci.languages.en="${name:-English}"
uci set luci.main.lang=en
uci commit luci
echo "panel pack: $(cat /tmp/panel_pack.state)"

if [ "${AUTO_UPDATE:-off}" = keep ]; then
    "$P/remove.sh" auto-update-on
    echo "WARNING: automatic firmware updates are ON. An automatic update replaces the firmware:"
    echo "         the pack stops, root access may be lost, and you cannot go back."
else
    sed -i '/otapredownload/d' "$CRON"
    { uci -q set otapred.settings.auto=0 && uci -q set otapred.settings.plugin=0 && uci commit otapred; } || true
    /etc/init.d/cron restart >/dev/null 2>&1 || true
    echo "automatic firmware updates: off (python router.py restore turns them back on)"
fi
