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

Inputs (node-exclusive model, clbs_new/)
  clbs_new/output/baseline_ladder.csv   case,contention,arm,seed,makespan
  clbs_new/output/prune_ablation.csv    case,contention,arm,seed,makespan,decodes,ms_per_eval
  clbs_new/output/run_prune.log         equivalence check, read for routing-call cuts
  clbs_new/output/ladder_cost.csv       ms_per_eval per arm, read for the cost multiple
Outputs (LaTeX tabular fragments, no float wrapper -- the paper supplies that)
  tab_instances.tex  tab_main.tex  tab_bytag.tex  tab_prune.tex
The public-benchmark table (tab_external) is not regenerated here: it calibrates
the upper-level search on ideal travel times and does not depend on the node model.

Run from the repository root:  py -3 paper01_SCI/CAIE/tab/gen_tables_ladder.py [--apply]
--apply rewrites the values of the macros below in paper01_CN_v2.tex in place.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CLBS = os.path.join(ROOT, "clbs_new")
OUT = os.environ.get("LADDER_OUT", os.path.join(CLBS, "output"))
PAPER = os.environ.get("LADDER_PAPER", os.path.join(HERE, "..", "paper01_CN_v2.tex"))
sys.path.insert(0, CLBS)

from algorithm.stats import (benjamini_hochberg, hodges_lehmann_ci,  # noqa: E402
                             holm, wilcoxon_signed_rank)

# 代码与 CSV 沿用旧名,只在写进论文时换成新名(macro 名也保持旧名):
# The code and CSVs keep the old names; only what is written into the paper
# uses the new ones (macro names keep the old names too):
#   arm   B0 -> OL       open loop, rule dispatch (plan replayed)
#         B0宽松 -> OL-RD open loop, vehicles re-dispatched by rule at execution
#         B0+ -> TS      two-stage: frozen schedule, probe dispatch at execution
#         BL -> AE       AGV-encoded chromosome (Lyu 2019 / He 2019), dispatch="gene"
#         B1 -> CLBS-R   closed loop, rule dispatch (ablation only)
#         B2 -> CLBS     closed loop, probe dispatch (this paper)
#   layout funnel -> S11  spine, 1 exit lane at each store, 1 mid corridor
#          high -> S21    spine, 2 exit lanes, 1 mid corridor
#          mid -> S22     spine, 2 exit lanes, 2 mid corridors
#          low -> GC      grid, machines clustered far from the raw store
#          scatter -> GD  grid, machines dispersed by farthest-point sampling
# Comparison methods first, then the ablation-only arm, then this paper's arm.
ARMS = ["B0", "B0+", "BL", "B1", "B2"]
ARM_NAME = {"B0": "OL", "B0+": "TS", "BL": "AE", "B1": "CLBS-R", "B2": "CLBS"}
ARM_TEX = dict(ARM_NAME, B2=r"\textbf{CLBS}")
LAYOUT_NAME = {"funnel": "S11", "high": "S21", "mid": "S22",
               "low": "GC", "scatter": "GD"}
LAYOUT_ORDER = list(LAYOUT_NAME)


def case_tex(c: str) -> str:
    """Paper label of a case: 'A funnel' -> 'A S11', 'B NA/NM 0.5' -> 'B $N_A/N_M=0.5$'."""
    fam, _, rest = c.partition(" ")
    if rest.startswith("NA/NM "):
        rest = "$N_A/N_M=%s$" % rest.split()[1]
    elif rest.startswith("F="):
        rest = "$F=%s$" % rest[2:]
    return "%s %s" % (fam, LAYOUT_NAME.get(rest, rest))


def case_key(c: str):
    fam, _, rest = c.partition(" ")
    return (fam, LAYOUT_ORDER.index(rest) if rest in LAYOUT_ORDER else 99, c)


def arrow(a: str, b: str) -> str:
    return r"%s$\rightarrow$%s" % (ARM_NAME[a], ARM_NAME[b])


