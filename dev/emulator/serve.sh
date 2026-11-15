#!/bin/sh
# Runs inside the emulated stock rootfs (see dev/emulator.sh). Not for real routers.
# Starts the stock web panel on port 80. With WITH_PACK=1, installs build/pack first.
# The repository is mounted at /repo.
set -e
mkdir -p /data /var/run /var/lock /tmp/run /tmp/luci-sessions
chmod 700 /tmp/luci-sessions          # LuCI refuses a session dir other users can read

# nvram needs /dev/nvram: replace it with a small file-backed version
cp /repo/dev/emulator/nvram_shim.sh /tmp/nvram && chmod 755 /tmp/nvram
mount --bind /tmp/nvram /usr/sbin/nvram

if [ "$WITH_PACK" = 1 ]; then
    rm -rf /tmp/panel_upload && mkdir -p /tmp/panel_upload
    cp -r /repo/build/pack/files /repo/build/pack/manifest.txt /repo/build/pack/info.txt /repo/build/pack/language.txt /tmp/panel_upload/
    cp /repo/router/apply.sh /repo/router/install.sh /repo/router/remove.sh /tmp/panel_upload/
    sh /tmp/panel_upload/install.sh
fi

# skip the first-run wizard and set the admin password of this emulator
uci set xiaoqiang.common.INITTED=YES && uci commit xiaoqiang
lua -e 'require("xiaoqiang.util.XQSecureUtil").savePlaintextPwd("admin", os.getenv("ADMIN_PW"))'
echo "web panel ready"
exec /usr/sbin/uhttpd -f -h /www -p 0.0.0.0:80 -x /cgi-bin -t 60 -T 30
