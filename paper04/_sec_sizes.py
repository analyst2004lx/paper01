# -*- coding: utf-8 -*-
"""量出施工稿每个 (sub)section 的行数、汉字数与浮动体个数，供决定 H 的选项估页。"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "paper04_CN_AI-Modify-26-09-17.tex")
OUT = os.path.join(HERE, "_sec_sizes.txt")

CJK = re.compile(u"[\u4e00-\u9fff]")
HEAD = re.compile(r"^\\(sub)?section\{(.*)\}")
LABEL = re.compile(r"^\\label\{([^}]*)\}")
FLOAT = re.compile(r"^\\begin\{(table|figure)\}")

with io.open(TEX, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

secs = []
cur = None
for i, ln in enumerate(lines, 1):
    m = HEAD.match(ln)
    if m:
        cur = {"start": i, "title": m.group(2), "label": "", "cjk": 0,
               "lines": 0, "tab": 0, "fig": 0}
        secs.append(cur)
        continue
    if cur is None:
        continue
    lm = LABEL.match(ln)
    if lm and not cur["label"]:
        cur["label"] = lm.group(1)
    fm = FLOAT.match(ln)
    if fm:
        cur["tab" if fm.group(1) == "table" else "fig"] += 1
    cur["cjk"] += len(CJK.findall(ln))
    cur["lines"] += 1

rows = []
rows.append("施工稿分节体量（汉字数 / 行数 / 表 / 图）；估页按 1700 汉字≈1 页正文，"
            "每个浮动体另计 0.35 页")
rows.append("")
rows.append("%-28s %-16s %7s %6s %4s %4s %7s" %
            ("label", "标题", "汉字", "行", "表", "图", "估页"))
tot = 0.0
for s in secs:
    pages = s["cjk"] / 1700.0 + 0.35 * (s["tab"] + s["fig"])
    tot += pages
    title = s["title"][:16]
    rows.append("%-28s %-16s %7d %6d %4d %4d %7.2f" %
                (s["label"] or "-", title, s["cjk"], s["lines"],
                 s["tab"], s["fig"], pages))
rows.append("")
rows.append("合计估页（仅正文节，不含标题页/摘要/参考文献）：%.1f" % tot)

with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(rows) + "\n")
