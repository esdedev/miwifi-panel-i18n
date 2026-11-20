#!/usr/bin/env python3
"""Build the language pack for a stock MiWiFi rootfs.

Usage: build_pack.py <base.en.po> <rootfs_dir> <en.json[,more.json]> <out_dir>
                     [--lang FILE.json] [--templates DIR]

Two steps for every Chinese string of the firmware:
  1. Chinese -> English: en.json (and any extra files), then the .po by text, then by hash.
  2. English -> target language: the --lang file {english: translation}. Strings it does not
     have stay in English. Without --lang the pack is English.
--templates DIR: more LuCI templates (the pack's own) whose <%: %> English msgids are
translated into the target language too.

The catalogue is always written as base.en.lmo and the router keeps luci.main.lang=en: the
stock code paths for the international (English) panel are used whatever the language.

Output (<out_dir>/files mirrors the router paths; only files that change are written):
  files/usr/lib/lua/luci/i18n/base.en.lmo
  files/www/**.js|.html            source literals replaced in place
  manifest.json                    [{path, orig_sha256, new_sha256}]  for the installer
  untranslated.json                Chinese strings with no English translation
  strings_en.json                  every English string this firmware uses (for translators)
  missing_lang.json                English strings the --lang file does not cover yet
  from_po.json                     Chinese strings only the community .po translates (local use only:
                                   its English must not be copied into translations/)
"""
import glob
import hashlib
import json
import os
import argparse
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_strings import TXT, js_strings, template_spans  # noqa: E402
from lmo import key_id, norm, parse_po, write_lmo  # noqa: E402

CJK = re.compile(r"[一-鿿]")


def safe_markup(s: str) -> str:
    """Template output lands inside HTML attributes and JS strings unescaped:
    never emit ASCII quotes there. The apostrophe becomes U+02BC (looks the same); U+2019
    would be drawn full-width by the CJK fonts of the stock CSS ("router’ s")."""
    return s.replace("'", "ʼ").replace('"', "”")


