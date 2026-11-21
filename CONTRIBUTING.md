# Contributing

Pull requests are welcome, in particular:

- **A new language**, or corrections to one: `translations/<code>.json`. See
  [docs/translating.md](docs/translating.md). You only need English and your language.
- **Fixes to the English text**: `translations/en.json`.
- **Reports from other models and firmware versions**: open an issue with the model, the
  version (`python router.py status` shows it) and the output of `python build.py`.
- **Patch anchors for another firmware**, in `tools/build_panel.py`, with the model and version
  you tested them on.

Before opening the pull request:

```sh
python tools/lang.py check                    # every language file
python -m unittest discover -s tests
```

CI runs the same checks on Linux and Windows.

Please do not include:

- Files from the firmware, or anything copied from a router (`rootfs/`, `build/` and firmware
  images are ignored by git).
- Translations of Xiaomi's legal documents ([LEGAL.md](LEGAL.md)).
- Anything that identifies a router: serial numbers, MAC addresses, passwords, keys.

Contributions are licensed under GPL-3.0-or-later, like the rest of the project.