# Section 5.2 compares the whole method against each comparison method; the
# ablation rows hold one factor of the 2x2 fixed and move the other.  The six
# rows form one Holm family.
COMPARE = [
    ("B0", "B2", r"开环方法 OL $\rightarrow$ 本文"),
    ("B0+", "B2", r"两阶段方法 TS $\rightarrow$ 本文"),
    ("BL", "B2", r"三段式编码 AE $\rightarrow$ 本文"),
]
ABLATE = [
    ("B0", "B1", r"路径规划内嵌评价(规则派车下)"),
    ("B0", "B0+", r"派遣(开环下)"),
    ("B1", "B2", r"派遣(路径规划内嵌评价下)"),
]
CONTRASTS = COMPARE + ABLATE

FAMILY = {"A": "布局", "B": "AGV 配比", "C": "柔性"}
# Section 5.3 (sensitivity) reads CLBS against each comparison method per cell.
SCN = [("B0", "OL"), ("B0+", "TS"), ("BL", "AE")]


def read(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(
            "缺少 %s\n  先在 clbs/ 目录下运行对应的工具生成它。" % path)
    # utf-8-sig, 不是 utf-8:experiments_database 的 CSV 带 BOM,若不吃掉它,
    # 首列列名会变成 "\ufeffinstance" 而只在读第一列时才报错。
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def group(rows: List[dict], value: str = "makespan"):
    """(case, arm) -> list of values ordered by seed, plus the case/seed order."""
    by: Dict[str, Dict[str, Dict[int, float]]] = {}
    cont: Dict[str, float] = {}
    for r in rows:
        c, a, s = r["case"], r["arm"], int(r["seed"])
        by.setdefault(c, {}).setdefault(a, {})[s] = float(r[value])
        cont[c] = float(r["contention"])
    cases = sorted(by, key=case_key)
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


def write(name: str, body: str,
          src: str = "clbs/output/baseline_ladder.csv 等,见脚本首部") -> None:
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("%% 由 tab/gen_tables_ladder.py 生成,请勿手工编辑\n")
        f.write("%%%% 数据源:%s\n" % src)
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
             r"算例 & 变化的因子 & 节点 & 走廊 & $N_A$ & $F$ & 争用强度 "
             r"& 复合下界(时间单位) \\",
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
                     % (case_tex(c), FAMILY.get(fam_seen, ""),
                        len(inst.nodes), len(inst.corridors), inst.num_agvs,
                        flex, 100.0 * cont[c], lb))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_instances.tex", "\n".join(lines) + "\n")
    return legs, layout


