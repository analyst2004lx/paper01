# -*- coding: utf-8 -*-
"""把 v3 中 Lyu 外部布局的「布局 k」改称 \\texttt{Lk}。"""
import re

P = r"c:\Users\analy\Desktop\AI_Folder\paper04\paper04_CN_v3.tex"
s = open(P, encoding="utf-8").read()

fixed = [
    ("附录 A 的布局 2--6）", r"附录 A 的第 2--6 张布局，记为 \texttt{L2}--\texttt{L6}）"),
    ("附录共六张布局（下称布局 1--6，依次含 \\(3\\) 至 \\(8\\) 台机器）",
     r"附录共六张布局（下称 \texttt{L1}--\texttt{L6}，L 取自 Lyu，编号沿用原文，依次含 \(3\) 至 \(8\) 台机器）"),
    ("布局 1 只有", r"\texttt{L1} 只有"),
    ("发表的布局 2--6", r"发表的布局 \texttt{L2}--\texttt{L6}"),
    ("外部布局 6", r"外部布局 \texttt{L6}"),
    ("外部布局 2", r"外部布局 \texttt{L2}"),
    ("布局 2 换成布局 3", r"\texttt{L2} 换成 \texttt{L3}"),
]
for old, new in fixed:
    n = s.count(old)
    assert n >= 1, old
    s = s.replace(old, new)

s = re.sub(r"布局 (\d)--(\d)", r"\\texttt{L\1}--\\texttt{L\2}", s)
s = re.sub(r"布局 (\d)、(\d)", r"\\texttt{L\1}、\\texttt{L\2}", s)
s = re.sub(r"布局 (\d)", r"\\texttt{L\1}", s)

open(P, "w", encoding="utf-8").write(s)
for i, line in enumerate(s.splitlines(), 1):
    if "texttt{L" in line:
        print(i, line[:160])