def js_escape(body: str, quote: str) -> str:
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            out.append(body[i:i + 2])
            i += 2
            continue
        if c == quote or (c == "\n" and quote != "`"):
            out.append("\\n" if c == "\n" else "\\" + c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_lang(path):
    """{english: translation}; keys are matched without their edge whitespace."""
    if not path:
        return None
    d = json.load(open(path, encoding="utf-8"))
    return {k.strip(): v for k, v in d.items() if not k.startswith("@") and v and v.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("po")
    ap.add_argument("root")
    ap.add_argument("ours")
    ap.add_argument("out")
    ap.add_argument("--lang")
    ap.add_argument("--templates")
    a = ap.parse_args()
    po, root, ours_path, out = a.po, a.root, a.ours, a.out
    text, hashed = parse_po(po)
    ours = {}
    for p in ours_path.split(","):  # e.g. translations/en.json,my-legal.local.json
        if os.path.exists(p):
            ours.update(json.load(open(p, encoding="utf-8")))
        else:
            print("note: translation file not found, skipped:", p)
    by_norm = {norm(k): v for k, v in text.items() if v}
    ours_norm = {norm(k): v for k, v in ours.items()}
    lang = load_lang(a.lang)
    used_en, missing_lang = set(), set()

    def to_lang(en, track=True):
        """English -> target language, keeping the English edge whitespace.
        track=False: a .po entry that may be unused on this firmware (Lua strings cannot be
        listed from the fetched files), so it is not reported to translators."""
        core = en.strip()
        if not core:
            return en
        if track:
            used_en.add(core)
        if lang is None:
            return en
        t = lang.get(core)
        if t is None:
            if track:
                missing_lang.add(core)
            return en
        lead = en[:len(en) - len(en.lstrip())]
        trail = en[len(en.rstrip()):]
        return lead + t.strip() + trail

    from_po = {}  # Chinese strings of this firmware that only the community .po translates

    def lookup(s):
        if s in ours:
            en = ours[s]
        else:
            n = norm(s)
            en = ours_norm.get(n)
            if not en:
                en = by_norm.get(n) or hashed.get(key_id(s)) or None
                if en:
                    from_po[s] = en
        return to_lang(en) if en else None

    files_dir = os.path.join(out, "files")
    manifest, missing = [], set()

    # 1. LMO: every .po entry plus our template strings
    # Our own English wins over the .po's for the same Chinese string, so that the language
    # files (keyed by our English) also reach the strings Lua code looks up by hash.
    ours_by_hash = {key_id(k): v for k, v in ours.items()}
    entries = {k: safe_markup(to_lang(ours_by_hash.get(k, v), track=False))
               for k, v in hashed.items() if v}
    for k, v in text.items():
        if v:
            entries[key_id(k)] = safe_markup(to_lang(ours_by_hash.get(key_id(k), v), track=False))
    tpl_hit = tpl_tot = 0
    for f in glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True):
        for m in re.findall(r"<%:(.*?)%>", open(f, encoding="utf-8", errors="ignore").read(), re.S):
            s = norm(m)
            if not CJK.search(s):
                continue
            tpl_tot += 1
            en = lookup(s)
            if en:
                entries[key_id(s)] = safe_markup(en)
                tpl_hit += 1
            else:
                missing.add(s)
    # the pack's own templates use English msgids
    own = 0
    if a.templates:
        for f in glob.glob(os.path.join(a.templates, "**/*.htm"), recursive=True):
            for m in re.findall(r"<%:(.*?)%>", open(f, encoding="utf-8").read(), re.S):
                s = norm(m)
                if s:
                    entries[key_id(s)] = safe_markup(to_lang(s))
                    own += 1
    lmo_rel = "usr/lib/lua/luci/i18n/base.en.lmo"
    os.makedirs(os.path.dirname(os.path.join(files_dir, lmo_rel)), exist_ok=True)
    write_lmo(os.path.join(files_dir, lmo_rel), entries)
    manifest.append({"path": "/" + lmo_rel, "orig_sha256": None,
                     "new_sha256": sha(open(os.path.join(files_dir, lmo_rel), "rb").read())})
    print(f"lmo: {len(entries)} entries; template occurrences translated {tpl_hit}/{tpl_tot}; "
          f"pack strings {own}")

    # 2. /www: replace literals in place
    lit_hit = lit_tot = 0
    for f in sorted(glob.glob(os.path.join(root, "www/**/*"), recursive=True)):
        if not f.endswith((".js", ".html", ".htm")):
            continue
        raw = open(f, "rb").read()
        src = raw.decode("utf-8", errors="surrogateescape")
        pieces, last = [], 0
        if f.endswith(".js"):
            spans = [(a, b, q, body) for a, b, q, body in js_strings(src)
                     if CJK.search(body) and not (q == "`" and "${" in body)]
        else:
            spans = [(m.start(1), m.end(1), "<", m.group(1)) for m in TXT.finditer(src)]
        for a, b, q, body in spans:
            key = body if q != "<" else body.strip()
            lit_tot += 1
            en = lookup(key)
            if not en:
                missing.add(key)
                continue
            lit_hit += 1
            if q == "<":
                lead = body[:len(body) - len(body.lstrip())]
                trail = body[len(body.rstrip()):]
                new = lead + en.replace("<", "&lt;").replace(">", "&gt;") + trail
            else:
                new = js_escape(en, q)
            pieces.append(src[last:a])
            pieces.append(new)
            last = b
        if not pieces:
            continue
        pieces.append(src[last:])
        new_raw = "".join(pieces).encode("utf-8", errors="surrogateescape")
        rel = os.path.relpath(f, root).replace("\\", "/")
        dst = os.path.join(files_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(new_raw)
        manifest.append({"path": "/" + rel, "orig_sha256": sha(raw), "new_sha256": sha(new_raw)})
    print(f"www: literals translated {lit_hit}/{lit_tot}; files changed {len(manifest) - 1}")

    # 3. LuCI templates: raw CJK outside <%: %> (inline JS, HTML text, attributes)
    n_before = len(manifest)
    raw_hit = raw_tot = 0
    for f in sorted(glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True)):
        raw = open(f, "rb").read()
        src = raw.decode("utf-8", errors="surrogateescape")
        pieces, last = [], 0
        for a, b, kind, body in sorted(template_spans(src)):
            if a < last:
                continue  # overlapping span
            raw_tot += 1
            en = lookup(body)
            if not en:
                missing.add(body)
                continue
            raw_hit += 1
            if kind == "<":
                new = en.replace("<", "&lt;").replace(">", "&gt;") if "<" not in body else en
            elif kind.startswith("attr"):
                new = en.replace(kind[4:], "&quot;" if kind[4:] == '"' else "&#39;")
            else:
                new = js_escape(en, kind).replace("</script", "<\\/script")
            pieces.append(src[last:a])
            pieces.append(new)
            last = b
        if not pieces:
            continue
        pieces.append(src[last:])
        new_raw = "".join(pieces).encode("utf-8", errors="surrogateescape")
        rel = os.path.relpath(f, root).replace("\\", "/")
        dst = os.path.join(files_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(new_raw)
        manifest.append({"path": "/" + rel, "orig_sha256": sha(raw), "new_sha256": sha(new_raw)})
    print(f"templates raw: translated {raw_hit}/{raw_tot}; files changed {len(manifest) - n_before}")

    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    json.dump(sorted(missing), open(os.path.join(out, "untranslated.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("untranslated distinct strings:", len(missing))
    json.dump(sorted(used_en), open(os.path.join(out, "strings_en.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump(sorted(missing_lang), open(os.path.join(out, "missing_lang.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    with open(os.path.join(out, "from_po.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(from_po.items())), fh, ensure_ascii=False, indent=0)
    print("strings translated only by the community .po:", len(from_po))
    if lang is not None:
        print(f"language file: {len(used_en) - len(missing_lang)}/{len(used_en)} English strings translated")


if __name__ == "__main__":
    main()
