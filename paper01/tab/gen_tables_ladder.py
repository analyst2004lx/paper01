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

from algorithm.stats import (benjamini_hochberg, hodges_lehmann_ci,  # noqa: E402
                             holm, wilcoxon_signed_rank)

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


def paired(by, cases, seeds, ka: str, kb: str) -> dict:
    """Paired gain of kb over ka, pooled over cases and seeds.

    Pairing is by (case, seed): the two arms share the seed, hence the same
    initial population, so the difference is the mechanism and not the draw.

    Alongside the mean relative gain the result carries the Hodges--Lehmann
    pseudo-median of the per-pair relative gains and its distribution-free
    95% interval.  The mean is kept as the headline estimator because every
    per-cell table in the paper uses it and the design is balanced, but a mean
    carries no precision statement; the HL pair does, and it is the estimator
    that actually corresponds to the Wilcoxon test reported next to it.
    """
    xa = [by[c][ka][s] for c in cases for s in seeds
          if ka in by[c] and s in by[c][ka]]
    xb = [by[c][kb][s] for c in cases for s in seeds
          if kb in by[c] and s in by[c][kb]]
    rels = [(y - x) / x for x, y in zip(xa, xb)]
    w = wilcoxon_signed_rank(xb, xa)
    ci = hodges_lehmann_ci(rels) or {}
    win = sum(1 for x, y in zip(xa, xb) if y < x - 1e-9)
    lose = sum(1 for x, y in zip(xa, xb) if y > x + 1e-9)
    return {"rel": mean(rels), "win": win, "lose": lose,
            "tie": len(xa) - win - lose, "p": w["p_value"], "n": len(xa),
            "hl": ci.get("hl"), "lo": ci.get("lo"), "hi": ci.get("hi"),
            "ci_method": ci.get("method")}


def per_cell(by, cases, seeds, ka: str, kb: str) -> List[dict]:
    """The ten single-cell contrasts of one effect, with Holm/BH adjustment.

    The family is exactly the ten cells of one effect.  This is the family the
    prose reads signs off, so it is the family that has to be corrected; mixing
    the two effects into one family of twenty would correct a comparison nobody
    makes.  Both adjustments are attached: Holm because the per-cell claims are
    "does this cell pay" (FWER), BH as the looser reading, so that it is visible
    that the choice was not made after seeing which one helped.
    """
    out = [dict(case=c, **paired(by, [c], seeds, ka, kb)) for c in cases]
    ps = [r["p"] for r in out]
    for r, a, b in zip(out, holm(ps), benjamini_hochberg(ps)):
        r["p_holm"], r["p_bh"] = a, b
    return out


def stars(p: float) -> str:
    return ("^{***}" if p < 0.001 else "^{**}" if p < 0.01
            else "^{*}" if p < 0.05 else "")


def cell_stars(r: dict) -> str:
    """Per-cell marks: stars by Holm-adjusted p, dagger = raw-only significance.

    The dagger is the point of this function.  A cell that is significant before
    correction and not after is exactly the case the paper must not narrate as a
    finding, and hiding it behind a blank would make the corrected table look
    like the uncorrected one with fewer stars rather than like a different
    statement about the same data.
    """
    if r["p_holm"] < 0.01:
        return "^{**}"
    if r["p_holm"] < 0.05:
        return "^{*}"
    if r["p"] < 0.05:
        return r"^{\dagger}"
    return ""


def ptex(p: float) -> str:
    if p < 1e-4:
        return r"$<10^{-4}$"
    return "$%.4f$" % p


def pmac(p: float) -> str:
    """A p value as it appears in prose, with its relation symbol included.

    The relation belongs inside the macro, not at the call site.  A p below the
    reporting floor has to read "p<10^{-4}"; writing "p=0.0000" claims a p of
    zero, which no test returns.  If the "=" lived in the body instead, a re-run
    that pushed some p under the floor would silently render "p=<10^{-4}"
    wherever that macro is quoted, and nothing would catch it.  So every P-macro
    carries its own relation and every call site is "$p\\PSomething$".
    """
    return "<10^{-4}" if p < 1e-4 else "=%.4f" % p


