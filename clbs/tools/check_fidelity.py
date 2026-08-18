"""布局矩阵保真度体检:判定一张行驶时间矩阵能否还原成图(规格 12.4 第 3 项)。

用法(在 clbs/ 目录下):

    py -m tools.check_fidelity bu        # 体检 Bilge & Ulusoy 的 4 个布局
    py -m tools.check_fidelity bu --csv  # 同时写 experiments_database/fidelity_bu.csv

判据与 `tools.convert_public` 共用同一套实现(直接 import,不复制),故 hf 与 bu 的结论
可以逐列对比。两个"可还原"列的区别见 `convert_public.fidelity_report` 的文档:
`digraph_reconstructible` 只查三角不等式,`corridor_reconstructible` 还要求对称,
**后者才是能否跑争用档(规格 12.3)的判据**。

hf 的矩阵由 pdftotext 机读得到,故其体检并入转换器;bu 的原始 PDF 是纯栅格
(无内嵌字体,pdftotext 全文仅 5 字符),矩阵只能人工转录,故单独放一个入口,
输入是 `database/extracted/bu/layouts_4machines.txt`。
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Dict, List

from tools.convert_public import fidelity_report
from tools import convert_public as cp

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "database")
EXP = os.path.join(HERE, "experiments_database")

_LAYOUT_RE = re.compile(r"^layout\s+(\d+)\s*$", re.IGNORECASE)
_ROW_RE = re.compile(r"^(LU|M\d+)\s+((?:-?\d+(?:\.\d+)?\s+)*-?\d+(?:\.\d+)?)\s*$")


def parse_layouts(path: str) -> Dict[int, List[List[float]]]:
    """读人工转录的布局文件。注释行以 # 起头,表头行(纯标号)被忽略。"""
    layouts: Dict[int, List[List[float]]] = {}
    current: int = -1
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = _LAYOUT_RE.match(line)
            if m:
                current = int(m.group(1))
                if current in layouts:
                    raise ValueError("第 %d 行:布局 %d 重复" % (lineno, current))
                layouts[current] = []
                continue
            m = _ROW_RE.match(line)
            if m:
                if current < 0:
                    raise ValueError("第 %d 行:数据行出现在任何 layout 之前" % lineno)
                layouts[current].append([float(x) for x in m.group(2).split()])
    if not layouts:
        raise ValueError("没解析到任何布局:%s" % path)
    for nm, mat in sorted(layouts.items()):
        n = len(mat)
        for i, row in enumerate(mat):
            if len(row) != n:
                raise ValueError(
                    "布局 %d 不是方阵:第 %d 行有 %d 列,应为 %d 列"
                    % (nm, i + 1, len(row), n))
            if abs(row[i]) > 1e-9:
                raise ValueError("布局 %d 对角线第 %d 项应为 0,实为 %s"
                                 % (nm, i + 1, row[i]))
    return layouts


def crosscheck_bu_layout1(bu: Dict[int, List[List[float]]]) -> str:
    """把人工转录对上一个**独立**取得的机读矩阵。

    hf 那一族的 4 机布局,其原文(Homayouni & Fontes)说明就是 Bilge & Ulusoy 的布局 1。
    而 hf 的矩阵是 `pdftotext` 从**另一份** PDF 机读来的,与 bu 的人工转录完全独立。
    两者若逐项相等,就等于用机器复核了转录的 25 格中的 25 格 —— 这是这份栅格 PDF
    唯一拿得到的自动化复核,故做成硬断言:不等即报错,不要只印一行警告。
    """
    src = os.path.join(DB, "extracted", "hf", "layouts_2to8.txt")
    if not os.path.isfile(src):
        return "跳过(hf 提取物不在:%s)" % os.path.relpath(src, HERE)
    with open(src, encoding="utf-8") as fh:
        hf = cp.parse_layouts(fh.read())
    if 4 not in hf:
        return "跳过(hf 提取物里没有 4 机布局)"
    if 1 not in bu:
        return "跳过(bu 转录里没有布局 1)"
    a, b = hf[4], bu[1]
    if len(a) != len(b) or any(
            abs(a[i][j] - b[i][j]) > 1e-9
            for i in range(len(a)) for j in range(len(a))):
        raise AssertionError(
            "bu 布局 1 与 hf 的 4 机布局不一致,但文献称两者是同一张布局。\n"
            "  hf(机读)= %s\n  bu(人工转录)= %s\n"
            "  => 人工转录很可能有误,先核对再继续。" % (a, b))
    return "通过(%d×%d 逐项相等,人工转录已被机读矩阵复核)" % (len(a), len(a))


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="布局矩阵保真度体检")
    ap.add_argument("key", choices=["bu"], help="数据集键")
    ap.add_argument("--csv", action="store_true",
                    help="写 experiments_database/fidelity_<key>.csv")
    args = ap.parse_args(argv)

    src = os.path.join(DB, "extracted", args.key, "layouts_4machines.txt")
    layouts = parse_layouts(src)
    # bu 的 4 个布局**都是 4 台机**,只是导轨走法不同,故按序号标号;沿用 hf 的 "{}-M"
    # 会把"布局 1"写成 "1-M",读起来像"1 台机的布局",与事实相反。
    rows = fidelity_report(layouts, label_fmt="layout{}")

    print("== %s 布局保真度体检(输入:%s)==" % (args.key, os.path.relpath(src, HERE)))
    print("%-8s %-5s %-7s %-10s %-10s %-8s %s"
          % ("布局", "阶", "对称", "三角违反", "最大超出", "有向图", "无向走廊"))
    for r in rows:
        print("%-8s %-5d %-7s %-10d %-10s %-8s %s"
              % (r["layout"], r["size"], str(r["symmetric"]),
                 r["closure_violations"], r["max_excess"],
                 "是" if r["digraph_reconstructible"] else "否",
                 "是" if r["corridor_reconstructible"] else "否"))

    if args.key == "bu":
        print("\n-- 转录复核(bu 布局 1 vs hf 4 机布局)--")
        print("   %s" % crosscheck_bu_layout1(layouts))
        print()

    n_di = sum(1 for r in rows if r["digraph_reconstructible"])
    n_co = sum(1 for r in rows if r["corridor_reconstructible"])
    total = len(rows)
    print("  -> 可还原为有向图:%d/%d;可还原为无向走廊网络:%d/%d"
          % (n_di, total, n_co, total))
    if n_co == 0:
        print("  -> 无一可还原为无向走廊,故这一族**不能**用于争用档(规格 12.3),"
              "只能跑退化对标(规格 12.2)")

    if args.csv:
        if not os.path.isdir(EXP):
            os.makedirs(EXP)
        out = os.path.join(EXP, "fidelity_%s.csv" % args.key)
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("  -> 已写 %s" % os.path.relpath(out, HERE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
