#!/usr/bin/env python3
"""Collect raw template strings (outside <%: %>) that still lack a translation and split
them into translator chunks.

Usage: make_chunks.py <base.en.po> <rootfs_dir> <translations.json> <out_dir> [chunks=3]
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_strings import template_spans  # noqa: E402
from lmo import key_id, norm, parse_po  # noqa: E402


def main():
    po, root, ours_path, out = sys.argv[1:5]
    n_chunks = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    text, hashed = parse_po(po)
    ours = json.load(open(ours_path, encoding="utf-8"))
    have = {norm(k) for k in text} | {norm(k) for k in ours}
    raw = {}
    for f in glob.glob(os.path.join(root, "usr/lib/lua/luci/view/**/*.htm"), recursive=True):
        rel = "/" + os.path.relpath(f, root).replace(os.sep, "/")
        for _, _, _, body in template_spans(open(f, encoding="utf-8", errors="ignore").read()):
            raw.setdefault(body, set()).add(rel)
    miss = {s: sorted(v) for s, v in sorted(raw.items())
            if norm(s) not in have and key_id(s) not in hashed}
    print("raw template strings", len(raw), "missing", len(miss), "chars", sum(map(len, miss)))
    os.makedirs(out, exist_ok=True)
    items = [{"id": f"r{i:04d}", "kind": "template-raw", "zh": k, "files": v[:2]}
             for i, (k, v) in enumerate(miss.items())]
    json.dump(items, open(os.path.join(out, "all_items.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    total = sum(len(x["zh"]) for x in items)
    chunks, cur, k = [[] for _ in range(n_chunks)], 0, 0
    for it in items:
        if cur >= total / n_chunks * (k + 1) and k < n_chunks - 1:
            k += 1
        chunks[k].append(it)
        cur += len(it["zh"])
    for k, c in enumerate(chunks):
        json.dump(c, open(os.path.join(out, f"chunk_{k}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print("chunk", k, len(c))


if __name__ == "__main__":
    main()
