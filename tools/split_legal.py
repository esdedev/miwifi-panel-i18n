#!/usr/bin/env python3
"""Move translations of Xiaomi's legal documents out of the published translation file.

Usage: split_legal.py <rootfs_dir> <translations.json> <legal_out.json>

The user agreement, privacy policy and "user experience program" texts are copyrighted
documents; a complete translation is a derivative work, so it is kept in a local,
git-ignored file (build_pack.py accepts several translation files, comma-separated).
Ordinary UI strings stay in <translations.json>.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_strings import js_strings, template_spans  # noqa: E402

CLAUSE = re.compile(r"^\s*(?:\\n\s*)*(?:\d+(?:\.\d+)+|[（(]\d+[）)]|第[一二三四五六七八九十]+条)")
KW = re.compile(r"本协议|本計劃|本计划|本計畫|隐私政策|隱私政策|个人信息|個人資料|個人信息|用户许可|"
                r"使用協議|使用协议|知识产权|免责|法律|小米通讯技术|北京小米|您于此授权|监护人")
INDENTED = re.compile(r"^\\n\s+\S")  # SPA document paragraphs: literal "\n" + indentation


def files_per_string(root):
    out = {}
    for f in glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True):
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        for _, _, _, body in template_spans(open(f, encoding="utf-8", errors="ignore").read()):
            out.setdefault(body, set()).add(rel)
    for f in glob.glob(os.path.join(root, "www/**/*.js"), recursive=True):
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        for _, _, _, body in js_strings(open(f, encoding="utf-8", errors="ignore").read()):
            out.setdefault(body, set()).add(rel)
    return out


def is_legal(s, files):
    if any("privacy" in f for f in files):
        return True
    # indented SPA document paragraphs (long prose only, not short indented UI labels)
    if INDENTED.match(s) and len(re.sub(r"\\[nt]|\s", "", s)) > 40:
        return True
    if "•" in s:
        return True
    # headings and short clauses of those documents
    if (INDENTED.match(s) or "隐私政策" in s) and (CLAUSE.search(s) or KW.search(s)):
        return True
    return len(s) > 30 and bool(CLAUSE.search(s) or KW.search(s))


def main():
    root, tr_path, legal_path = sys.argv[1:4]
    tr = json.load(open(tr_path, encoding="utf-8"))
    files = files_per_string(root)
    legal = {k: v for k, v in tr.items() if is_legal(k, files.get(k, ()))}
    ui = {k: v for k, v in tr.items() if k not in legal}
    old = json.load(open(legal_path, encoding="utf-8")) if os.path.exists(legal_path) else {}
    old.update(legal)
    json.dump(old, open(legal_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    json.dump(ui, open(tr_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"legal moved: {len(legal)} ({sum(map(len, legal))} chars) -> {legal_path}; UI kept: {len(ui)}")
    for k in sorted(ui, key=len, reverse=True)[:10]:
        print("  kept:", repr(k)[:100])


if __name__ == "__main__":
    main()
