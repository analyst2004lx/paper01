# -*- coding: utf-8 -*-
"""Generate the four LaTeX tables of the ladder batch from their source CSVs.

Why this exists at all.  The preamble of paper.tex declares every headline
number as a macro so that one CSV is the single source; a table typed by hand
would reintroduce exactly the drift the macros were meant to remove, because a
table has forty numbers and nobody re-derives forty numbers after a re-run.  So
the tables are generated from the same CSVs the macros are read off, and the
last section of this script prints the macro block for pasting, which makes any
disagreement between table and prose impossible rather than merely unlikely.

Deliberately stdlib-only (csv, no pandas): the solver is pure Python and runs on
machines without a scientific stack, and a table generator that cannot run there
would not be run.

Inputs
  clbs/output/baseline_ladder.csv   case,contention,arm,seed,makespan
  clbs/output/prune_ablation.csv    case,contention,arm,seed,makespan,decodes,ms_per_eval
Outputs (LaTeX tabular fragments, no float wrapper -- paper.tex supplies that)
  tab_instances.tex  tab_main.tex  tab_bytag.tex  tab_prune.tex

Run from the repository root:  py paper01/tab/gen_tables_ladder.py
"""
from __future__ import annotations

import csv
import os
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CLBS = os.path.join(ROOT, "clbs")
OUT = os.path.join(CLBS, "output")
sys.path.insert(0, CLBS)

from algorithm.stats import wilcoxon_signed_rank  # noqa: E402

# Reading order of the arms.  It is the 2x2 factorial of Section 5.2 read
# row-major (open loop first, rule dispatch first), not a cost ordering, so
# that the table's columns and the paper's four contrasts line up.
ARMS = ["B0", "B0+", "B1", "B2"]
ARM_TEX = {
    "B0": r"B0",
    "B0+": r"B0$^{+}$",
    "B1": r"B1",
    "B2": r"\textbf{B2}",
}
# The four single-factor contrasts.  Each holds one factor fixed and moves the
# other; the two cross-factor comparisons the tool also prints are excluded on
# purpose, since they cannot be attributed to either mechanism.
CONTRASTS = [
    ("B0", "B1", r"闭环的价值(规则派车下)"),
    ("B0+", "B2", r"闭环的价值(试探派车下)"),
    ("B0", "B0+", r"试探派车的价值(开环下)"),
    ("B1", "B2", r"试探派车的价值(闭环内)"),
    ("B0", "B2", r"\textbf{端到端:文献结构 $\rightarrow$ 本文}"),
]

FAMILY = {"A": "布局", "B": "车臂比", "C": "柔性"}