def citex(r: dict) -> str:
    """HL pseudo-median with its 95% interval, both as percentages."""
    if r.get("hl") is None:
        return "---"
    return (r"$%+.2f$ $[%+.2f,%+.2f]$"
            % (100.0 * r["hl"], 100.0 * r["lo"], 100.0 * r["hi"]))


def write(name: str, body: str) -> None:
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("%% 由 tab/gen_tables_ladder.py 生成,请勿手工编辑\n")
        f.write("%% 数据源:clbs/output/baseline_ladder.csv 等,见脚本首部\n")
        f.write(body)
    print("写出 %s" % os.path.relpath(path, ROOT))


# ---------------------------------------------------------------------------
def tab_instances(cont: Dict[str, float], cases: List[str]) -> Dict[str, float]:
    """Instance table.  Structural columns come from the generator, not typed.

    Returns, per case, the longest ideal LU-to-arm haul.  Section 5.1.1 needs it
    as the evidence for where the layout family stops being a capacity-only
    sweep: it is a pure distance quantity, whereas the composite bound in the
    table is a max over three relaxations and is dominated by the funnel cut on
    some cells and by the job chain on others, so the bound moves for reasons
    that have nothing to do with distance and must not be read as a proxy for it.
    """
    try:
        from algorithm.generator import CONGESTION_PRESETS
        from algorithm.instance import simple_lower_bound
        from tools.abc_matrix import CASES, build
    except Exception as exc:                       # pragma: no cover
        print("!! 无法构造算例(%s),跳过 tab_instances" % exc)
        return {}, {}

    legs: Dict[str, float] = {}
    layout: Dict[str, str] = {}
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
        inst, net, merged = build(spec[c])
        flex = (sum(len(r) for r in inst.proc_time.values())
                / len(inst.proc_time) / inst.num_machines)
        lb = simple_lower_bound(inst, net)["lower_bound"]
        legs[c] = max(net.ideal_dist[inst.lu_node][inst.machine_node[m]]
                      for m in inst.machine_node)
        # Read off the generator's own preset rather than the case name, so that
        # retagging a case cannot silently move it to the wrong segment.
        layout[c] = CONGESTION_PRESETS[merged["tag"]]["layout"]
        lines.append("%s & %s & %d & %d & %d & %.2f & %.1f\\%% & %.1f \\\\"
                     % (c.replace("/", "/"), FAMILY.get(fam_seen, ""),
                        len(inst.nodes), len(inst.corridors), inst.num_agvs,
                        flex, 100.0 * cont[c], lb))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_instances.tex", "\n".join(lines) + "\n")
    return legs, layout


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
    # The five contrasts form one family, so they are corrected together.  The
    # end-to-end row is included rather than exempted: leaving it out would make
    # the four attribution rows look slightly stronger for no reason other than
    # a smaller m, and with these p values the correction costs nothing anyway.
    rows = [dict(label=label, **paired(by, cases, seeds, ka, kb))
            for ka, kb, label in CONTRASTS]
    for r, adj in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = adj

    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{0.6em}", "",
              r"\begin{tabular}{@{}lrlrr@{}}", r"\toprule",
              r"单因子配对对比 & $\Delta C_{\max}$ & HL 伪中位数与 $95\%$ CI(\%) "
              r"& 胜/负/平 & $p_{\mathrm{Holm}}$ \\",
              r"\midrule"]
    for (ka, kb, _label), r in zip(CONTRASTS, rows):
        if ka == "B0" and kb == "B2":
            lines.append(r"\midrule")
        lines.append("%s & $%+.2f\\%%%s$ & %s & %d/%d/%d & %s \\\\"
                     % (r["label"], 100.0 * r["rel"], stars(r["p_holm"]),
                        citex(r), r["win"], r["lose"], r["tie"],
                        ptex(r["p_holm"])))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_main.tex", "\n".join(lines) + "\n")


