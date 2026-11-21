# Translating

Every language is built in two steps:

```
Chinese (firmware)  --translations/en.json-->  English  --translations/<code>.json-->  your language
```

- `translations/en.json` maps each Chinese source string, exactly as it appears in the firmware,
  to English. Every entry is translated from the Chinese for this project. Do not copy texts from
  other translation files, including xmir-patcher's `base.en.po` that the build downloads; see
  [LEGAL.md](../LEGAL.md).
- `translations/<code>.json` maps each English string to one language. Translators only need
  English; nobody has to read Chinese to add a language.

A language file has one entry per line, sorted by key, and an `@name` with the language's own name
(it is what the panel's language menu shows):

```json
{
"@name": "Español",
"2.5G port": "Puerto 2.5G",
"Save": "Guardar",
"Status indicator": ""
}
```

An empty value means "not translated yet": the panel shows the English text there. Keys are the
English strings without their leading or trailing spaces; the build puts the spaces back.

## Add a language

```sh
python router.py fetch 192.168.31.1     # or: sh dev/emulator.sh rootfs <firmware.bin>
python build.py                          # writes build/i18n/strings_en.json
python tools/lang.py update fr --name "Français"
```

`update` creates `translations/fr.json` with every English string the panel uses, all empty.
Translate them, then:

```sh
python tools/lang.py check fr            # the same check CI runs
python build.py --lang fr                # build/pack, ready to install or to try in the emulator
```

The code is the language code in lower case, with an optional region: `fr`, `pt_br`, `zh_tw`.
Partial files are welcome: whatever is missing stays in English, and `python tools/lang.py stats`
shows how far each language is.

## Rules

The text is put back mechanically inside HTML and JavaScript, so:

1. Every key must be an English text of this project (a value of `translations/en.json` or a
   text in `src/`); `lang.py update` only adds such keys, and `lang.py check` rejects others.
2. Keep placeholders (`%s`, `%d`, `{0}`, `{$0}`, `${...}`, `<%...%>`), HTML tags and backslash
   escapes (`\n`, `\"`) exactly as in the English. `lang.py check` rejects a translation that
   changes them.
3. Some strings are fragments of one sentence (`Click "` … `" to test the connection`). Translate
   each piece so that the joined sentence reads naturally.
4. Keep it short: buttons and labels are narrow. Check the page in the emulator or on your router.
5. Leave product names, protocol names and model names as they are (Wi-Fi, PPPoE, Mesh, Xiaomi).
6. Do not translate Xiaomi's legal documents ([LEGAL.md](../LEGAL.md)).

`translation-brief.md` has the longer rules used for the English text.

## Update a language after a change

When a new firmware or a new feature adds English strings, run `python build.py` and then
`python tools/lang.py update <code>`: it adds the new strings as empty entries and keeps the rest.
With `--prune` it also drops the strings the panel no longer uses.

## Fix the English

1. Find the Chinese source text: with your browser's inspector on the page, with
   `build/i18n/untranslated.json` (strings the last build could not translate), or with
   `build/i18n/from_po.json` (strings only the community `.po` translated: translate the Chinese
   yourself, without its English).
2. Add or edit the entry in `translations/en.json`. Keep placeholders, HTML tags, backslash
   escapes and leading/trailing whitespace exactly as in the source.
3. If you changed an English text that other languages already translate, the old key in their
   files stops matching, and `lang.py check` reports it. Run `python tools/lang.py update <code>
   --prune` for each language: the old key goes and the new text appears as an empty entry, so the
   change is visible in the pull request.
4. Run `python build.py` and `python -m unittest discover -s tests`.

The pack's own strings (the WAN VLAN section) are English `<%: %>` texts in `src/`, translated
like any other string.

Do not add translations of Xiaomi's legal documents (user agreement, privacy policy, user
experience programme). For your own use, put them in a `*.local.json` file, which git ignores, and
pass it with `python build.py --extra my.local.json`.

## Tools

All tools take explicit paths, so they can be used on any unpacked firmware.

| Tool | What it does |
|---|---|
| `tools/lang.py update/check/stats` | Creates and updates a language file, checks every language file, shows how complete each one is |
| `tools/extract_strings.py <po> <rootfs> <out>` | Writes the Chinese strings that the `.po` does not cover: `missing_templates.json` and `missing_www.json` |
| `tools/make_chunks.py <po> <rootfs> <translations.json> <out> [n]` | Splits the template strings that are still missing into batches for translators |
| `tools/check_translations.py <work_dir>` | Validates the translators' output and merges it into `merged.json`. It reports leftover Chinese and changed placeholders, tags, escapes or edge whitespace |
| `tools/split_legal.py <rootfs> <translations.json> <legal_out.json>` | Moves legal-document strings out of a translation file |
| `tools/export_po.py <po> <rootfs> <translations.json> <header>` | Appends the template translations to a `.po` in xmir-patcher's format |
| `tools/lmo.py` | LuCI `.lmo` reader and writer, and the `.po` parser |

## Another model

1. Fetch its files with `python router.py fetch`, or unpack its firmware with
   `dev/unpack_firmware.py`.
2. Run `python build.py`.
3. Look at `build/i18n/untranslated.json`. Strings shared with the RD15 are already translated; the
   rest can be added to `translations/en.json`. Then `lang.py update` brings them into the other
   languages.

If a patch anchor of the WAN VLAN feature does not match, the build reports it. The anchors are in
`tools/build_panel.py`. A pull request that adds anchors for another firmware is welcome, together
with the model and version it was tested on.