def read(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(
            "缺少 %s\n  先在 clbs/ 目录下运行对应的工具生成它。" % path)
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group(rows: List[dict], value: str = "makespan"):
    """(case, arm) -> list of values ordered by seed, plus the case/seed order."""
    by: Dict[str, Dict[str, Dict[int, float]]] = {}
    cont: Dict[str, float] = {}
    for r in rows:
        c, a, s = r["case"], r["arm"], int(r["seed"])
        by.setdefault(c, {}).setdefault(a, {})[s] = float(r[value])
        cont[c] = float(r["contention"])
    cases = sorted(by, key=lambda c: (c.split()[0], c))
    seeds = sorted({int(r["seed"]) for r in rows})
    return by, cont, cases, seeds


def mean(xs) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def paired(by, cases, seeds, ka: str, kb: str):
    """Paired gain of kb over ka, pooled over cases and seeds.

    Pairing is by (case, seed): the two arms share the seed, hence the same
    initial population, so the difference is the mechanism and not the draw.
    """
    xa = [by[c][ka][s] for c in cases for s in seeds
          if ka in by[c] and s in by[c][ka]]
    xb = [by[c][kb][s] for c in cases for s in seeds
          if kb in by[c] and s in by[c][kb]]
    rel = mean([(y - x) / x for x, y in zip(xa, xb)])
    w = wilcoxon_signed_rank(xb, xa)
    win = sum(1 for x, y in zip(xa, xb) if y < x - 1e-9)
    lose = sum(1 for x, y in zip(xa, xb) if y > x + 1e-9)
    tie = len(xa) - win - lose
    return rel, win, lose, tie, w["p_value"], len(xa)


def stars(p: float) -> str:
    return ("^{***}" if p < 0.001 else "^{**}" if p < 0.01
            else "^{*}" if p < 0.05 else "")


def ptex(p: float) -> str:
    if p < 1e-4:
        return r"$<10^{-4}$"
    return "$%.4f$" % p


def write(name: str, body: str) -> None:
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("%% 由 tab/gen_tables_ladder.py 生成,请勿手工编辑\n")
        f.write("%% 数据源:clbs/output/baseline_ladder.csv 等,见脚本首部\n")
        f.write(body)
    print("写出 %s" % os.path.relpath(path, ROOT))


# ---------------------------------------------------------------------------
def tab_instances(cont: Dict[str, float], cases: List[str]) -> None:
    """Instance table.  Structural columns come from the generator, not typed."""
    try:
        from algorithm.instance import simple_lower_bound
        from tools.abc_matrix import CASES, build
    except Exception as exc:                       # pragma: no cover
        print("!! 无法构造算例(%s),跳过 tab_instances" % exc)
        return

    spec = {c["name"]: c for c in CASES}
    lines = [r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
             r"算例 & 变化的因子 & 节点 & 走廊 & $N_A$ & $F$ & 争用强度 & 复合下界 \\",
             r"\midrule"]
    fam_seen = None
    for c in cases:
        if c not in spec:
            print("!! CSV 里的算例 %r 不在 abc_matrix.CASES 中,跳过" % c)
            continue
        if fam_seen is not None and c.split()[0] != fam_seen:
            lines.append(r"\midrule")
        fam_seen = c.split()[0]
        inst, net, _cc = build(spec[c])
        flex = (sum(len(r) for r in inst.proc_time.values())
                / len(inst.proc_time) / inst.num_machines)
        lb = simple_lower_bound(inst, net)["lower_bound"]
        lines.append("%s & %s & %d & %d & %d & %.2f & %.1f\\%% & %.1f \\\\"
                     % (c.replace("/", "/"), FAMILY.get(fam_seen, ""),
                        len(inst.nodes), len(inst.corridors), inst.num_agvs,
                        flex, 100.0 * cont[c], lb))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_instances.tex", "\n".join(lines) + "\n")


def tab_main(by, cont, cases, seeds) -> None:
    """Main result: per-case means on top, the factorial contrasts below."""
    lines = [r"\begin{tabular}{@{}lrrrrr@{}}", r"\toprule",
             r"算例 & 争用强度 & "
             + " & ".join(ARM_TEX[a] for a in ARMS) + r" \\",
             r"\midrule"]
    fam_seen = None
    for c in cases:
        if fam_seen is not None and c.split()[0] != fam_seen:
            lines.append(r"\midrule")
        fam_seen = c.split()[0]
        vals = " & ".join(
            ("\\textbf{%.2f}" if a == "B2" else "%.2f")
            % mean([by[c][a][s] for s in seeds if s in by[c].get(a, {})])
            for a in ARMS)
        lines.append("%s & %.1f\\%% & %s \\\\" % (c, 100.0 * cont[c], vals))

    lines.append(r"\midrule")
    allv = " & ".join(
        ("\\textbf{%.2f}" if a == "B2" else "%.2f")
        % mean([by[c][a][s] for c in cases for s in seeds
                if s in by[c].get(a, {})]) for a in ARMS)
    lines.append(r"\emph{全体均值} & --- & %s \\" % allv)
    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{0.6em}", "",
              r"\begin{tabular}{@{}lrrr@{}}", r"\toprule",
              r"单因子配对对比 & $\Delta C_{\max}$ & 胜/负/平 & $p$ \\",
              r"\midrule"]
    for ka, kb, label in CONTRASTS:
        if ka == "B0" and kb == "B2":
            lines.append(r"\midrule")
        rel, win, lose, tie, p, n = paired(by, cases, seeds, ka, kb)
        lines.append("%s & $%+.2f\\%%%s$ & %d/%d/%d & %s \\\\"
                     % (label, 100.0 * rel, stars(p), win, lose, tie, ptex(p)))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_main.tex", "\n".join(lines) + "\n")