def tab_bytag(by, cont, cases, seeds) -> None:
    """Per-cell robustness view: where each mechanism pays and where it does not.

    The two gain columns use the *same* estimator as the pooled table, i.e. the
    mean over seeds of the per-pair relative gain, not the ratio of the two
    displayed means.  The design is balanced, so with this estimator the ten
    cells average exactly to the headline macros; with the ratio-of-means it did
    not, and a reader averaging the column got a different number from the one
    in the prose.  The price is that the gain column is no longer reproducible
    from the two mean columns on its own row -- said so in the caption.

    Per-cell significance is printed because Section 5.5 reads signs off single
    cells.  Ten seeds is thin, and a sign that is not significant must not be
    narrated as a threshold.  The marks are therefore set by the Holm-adjusted
    p within each ten-cell family, with a dagger for cells that were significant
    only before correction -- reading an uncorrected per-cell sign as an
    applicability range is precisely the error the section is written to avoid.
    """
    loop = {r["case"]: r for r in per_cell(by, cases, seeds, "B0", "B1")}
    probe = {r["case"]: r for r in per_cell(by, cases, seeds, "B1", "B2")}

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
        r1, r2 = loop[c], probe[c]
        lines.append("%s & %.1f\\%% & %s & $%+.1f\\%%%s$ & $%+.1f\\%%%s$ \\\\"
                     % (c, 100.0 * cont[c],
                        " & ".join("%.2f" % m[a] for a in ARMS),
                        100.0 * r1["rel"], cell_stars(r1),
                        100.0 * r2["rel"], cell_stars(r2)))
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
    r = paired(by, cases, seeds, off, on)
    lines += [r"\midrule",
              r"\emph{配对合计}(%d 配对) & --- & --- & --- & $%+.2f\%%%s$ & "
              r"\multicolumn{2}{r}{%d/%d/%d,\ %s} \\"
              % (r["n"], 100.0 * r["rel"], stars(r["p"]), r["win"], r["lose"],
                 r["tie"], ptex(r["p"])),
              r"\midrule",
              r"\multicolumn{7}{@{}l@{}}{\footnotesize HL 伪中位数与 $95\%$ CI:"
              + citex(r) + r"\,\%} \\",
              r"\bottomrule", r"\end{tabular}"]
    write("tab_prune.tex", "\n".join(lines) + "\n")


