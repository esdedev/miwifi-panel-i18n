# Legal notice

*This describes how the project is scoped. It is not legal advice.*

## No affiliation

This is an independent project. It is not affiliated with, endorsed by or sponsored by Xiaomi or
any of its affiliates. "Xiaomi", "Redmi" and "MiWiFi" are trademarks of their owners. They are used
here only to name the hardware and firmware this project works with.

## What this repository does **not** contain

- **No Xiaomi firmware, files or patched files.** The tools build the modified panel files on your
  own PC, from the files on your own router (`router.py fetch`) or from a firmware image you already
  have (`dev/`). Build outputs, fetched files and firmware images are excluded by `.gitignore`.
  Every change is a small text substitution.
- **No translations of Xiaomi's legal documents** (user agreement, privacy policy, user experience
  programme). A full translation would be a derivative work of a copyrighted text. The build
  accepts them from your own local, git-ignored file (`--extra *.local.json`); without one, those
  screens stay in Chinese.
- **No third-party translations.** xmir-patcher's `base.en.po` declares no licence, so neither the
  file nor any of its texts is in this repository. Every string the stock panel shows on the
  supported firmware was translated from the Chinese for this project, without using the `.po`.
  The build still downloads the `.po` (from a fixed commit, checked against a fixed SHA-256) and
  uses it only on your PC, for strings this project does not translate: mostly messages from the
  router's compiled Lua code, which cannot be listed from the fetched files. `tools/lang.py check`,
  run by CI, rejects any language-file key that is not an English text of this project.
- **No device-specific data**: no serial numbers, MAC addresses, keys or passwords.

## What it does contain

- Original code and documentation, Copyright (C) 2026 Esdedev, under the GNU General Public
  License v3.0 or later (`LICENSE`).
- English renderings of short UI strings (labels, buttons, help texts), with the Chinese source
  strings as lookup keys, as other community language packs do; and renderings of those English
  strings in other languages (`translations/<code>.json`), contributed under the same licence.
- Short excerpts of firmware scripts (a few lines each) used as patch anchors in
  `tools/build_panel.py`, and quoted in `docs/` for commentary. They are needed to apply
  interoperability changes on the user's own device.
- Screenshots of the panel (`docs/screenshots/`), taken in the emulator with no device data, to
  show what the tools change.

## Interoperability

The firmware was studied on hardware owned by the author:
- to translate its interface;
- to make its existing, hidden WAN VLAN support usable.

This is the kind of observation, study and interoperability work contemplated by Articles 5(3) and
6 of Directive 2009/24/EC on the legal protection of computer programs. In Spain those provisions
are implemented in Article 100 of the Ley de Propiedad Intelectual.

## Use

- Use these tools **only on devices you own** or are explicitly authorised to modify.
- Modifying the firmware may void the warranty. Everything is provided **as is, without warranty**
  (GPL-3.0 sections 15 and 16).

## Contact

If you are a rights holder and believe something here should not be published, please open an
issue. It will be reviewed and, if appropriate, removed promptly.
