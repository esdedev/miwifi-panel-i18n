#!/usr/bin/env python3
"""Extract Chinese UI strings from an unpacked MiWiFi rootfs that are missing from a .po file.

Usage: extract_strings.py <base.en.po> <rootfs_dir> <out_dir>

Writes:
  missing_templates.json  {msgid: [files]}  LuCI template strings (<%: ... %>), normalised
  missing_www.json        {literal: [files]} quoted literals / text nodes with CJK in /www
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lmo import key_id, parse_po as parse_po_full  # noqa: E402

CJK = re.compile(r"[一-鿿]")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_po(path: str) -> dict:
    entries, cur, key = {}, {"msgid": "", "msgstr": ""}, None

    def flush():
        if cur["msgid"]:
            entries[cur["msgid"]] = cur["msgstr"]

    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\r\n")
        m = re.match(r'^(msgid|msgstr) "(.*)"$', line)
        if m:
            if m.group(1) == "msgid":
                flush()
                cur = {"msgid": "", "msgstr": ""}
            key = m.group(1)
            cur[key] = m.group(2)
        elif line.startswith('"') and key:
            cur[key] += line[1:-1]
    flush()
    return entries


TXT = re.compile(r">([^<>{}]*?[一-鿿][^<>{}]*?)<")

# Characters after which a "/" starts a regex literal rather than a division.
_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")


def js_strings(src: str):
    """Yield (start, end, quote, body) for every string literal in JS source.

    Minimal scanner: handles '...', "...", `...` (with ${...} nesting), // and /* */
    comments and regex literals (heuristic on the previous significant character).
    start/end delimit the body (without quotes).
    """
    i, n, prev = 0, len(src), ""
    while i < n:
        c = src[i]
        if c in "'\"`":
            q, j = c, i + 1
            depth = 0
            while j < n:
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if q == "`" and d == "$" and j + 1 < n and src[j + 1] == "{":
                    depth += 1
                    j += 2
                    continue
                if q == "`" and d == "}" and depth:
                    depth -= 1
                elif d == q and not depth:
                    break
                elif d == "\n" and q != "`":
                    break
                j += 1
            yield i + 1, j, q, src[i + 1:j]
            i, prev = j + 1, q
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and (prev in _REGEX_PREV or prev == ""):
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "[":
                    cls = True
                elif d == "]":
                    cls = False
                elif d == "/" and not cls:
                    break
                j += 1
            i, prev = j + 1, "/"
            continue
        if not c.isspace():
            prev = c
        i += 1


_MASK = re.compile(r"<%.*?%>|<!--.*?-->", re.S)
_SCRIPT = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)
_ATTR = re.compile(r"""=\s*(["'])([^"'<>]*?[一-鿿][^"'<>]*?)\1""")


def template_spans(src: str):
    """Yield (start, end, kind, body) for raw CJK text in a LuCI template.

    <% ... %> blocks and HTML comments are masked (never touched). Inside <script> the JS
    scanner is used (kind = quote char); elsewhere HTML text nodes (kind "<") and quoted
    attribute values (kind = quote char).
    """
    masked = _MASK.sub(lambda m: "\x00" * len(m.group(0)), src)
    script_ranges = []
    for m in _SCRIPT.finditer(masked):
        if re.search(r"type\s*=\s*[\"']?tmpl", m.group(1), re.I):
            continue  # client-side HTML template: handled as HTML text below
        a = m.start(2)
        script_ranges.append((m.start(), m.end()))
        for s, e, q, body in js_strings(m.group(2)):
            if not CJK.search(body) or (q == "`" and "${" in body):
                continue
            # quotes are never inside a masked block, so any <% %> is wholly inside the
            # string: yield the original text, the translation keeps the block verbatim
            if "\x00" in body:
                if not CJK.search(re.sub(r"\x00+", "", body)):
                    continue
                body = src[a + s:a + e]
            yield a + s, a + e, q, body

    def in_script(pos):
        return any(a <= pos < b for a, b in script_ranges)

    for m in TXT.finditer(masked):
        body = m.group(1)
        if "\x00" in body or in_script(m.start(1)):
            continue
        lead = len(body) - len(body.lstrip())
        core = body.strip()
        if core:
            yield m.start(1) + lead, m.start(1) + lead + len(core), "<", core
    for m in _ATTR.finditer(masked):
        if "\x00" in m.group(2) or in_script(m.start(2)):
            continue
        yield m.start(2), m.end(2), "attr" + m.group(1), m.group(2)


def main() -> None:
    po, root, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    text, hashed = parse_po_full(po)
    have = {norm(k) for k in text}
    have_ids = set(hashed) | {key_id(k) for k in text}
    print("po entries: text", len(text), "hashed", len(hashed))

    def known(s):
        return norm(s) in have or key_id(s) in have_ids

    tpl = {}
    for f in glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True):
        rel = "/" + os.path.relpath(f, root).replace("\\", "/")
        for m in re.findall(r"<%:(.*?)%>", open(f, encoding="utf-8", errors="ignore").read(), re.S):
            s = norm(m)
            if CJK.search(s):
                tpl.setdefault(s, set()).add(rel)
    miss_tpl = {s: sorted(v) for s, v in sorted(tpl.items()) if not known(s)}
    print("templates CJK:", len(tpl), "missing:", len(miss_tpl))

    raw = {}
    for f in glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True):
        rel = "/" + os.path.relpath(f, root).replace("\\", "/")
        for _, _, _, body in template_spans(open(f, encoding="utf-8", errors="ignore").read()):
            raw.setdefault(body, set()).add(rel)
    miss_raw = {s: sorted(v) for s, v in sorted(raw.items()) if not known(s)}
    print("templates raw CJK:", len(raw), "missing:", len(miss_raw))

    www = {}
    for f in glob.glob(os.path.join(root, "www/**/*"), recursive=True):
        if not f.endswith((".js", ".html", ".htm")):
            continue
        rel = "/" + os.path.relpath(f, root).replace("\\", "/")
        t = open(f, encoding="utf-8", errors="ignore").read()
        if f.endswith(".js"):
            for _, _, q, body in js_strings(t):
                if CJK.search(body) and not (q == "`" and "${" in body):
                    www.setdefault(body, set()).add(rel)
        else:
            for m in TXT.finditer(t):
                s = m.group(1).strip()
                if s:
                    www.setdefault(s, set()).add(rel)
    miss_www = {s: sorted(v) for s, v in sorted(www.items()) if not known(s)}
    print("www CJK literals:", len(www), "missing:", len(miss_www))

    for name, data in (("missing_templates.json", miss_tpl), ("missing_www.json", miss_www),
                       ("missing_template_raw.json", miss_raw)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=0)
    print("chars: templates", sum(map(len, miss_tpl)), "www", sum(map(len, miss_www)))


if __name__ == "__main__":
    main()
