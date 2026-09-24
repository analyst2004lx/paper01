# -*- coding: utf-8 -*-
"""按 \section 统计正文 CJK 字数占比，用于核 P16（篇幅分布）。

协议目标区间：导言 15--20%、相关工作 8--12%、实验不宜远高于其余各章。
只数正文 CJK，剔除注释、宏定义区、caption/Description 之外的版式命令不另处理
（它们不含 CJK 或占比极小，不影响百分比的量级判断）。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
tex = sys.argv[1] if len(sys.argv) > 1 else "paper04_CN_AI-Modify-26-09-17.tex"
lines = open(os.path.join(HERE, tex), encoding="utf-8").read().split("\n")

CJK = re.compile(r"[\u4e00-\u9fff]")
buf = io.StringIO()

# 正文自 \begin{document} 起算，避开宏定义区。
start = next(i for i, l in enumerate(lines) if "\\begin{document}" in l)

secs = []          # (标题, 起始行)
for i in range(start, len(lines)):
    m = re.match(r"\\section\{(.+?)\}", lines[i].strip())
    if m:
        secs.append([m.group(1), i, 0])

# 摘要区（\begin{abstract} 到 \section 之前）单列。
abs_n = 0
first_sec = secs[0][1] if secs else len(lines)
for i in range(start, first_sec):
    l = lines[i]
    if l.strip().startswith("%"):
        continue
    abs_n += len(CJK.findall(l))

for k, (_t, s, _n) in enumerate(secs):
    end = secs[k + 1][1] if k + 1 < len(secs) else len(lines)
    n = 0
    for i in range(s, end):
        l = lines[i]
        if l.strip().startswith("%"):
            continue
        n += len(CJK.findall(l))
    secs[k][2] = n

total = sum(s[2] for s in secs) + abs_n
buf.write("正文 CJK 合计（含摘要区）= %d\n\n" % total)
buf.write("%-34s %8s %8s\n" % ("章", "CJK", "占比"))
buf.write("-" * 52 + "\n")
buf.write("%-34s %8d %7.1f%%\n" % ("（摘要/题名/关键词区）", abs_n, 100.0 * abs_n / total))
for t, _s, n in secs:
    buf.write("%-34s %8d %7.1f%%\n" % (t, n, 100.0 * n / total))

open(os.path.join(HERE, "sec_sizes.txt"), "w", encoding="utf-8").write(buf.getvalue())
print(buf.getvalue())
