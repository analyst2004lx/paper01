# -*- coding: utf-8 -*-
"""列出每张表的数字单元格数与已用宏,为 P11「脚本化清单」取证。"""
import io
import re

SRC = "paper04_CN_AI-Modify-26-09-17.tex"
OUT = "table_inventory.txt"

KNOWN = {
    "multirow", "texttt", "emph", "textbf", "mathrm", "max", "ref",
    "cmark", "xmark", "omark", "times", "le", "ge", "frac", "small",
    "toprule", "midrule", "bottomrule", "addlinespace", "multicolumn",
    "centering", "caption", "label", "begin", "end", "hline", "cline",
}

buf = io.StringIO()
src = open(SRC, encoding="utf-8").read()

for m in re.finditer(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", src, re.S):
    blk = m.group(1)
    start = src[: m.start()].count("\n") + 1
    lab = re.search(r"\\label\{([^}]*)\}", blk)
    cap = re.search(r"\\caption\{(.{0,70})", blk, re.S)
    body = re.search(r"\\begin\{tabular\}.*?\n(.*?)\\end\{tabular\}", blk, re.S)
    nums, macros = 0, set()
    if body:
        b = body.group(1)
        nums = len(re.findall(r"(?<![\w.])\d+\.\d+|(?<![\w.])\d+(?![\w.])", b))
        macros = set(re.findall(r"\\([A-Za-z]{3,})", b))
    capt = re.sub(r"\s+", " ", cap.group(1)) if cap else "?"
    buf.write("line %-5d  %-16s  数字单元格=%-4d  %s\n" % (
        start, lab.group(1) if lab else "?", nums, capt[:52]))
    use = sorted(x for x in macros if x not in KNOWN)
    if use:
        buf.write("               已用宏: " + ", ".join(use) + "\n")

open(OUT, "w", encoding="utf-8").write(buf.getvalue())
print("written " + OUT)
