# -*- coding: utf-8 -*-
"""量摘要字数，口径与 paper04_CN_selfcheck.py 的 ABS_LEN 检查一致（只数 CJK）。"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "paper04_CN.tex"
body = open(path, encoding="utf-8").read()
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
if not m:
    sys.exit("no abstract in " + path)

cjk = lambda s: len(re.findall(r"[\u4e00-\u9fff]", s))
a = m.group(1)
print("%s: abstract CJK = %d  (limit 400-700, headroom %d)"
      % (path, cjk(a), 700 - cjk(a)))
for i, p in enumerate(a.strip().split("\n\n"), 1):
    head = re.sub(r"\s+", "", p)[:24]
    print("  para %d: %3d CJK   %s..." % (i, cjk(p), head))