def tab_bytag(by, cont, cases, seeds) -> None:
    """Per-cell robustness view: where each mechanism pays and where it does not."""
    lines = [r"\begin{tabular}{@{}lrrrrrrr@{}}", r"\toprule",
             r"算例 & 争用强度 & " + " & ".join(ARM_TEX[a] for a in ARMS)
             + r" & B0$\rightarrow$B1 & B1$\rightarrow$B2 \\",
             r"\midrule"]
    fam_seen = None
    for c in cases:
        if fam_seen is not None and c.split()[0] != fam_seen:
            lines.append(r"\midrule")
        fam_seen = c.split()[0]
        m = {a: mean([by[c][a][s] for s in seeds if s in by[c].get(a, {})])
             for a in ARMS}
        g1 = (m["B1"] - m["B0"]) / m["B0"]
        g2 = (m["B2"] - m["B1"]) / m["B1"]
        lines.append("%s & %.1f\\%% & %s & $%+.1f\\%%$ & $%+.1f\\%%$ \\\\"
                     % (c, 100.0 * cont[c],
                        " & ".join("%.2f" % m[a] for a in ARMS),
                        100.0 * g1, 100.0 * g2))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_bytag.tex", "\n".join(lines) + "\n")


def tab_prune() -> None:
    """Cost-reduction ablation.  Absent until prune_ablation.py has run."""
    path = os.path.join(OUT, "prune_ablation.csv")
    if not os.path.exists(path):
        print("跳过 tab_prune:%s 尚未生成(实验排在基线阶梯之后)"
              % os.path.relpath(path, ROOT))
        return
    rows = read(path)
    by, cont, cases, seeds = group(rows)
    ev, _, _, _ = group(rows, "decodes")
    ms, _, _, _ = group(rows, "ms_per_eval")
    on, off = "开", "关"

    lines = [r"\begin{tabular}{@{}lrrrrrr@{}}", r"\toprule",
             r"算例 & 争用强度 & 关 & 开 & $\Delta C_{\max}$ & 评价次数比 & 加速比 \\",
             r"\midrule"]
    for c in cases:
        a = mean([by[c][on][s] for s in seeds if s in by[c].get(on, {})])
        b = mean([by[c][off][s] for s in seeds if s in by[c].get(off, {})])
        ea = mean([ev[c][on][s] for s in seeds if s in ev[c].get(on, {})])
        eb = mean([ev[c][off][s] for s in seeds if s in ev[c].get(off, {})])
        ma = mean([ms[c][on][s] for s in seeds if s in ms[c].get(on, {})])
        mb = mean([ms[c][off][s] for s in seeds if s in ms[c].get(off, {})])
        lines.append("%s & %.1f\\%% & %.2f & \\textbf{%.2f} & $%+.2f\\%%$ & "
                     "%.2f$\\times$ & %.2f$\\times$ \\\\"
                     % (c, 100.0 * cont[c], b, a, 100.0 * (a - b) / b,
                        ea / max(eb, 1e-9), mb / max(ma, 1e-9)))
    rel, win, lose, tie, p, n = paired(by, cases, seeds, off, on)
    lines += [r"\midrule",
              r"\emph{配对合计}(%d 配对) & --- & --- & --- & $%+.2f\%%%s$ & "
              r"\multicolumn{2}{r}{%d/%d/%d,\ %s} \\"
              % (n, 100.0 * rel, stars(p), win, lose, tie, ptex(p)),
              r"\bottomrule", r"\end{tabular}"]
    write("tab_prune.tex", "\n".join(lines) + "\n")


