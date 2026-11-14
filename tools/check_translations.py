#!/usr/bin/env python3
"""Validate translator output against the source items and merge it.

Usage: check_translations.py <work_dir>    (reads all_items.json + out_*.json)
Writes <work_dir>/merged.json  {zh: en}  and prints every problem found.

Checks per string: all ids present; no CJK left; same placeholders (%s %d {x} ${x}),
same HTML tags, same backslash escapes, same leading/trailing whitespace.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

CJK = re.compile(r"[一-鿿]")
PH = re.compile(r"<%.*?%>|%[0-9]*[sd]|\$\{[^}]*\}|\{\$?[A-Za-z0-9_]*\}", re.S)
TAG = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)")
ESC = re.compile(r"\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)")


def edge(s):
    m1 = re.match(r"^(\s|\\n|\\t)*", s).group(0)
    m2 = re.search(r"(\s|\\n|\\t)*$", s).group(0)
    return m1, m2


def problems(zh, en):
    out = []
    if CJK.search(en):
        out.append("CJK left")
    if Counter(PH.findall(zh)) != Counter(PH.findall(en)):
        out.append(f"placeholders {PH.findall(zh)} -> {PH.findall(en)}")
    if Counter(t.lower() for t in TAG.findall(zh)) != Counter(t.lower() for t in TAG.findall(en)):
        out.append(f"tags {TAG.findall(zh)} -> {TAG.findall(en)}")
    ez = Counter(e for e in ESC.findall(zh) if e not in ("\\n", "\\t"))
    ee = Counter(e for e in ESC.findall(en) if e not in ("\\n", "\\t"))
    if ez != ee:
        out.append(f"escapes {dict(ez)} -> {dict(ee)}")
    if edge(zh) != edge(en):
        out.append(f"edges {edge(zh)!r} -> {edge(en)!r}")
    return out


def main():
    work = sys.argv[1]
    items = json.load(open(os.path.join(work, "all_items.json"), encoding="utf-8"))
    tr = {}
    for f in sorted(glob.glob(os.path.join(work, "out_*.json"))):
        tr.update(json.load(open(f, encoding="utf-8")))
    merged, bad, missing = {}, 0, 0
    for it in items:
        en = tr.get(it["id"])
        if en is None:
            missing += 1
            continue
        p = problems(it["zh"], en)
        if p:
            bad += 1
            print(it["id"], repr(it["zh"])[:70], "=>", repr(en)[:70], "|", "; ".join(p))
        merged[it["zh"]] = en
    json.dump(merged, open(os.path.join(work, "merged.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"items {len(items)}  translated {len(merged)}  missing {missing}  with problems {bad}")


if __name__ == "__main__":
    main()