def macro_block(by, cont, cases, seeds, legs: Dict[str, float],
                layout: Dict[str, str]) -> None:
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
    pooled = [dict(g=g, pn=pn, **paired(by, cases, seeds, ka, kb))
              for ka, kb, g, pn in named]
    for r, adj in zip(pooled, holm([r["p"] for r in pooled])):
        r["p_holm"] = adj
    gains = {}
    for r in pooled:
        gains[r["g"]] = r["rel"]
        # The prose quotes improvements as positive magnitudes, so the sign is
        # dropped here and carried by the wording instead.
        print(r"\newcommand{\%s}{%.2f\%%}" % (r["g"], abs(100.0 * r["rel"])))
        # Holm-adjusted, because the table and the prose must quote the same
        # number and the table is corrected.  With these p values the correction
        # is inert, which is itself worth being able to state from a macro.
        print(r"\newcommand{\P%s}{%s}" % (r["pn"][1:], pmac(r["p_holm"])))
        if r["g"] == "GainEndToEnd":
            print(r"\newcommand{\WinEndToEnd}{%d}" % r["win"])
            print(r"\newcommand{\LoseEndToEnd}{%d}" % r["lose"])
    # Effect sizes for the two contrasts the prose quantifies in text.  A mean
    # relative gain has no precision attached; these do, and they come from the
    # same signed-rank null distribution as the p value beside them.
    for r in pooled:
        if r["g"] in ("GainLoopRule", "GainProbeLoop"):
            key = r["g"].replace("Gain", "")
            print(r"\newcommand{\HL%s}{%.2f\%%}" % (key, abs(100.0 * r["hl"])))
            print(r"\newcommand{\CI%s}{$[%.2f\%%,\ %.2f\%%]$}"
                  % (key, abs(100.0 * r["hi"]), abs(100.0 * r["lo"])))
    # If the two mechanisms did not interact, composing them would give this.
    indep = 1.0 - (1.0 + gains["GainLoopRule"]) * (1.0 + gains["GainProbeOpen"])
    print(r"\newcommand{\GainIndepProduct}{%.1f\%%}" % (100.0 * abs(indep)))
    print(r"\newcommand{\ContentionLo}{%.1f\%%}" % (100.0 * min(cont.values())))
    print(r"\newcommand{\ContentionHi}{%.1f\%%}" % (100.0 * max(cont.values())))
    # The layout family's own upper end, which is not the global maximum: the
    # most contended cell of all is a C-family cell built on the same funnel
    # layout but at full flexibility.  Section 5.1.1 describes the span of the
    # five layout cells and must therefore use this macro; quoting the global
    # \ContentionHi there credits the layout sweep with a reading taken from a
    # different family.
    cont_a = [v for c, v in cont.items() if c.split()[0] == "A"]
    if cont_a:
        print(r"\newcommand{\ContentionAHi}{%.1f\%%}" % (100.0 * max(cont_a)))
    # The two hauls Section 5.1.1 contrasts to show that the layout family stops
    # being a capacity-only sweep at the dumbbell -> grid step.  Each value is
    # shared exactly by the cells of its segment, which is the whole point: the
    # dumbbell trio really does hold distance fixed, so a single number states
    # it, and if a future edit breaks that the assertion below fails loudly
    # rather than letting the paper keep a claim the generator no longer honours.
    fam_a = [c for c in cases if c.split()[0] == "A" and c in legs]
    dumb = {c: legs[c] for c in fam_a if layout.get(c) == "dumbbell"}
    grid = {c: legs[c] for c in fam_a if layout.get(c) != "dumbbell"}
    for name, seg in (("哑铃", dumb), ("网格/错落", grid)):
        if len(set(seg.values())) > 1:
            raise SystemExit(
                "!! 布局族 %s 段内各格的最远行程不再相同(%s):第 5.1.1 小节"
                "\"该段只动容量不动距离\"的说法已不成立,必须先改正文再出表。"
                % (name, seg))
    if dumb and grid:
        print(r"\newcommand{\LegDumbbell}{%.1f}" % max(dumb.values()))
        print(r"\newcommand{\LegGrid}{%.1f}" % max(grid.values()))
    # How many of the ten cells reach significance on their own.  Section 5.5
    # reads signs off single cells, and the two effects differ sharply here:
    # quoting these counts keeps the per-cell narrative honest about what ten
    # seeds can and cannot resolve.
    # Both the raw and the Holm-adjusted counts are emitted.  The paper leads
    # with the adjusted one, because that is the number its per-cell discipline
    # is entitled to; the raw one is kept so the section can state plainly how
    # much of the per-cell picture was an artefact of not correcting, which is
    # the honest way to report a count that moved.
    cells = {}
    for ka, kb, cname in (("B0", "B1", "CellsSigLoop"),
                          ("B1", "B2", "CellsSigProbe")):
        rs = per_cell(by, cases, seeds, ka, kb)
        cells[cname] = rs
        print(r"\newcommand{\%s}{%d}"
              % (cname, sum(1 for r in rs if r["p"] < 0.05)))
        print(r"\newcommand{\%sAdj}{%d}"
              % (cname, sum(1 for r in rs if r["p_holm"] < 0.05)))

    # B-family cells quoted in Section 5.5: scarce fleet (probing pays most) and
    # the two large-fleet cells (probing harmful inside the closed loop).
    # Same estimator as the pooled contrasts and as tab_bytag, so the cell
    # macros and the table cannot disagree.
    def cell_gain(name, ka, kb):
        if name not in by:
            return None
        return paired(by, [name], seeds, ka, kb)["rel"]

    def cell_p(name, ka, kb):
        if name not in by:
            return None
        return paired(by, [name], seeds, ka, kb)["p"]

    starved = cell_gain("B NA/NM 0.5", "B0", "B1")
    starve_p = cell_gain("B NA/NM 0.5", "B1", "B2")
    fleet1 = cell_gain("B NA/NM 1.0", "B1", "B2")
    fleet2 = cell_gain("B NA/NM 2.0", "B1", "B2")
    # The base cell is the fourth point of the B family (N_A/N_M = 1.5) and the
    # middle point of the C family (F = 0.6); tools/abc_matrix.py shares it
    # across the three families and runs it once, under the name "A funnel".
    # Section 5.5 must quote it, otherwise the fleet sweep looks monotone when
    # it is not.
    fleetbase = cell_gain("A funnel", "B1", "B2")
    if starved is not None:
        print(r"\newcommand{\GainLoopStarve}{%+.1f\%%}" % (100.0 * starved))
        print(r"\newcommand{\GainProbeStarve}{%.1f\%%}" % abs(100.0 * starve_p))
    if fleetbase is not None:
        print(r"\newcommand{\GainProbeFleetBase}{%+.1f\%%}" % (100.0 * fleetbase))
    if fleet1 is not None:
        print(r"\newcommand{\GainProbeFleetOne}{%+.1f\%%}" % (100.0 * fleet1))
        print(r"\newcommand{\GainProbeFleetTwo}{%+.1f\%%}" % (100.0 * fleet2))
        if fleet1 <= 0 or fleet2 <= 0:
            print("%%!! 注意:大车队两格上 B1->B2 已不都为正,第 5.5 适用上界段须核对。")

    # ---- The remaining per-cell readings Section 5.5 quotes verbatim --------
    # That section walks the three families cell by cell, and those figures were
    # the last ones still typed into the body by hand while every pooled figure
    # came from a macro.  They duplicate tab_bytag exactly, which is the drift
    # the macro block exists to prevent: a re-run regenerates the table and
    # leaves the sentences describing the previous run.  Like the fleet macros
    # above, each carries its own sign, so the prose quotes it bare.
    for name, suffix in (("A funnel", "Funnel"), ("A high", "High"),
                         ("A mid", "Mid"), ("A low", "Low"),
                         ("A scatter", "Scatter"),
                         ("B NA/NM 1.0", "FleetOne"),
                         ("B NA/NM 2.0", "FleetTwo"),
                         ("C F=0.3", "FlexLo"), ("C F=1.0", "FlexHi")):
        g = cell_gain(name, "B0", "B1")
        if g is not None:
            print(r"\newcommand{\GainLoop%s}{%+.1f\%%}" % (suffix, 100.0 * g))
    for name, suffix in (("C F=0.3", "FlexLo"), ("C F=1.0", "FlexHi")):
        g = cell_gain(name, "B1", "B2")
        if g is not None:
            print(r"\newcommand{\GainProbe%s}{%+.1f\%%}" % (suffix, 100.0 * g))
    # Raw, uncorrected p for the four fleet levels.  Section 5.5 quotes these
    # as uncorrected on purpose -- the point it makes there is that they are
    # nowhere near the threshold even before any correction is applied -- so
    # the macro name says Raw and the prose says so too.
    for name, suffix in (("B NA/NM 0.5", "FleetHalf"),
                         ("B NA/NM 1.0", "FleetOne"),
                         ("A funnel", "FleetBase"),
                         ("B NA/NM 2.0", "FleetTwo")):
        p = cell_p(name, "B1", "B2")
        if p is not None:
            print(r"\newcommand{\PProbe%sRaw}{%s}" % (suffix, pmac(p)))
    # The flexibility family is the one place where correction changes the
    # verdict, so all three readings are supplied and the prose shows the move.
    probe_cells = {r["case"]: r for r in cells["CellsSigProbe"]}
    for name, suffix in (("C F=0.3", "FlexLo"), ("C F=1.0", "FlexHi")):
        r = probe_cells.get(name)
        if r is not None:
            print(r"\newcommand{\PProbe%sRaw}{%s}" % (suffix, pmac(r["p"])))
            print(r"\newcommand{\PProbe%sHolm}{%s}" % (suffix, pmac(r["p_holm"])))
            print(r"\newcommand{\PProbe%sBH}{%s}" % (suffix, pmac(r["p_bh"])))
    # The worst still-significant closed-loop cell.  Section 5.5 quotes it to
    # show that this family's verdict does not hinge on correcting or not.
    sig = [r["p_holm"] for r in cells["CellsSigLoop"] if r["p_holm"] < 0.05]
    if sig:
        print(r"\newcommand{\PLoopCellMax}{%s}" % pmac(max(sig)))
    print("=" * 74)

    # Per-cell correction audit.  Section 5.5 narrates per-cell signs, so the
    # gap between raw and adjusted significance is the number that licenses or
    # forbids each of those sentences; it is printed in full rather than
    # summarised into a count.
    for cname, title in (("CellsSigLoop", "闭环 B0->B1"),
                         ("CellsSigProbe", "闭环内试探 B1->B2")):
        print("\n逐格显著性(%s),族 = %d 格,Holm/BH 校正:"
              % (title, len(cases)))
        for r in cells[cname]:
            flag = ("显著" if r["p_holm"] < 0.05
                    else "校正后失去显著" if r["p"] < 0.05 else "不显著")
            print("  %-13s %+6.2f%%  p=%.4f  Holm=%.4f  BH=%.4f  %s"
                  % (r["case"], 100.0 * r["rel"], r["p"], r["p_holm"],
                     r["p_bh"], flag))
        raw = sum(1 for r in cells[cname] if r["p"] < 0.05)
        adj = sum(1 for r in cells[cname] if r["p_holm"] < 0.05)
        if raw != adj:
            print("  !! 校正后由 %d 格降为 %d 格:正文凡按格读符号处必须改写。"
                  % (raw, adj))

    print("\n合计口径的 HL 伪中位数与 95%% CI(逐对相对增益):")
    for r in pooled:
        print("  %-14s 均值 %+6.2f%%  HL %+6.2f%%  CI [%+6.2f%%, %+6.2f%%]  "
              "p=%.4f  Holm=%.4f  (%s)"
              % (r["g"], 100.0 * r["rel"], 100.0 * r["hl"], 100.0 * r["lo"],
                 100.0 * r["hi"], r["p"], r["p_holm"], r["ci_method"]))
        if (r["lo"] < 0) != (r["hi"] < 0):
            print("     !! 该对比的 95%% CI 跨零,而 p 值判显著:两者口径不一致,须核对。")

    # Section 5.5 reads a sign off individual cells, so the cells it names must
    # be checked for significance one by one and for monotonicity as a sweep.
    print("\nB 族(funnel 布局)完整车臂比扫描,B1->B2 逐格:")
    sweep = [(0.5, "B NA/NM 0.5"), (1.0, "B NA/NM 1.0"),
             (1.5, "A funnel"), (2.0, "B NA/NM 2.0")]
    signs = []
    for lvl, name in sweep:
        g, p = cell_gain(name, "B1", "B2"), cell_p(name, "B1", "B2")
        if g is None:
            continue
        signs.append(g > 0)
        print("  N_A/N_M=%.1f (%-13s): %+6.2f%%  p=%.4f%s"
              % (lvl, name, 100.0 * g, p, "" if p < 0.05 else "  [不显著]"))
    if len(set(signs)) > 1 and signs != sorted(signs):
        print("  !! 符号在车队维度上不单调:不得把它叙述为一个单调的适用上界。")
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

    legs, layout = tab_instances(cont, cases)
    tab_main(by, cont, cases, seeds)
    tab_bytag(by, cont, cases, seeds)
    tab_prune()
    macro_block(by, cont, cases, seeds, legs, layout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
