"""Tests on a small synthetic rootfs (no Xiaomi files needed). Run: python -m unittest -v"""
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, REPO)

import build_pack  # noqa: E402
import build_panel  # noqa: E402
import lmo  # noqa: E402
import router  # noqa: E402

ARCH_SH = """arch_ps_setup_wan() {
    wan_ifname=$(port_map iface port "$wan_port")
    wan6_ifname="$wan_ifname"
    uci -q batch <<-EOF
        set network."$service".ifname="$wan_ifname"
        set network."macv_${service/n/n6}".ifname="$wan_ifname"
EOF
}
"""
WAN_HTM = """<div class="mod-set">
    <h3><%:上网设置%></h3>
        <div class="mod-set mod-macclone">
        </div>
</div>
<%include("web/inc/netmod.js")%>
<script>var s = '2.5G网口';</script>
"""
SYSINFO_HTM = '<% if romChannel == "release" and features["system"]["i18n"] == "1" then %>x<% end %>\n'
JS = 'var a="2.5G网口",b=\'取消\';\n'
PO = 'msgid "取消"\nmsgstr "Cancel"\n'


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def make_rootfs(root, vlan_anchors=True):
    write(root, "usr/share/xiaoqiang/xiaoqiang_version",
          "config version 'version'\n\toption ROM '9.9.9'\n\toption HARDWARE 'TEST'\n")
    write(root, "lib/miwifi/arch/lib_arch_port_service.sh",
          ARCH_SH if vlan_anchors else "arch_ps_setup_wan() { :; }\n")
    write(root, "usr/lib/lua/luci/view/web/setting/wan.htm", WAN_HTM)
    write(root, "usr/lib/lua/luci/view/web/inc/sysinfo.htm", SYSINFO_HTM)
    write(root, "www/static/js/app.js", JS)