def macro_block(by, cont, cases, seeds) -> None:
    """Print the preamble macro block so prose and tables cannot disagree."""
    print("\n" + "=" * 74)
    print("把下面这段替换进 paper.tex 导言区的对应位置(数字与上面的表同源):")
    print("=" * 74)
    print(r"\newcommand{\NCases}{%d}" % len(cases))
    print(r"\newcommand{\NSeeds}{%d}" % len(seeds))
    print(r"\newcommand{\NPairs}{%d}" % (len(cases) * len(seeds)))
    named = [("B0", "B1", "GainLoopRule", "PLoopRule"),
             ("B0+", "B2", "GainLoopProbe", "PLoopProbe"),
             ("B0", "B0+", "GainProbeOpen", "PProbeOpen"),
             ("B1", "B2", "GainProbeLoop", "PProbeLoop"),
             ("B0", "B2", "GainEndToEnd", "PEndToEnd")]
    gains = {}
    for ka, kb, gname, pname in named:
        rel, win, lose, tie, p, _n = paired(by, cases, seeds, ka, kb)
        gains[gname] = rel
        # The prose quotes improvements as positive magnitudes, so the sign is
        # dropped here and carried by the wording instead.
        print(r"\newcommand{\%s}{%.2f\%%}" % (gname, abs(100.0 * rel)))
        print(r"\newcommand{\P%s}{%.4f}" % (pname[1:], p))
        if gname == "GainEndToEnd":
            print(r"\newcommand{\WinEndToEnd}{%d}" % win)
            print(r"\newcommand{\LoseEndToEnd}{%d}" % lose)
    # If the two mechanisms did not interact, composing them would give this.
    indep = 1.0 - (1.0 + gains["GainLoopRule"]) * (1.0 + gains["GainProbeOpen"])
    print(r"\newcommand{\GainIndepProduct}{%.1f\%%}" % (100.0 * abs(indep)))
    print(r"\newcommand{\ContentionLo}{%.1f\%%}" % (100.0 * min(cont.values())))
    print(r"\newcommand{\ContentionHi}{%.1f\%%}" % (100.0 * max(cont.values())))

    # B-family cells quoted in Section 5.5: scarce fleet (probing pays most) and
    # the two large-fleet cells (probing harmful inside the closed loop).
    def cell_gain(name, ka, kb):
        if name not in by:
            return None
        ma = mean([by[name][ka][s] for s in seeds if s in by[name].get(ka, {})])
        mb = mean([by[name][kb][s] for s in seeds if s in by[name].get(kb, {})])
        return (mb - ma) / ma

    starved = cell_gain("B NA/NM 0.5", "B0", "B1")
    starve_p = cell_gain("B NA/NM 0.5", "B1", "B2")
    fleet1 = cell_gain("B NA/NM 1.0", "B1", "B2")
    fleet2 = cell_gain("B NA/NM 2.0", "B1", "B2")
    if starved is not None:
        print(r"\newcommand{\GainLoopStarve}{%+.1f\%%}" % (100.0 * starved))
        print(r"\newcommand{\GainProbeStarve}{%.1f\%%}" % abs(100.0 * starve_p))
    if fleet1 is not None:
        print(r"\newcommand{\GainProbeFleetOne}{%+.1f\%%}" % (100.0 * fleet1))
        print(r"\newcommand{\GainProbeFleetTwo}{%+.1f\%%}" % (100.0 * fleet2))
        if fleet1 <= 0 or fleet2 <= 0:
            print("%%!! 注意:大车队两格上 B1->B2 已不都为正,第 5.5 适用上界段须核对。")
    print("=" * 74)
    e2e = abs(100.0 * gains["GainEndToEnd"])
    ind = 100.0 * abs(indep)
    if e2e > ind + 0.05:
        print("交互自检:端到端 %.2f%% > 独立乘积 %.2f%% → 正交互;第 5.4 节按正交互写。"
              % (e2e, ind))
    else:
        print("交互自检:端到端 %.2f%% 未超过独立乘积 %.2f%% → 近加性/亚加性;"
              "第 5.4 节不得写正交互。" % (e2e, ind))


def main() -> int:
    rows = read(os.path.join(OUT, "baseline_ladder.csv"))
    by, cont, cases, seeds = group(rows)
    present = sorted({r["arm"] for r in rows})
    print("读入 baseline_ladder.csv:%d 算例 x %d 种子,臂 = %s"
          % (len(cases), len(seeds), ", ".join(present)))
    missing = [a for a in ARMS if a not in present]
    if missing:
        raise SystemExit("!! 缺少臂 %s,2x2 析因不完整,不能出表" % missing)
    if len(seeds) < 10:
        print("!! 警告:只有 %d 个种子,协议要求 10 个。表可以先出,但不得投稿。"
              % len(seeds))

    tab_instances(cont, cases)
    tab_main(by, cont, cases, seeds)
    tab_bytag(by, cont, cases, seeds)
    tab_prune()
    macro_block(by, cont, cases, seeds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
