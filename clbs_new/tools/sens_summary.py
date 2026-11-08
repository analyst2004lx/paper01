# -*- coding: utf-8 -*-
"""敏感性批次汇总:机器节点容量 c 与异构度 H,CLBS 相对 OL / TS / AE 的逐格差。

读 output/sens_*.csv(由 baseline_ladder --cap/--het/--out 写出)。Holm 校正的族为
同一对比、同一敏感性因素下的全部格(c 族 6 格,H 族 4 格)。

Summary of the sensitivity batches (machine-node capacity c and heterogeneity H):
per-cell gains of CLBS over OL / TS / AE, Holm-corrected within each factor.

  py -3 -m tools.sens_summary [--tex]   # --tex 写 paper01_SCI/CAIE/tab/tab_sens.tex 与 sens_macros.tex
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.stats import holm, mean, wilcoxon_signed_rank

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
# 论文名:B0→OL,B0+→TS,BL→AE,B2→CLBS;funnel→S11,high→S21
# Paper names: B0->OL, B0+->TS, BL->AE, B2->CLBS; funnel->S11, high->S21
PAIRS = (("B0", "OL"), ("B0+", "TS"), ("BL", "AE"))
LAYOUT = {"A funnel": "S11", "A high": "S21"}
FAMILIES = {
    "c": [("sens_c1.csv", "A funnel"), ("sens_c2.csv", "A funnel"), ("sens_cinf.csv", "A funnel"),
          ("sens_c1.csv", "A high"), ("sens_c2.csv", "A high"), ("sens_cinf.csv", "A high")],
    "H": [("sens_h0.csv", "A funnel"), ("sens_h015.csv", "A funnel"),
          ("sens_c2.csv", "A funnel"), ("sens_h05.csv", "A funnel")],
}


def load(fn: str):
    by = defaultdict(lambda: defaultdict(dict))
    meta = {}
    with open(os.path.join(OUT, fn), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by[r["case"]][r["arm"]][int(r["seed"])] = float(r["makespan"])
            meta[r["case"]] = (r["cap"], r["het"], float(r["contention"]))
    return by, meta


TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "paper01_SCI", "CAIE", "tab")
# 宏名只能用字母:格 -> 宏后缀
# Macro names must be letters only: cell -> macro suffix
MAC_SUFFIX = {("A funnel", "1"): "FunnelOne", ("A funnel", "2"): "FunnelTwo",
              ("A funnel", "inf"): "FunnelInf", ("A high", "1"): "HighOne",
              ("A high", "2"): "HighTwo", ("A high", "inf"): "HighInf"}
H_SUFFIX = {"0.0": "HZero", "0.15": "HLow", "0.3": "HMid", "0.5": "HHigh"}


def marks(r: dict) -> str:
    # 与 gen_tables_ladder.cell_stars 同一规则 / same rule as gen_tables_ladder.cell_stars
    if r["p_holm"] < 0.01:
        return "^{**}"
    if r["p_holm"] < 0.05:
        return "^{*}"
    return r"^{\dagger}" if r["p"] < 0.05 else ""


def pct(x: float) -> str:
    return r"$%+.1f\%%$" % (100 * x)


def cell_label(fam: str, r: dict) -> str:
    if fam == "c":
        c = r"\infty" if r["cap"] == "inf" else r["cap"]
        return r"\texttt{%s}, $c=%s$" % (LAYOUT[r["case"]], c)
    return r"\texttt{S11}, $H=%s$" % ("0" if r["het"] == "0.0" else r["het"])


def write_tex(fams: dict) -> None:
    lines = [r"%% 由 clbs_new/tools/sens_summary.py --tex 生成,请勿手工编辑",
             r"%% 数据源:clbs_new/output/sens_*.csv",
             r"\begin{tabular}{@{}lrrrrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{4}{c}{$C_{\max}$(时间单位)} & "
             r"\multicolumn{3}{c}{本文相对对比方法的逐对相对差} \\",
             r"\cmidrule(lr){3-6}\cmidrule(lr){7-9}",
             r"算例 & 争用强度 & OL & TS & AE & \textbf{CLBS} & OL$\rightarrow$CLBS & "
             r"TS$\rightarrow$CLBS & AE$\rightarrow$CLBS \\"]
    for i, (fam, rows) in enumerate(fams.items()):
        lines.append(r"\midrule")
        for r in rows:
            a = r["avg"]
            lines.append(" & ".join(
                [cell_label(fam, r), r"%.1f\%%" % (100 * r["cont"])]
                + ["%.2f" % a[k] for k in ("B0", "B0+", "BL", "B2")]
                + [r"$%+.1f\%%%s$" % (100 * r[k]["rel"], marks(r[k])) for k, _ in PAIRS])
                + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    with open(os.path.join(TAB_DIR, "tab_sens.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    mac = [r"%% 由 clbs_new/tools/sens_summary.py --tex 生成,请勿手工编辑"]
    for fam, rows in fams.items():
        for k, name in PAIRS:
            for r in rows:
                suf = MAC_SUFFIX[(r["case"], r["cap"])] if fam == "c" else H_SUFFIX[r["het"]]
                mac.append(r"\newcommand{\Sens%s%s}{%s}" % (name, suf, pct(r[k]["rel"])))
            vals = [r[k]["rel"] for r in rows]
            tag = "Cap" if fam == "c" else "Het"
            mac.append(r"\newcommand{\Sens%sRange%s}{%s 至 %s}"
                       % (name, tag, pct(min(vals)), pct(max(vals))))
            mac.append(r"\newcommand{\Sens%sSig%s}{%d}"
                       % (name, tag, sum(r[k]["p_holm"] < 0.05 and r[k]["rel"] < 0 for r in rows)))
            mac.append(r"\newcommand{\Sens%sWorse%s}{%d}"
                       % (name, tag, sum(r[k]["rel"] > 0 for r in rows)))
        mac.append(r"\newcommand{\SensN%s}{%d}" % ("Cap" if fam == "c" else "Het", len(rows)))
    with open(os.path.join(TAB_DIR, "sens_macros.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(mac) + "\n")


def main() -> int:
    fams = {}
    for fam, cells in FAMILIES.items():
        rows = []
        for fn, case in cells:
            by, meta = load(fn)
            cap, het, cont = meta[case]
            d = by[case]
            seeds = sorted(d["B2"])
            row = dict(label=f"{LAYOUT[case]} c={cap} H={het}", cont=cont,
                       case=case, cap=cap, het=het,
                       avg={k: mean([d[k][s] for s in seeds]) for k in ("B0", "B0+", "BL", "B2")})
            for k, _ in PAIRS:
                xa = [d[k][s] for s in seeds]
                xb = [d["B2"][s] for s in seeds]
                row[k] = dict(rel=mean([(y - x) / x for x, y in zip(xa, xb)]),
                              win=sum(y < x - 1e-9 for x, y in zip(xa, xb)),
                              lose=sum(y > x + 1e-9 for x, y in zip(xa, xb)),
                              p=wilcoxon_signed_rank(xb, xa)["p_value"])
            rows.append(row)
        for k, _ in PAIRS:
            for r, ph in zip(rows, holm([r[k]["p"] for r in rows])):
                r[k]["p_holm"] = ph

        print(f"\n== 因素 {fam}(Holm 族 = 本因素 {len(rows)} 格) ==")
        print(f"{'格':<20s}{'争用':>7s}{'OL':>8s}{'TS':>8s}{'AE':>8s}{'CLBS':>8s}"
              + "".join(f"{'CLBS vs ' + n:>26s}" for _, n in PAIRS))
        for r in rows:
            a = r["avg"]
            cells_txt = "".join(
                f"{r[k]['rel']:>+8.1%} {r[k]['win']:>2d}/{r[k]['lose']:<2d} "
                f"p={r[k]['p']:.3f} h={r[k]['p_holm']:.3f}" for k, _ in PAIRS)
            print(f"{r['label']:<20s}{r['cont']:>7.1%}{a['B0']:>8.2f}{a['B0+']:>8.2f}"
                  f"{a['BL']:>8.2f}{a['B2']:>8.2f}  {cells_txt}")
        fams[fam] = rows
    if "--tex" in sys.argv[1:]:
        write_tex(fams)
        print(f"\n已写入 {os.path.normpath(TAB_DIR)}\\tab_sens.tex 与 sens_macros.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