def tab_main(by, cont, cases, seeds) -> None:
    """Main result: per-case means on top, the factorial contrasts below."""
    # Bold marks the paper's configuration in the *header* only.  Bolding the
    # B2 cells read as "best in row", and it is not: on two of the ten cells B1
    # is faster.  One convention across every table in the paper -- bold header
    # = this paper's arm, no bold on any value -- is what stops that misreading.
    lines = [r"\begin{tabular}{@{}lrrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{5}{c}{$C_{\max}$(时间单位)} \\",
             r"\cmidrule(lr){3-7}",
             r"算例 & 争用强度 & "
             + " & ".join(ARM_TEX[a] for a in ARMS) + r" \\",
             r"\midrule"]
    fam_seen = None
    for c in cases:
        if fam_seen is not None and c.split()[0] != fam_seen:
            lines.append(r"\midrule")
        fam_seen = c.split()[0]
        vals = " & ".join(
            "%.2f" % mean([by[c][a][s] for s in seeds
                           if s in by[c].get(a, {})])
            for a in ARMS)
        lines.append("%s & %.1f\\%% & %s \\\\" % (case_tex(c), 100.0 * cont[c], vals))

    lines.append(r"\midrule")
    allv = " & ".join(
        "%.2f" % mean([by[c][a][s] for c in cases for s in seeds
                       if s in by[c].get(a, {})]) for a in ARMS)
    lines.append(r"\emph{全体均值} & --- & %s \\" % allv)
    rows = [dict(label=label, **paired(by, cases, seeds, ka, kb))
            for ka, kb, label in CONTRASTS]
    for r, adj in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = adj

    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{0.6em}", "",
              r"\begin{tabular}{@{}lrlrr@{}}", r"\toprule",
              r"配对比较 & $\Delta C_{\max}$ & HL 伪中位数与 $95\%$ CI(\%) "
              r"& 胜/负/平 & $p_{\mathrm{Holm}}$ \\",
              r"\midrule",
              r"\multicolumn{5}{@{}l}{\emph{与对比方法比较}} \\"]
    for i, r in enumerate(rows):
        if i == len(COMPARE):
            lines += [r"\midrule",
                      r"\multicolumn{5}{@{}l}{\emph{消融(只改变一个维度)}} \\"]
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
    # Section 5.3 compares the method with the comparison methods per cell; the
    # per-cell ablation contrasts live in fig_prediction3 (Section 5.4).
    arms = [a for a, _ in SCN] + ["B2"]
    gain = {a: {r["case"]: r for r in per_cell(by, cases, seeds, a, "B2")}
            for a, _ in SCN}

    lines = [r"\begin{tabular}{@{}lrrrrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{4}{c}{$C_{\max}$(时间单位)} "
             r"& \multicolumn{3}{c}{本文相对对比方法的逐对相对差} \\",
             r"\cmidrule(lr){3-6}\cmidrule(lr){7-9}",
             r"算例 & 争用强度 & " + " & ".join(ARM_TEX[a] for a in arms)
             + " & " + " & ".join("%s$\\rightarrow$CLBS" % n for _, n in SCN)
             + r" \\",
             r"\midrule"]
    fam_seen = None
    for c in cases:
        if fam_seen is not None and c.split()[0] != fam_seen:
            lines.append(r"\midrule")
        fam_seen = c.split()[0]
        m = {a: mean([by[c][a][s] for s in seeds if s in by[c].get(a, {})])
             for a in arms}
        cells = " & ".join("$%+.1f\\%%%s$" % (100.0 * gain[a][c]["rel"],
                                             cell_stars(gain[a][c]))
                           for a, _ in SCN)
        lines.append("%s & %.1f\\%% & %s & %s \\\\"
                     % (case_tex(c), 100.0 * cont[c],
                        " & ".join("%.2f" % m[a] for a in arms), cells))
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

    # Both ratio columns are against the *off* arm, but in opposite directions:
    # more evaluations is better, fewer ms per evaluation is better.  Printing
    # the quotient in the header is the only way a reader can tell which way
    # round each one runs without going to the text.
    lines = [r"\begin{tabular}{@{}lrrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{2}{c}{$C_{\max}$(时间单位)} & "
             r"& 评价次数比 & 单次评价加速比 \\",
             r"\cmidrule(lr){3-4}",
             r"算例 & 争用强度 & 关 & \textbf{开} & $\Delta C_{\max}$ "
             r"& (开/关) & (关/开) \\",
             r"\midrule"]
    for c in cases:
        a = mean([by[c][on][s] for s in seeds if s in by[c].get(on, {})])
        b = mean([by[c][off][s] for s in seeds if s in by[c].get(off, {})])
        ea = mean([ev[c][on][s] for s in seeds if s in ev[c].get(on, {})])
        eb = mean([ev[c][off][s] for s in seeds if s in ev[c].get(off, {})])
        ma = mean([ms[c][on][s] for s in seeds if s in ms[c].get(on, {})])
        mb = mean([ms[c][off][s] for s in seeds if s in ms[c].get(off, {})])
        lines.append("%s & %.1f\\%% & %.2f & %.2f & $%+.2f\\%%$ & "
                     "%.2f$\\times$ & %.2f$\\times$ \\\\"
                     % (case_tex(c), 100.0 * cont[c], b, a, 100.0 * (a - b) / b,
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


# ---------------------------------------------------------------------------
# 公开基准对标。这批数据与阶梯批次无关(另一套算例、另一条工具链),放进本脚本只
# 因为它同样是一张手打必漂的表:七列二十行共一百四十个数,重跑之后没有人会逐个
# 重核。工序数是全表唯一不在 CSV 里的列,故从算例文件现数,不从旧表里抄。
REF_TEX = {"proven_optimal": r"\textsc{opt}", "best_known": r"\textsc{bk}"}


def pub_name(base: str) -> str:
    """sfjs01 -> SFJST01。正文一律用带 T 的写法,数据文件不带,此处只此一处转换。"""
    return base[:4].upper() + "T" + base[4:]


def n_ops(instance: str) -> int:
    with open(os.path.join(CLBS, "database", "json", "hf", instance + ".json"),
              encoding="utf-8") as f:
        return len(json.load(f)["proc_time"])


def num(x) -> str:
    """整数不带小数点,与文献报告参照值的写法一致。"""
    v = float(x)
    return "%d" % round(v) if abs(v - round(v)) < 1e-9 else "%.1f" % v


def median(xs) -> float:
    ys = sorted(xs)
    n = len(ys)
    if not n:
        return 0.0
    return ys[n // 2] if n % 2 else 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def external_rows() -> List[dict]:
    path = os.path.join(CLBS, "experiments_database", "gap_ideal.csv")
    if not os.path.exists(path):
        print("跳过 tab_external:%s 不存在" % os.path.relpath(path, ROOT))
        return []
    rows = read(path)
    # sfjs 在前、mfjs 在后,与正文"小算例全部命中、间隙随规模上升"的读法同序。
    rows.sort(key=lambda r: (r["base"][:4] != "sfjs", r["base"]))
    return rows


def tab_external(rows: List[dict]) -> None:
    if not rows:
        return
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"& & & \multicolumn{3}{c}{$C_{\max}$(时间单位)} & \\",
             r"\cmidrule(lr){4-6}",
             r"算例 & 工序 & 参照 & \multicolumn{1}{c}{值} & 最优 & 均值 & 间隙 \\",
             r"\midrule"]
    for r in rows:
        star = r"\rlap{$^*$}" if r["matches_ref"] == "True" else ""
        lines.append("%s & %d & %s & %s & %s%s & %.1f & %.2f\\%% \\\\"
                     % (pub_name(r["base"]), n_ops(r["instance"]),
                        REF_TEX[r["ref_kind"]], num(r["ref_value"]),
                        num(r["best"]), star, float(r["mean"]),
                        float(r["gap_best_pct"])))
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_external.tex", "\n".join(lines) + "\n",
          "clbs/experiments_database/gap_ideal.csv;工序数取自 "
          "clbs/database/json/hf/*.json")


def macro_external(rows: List[dict]) -> None:
    """公开基准那一小节的导言区宏,与上表同源。"""
    if not rows:
        return
    gap = [float(r["gap_best_pct"]) for r in rows]
    big = sorted(rows, key=lambda r: n_ops(r["instance"]))[-4:]
    opt = [r for r in rows if r["ref_kind"] == "proven_optimal"]
    print(r"\newcommand{\PubNInst}{%d}" % len(rows))
    print(r"\newcommand{\PubNOpt}{%d}" % len(opt))
    print(r"\newcommand{\PubNMatch}{%d}"
          % sum(1 for r in rows if r["matches_ref"] == "True"))
    print(r"\newcommand{\PubGapMean}{%.2f\%%}" % mean(gap))
    print(r"\newcommand{\PubGapMed}{%.2f\%%}" % median(gap))
    print(r"\newcommand{\PubGapMax}{%.2f\%%}" % max(gap))
    print(r"\newcommand{\PubGapBig}{%.2f\%%}"
          % mean([float(r["gap_best_pct"]) for r in big]))
    print(r"\newcommand{\PubGapMeanSeed}{%.2f\%%}"
          % mean([float(r["gap_mean_pct"]) for r in rows]))
    # 复合下界的松弛:分母用参照值,只在有可证最优值的算例上算,否则"距最优多远"
    # 无从谈起。第二个是同一批算例上下界距本方法最好解的中位。
    print(r"\newcommand{\PubLBSlack}{%.1f\%%}"
          % median([100.0 * (float(r["ref_value"]) - float(r["lower_bound"]))
                    / float(r["ref_value"]) for r in opt]))
    print(r"\newcommand{\PubLBTotal}{%.1f\%%}"
          % median([100.0 * (float(r["best"]) - float(r["lower_bound"]))
                    / float(r["best"]) for r in opt]))


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
             ("B0", "B2", "GainEndToEnd", "PEndToEnd"),
             ("BL", "B2", "GainLyu", "PLyu")]
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
        if r["rel"] > 0:
            print("%%%%!! %s 为正(%+.2f%%%%):后者更差,正文以「降低」引用该宏处须改写。"
                  % (r["g"], 100.0 * r["rel"]))
        if r["g"] == "GainEndToEnd":
            print(r"\newcommand{\WinEndToEnd}{%d}" % r["win"])
            print(r"\newcommand{\LoseEndToEnd}{%d}" % r["lose"])
        if r["g"] == "GainLyu":
            print(r"\newcommand{\WinLyu}{%d}" % r["win"])
            print(r"\newcommand{\LoseLyu}{%d}" % r["lose"])
    # Effect sizes for the two contrasts the prose quantifies in text.  A mean
    # relative gain has no precision attached; these do, and they come from the
    # same signed-rank null distribution as the p value beside them.
    for r in pooled:
        if r["g"] in ("GainLoopRule", "GainProbeLoop"):
            key = r["g"].replace("Gain", "")
            if r["hi"] < 0:
                print(r"\newcommand{\HL%s}{%.2f\%%}" % (key, abs(100.0 * r["hl"])))
                print(r"\newcommand{\CI%s}{$[%.2f\%%,\ %.2f\%%]$}"
                      % (key, abs(100.0 * r["hi"]), abs(100.0 * r["lo"])))
            else:
                # Interval reaches zero or above: print signed, as a change.
                print(r"\newcommand{\HL%s}{%+.2f\%%}" % (key, 100.0 * r["hl"]))
                print(r"\newcommand{\CI%s}{$[%+.2f\%%,\ %+.2f\%%]$}"
                      % (key, 100.0 * r["lo"], 100.0 * r["hi"]))
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
            print("%%%%!! 布局族 %s 段内各格的最远行程不同(%s):宏取最大值,"
                  "正文引用处须按此改写。" % (name, seg))
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
        print(r"\newcommand{\GainProbeStarve}{%+.1f\%%}" % (100.0 * starve_p))
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
    # Section 5.3: CLBS against each comparison method, cell by cell.  Counts
    # are Holm-adjusted within the ten cells of one contrast; ranges are per
    # family and include the shared base cell in B and C.
    for a, n in SCN:
        rs = per_cell(by, cases, seeds, a, "B2")
        print(r"\newcommand{\Scn%sSig}{%d}"
              % (n, sum(1 for r in rs if r["p_holm"] < 0.05 and r["rel"] < 0)))
        print(r"\newcommand{\Scn%sSigRaw}{%d}"
              % (n, sum(1 for r in rs if r["p"] < 0.05 and r["rel"] < 0)))
        print(r"\newcommand{\Scn%sWorse}{%d}"
              % (n, sum(1 for r in rs if r["rel"] > 0)))
        for fam in "ABC":
            g = [100.0 * r["rel"] for r in rs
                 if r["case"].split()[0] == fam
                 or (fam != "A" and r["case"] == "A funnel")]
            if g:
                print(r"\newcommand{\Scn%sRange%s}{$%+.1f\%%$ 至 $%+.1f\%%$}"
                      % (n, fam, min(g), max(g)))
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

    buf = io.StringIO()
    with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
        macro_block(by, cont, cases, seeds, legs, layout)
        macro_prune()
    if "--apply" in sys.argv:
        apply_macros(buf.getvalue())
    return 0


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)


