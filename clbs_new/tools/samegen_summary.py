# -*- coding: utf-8 -*-
"""同代数对照汇总:CLBS-R(B1,规则派车)与 CLBS(B2,预约表感知派遣)各跑 30 代、不设挂钟。

读 output/samegen_full.csv 与 samegen_full_BC.csv(由 samegen_check --out 写出)。逐格
Holm 校正的族为全部 10 格;合计按(算例,种子)配对。

Summary of the equal-generation contrast of B1 and B2. Per-cell Holm over the 10 cells;
the pooled test pairs by (case, seed).

  py -3 -m tools.samegen_summary [--tex]   # --tex 写 paper01_SCI/CAIE/tab/samegen_macros.tex
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.stats import hodges_lehmann, holm, mean, wilcoxon_signed_rank

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
FILES = ("samegen_full.csv", "samegen_full_BC.csv")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "paper01_SCI", "CAIE", "tab")
ORDER = ["A funnel", "A high", "A mid", "A low", "A scatter",
         "B NA/NM 0.5", "B NA/NM 1.0", "B NA/NM 2.0", "C F=0.3", "C F=1.0"]


def main() -> int:
    mk = defaultdict(lambda: defaultdict(dict))   # case -> arm -> seed -> makespan
    rt = defaultdict(list)                        # arm -> runtime_sec
    for fn in FILES:
        with open(os.path.join(OUT, fn), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                mk[r["case"]][r["arm"]][int(r["seed"])] = float(r["makespan"])
                rt[r["arm"]].append(float(r["runtime_sec"]))
    cases = [c for c in ORDER if c in mk]
    rows = []
    for c in cases:
        seeds = sorted(set(mk[c]["B1"]) & set(mk[c]["B2"]))
        a = [mk[c]["B1"][s] for s in seeds]
        b = [mk[c]["B2"][s] for s in seeds]
        rows.append(dict(case=c, n=len(seeds), rel=mean([(y - x) / x for x, y in zip(a, b)]),
                         win=sum(y < x - 1e-9 for x, y in zip(a, b)),
                         lose=sum(y > x + 1e-9 for x, y in zip(a, b)),
                         p=wilcoxon_signed_rank(b, a)["p_value"]))
    for r, ph in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = ph

    xa = [mk[c]["B1"][s] for c in cases for s in sorted(mk[c]["B1"])]
    xb = [mk[c]["B2"][s] for c in cases for s in sorted(mk[c]["B1"])]
    rels = [(y - x) / x for x, y in zip(xa, xb)]
    pooled = dict(rel=mean(rels), hl=hodges_lehmann(rels),
                  win=sum(y < x - 1e-9 for x, y in zip(xa, xb)),
                  lose=sum(y > x + 1e-9 for x, y in zip(xa, xb)),
                  p=wilcoxon_signed_rank(xb, xa)["p_value"], n=len(xa))
    time_ratio = mean(rt["B2"]) / mean(rt["B1"])

    print(f"{'算例':<14s}{'n':>4s}{'CLBS vs CLBS-R':>16s}{'胜/负':>8s}{'p':>9s}{'p_holm':>9s}")
    for r in rows:
        print(f"{r['case']:<14s}{r['n']:>4d}{r['rel']:>+16.1%}{r['win']:>4d}/{r['lose']:<3d}"
              f"{r['p']:>9.4f}{r['p_holm']:>9.4f}")
    print(f"\n合计 {pooled['n']} 对:均值 {pooled['rel']:+.2%},HL {pooled['hl']:+.2%},"
          f"{pooled['win']} 胜 / {pooled['lose']} 负,p={pooled['p']:.2e}")
    print(f"30 代耗时:CLBS {mean(rt['B2']):.0f}s,CLBS-R {mean(rt['B1']):.0f}s,"
          f"比 {time_ratio:.2f}x")

    if "--tex" in sys.argv[1:]:
        sig = sum(r["p_holm"] < 0.05 and r["rel"] < 0 for r in rows)
        rel_sorted = sorted(r["rel"] for r in rows)
        mac = [r"%% 由 clbs_new/tools/samegen_summary.py --tex 生成,请勿手工编辑",
               r"\newcommand{\SameGenGens}{30}",
               r"\newcommand{\SameGenNCells}{%d}" % len(rows),
               r"\newcommand{\SameGenNPairs}{%d}" % pooled["n"],
               r"\newcommand{\SameGenGain}{$%+.2f\%%$}" % (100 * pooled["rel"]),
               r"\newcommand{\SameGenGainAbs}{%.2f\%%}" % (-100 * pooled["rel"]),
               r"\newcommand{\SameGenSigRaw}{%d}" % sum(r["p"] < 0.05 and r["rel"] < 0
                                                        for r in rows),
               r"\newcommand{\SameGenHolmMin}{%.3f}" % min(r["p_holm"] for r in rows),
               r"\newcommand{\SameGenHL}{$%+.2f\%%$}" % (100 * pooled["hl"]),
               r"\newcommand{\SameGenWin}{%d}" % pooled["win"],
               r"\newcommand{\SameGenLose}{%d}" % pooled["lose"],
               r"\newcommand{\SameGenP}{%s}" % ("<10^{-4}" if pooled["p"] < 1e-4
                                                 else "=%.4f" % pooled["p"]),
               r"\newcommand{\SameGenSig}{%d}" % sig,
               r"\newcommand{\SameGenRange}{$%+.1f\%%$ 至 $%+.1f\%%$}"
               % (100 * rel_sorted[0], 100 * rel_sorted[-1]),
               r"\newcommand{\SameGenTimeRatio}{%.1f}" % time_ratio]
        with open(os.path.join(TAB_DIR, "samegen_macros.tex"), "w", encoding="utf-8") as f:
            f.write("\n".join(mac) + "\n")
        print(f"\n已写入 {os.path.normpath(TAB_DIR)}\\samegen_macros.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
