# How it works

Details below refer to the Xiaomi BE3600 2.5G (RD15) on firmware 1.0.87, where the pack was
developed. Other Xiaomi models of the same generation share most of the panel code.

## The two halves of the stock panel

| Part | Where | How it is translated |
|---|---|---|
| LuCI templates (`<%: … %>` strings, rendered on the router) | `/usr/lib/lua/luci/view/**/*.htm` | A new `base.en.lmo` catalogue, plus in-place edits for Chinese text outside `<%: %>` (inline JavaScript, HTML text, attributes) |
| JavaScript pages built with Vue | `/www/**/*.js, *.html` | String literals replaced in place |

The China firmware ships only `zh-cn`, `zh-hk` and `zh-tw` catalogues. LuCI looks up each string by
the SuperFastHash of its whitespace-normalised text, so `tools/lmo.py` writes a catalogue with the
same hashing.

## Languages

Each Chinese string goes through two lookups:

1. **Chinese → English**: `translations/en.json`, this project's own translations, made from the
   Chinese. On RD15 1.0.87 it covers every string the templates and JavaScript pages show,
   except Xiaomi's legal texts. Only then xmir-patcher's community `base.en.po`, by text and by
   hash; on the PC, for strings `en.json` lacks, mostly messages of the router's compiled Lua code.
   `build/i18n/from_po.json` lists the firmware strings that only the `.po` translated. Its
   English is never copied into `translations/` (see [LEGAL.md](../LEGAL.md)); new strings there
   are translated from the Chinese.
2. **English → target language**: `translations/<code>.json`, keyed by the English text without
   its edge whitespace, which is put back after the lookup. A string the language file does not
   have, or has empty, stays in English.

The pack's own section (WAN VLAN) is written with English `<%: %>` msgids in `src/`, and goes
through step 2 only.

Whatever the language, the result is written as `base.en.lmo` and the router keeps
`luci.main.lang=en`. That is the code path Xiaomi built for its international (English) panel,
so the stock code treats it like the English panel it already knows; only the text differs.
The menu label comes from `luci.languages.en`, which `install.sh` sets to the language's own name
(`@name` in its file, shipped in the pack as `language.txt`).

The build also writes `build/i18n/strings_en.json`, every English string the firmware uses, and
`missing_lang.json`, the ones the chosen language does not cover. `tools/lang.py update` uses the
first to add new strings to a language file.

`tools/extract_strings.py` finds the strings with a small JavaScript lexer that understands
strings, template literals, comments and regex literals, not with regular expressions. That way
minified code is never mistaken for text. Replacements are re-escaped for their quote type.
Translations that LuCI inserts unescaped never contain ASCII quotes: an apostrophe becomes U+02BC
(`ʼ`), which looks the same. U+2019 would be drawn full-width by the panel's Chinese font.

## WAN VLAN: why it needs a patch

The firmware already has hidden options for a tagged WAN, in `port_service`:

```
port_service.wan.wantag='1'
port_service.wantag_attr=attr
port_service.wantag_attr.vid='20'
```

`ps_setup_wan()` reads them and stores the tagged device name as `port_map.<port>.dial_ifname`,
e.g. `eth0.1.20`. On this platform, though, `arch_ps_setup_wan()` in
`lib/miwifi/arch/lib_arch_port_service.sh` always writes the untagged device to
`network.wan.ifname`. `dial_ifname` is otherwise only read for IPTV bridge mode. Setting the
options alone therefore tags nothing.

The pack changes 3 places in `arch_ps_setup_wan()`. When `wantag=1`, `network.wan.ifname`,
`wan6.ifname` and `macv_wan6.ifname` use the tagged device. netifd then creates the VLAN device:
`eth0.1.20` on a 1G port, `eth1.20` on the 2.5G port.

The panel side:
- **Section**: *WAN VLAN (802.1Q)*, added to `web/setting/wan.htm`.
- **API**: `luci/controller/api/xqwanvlan.lua`.
  - `GET api/xqwanvlan/get`
  - `POST api/xqwanvlan/set` with `enable=0|1` and `vid=1..4094`.
- **Login**: the API uses the same `sysauth=admin` login and `stok` token as the stock API.
- **Checks on the VLAN ID**: it must be a number from 1 to 4094, and not one of the switch's
  internal port VIDs.
- **What runs when you save**: always the same shell command,
  `port_service restart wan`. The WAN reconnects.

One more patch, in `web/inc/sysinfo.htm`, shows the language menu: it no longer requires
`features.system.i18n=1`.

## Build

`build.py` runs, in order:

1. `tools/build_pack.py`: the catalogue and the translated templates and JavaScript files.
2. `tools/build_panel.py`: the VLAN section, its API, the `arch_ps_setup_wan()` patch and the
   language menu. Every patch is an exact text replacement that must match exactly once. On a
   firmware where an anchor is missing or appears twice, that feature is left out and reported. A
   feature's patches are applied together or not at all.
3. `tools/check_template_js.py`, when Node.js is installed. It runs `node --check` on every changed
   inline `<script>` block. A block that parsed before the change and fails after it counts as a
   regression.

The output is `build/pack`:

