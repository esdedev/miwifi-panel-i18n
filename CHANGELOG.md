# Changelog

## Unreleased

- `install` turns off automatic firmware updates, which would replace the firmware at night:
  the pack would stop, root may be lost, and anti-rollback prevents going back.
  `restore` turns them back on; `install --keep-auto-update` leaves them on; `status` shows them.
- README: how to get root (links to public community methods), badges; issue templates.

## 0.1.0 (2026-11-21)

First release.

- Stock web panel in English or Spanish, through JSON dictionaries keyed by English
  (`translations/<code>.json`); `tools/lang.py` to add and check languages.
- WAN VLAN (802.1Q) setting in *Network settings*.
- `router.py` commands: `fetch`, `install`, `status`, `remove`, `restore`. `restore` puts back
  every setting the pack changed, from a backup taken on the first install.
- Tested on a real BE3600 2.5G (RD15) with firmware 1.0.87.
