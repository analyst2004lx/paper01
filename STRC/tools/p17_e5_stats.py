# -*- coding: utf-8 -*-
"""为 paper04 的 P17(离散度口径)与 NEW-05(E5 交叉)算一次读数。

输出写文件,不走 stdout,避免 Windows 控制台编码问题。
"""
import csv
import io
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, os.pardir, "experiments")
OUT = os.path.join(EXP, "p17_e5_stats.txt")

buf = io.StringIO()


def w(s=""):
    buf.write(s + "\n")


def load(*parts):
    p = os.path.join(EXP, *parts)
    with open(p, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def quantile(sorted_vals, q):
    """线性插值分位数,口径与 numpy 默认一致。"""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def describe(vals):
    v = sorted(float(x) for x in vals)
    n = len(v)
    q1 = quantile(v, 0.25)
    q3 = quantile(v, 0.75)
    return {
        "n": n,
        "min": v[0],
        "max": v[-1],
        "mean": sum(v) / n,
        "median": quantile(v, 0.5),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def fmt(d, nd=3):
    f = "%%.%df" % nd
    return ("n=%d  min=" + f + "  Q1=" + f + "  med=" + f + "  Q3=" + f
            + "  max=" + f + "  IQR=" + f + "  mean=" + f) % (
        d["n"], d["min"], d["q1"], d["median"], d["q3"], d["max"],
        d["iqr"], d["mean"])


# ---------------------------------------------------------------- P17 (1)
# tab:e1 与 fig:e1e3 左幅:每算例 10 个随机种子的 Cl/|R|、|Cl|、|Seeds|、|R|
w("=" * 72)
w("P17-A  tab:e1 / fig:e1e3(左):逐算例 10 种子的离散度")
w("        源 expanded/e1_miss.csv")
w("=" * 72)
e1 = load("expanded", "e1_miss.csv")
by_inst = defaultdict(list)
for r in e1:
    by_inst[r["instance"]].append(r)

all_frac = []
w("")
for inst in by_inst:
    rows = by_inst[inst]
    frac = describe([r["closure_frac"] for r in rows])
    res = describe([r["n_reservations"] for r in rows])
    clo = describe([r["n_closure"] for r in rows])
    sds = describe([r["n_seeds"] for r in rows])
    all_frac.extend(float(r["closure_frac"]) for r in rows)
    w("  %-22s" % inst)
    w("     Cl/|R|   %s" % fmt(frac, 4))
    w("     |R|      %s" % fmt(res, 1))
    w("     |Cl|     %s" % fmt(clo, 1))
    w("     |Seeds|  %s" % fmt(sds, 1))
    w("")

w("  全部 %d 对合池 Cl/|R|: %s" % (len(all_frac), fmt(describe(all_frac), 4)))
w("")
w("  >>> 逐算例 IQR 的最大值 = %.4f" % max(
    describe([r["closure_frac"] for r in by_inst[i]])["iqr"] for i in by_inst))
w("  >>> 逐算例 IQR 的最小值 = %.4f" % min(
    describe([r["closure_frac"] for r in by_inst[i]])["iqr"] for i in by_inst))

# ---------------------------------------------------------------- P17 (2)
# fig:scale:congested_8x4x4 上按 phi 分档,逐档种子间离散度
w("")
w("=" * 72)
w("P17-B  fig:scale:phi 扫描逐档离散度   源 expanded/scale_compare.csv")
w("=" * 72)
try:
    sc = load("expanded", "scale_compare.csv")
except IOError:
    sc = []
if sc:
    w("  列名: %s" % ", ".join(sc[0].keys()))
    w("")
    cong = [r for r in sc if "congested" in r["instance"]]
    by_phi = defaultdict(list)
    for r in cong:
        by_phi[float(r["phi"])].append(r)
    for phi in sorted(by_phi):
        rows = by_phi[phi]
        w("  phi=%.2f  (n=%d)" % (phi, len(rows)))
        ok = sum(1 for r in rows if r["strc_feasible"] == "True")
        w("     strc_feasible  %d/%d 可行" % (ok, len(rows)))
        for col, nd in (("strc_wall_ms", 2), ("strc_makespan", 1),
                        ("r0_makespan", 1), ("r0_wall_ms", 1),
                        ("speedup", 1), ("n_closure", 1)):
            if col in rows[0] and all(r[col] != "" for r in rows):
                w("     %-14s %s" % (col, fmt(describe(
                    [r[col] for r in rows]), nd)))
        w("")

    w("  --- 跨档汇总(便于写图注) ---")
    for col, nd in (("strc_wall_ms", 1), ("r0_makespan", 1), ("speedup", 0)):
        lows, highs, iqrs = [], [], []
        for phi in sorted(by_phi):
            d = describe([r[col] for r in by_phi[phi]])
            lows.append(d["min"])
            highs.append(d["max"])
            iqrs.append(d["iqr"])
        f = "%%.%df" % nd
        w(("     %-14s 逐档 IQR 在 " + f + "--" + f
           + " 之间;全扫描极差 " + f + "--" + f) % (
            col, min(iqrs), max(iqrs), min(lows), max(highs)))

# ---------------------------------------------------------------- NEW-05
w("")
w("=" * 72)
w("NEW-05  E5 两批合并:单调性 + 逐格胜负")
w("        源 expanded/e5_cross_curve.csv(自建布局)")
w("            pub_layouts/e5_cross_curve.csv(外部布局)")
w("=" * 72)

batches = [("自建 expanded", ("expanded", "e5_cross_curve.csv")),
           ("外部 pub_layouts", ("pub_layouts", "e5_cross_curve.csv"))]

grand = {"cells": 0, "points": 0, "r0_win": 0, "tie": 0, "r2_win": 0,
         "mono_ok": 0, "mono_bad": 0, "r2_const_ok": 0, "r2_const_bad": 0,
         "win_at_min": 0, "tie_at_min": 0, "loss_at_min": 0}
insts = set()

for label, parts in batches:
    rows = load(*parts)
    w("")
    w("--- %s  (%d 行) ---" % (label, len(rows)))
    cells = defaultdict(list)
    for r in rows:
        cells[(r["instance"], r["seed"])].append(r)
    for key in sorted(cells):
        rs = sorted(cells[key], key=lambda x: float(x["budget_sec"]))
        insts.add(key[0])
        r0 = [float(x["R0_makespan"]) for x in rs]
        r2 = [float(x["R2_makespan"]) for x in rs]
        buds = [float(x["budget_sec"]) for x in rs]
        mono = all(r0[i + 1] <= r0[i] + 1e-9 for i in range(len(r0) - 1))
        r2const = max(r2) - min(r2) < 1e-9
        wins = sum(1 for a, b in zip(r0, r2) if a < b - 1e-9)
        ties = sum(1 for a, b in zip(r0, r2) if abs(a - b) <= 1e-9)
        loss = sum(1 for a, b in zip(r0, r2) if a > b + 1e-9)
        grand["cells"] += 1
        grand["points"] += len(rs)
        grand["r0_win"] += wins
        grand["tie"] += ties
        grand["r2_win"] += loss
        grand["mono_ok" if mono else "mono_bad"] += 1
        grand["r2_const_ok" if r2const else "r2_const_bad"] += 1
        if r0[0] < r2[0] - 1e-9:
            grand["win_at_min"] += 1
        elif abs(r0[0] - r2[0]) <= 1e-9:
            grand["tie_at_min"] += 1
        else:
            grand["loss_at_min"] += 1
        w("  %-16s seed=%-6s buds=%s" % (key[0], key[1],
                                         ",".join("%g" % b for b in buds)))
        w("      R0+ Cmax = %s   单调不增=%s" %
          (", ".join("%g" % x for x in r0), mono))
        w("      R2  Cmax = %s   随预算恒定=%s" %
          (", ".join("%g" % x for x in r2), r2const))
        w("      逐点 R0+胜/持平/负 = %d/%d/%d" % (wins, ties, loss))

w("")
w("=" * 72)
w("合并结论")
w("=" * 72)
w("  算例数              = %d  (%s)" % (len(insts), ", ".join(sorted(insts))))
w("  独立算例--种子格     = %d" % grand["cells"])
w("  预算点总数          = %d" % grand["points"])
w("  逐点 R0+ 胜/持平/负 = %d/%d/%d" %
  (grand["r0_win"], grand["tie"], grand["r2_win"]))
w("")
w("  R0+ Cmax 随预算单调不增: %d/%d 格成立" %
  (grand["mono_ok"], grand["cells"]))
w("  R2  Cmax 随预算恒定    : %d/%d 格成立" %
  (grand["r2_const_ok"], grand["cells"]))
w("  最小预算点上 R0+ 胜/持平/负: %d/%d/%d" %
  (grand["win_at_min"], grand["tie_at_min"], grand["loss_at_min"]))
w("")
w("  => 若 R2 随预算恒定且 R0+ 随预算单调不增,则在 R0+ 于最小预算已不劣的格上,")
w("     「预算放宽后 R2 反超」在预算维上不可能发生(非统计判断,是构造性判断)。")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(buf.getvalue())
print("written: " + OUT)