| File | Contents |
|---|---|
| `files/` | the new and changed files, at their router paths |
| `manifest.txt` | one line per file: `<original sha256 or -> <new sha256> <path>` |
| `info.txt` | model, version, language, `tested` or `experimental`, features, counts |
| `language.txt` | the language's own name, for the language menu |

## On the router

| Piece | Where | Persistent |
|---|---|---|
| Pack files, manifest, scripts | `/data/panel/` | yes |
| What the router had before the first install | `/data/panel_backup/` | yes |
| `* * * * * /data/panel/apply.sh` | `/etc/crontabs/root` | yes |
| `luci.main.lang=en`, `luci.languages.en=<language name>` | uci | yes |
| Bind mounts over the originals; RAM copies of directories that gain a new file | `/tmp/panel_mirror` | no: re-applied after each boot |

`apply.sh` runs every minute from cron and does its work once per boot:
1. It checks the SHA-256 of every pack file and every original file against the manifest. If one
   differs, it mounts nothing and logs it. For example, after a firmware update it logs
   `panel_pack: firmware changed (e.g. after an update): <path> - not applied. Rebuild the pack`.
2. It bind-mounts each changed file over the original. For a new file, such as the VLAN API, it
   copies the directory to RAM, adds the file and bind-mounts the copy over the directory.
3. If a WAN tag is set, it restarts `port_service wan`. That step is needed because the stock WAN
   setup already ran at boot without the tag.

After a reboot the stock Chinese panel shows for up to a minute, until cron runs `apply.sh`.
A lock directory (`/tmp/panel_pack.lock`) keeps the cron run and the installer from applying at
the same time.

`install.sh` switches the language only after `apply.sh` succeeds. If the pack cannot be applied,
for example because it was built from another firmware, it prints the reason, takes the pack down
again and leaves the language settings untouched.

### Backup and restore

Before the first install, `install.sh` saves in `/data/panel_backup/` one file per uci value it
may change, each holding the old value, or empty when the option did not exist:

| File | Changed by |
|---|---|
| `luci.main.lang`, `luci.languages.en` | the install |
| `port_service.wan.wantag`, `port_service.wantag_attr`, `port_service.wantag_attr.vid` | the WAN VLAN section |
| `otapred.settings.auto`, `otapred.settings.plugin` | the install (automatic updates off) |
| `cron.ota`: the crontab lines that run `otapredownload` | the install (automatic updates off) |

It also keeps a copy of `/etc/crontabs/root` for reference, and writes `complete` last. The
automatic update files are saved whenever they are missing, so a backup made by version 0.1.0
gets them from its crontab copy on the next install. A
reinstall or an upgrade finds `complete` and keeps the first backup, so the backup always
describes the router before the pack was ever installed.

`remove.sh` undoes the mounts and puts the language settings back as they were (an option that
did not exist is deleted again); the pack stays in `/data/panel`. If an unmount fails because a
file is in use, it keeps the RAM copies, which are still mounted, and says that they go away at
the next reboot.
Without the pack, a WAN tag that is still set is ignored again, so `remove.sh` rebuilds the WAN
untagged.

`remove.sh restore` (`python router.py restore`) also:
1. sets every saved value back, and deletes the ones that were empty (did not exist);
2. puts the `otapredownload` cron lines back if they were there, and removes the pack's cron
   line; nothing else in the crontab changes;
3. restarts `port_service wan` if the WAN tag differs from what it was;
4. deletes `/data/panel` and `/data/panel_backup`.

### Automatic updates

Unless `AUTO_UPDATE=keep` (`router.py install --keep-auto-update`), `install.sh` deletes the
`otapredownload` lines from the crontab and sets `otapred.settings.auto` and `plugin` to 0, after
the pack is applied. The firmware's `otapredownload` ignores `otapred.settings.enabled`, and
installs an update the server marks as mandatory even with `auto=0`, so the cron line is the
switch that matters. A plain `remove.sh` leaves updates off; `remove.sh restore` and
`remove.sh auto-update-on` put the saved values and cron lines back.

Tested in the emulator: install (cron line gone, `auto=0`), plain remove (still off), reinstall
with `AUTO_UPDATE=keep` (back to the factory state, with a warning), reinstall, `restore` (cron
line back, `auto` and `plugin` deleted again as in the factory config); `status` shows each state.

`router.py` opens one SSH session per command and moves files as a tar stream, so it needs no
`scp`. `fetch` refuses to run while the pack is applied: it would copy the translated files instead
of the originals.

## Test results (2026-11-21)

**Builds from official images**, all RD15 (`dev/unpack_firmware.py` + `unsquashfs`):

| Version | Translated UI | WAN VLAN | Language menu | Status |
|---|---|---|---|---|
| 1.0.87 | ok | ok | ok | tested |
| 1.0.106 | ok | ok | ok | experimental |
| 1.0.68 | ok | ok | ok | experimental |

- The panel files of 1.0.106 are identical to those of 1.0.87.
- In 1.0.68, 21 of them differ (rebuilt JavaScript bundles and a few templates). It ends up with
  one more untranslated string.
