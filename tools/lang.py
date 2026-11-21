#!/usr/bin/env python3
"""Create, update and check the files of a panel language (translations/<code>.json).

Usage:
  python tools/lang.py update <code> [--name NATIVE_NAME] [--prune]
                                                            add every English string of the
                                                            last build (build/i18n/strings_en.json)
                                                            that the file does not have yet, as "";
                                                            --prune also drops strings it no longer uses
  python tools/lang.py check  [<code> ...]                  check every language file (or some)
  python tools/lang.py stats                                how complete each language is

A language file maps English (the key, as shown by the English pack) to the translation:
  {
  "@name": "Español",
  "Save": "Guardar",
  "Wi-Fi password: ": "Contraseña Wi-Fi: ",
  ...
  }
An empty value means "not translated yet": the panel shows the English text there.

Every key must be an English text of this project: a value of translations/en.json or a <%: %>
text of src/. `check` enforces it, so no text from other projects' translation files ends up here.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, "..", "translations")
STRINGS = os.path.join(HERE, "..", "build", "i18n", "strings_en.json")
SRC = os.path.join(HERE, "..", "src")

CJK = re.compile(r"[一-鿿]")
PH = re.compile(r"<%.*?%>|%[0-9]*[sd]|\$\{[^}]*\}|\{\$?[A-Za-z0-9_]*\}", re.S)
TAG = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)")
ESC = re.compile(r"\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)")
CODE = re.compile(r"[a-z]{2,3}(_[a-z]{2,4})?")


def path(code):
    return os.path.join(TR, f"{code}.json")


def load(code):
    with open(path(code), encoding="utf-8") as fh:
        return json.load(fh)


def save(code, d):
    meta = sorted((k, v) for k, v in d.items() if k.startswith("@"))
    body = sorted((k, v) for k, v in d.items() if not k.startswith("@"))
    lines = [json.dumps(k, ensure_ascii=False) + ": " + json.dumps(v, ensure_ascii=False)
             for k, v in meta + body]
    with open(path(code), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("{\n" + ",\n".join(lines) + "\n}\n")


def project_english():
    """The English texts this project owns: en.json values and the pack's own msgids."""
    with open(path("en"), encoding="utf-8") as fh:
        own = {v.strip() for v in json.load(fh).values() if v.strip()}
    for f in glob.glob(os.path.join(SRC, "**", "*.htm"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            own |= {" ".join(m.split()) for m in re.findall(r"<%:(.*?)%>", fh.read(), re.S)}
    return own


def languages():
    return sorted(f[:-5] for f in os.listdir(TR) if f.endswith(".json") and f != "en.json")


def problems(en, tr):
    """Differences that would break the page: placeholders, HTML tags, escapes."""
    out = []
    if CJK.search(tr):
        out.append("Chinese text left")
    if Counter(PH.findall(en)) != Counter(PH.findall(tr)):
        out.append(f"placeholders {PH.findall(en)} -> {PH.findall(tr)}")
    if Counter(t.lower() for t in TAG.findall(en)) != Counter(t.lower() for t in TAG.findall(tr)):
        out.append(f"HTML tags {TAG.findall(en)} -> {TAG.findall(tr)}")
    e1 = Counter(e for e in ESC.findall(en) if e not in ("\\n", "\\t"))
    e2 = Counter(e for e in ESC.findall(tr) if e not in ("\\n", "\\t"))
    if e1 != e2:
        out.append(f"backslash escapes {dict(e1)} -> {dict(e2)}")
    if en.count("\\n") != tr.count("\\n"):
        out.append("number of \\n line breaks differs")
    return out


def check(codes):
    bad = 0
    own = project_english()
    for code in codes:
        if not CODE.fullmatch(code):
            print(f"{code}: file name must be a language code like es, pt_br, zh_tw")
            bad += 1
            continue
        try:
            d = load(code)
        except (OSError, ValueError) as e:
            print(f"{code}: cannot read: {e}")
            bad += 1
            continue
        if not str(d.get("@name", "")).strip():
            print(f'{code}: missing "@name" (the language name in that language)')
            bad += 1
        for en, tr in d.items():
            if en.startswith("@") or not isinstance(tr, str):
                if not en.startswith("@"):
                    print(f"{code}: {en!r}: value must be a string")
                    bad += 1
                continue
            if en != en.strip():
                print(f"{code}: {en[:50]!r}: key has spaces at the edges")
                bad += 1
            if en.strip() not in own:
                print(f"{code}: {en[:60]!r}: not an English text of this project "
                      f"(translations/en.json or src/); run `lang.py update {code} --prune`")
                bad += 1
            if not tr.strip():
                continue
            for p in problems(en, tr):
                print(f"{code}: {en[:60]!r}: {p}")
                bad += 1
    return bad


def update(code, name, prune=False):
    if not CODE.fullmatch(code):
        sys.exit("error: use a language code like es, fr, pt_br")
    if code == "en":
        sys.exit("error: English is the source language (translations/en.json maps Chinese to English)")
    if not os.path.exists(STRINGS):
        sys.exit("error: build first (python build.py) so build/i18n/strings_en.json exists")
    with open(STRINGS, encoding="utf-8") as fh:
        strings = [s.strip() for s in json.load(fh) if s.strip()]
    d = load(code) if os.path.exists(path(code)) else {}
    if name:
        d["@name"] = name
    d.setdefault("@name", "")
    added = 0
    for s in strings:
        if s not in d:
            d[s] = ""
            added += 1
    if prune:
        keep = set(strings)
        gone = [k for k in d if not k.startswith("@") and k not in keep]
        for k in gone:
            del d[k]
        print(f"pruned {len(gone)} strings the panel no longer uses")
    save(code, d)
    done = sum(1 for k, v in d.items() if not k.startswith("@") and v.strip())
    print(f"translations/{code}.json: {added} new strings, {done}/{len(d) - 1} translated")


def stats():
    used = None
    if os.path.exists(STRINGS):
        with open(STRINGS, encoding="utf-8") as fh:
            used = {x.strip() for x in json.load(fh) if x.strip()}
    for code in languages():
        d = load(code)
        keys = [k for k in d if not k.startswith("@") and (used is None or k in used)]
        done = sum(1 for k in keys if d[k].strip())
        total = len(used) if used is not None else len(keys)
        print(f"{code:6} {d.get('@name', ''):20} {done}/{total}  {100 * done // max(total, 1)}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["update", "check", "stats"])
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--name")
    ap.add_argument("--prune", action="store_true")
    a = ap.parse_args()
    if a.command == "update":
        if len(a.codes) != 1:
            sys.exit("usage: lang.py update <code> [--name NAME]")
        update(a.codes[0], a.name, a.prune)
    elif a.command == "check":
        bad = check(a.codes or languages())
        print("ok" if not bad else f"{bad} problem(s)")
        sys.exit(1 if bad else 0)
    else:
        stats()


if __name__ == "__main__":
    main()