def macro_prune() -> None:
    """Macros of the cost subsection: speedup ablation and the cost multiple."""
    path = os.path.join(OUT, "prune_ablation.csv")
    if not os.path.exists(path):
        print("%% 跳过降本宏:prune_ablation.csv 尚未生成")
        return
    rows = read(path)
    by, _cont, cases, seeds = group(rows)
    ev, _, _, _ = group(rows, "decodes")
    ms, _, _, _ = group(rows, "ms_per_eval")
    on, off = "开", "关"
    r = paired(by, cases, seeds, off, on)
    print(r"\newcommand{\GainPrune}{%.2f\%%}" % abs(100.0 * r["rel"]))
    print(r"\newcommand{\PPrune}{%s}" % pmac(r["p"]))
    print(r"\newcommand{\WinPrune}{%d}" % r["win"])
    print(r"\newcommand{\LosePrune}{%d}" % r["lose"])
    tot = lambda d, a: sum(d[c][a][s] for c in cases for s in seeds)  # noqa: E731
    print(r"\newcommand{\EvalRatioPrune}{%.2f}" % (tot(ev, on) / tot(ev, off)))
    speed = tot(ms, off) / tot(ms, on)
    print(r"\newcommand{\SpeedupProbe}{%.2f}" % speed)

    log = os.path.join(OUT, "run_prune.log")
    if os.path.exists(log):
        cut = {}
        pat = re.compile(r"^(.+?)\s+\d+\s+\d+/\d+ .*?(\d+)/(\d+)\s+[\d.]+%\s*$")
        with open(log, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                m = pat.match(line.strip())
                if m and m.group(1).strip() in cases:
                    cut[m.group(1).strip()] = (int(m.group(2)), int(m.group(3)))
        if cut:
            a = sum(v[0] for v in cut.values())
            b = sum(v[1] for v in cut.values())
            per = {c: 1.0 - v[0] / v[1] for c, v in cut.items()}
            lo, hi = min(per, key=per.get), max(per, key=per.get)
            print(r"\newcommand{\RouteCallCut}{%.1f\%%}" % (100.0 * (1 - a / b)))
            print(r"\newcommand{\RouteCallCutLo}{%.1f\%%}" % (100.0 * per[lo]))
            print(r"\newcommand{\RouteCallCutHi}{%.1f\%%}" % (100.0 * per[hi]))
            print("%%%% 路由调用削减:最低 %s,最高 %s" % (lo, hi))

    cost = os.path.join(OUT, "ladder_cost.csv")
    if os.path.exists(cost):
        crow = read(cost)
        msb = {}
        for x in crow:
            msb.setdefault(x["arm"], []).append(float(x["ms_per_eval"]))
        if "B1" in msb and "B2" in msb:
            after = mean(msb["B2"]) / mean(msb["B1"])
            print(r"\newcommand{\CostMultAfter}{%.2f}" % after)
            print(r"\newcommand{\CostMultBefore}{%.1f}" % (after * speed))


def apply_macros(text: str) -> None:
    """Rewrite the bodies of the printed macros in the paper, brace-balanced."""
    vals = {}
    for line in text.splitlines():
        m = re.match(r"^\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", line)
        if m:
            vals[m.group(1)] = m.group(2)
    with open(PAPER, encoding="utf-8", newline="") as f:
        tex = f.read()
    missing = []
    for name, val in vals.items():
        head = "\\newcommand{\\%s}{" % name
        i = tex.find(head)
        if i < 0:
            missing.append(name)
            continue
        j = k = i + len(head)
        depth = 1
        while depth:
            depth += {"{": 1, "}": -1}.get(tex[k], 0)
            k += 1
        tex = tex[:j] + val + tex[k - 1:]
    with open(PAPER, "w", encoding="utf-8", newline="") as f:
        f.write(tex)
    print("\n已写回 %d 个宏到 %s" % (len(vals) - len(missing),
                                  os.path.relpath(PAPER, ROOT)))
    if missing:
        print("!! 论文中找不到这些宏(未写入):%s" % ", ".join(missing))


if __name__ == "__main__":
    raise SystemExit(main())