def run_build(root, out, po, *extra):
    env = dict(os.environ, PYTHONUTF8="1")
    r = subprocess.run([sys.executable, os.path.join(REPO, "build.py"), "--rootfs", root,
                        "--po", po, "--out", out, *extra], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    if r.returncode != 0:
        raise AssertionError(r.stdout + r.stderr)
    return r.stdout


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "rootfs")
        self.out = os.path.join(self.tmp.name, "build")
        self.po = os.path.join(self.tmp.name, "base.en.po")
        write(self.tmp.name, "base.en.po", PO)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_build_is_experimental_on_unknown_firmware(self):
        make_rootfs(self.root)
        log = run_build(self.root, self.out, self.po)
        self.assertIn("EXPERIMENTAL", log)
        pack = os.path.join(self.out, "pack")
        info = read(os.path.join(pack, "info.txt"))
        self.assertIn("firmware: TEST 9.9.9", info)
        self.assertIn("status: experimental", info)
        self.assertIn("wan_vlan: ok", info)
        self.assertIn("language_menu: ok", info)

        manifest = {e["path"]: e for e in read_json(os.path.join(pack, "manifest.json"))}
        self.assertIn("/usr/lib/lua/luci/controller/api/xqwanvlan.lua", manifest)
        self.assertIsNone(manifest["/usr/lib/lua/luci/controller/api/xqwanvlan.lua"]["orig_sha256"])
        for path, e in manifest.items():
            self.assertEqual(e["new_sha256"], sha(os.path.join(pack, "files") + path), path)
            if e["orig_sha256"]:
                self.assertEqual(e["orig_sha256"], sha(self.root + path), path)

        js = read(os.path.join(pack, "files/www/static/js/app.js"))
        self.assertIn('"2.5G port"', js)            # from translations/en.json
        self.assertIn("'Cancel'", js)          # from the .po
        wan = read(os.path.join(pack, "files/usr/lib/lua/luci/view/web/setting/wan.htm"))
        self.assertIn("WAN VLAN (802.1Q)", wan)
        self.assertIn("var s = '2.5G port'", wan)
        arch = read(os.path.join(pack, "files/lib/miwifi/arch/lib_arch_port_service.sh"))
        self.assertEqual(arch.count('.ifname="$dial_ifname"'), 2)

        lines = read(os.path.join(pack, "manifest.txt")).splitlines()
        self.assertEqual(len(lines), len(manifest))
        self.assertTrue(all(len(l.split(" ")) == 3 for l in lines))

    def test_missing_anchor_leaves_vlan_out_but_keeps_english(self):
        make_rootfs(self.root, vlan_anchors=False)
        run_build(self.root, self.out, self.po)
        pack = os.path.join(self.out, "pack")
        info = read(os.path.join(pack, "info.txt"))
        self.assertIn("wan_vlan: left out", info)
        self.assertIn("translated_ui: ok", info)
        paths = {e["path"] for e in read_json(os.path.join(pack, "manifest.json"))}
        self.assertNotIn("/usr/lib/lua/luci/controller/api/xqwanvlan.lua", paths)
        self.assertNotIn("/lib/miwifi/arch/lib_arch_port_service.sh", paths)
        self.assertIn("/www/static/js/app.js", paths)

    def test_pack_tar_for_the_router(self):
        make_rootfs(self.root)
        run_build(self.root, self.out, self.po)
        data = router.pack_tar(os.path.join(self.out, "pack"))
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            names = {m.name: m for m in tf.getmembers()}
        for n in ("manifest.txt", "info.txt", "apply.sh", "install.sh", "remove.sh",
                  "files/www/static/js/app.js"):
            self.assertIn(n, names)
        self.assertEqual(names["install.sh"].mode, 0o755)
        self.assertEqual(names["files/www/static/js/app.js"].mode, 0o644)  # not 0o666 from Windows
        self.assertFalse(any("\\" in n for n in names))

    def test_po_strings_follow_the_language_and_info_is_utf8(self):
        make_rootfs(self.root)
        lang = os.path.join(self.tmp.name, "zz.json")
        with open(lang, "w", encoding="utf-8") as fh:
            json.dump({"@name": "Русский тест", "Cancel": "Отмена"}, fh, ensure_ascii=False)
        # no UTF-8 mode: the files must not depend on the PC's code page
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
        r = subprocess.run([sys.executable, os.path.join(REPO, "build.py"), "--rootfs", self.root,
                            "--po", self.po, "--out", self.out, "--lang", lang],
                           capture_output=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        pack = os.path.join(self.out, "pack")
        self.assertIn("Русский тест", read(os.path.join(pack, "info.txt")))
        entries = lmo.read_lmo(os.path.join(pack, "files/usr/lib/lua/luci/i18n/base.en.lmo"))
        self.assertEqual(entries[lmo.key_id("取消")], "Отмена")   # .po entry, used by Lua code


    def test_language_file_translates_english_with_fallback(self):
        make_rootfs(self.root)
        lang = os.path.join(self.tmp.name, "zz.json")
        with open(lang, "w", encoding="utf-8") as fh:
            json.dump({"@name": "Testish", "2.5G port": "Puerto 2.5G", "Save": "Guardar",
                       "Cancel": ""}, fh)
        log = run_build(self.root, self.out, self.po, "--lang", lang)
        self.assertIn("language file:", log)
        pack = os.path.join(self.out, "pack")
        js = read(os.path.join(pack, "files/www/static/js/app.js"))
        self.assertIn('"Puerto 2.5G"', js)     # translated
        self.assertIn("'Cancel'", js)          # empty value: English stays
        self.assertEqual(read(os.path.join(pack, "language.txt")).strip(), "Testish")
        self.assertIn("language: ", read(os.path.join(pack, "info.txt")))
        used = read_json(os.path.join(self.out, "i18n", "strings_en.json"))
        self.assertIn("Tag WAN traffic with a VLAN ID", used)   # the pack's own strings
        lmo_entries = lmo.read_lmo(os.path.join(pack, "files/usr/lib/lua/luci/i18n/base.en.lmo"))
        self.assertEqual(lmo_entries[lmo.key_id("Save")], "Guardar")


class UnitTest(unittest.TestCase):
    def test_fetch_rejects_paths_outside_the_folder(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for name in ("www/ok.js", "../evil.py", "./../evil2.py", "/etc/passwd", "www/../../x",
                         "C:/x"):
                ti = tarfile.TarInfo(name)
                ti.size = 1
                tf.addfile(ti, io.BytesIO(b"x"))
        buf.seek(0)
        with tarfile.open(fileobj=buf) as tf:
            kept = [m.name for m in router.safe_members(tf)]
        self.assertEqual(kept, ["www/ok.js"])

    def test_install_turns_auto_update_off_unless_kept(self):
        with tempfile.TemporaryDirectory() as here:
            pack = os.path.join(here, "build", "pack")
            os.makedirs(pack)
            open(os.path.join(pack, "manifest.txt"), "w").close()
            with open(os.path.join(pack, "info.txt"), "w", encoding="utf-8") as fh:
                fh.write("status: supported\n")
            remotes = self._install_remotes(here)
        self.assertNotIn("AUTO_UPDATE", remotes[0])
        self.assertIn("AUTO_UPDATE=keep sh /tmp/panel_upload/install.sh", remotes[1])

    @staticmethod
    def _install_remotes(here):
        from unittest import mock
        remotes = []

        def fake_run(cmd, input=None):
            remotes.append(cmd[-1])
            return subprocess.CompletedProcess(cmd, 0)

        with mock.patch.object(router, "HERE", here), \
             mock.patch.object(router, "pack_tar", lambda _: b""), \
             mock.patch.object(router.subprocess, "run", fake_run), \
             mock.patch("builtins.print"):
            router.install("192.0.2.1", yes=True)
            router.install("192.0.2.1", yes=True, keep_auto_update=True)
        return remotes

    def test_lmo_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "t.lmo")
            entries = {lmo.key_id("网口"): "Port", lmo.key_id("取消"): "Cancel"}
            lmo.write_lmo(p, entries)
            self.assertEqual(lmo.read_lmo(p), entries)

    def test_key_id_normalises_whitespace(self):
        self.assertEqual(lmo.key_id("  a \n b "), lmo.key_id("a b"))

    def test_safe_markup_never_emits_ascii_quotes(self):
        out = build_pack.safe_markup("router's \"name\"")
        self.assertNotIn("'", out)
        self.assertNotIn('"', out)
        self.assertIn("ʼ", out)

    def test_replace_once_rejects_ambiguous_anchor(self):
        with self.assertRaises(build_panel.AnchorError):
            build_panel.replace_once("aa", "a", "b", "test")

    def test_language_files_pass_the_checker(self):
        import lang
        self.assertEqual(lang.check(lang.languages()), 0)

    def test_language_checker_catches_broken_markup(self):
        import lang
        self.assertTrue(lang.problems("Click <b>%s</b>", "Pulsa %s"))
        self.assertFalse(lang.problems("Click <b>%s</b>", "Pulsa <b>%s</b>"))
        self.assertTrue(lang.problems(r"a\nb", "a b"))  # a literal backslash-n was dropped

    def test_translations_file_is_valid(self):
        with open(os.path.join(REPO, "translations", "en.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertGreater(len(d), 1000)
        self.assertTrue(all(isinstance(v, str) and v for v in d.values()))


if __name__ == "__main__":
    unittest.main()