- On all three, the inline-script check found 0 regressions in 27 changed blocks.

**Emulator** (`dev/emulator.sh`, stock 1.0.87 rootfs under arm64 emulation in Docker):

| Test | Result |
|---|---|
| Install | 86 files applied; one cron line added and existing lines kept; language set to `en` |
| Reinstall over itself | still one cron line; pack applied |
| Simulated reboot (mounts dropped, `apply.sh` run again) | all 86 files applied again |
| A firmware file changed | `firmware changed … not applied`; 0 mounts |
| `remove.sh` | 0 mounts; language back to `zh_cn`; VLAN setting kept |
| Install, set VLAN 20, reinstall, `remove.sh restore` | `uci show luci`, `uci show port_service` and the crontab hold the same values as before the install (one option comes back at the end of its section, as `uci set` adds it); `wantag_attr` deleted because it did not exist before; `wan.htm` back to the stock file; `/data/panel` and `/data/panel_backup` gone |
| Panel in the browser, English | login, status, network and system pages in English; language menu shows *English* |
| Panel in the browser, `--lang es` | 2,042 of 2,042 English strings translated; login, status, network and system pages and the VLAN section in Spanish; language menu shows *Español*; 0 inline-script regressions |
| VLAN section | ticking the box, typing 20 and saving stores `wantag=1`, `vid=20` |
| VLAN API without login | `{"code":401,"msg":"Invalid token"}` |

The emulator has no hardware, so it could not test whether a tagged WAN actually gets traffic.

**Real router** (RD15, stock 1.0.87, 2026-11-21), with the tools of this repository over SSH:

| Test | Result |
|---|---|
| Starting point | an earlier test version of the pack (from the author's research repository) was removed with its own `remove.sh purge`; `luci.languages.en`, which it had left, was deleted: the factory firmware has no such option. A snapshot of `uci show luci`, `uci show port_service` and the crontab was saved on the PC |
| `fetch`, `build --lang es`, `install` | 798 files fetched; 86 files applied; login page and panel in Spanish; language menu shows *Español*; backup in `/data/panel_backup` |
| Reboot | applied again by cron, 99 s after boot |
| WAN VLAN from the panel (VLAN 20) | `wantag=1`, `vid=20` saved. With a cable in the 2.5G port and the WAN port set to it, the router created `eth1.20` and used it for `wan` and `wan6`; DHCP discovers went out on it (no answer: the upstream router does not use VLAN 20) |
| `remove` | login page in Chinese; 0 mounts; `luci.main.lang=zh_cn`; `luci.languages.en` deleted again; pack kept; VLAN setting kept |
| `restore` | `uci show luci`, `uci show port_service` and the crontab identical to the snapshot taken before the install; `/data/panel`, `/data/panel_backup` and `eth1.20` gone |

Found on the way: with the tag on, the stock automatic WAN port detection (`wandt`) also probes on
the VLAN (`port_service.wandt_attr.vid` follows the tag). It never picked a port connected to an
untagged upstream router. With an ISP that tags, such as Digi, that is the expected behaviour;
otherwise the WAN port has to be chosen by hand. The README says so.

## Code review (2026-11-21)

A review of the multi-language version found, and this version fixes:

- `info.txt` was written in the PC's code page: on Windows, `install` then failed to read a pack
  built with `--lang es` (`Español`). It is UTF-8 now, and console output no longer fails on
  characters the console cannot show.
- The `.po` entries, which the router's Lua code also uses, stayed in English in other languages.
  They now go through the language file too.
- `fetch` failed on a firmware without the WAN VLAN script; only `www` and the views are required
  now. It also refused to run when the pack had been rejected rather than applied.
- On old Python versions without tar extraction filters, the check against paths outside
  `rootfs/` could be bypassed with `../`; it now checks the member name itself.
- Files uploaded from Windows were world-writable on the router; they are 0644 now (scripts 0755).
- The installer and the language/mirror handling described above (failed apply, failed unmount,
  options that did not exist, two applies at once).

All were checked with unit tests or in the emulator: a firmware without the VLAN script (850
files fetched), without `www` (refused), a changed firmware file (install refused, language
unset as before), two concurrent applies (86 mounts, not 172), and `remove` on a router that had
no `luci.main.lang` (option deleted again, not set to `zh_cn`).

## Fixed during testing

- **VLAN form layout.** The VLAN ID field had both a placeholder and the stock floating label, so
  the two texts overlapped. The checkbox had no visible label. The form now follows the stock
  markup.
- **Apostrophes.** They were drawn full-width (`router’ s`), so they now use U+02BC.
- **WAN port selector.** *Smart selection of WAN port (recommended)* ran into the selector's *Mode*
  label. It was shortened to *Auto WAN port (recommended)*.
- **Spanish.** *Indicador de estado* wrapped onto two lines in the narrow label column and ran into
  the text below; it is now *LED de estado*. *Release*, the stable firmware channel in the footer,
  had been translated as a verb (*Liberar*); it is now *Estable*.
- **Emulator port.** The emulator could not start on a PC where another program (a proxy) already
  listened on port 8080: pick another port with `dev/emulator.sh run <fw> <port>`.
