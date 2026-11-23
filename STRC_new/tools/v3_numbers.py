"""paper04_CN_v3 正文所需的全部数字,直接由 experiments/ 下的 CSV 计算。

paper_numbers 只打印各节摘要;本脚本补齐表格逐格数值、四分位距、合并统计等,
逐项标注对应的宏名或表格位置,改稿时照抄。

用法: py -m tools.v3_numbers
"""
from __future__ import annotations

import csv
import math
import os
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(os.path.dirname(HERE), "experiments")
ORDER = ["example_3x3x2", "congested_8x4x4", "S8x4x4_high", "S8x4x4_funnel", "S8x4x4_mid"]
LABEL = {"example_3x3x2": "小例", "congested_8x4x4": "拥堵例", "S8x4x4_funnel": "S11",
         "S8x4x4_high": "S21", "S8x4x4_mid": "S22"}
TAB_ORDER = ["example_3x3x2", "congested_8x4x4", "S8x4x4_funnel", "S8x4x4_high", "S8x4x4_mid"]


def read(*parts):
    p = os.path.join(EXP, *parts)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def T(v):
    return str(v).strip().lower() in ("true", "1", "yes")


def F(v):
    return None if v in (None, "", "None") else float(v)


def q(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def iqr(xs):
    return q(xs, 0.75) - q(xs, 0.25)


def group(rows, key="instance"):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g


def e1():
    rows = read("expanded", "e1_miss.csv")
    g = group(rows)
    print("== tab:e1 ==")
    meds = []
    for k in TAB_ORDER:
        rs = g[k]
        fr = [F(r["closure_frac"]) for r in rs]
        print("  %-6s %d/%d  |R| %.1f  |Src| %.1f (node %.1f)  |Cl| %.1f  Cl/|R| %.2f  IQR %.3f"
              % (LABEL[k], sum(T(r["pass_C1"]) for r in rs), len(rs),
                 st.mean(F(r["n_reservations"]) for r in rs), st.mean(F(r["n_seeds"]) for r in rs),
                 st.mean(F(r["n_node_seeds"]) for r in rs), st.mean(F(r["n_closure"]) for r in rs),
                 st.mean(fr), iqr(fr)))
        meds.append(st.mean(fr))
    allf = [F(r["closure_frac"]) for r in rows]
    iq = [iqr([F(r["closure_frac"]) for r in g[k]]) for k in ORDER]
    print("  EoneCloLo/Hi %.2f/%.2f  EoneFracIqrLo/Hi %.3f/%.3f  EoneFracMed %.3f  Min/Max %.3f/%.3f"
          % (min(meds), max(meds), min(iq), max(iq), st.median(allf), min(allf), max(allf)))
    ncl = [iqr([F(r["n_closure"]) for r in g[k]]) for k in ORDER]
    print("  |Cl| per-instance IQR %.1f--%.1f" % (min(ncl), max(ncl)))


def e2e3():
    e2 = read("expanded", "e2_containment.csv")
    print("== tab:e2 ==")
    for k in TAB_ORDER:
        rs = [r for r in e2 if r["instance"] == k]
        print("  %-6s E2a %d/%d  feas %d/%d  E2b %d/%d"
              % (LABEL[k], sum(T(r["pass_E2a"]) for r in rs), len(rs),
                 sum(T(r["feasible"]) for r in rs), len(rs), sum(T(r["pass_E2b"]) for r in rs), len(rs)))
    bad = [(r["instance"], r["seed"], r["outside_changes"]) for r in e2 if not T(r["pass_E2b"])]
    print("  E2b failures:", bad, " infeasible:", [(r["instance"], r["seed"]) for r in e2 if not T(r["feasible"])])
    e3 = read("expanded", "e3_boundary.csv")
    print("== tab:e3 ==")
    for k in TAB_ORDER:
        rs = [r for r in e3 if r["instance"] == k]
        print("  %-6s miss %d/%d  R1 %d/%d  R2 %d/%d  |U| %.1f  ms mean %.2f"
              % (LABEL[k], sum(T(r["miss_on_B"]) for r in rs), len(rs),
                 sum(T(r["R1_feasible"]) for r in rs), len(rs), sum(T(r["R2_feasible"]) for r in rs),
                 len(rs), st.mean(F(r["R2_release"]) for r in rs),
                 st.mean(F(r["R2_wall_ms"]) for r in rs)))
    ms = [F(r["R2_wall_ms"]) for r in e3]
    print("  MsRepairMed %.1f  MsRepairMax %.1f   R2 failures %s"
          % (st.median(ms), max(ms), [(r["instance"], r["seed"]) for r in e3 if not T(r["R2_feasible"])]))


def e5():
    print("== tab:e5 / E5 pooled ==")
    a = read("expanded", "e5_cross_curve.csv")
    b = read("pub_layouts", "e5_cross_curve.csv")
    for k in ("congested_8x4x4", "example_3x3x2"):
        for bud in ("0.2", "1.0", "2.0"):
            rs = [r for r in a if r["instance"] == k and float(r["budget_sec"]) == float(bud)]
            if rs:
                print("  %-6s %s  GR %.1f  STRC %.1f  res %.2f / %.2f"
                      % (LABEL[k], bud, st.mean(F(r["R0_makespan"]) for r in rs),
                         st.mean(F(r["R2_makespan"]) for r in rs),
                         st.mean(F(r["R0_res_frac"]) for r in rs), st.mean(F(r["R2_res_frac"]) for r in rs)))
    allr = a + b
    w = sum(F(r["R0_makespan"]) < F(r["R2_makespan"]) - 1e-9 for r in allr)
    t = sum(abs(F(r["R0_makespan"]) - F(r["R2_makespan"])) <= 1e-9 for r in allr)
    l = len(allr) - w - t
    cells = {(r["instance"], r["seed"]) for r in allr}
    mn = [r for r in allr if float(r["budget_sec"]) == 0.2]
    wm = sum(F(r["R0_makespan"]) < F(r["R2_makespan"]) - 1e-9 for r in mn)
    tm = sum(abs(F(r["R0_makespan"]) - F(r["R2_makespan"])) <= 1e-9 for r in mn)
    ties = [(r["instance"], r["seed"], r["budget_sec"]) for r in allr
            if abs(F(r["R0_makespan"]) - F(r["R2_makespan"])) <= 1e-9]
    print("  EfiveInst %d  EfiveCells %d  EfivePts %d  EfiveWLT %d/%d/%d  WinMin %d  TieMin %d  ties %s"
          % (len({r["instance"] for r in allr}), len(cells), len(allr), w, t, l, wm, tm, ties))
    print("  R0 past_changed max %s   pub R2 ms %.1f--%.1f  R0 ms %.0f--%.0f"
          % (max(int(float(r["R0_past_changed"] or 0)) for r in allr),
             min(F(r["R2_wall_ms"]) for r in b), max(F(r["R2_wall_ms"]) for r in b),
             min(F(r["R0_wall_ms"]) for r in b), max(F(r["R0_wall_ms"]) for r in b)))


def e6():
    rows = read("expanded", "e6_types.csv")
    print("== tab:e6 ==")
    for d in ("corridor_block", "corridor_slowdown", "agv_breakdown", "ra_failure"):
        rs = [r for r in rows if r["dist_type"] == d]
        print("  %-18s empty %d/%d  |U_AOR| %.1f  |Cl| %.1f  Cl/alive %.2f  feas %d/%d  feas_expand %d/%d  strict %d"
              % (d, sum(T(r["R1_empty"]) for r in rs), len(rs), st.mean(F(r["n_R1_release"]) for r in rs),
                 st.mean(F(r["n_closure"]) for r in rs), st.mean(F(r["closure_frac"]) for r in rs),
                 sum(T(r["R2_feasible"]) for r in rs), len(rs), sum(T(r["R2_feasible_expand"]) for r in rs),
                 len(rs), sum(T(r["R2_strictly_larger"]) for r in rs)))
    A = [r for r in rows if r["dist_class"] == "A"]
    print("  A covers %d/%d strictly %d" % (sum(T(r["R2_covers_R1"]) for r in A), len(A),
                                           sum(T(r["R2_strictly_larger"]) for r in A)))
    bl = {(r["instance"], r["seed"]): r for r in rows if r["dist_type"] == "corridor_block"}
    sl = {(r["instance"], r["seed"]): r for r in rows if r["dist_type"] == "corridor_slowdown"}
    same = sum(bl[k]["n_closure"] == sl[k]["n_closure"] for k in bl if k in sl)
    sub = sum(F(sl[k]["n_closure"]) <= F(bl[k]["n_closure"]) for k in bl if k in sl)
    print("  block vs slowdown same |Cl| %d/%d, slowdown<=block %d" % (same, len(bl), sub))
    fails = [(r["dist_type"], r["instance"], r["seed"]) for r in rows if not T(r["R2_feasible"])]
    print("  R2 first-level failures:", fails)


def phi():
    rows = read("expanded", "scale_compare.csv")
    print("== tab:scale (phi sweep) ==")
    for inst in ("congested_8x4x4", "example_3x3x2"):
        for p in sorted({float(r["phi"]) for r in rows}):
            rs = [r for r in rows if r["instance"] == inst and float(r["phi"]) == p]
            if not rs:
                continue
            esc = [int(float(r["strc_scope_rounds"] or 0)) for r in rs]
            print("  %-6s phi %.2f feas %d/%d  rounds %s  ms %.1f  STRC Cmax %.1f  GR Cmax %.1f  "
                  "IQR STRC %.0f GR %.0f  W/fut %.2f"
                  % (LABEL[inst], p, sum(T(r["strc_feasible"]) for r in rs), len(rs),
                     dict(sorted({e: esc.count(e) for e in esc}.items())),
                     st.mean(F(r["strc_wall_ms"]) for r in rs),
                     st.mean(F(r["strc_makespan"]) for r in rs if T(r["strc_feasible"])),
                     st.mean(F(r["r0_makespan"]) for r in rs if T(r["r0_feasible"])),
                     iqr([F(r["strc_makespan"]) for r in rs if T(r["strc_feasible"])]),
                     iqr([F(r["r0_makespan"]) for r in rs if T(r["r0_feasible"])]),
                     st.mean(F(r["n_W"]) / max(1, F(r["n_future_ops"])) for r in rs)))
        rs = [r for r in rows if r["instance"] == inst]
        print("  %-6s ms range %.1f--%.1f  ref Cmax mean %.1f  speedup %.0f--%.0f"
              % (LABEL[inst], min(F(r["strc_wall_ms"]) for r in rs), max(F(r["strc_wall_ms"]) for r in rs),
                 st.mean(F(r["ref_makespan"]) for r in rs), min(F(r["speedup"]) for r in rs),
                 max(F(r["speedup"]) for r in rs)))
    cg = [r for r in rows if r["instance"] == "congested_8x4x4"]
    by = defaultdict(list)
    for r in cg:
        by[float(r["phi"])].append(r)
    gi = [iqr([F(r["r0_makespan"]) for r in v]) for v in by.values()]
    si = [iqr([F(r["strc_makespan"]) for r in v]) for v in by.values()]
    print("  congested IQR GR %.0f--%.0f  STRC %.0f--%.0f" % (min(gi), max(gi), min(si), max(si)))


def instscale():
    rows = read("scale_curve.csv")
    print("== tab:instscale ==")
    ks = sorted({int(r["k"]) for r in rows})
    for k in ks:
        g = {a: [r for r in rows if int(r["k"]) == k and r["arm"] == a] for a in ("R2", "RS", "RD")}
        r2 = g["R2"]
        m2 = st.median(F(r["wall_ms"]) for r in r2)
        md = st.median(F(r["wall_ms"]) for r in g["RD"])
        idx = {(r["seed"], r["arm"]): r for r in rows if int(r["k"]) == k}
        w = t = l = 0
        ratios = []
        for r in r2:
            s = idx.get((r["seed"], "RS"))
            d = idx.get((r["seed"], "RD"))
            if d is not None:
                ratios.append(F(d["wall_ms"]) / F(r["wall_ms"]))
            if s is None or not (T(r["feasible"]) and T(s["feasible"])):
                continue
            x, y = F(r["makespan"]), F(s["makespan"])
            w, t, l = w + (x < y - 1e-9), t + (abs(x - y) <= 1e-9), l + (x > y + 1e-9)
        print("  %dx%dx%d |R| %.0f  Cl/|R| %.3f  Cl/|R°| %.3f  |R°|/|R| %.3f  R2 %.1f  RD %.1f  RD/R2 %.1f  "
              "pairRatio %.2f IQR %.2f  vsRS %d/%d/%d (RS feas %d)  first %d/%d final %d"
              % (2 * k, k, k, st.mean(F(r["n_res"]) for r in r2),
                 st.mean(F(r["closure_frac"]) for r in r2),
                 st.mean(F(r["closure"]) / F(r["n_live"]) for r in r2),
                 st.mean(F(r["n_live"]) / F(r["n_res"]) for r in r2), m2, md, md / m2,
                 st.mean(ratios), iqr(ratios), w, t, l, sum(T(r["feasible"]) for r in g["RS"]),
                 sum(1 for r in r2 if not r["esc_rounds"]), len(r2), sum(T(r["feasible"]) for r in r2)))
    r2 = [r for r in rows if r["arm"] == "R2"]
    print("  alive share mean %.3f" % st.mean(F(r["n_live"]) / F(r["n_res"]) for r in r2))
    for r in r2:
        if r["esc_rounds"]:
            print("  escalated: k=%s seed=%s rounds=%s esc_ms=%s feasible=%s Cmax=%s"
                  % (r["k"], r["seed"], r["esc_rounds"], r["esc_wall_ms"], r["feasible"], r["makespan"]))


def cheap():
    rows = read("cheap_baselines.csv")
    print("== tab:cheap (main, full block) ==")
    by = group(rows, "arm")
    for arm in ("RS", "RD", "RA", "R2"):
        rs = by[arm]
        ok = [r for r in rs if T(r["feasible"])]
        print("  %-3s feas %d/%d  past %d  ms med %.2f  deg %.1f%%  res %.3f"
              % (arm, len(ok), len(rs), sum(int(float(r["past_changed"] or 0)) > 0 for r in rs),
                 st.median(F(r["wall_ms"]) for r in rs),
                 100 * st.mean(F(r["makespan"]) / F(r["makespan_ref"]) - 1 for r in ok),
                 st.mean(F(r["res_frac"]) for r in ok)))
    idx = {(r["instance"], r["seed"], r["arm"]): r for r in rows}
    keys = sorted({(r["instance"], r["seed"]) for r in rows})
    both = [k for k in keys if T(idx[k + ("R2",)]["feasible"]) and T(idx[k + ("RD",)]["feasible"])]
    d = [F(idx[k + ("R2",)]["makespan"]) / F(idx[k + ("R2",)]["makespan_ref"])
         - F(idx[k + ("RD",)]["makespan"]) / F(idx[k + ("RD",)]["makespan_ref"]) for k in both]
    from tools.paper_numbers import _signrank_p
    print("  R2-RD degradation diff mean %+.4f  signrank p %.3f  n %d" % (st.mean(d), _signrank_p(d), len(d)))
    import random
    rnd = random.Random(20260816)
    boots = sorted(st.mean(rnd.choice(d) for _ in d) for _ in range(10000))
    print("  bootstrap 95%% CI [%+.4f, %+.4f]" % (boots[249], boots[9749]))
    fails = {a: [k for k in keys if not T(idx[k + (a,)]["feasible"])] for a in ("R2", "RS", "RD", "RA")}
    print("  infeasible:", fails)
    r2 = [r for r in by["R2"] if T(r["feasible"])]
    print("  W/alive(tasks) mean %.3f  Cl/|R°| mean %.3f min %.3f  n=1.00: %d"
          % (st.mean(F(r["n_W"]) / F(r["alive_tasks"]) for r in r2),
             st.mean(F(r["release_size"]) / F(r["alive_size"]) for r in r2),
             min(F(r["release_size"]) / F(r["alive_size"]) for r in r2),
             sum(F(r["release_size"]) >= F(r["alive_size"]) - 1e-9 for r in r2)))
    for name in ("cheap_baselines.csv", "cheap_baselines_L5.csv", "cheap_baselines_L2.csv"):
        rs = read(name)
        ix = {(r["instance"], r["seed"], r["arm"]): r for r in rs}
        ks = sorted({(r["instance"], r["seed"]) for r in rs})
        r2f = [k for k in ks if not T(ix[k + ("R2",)]["feasible"])]
        print("  %s R2 infeasible %s" % (name, r2f))


def tiers():
    print("== tier macros (main, full block, R2 feasible) ==")
    for name in ("cheap_baselines.csv", "cheap_baselines_L5.csv", "cheap_scale_L5.csv"):
        rows = [r for r in read(name) if r["arm"] == "R2" and T(r["feasible"])]
        sh = [F(r["n_replan"]) / F(r["n_W"]) for r in rows if F(r["n_replan"]) is not None and F(r["n_W"])]
        print("  %s replan/W mean %.2f [%.2f, %.2f]  route %.3f time %.3f untouched %.3f"
              % (name, st.mean(sh), min(sh), max(sh), st.mean(F(r["route_frac"]) for r in rows),
                 st.mean(F(r["time_frac"]) for r in rows),
                 1 - st.mean(F(r["route_frac"]) + F(r["time_frac"]) for r in rows)))


def pub():
    e1 = read("pub_layouts", "e1_miss.csv")
    g = group(e1)
    print("== pub ==")
    for k, rs in g.items():
        print("  %-12s Cl/|R| median %.3f" % (k, st.median(F(r["closure_frac"]) for r in rs)))
    e4 = read("pub_layouts", "e4_structure.csv")
    g4 = group(e4)
    for k, rs in g4.items():
        r0 = rs[0]
        print("  E4 %-18s m=%s nodes/corr %s/%s cut %s funnel %s Cl/|R| med %.3f"
              % (k, r0["num_machines"], r0["n_nodes"], r0["n_corridors"], r0["lu_min_cut"],
                 r0["funnel_share"], st.median(F(r["closure_frac"]) for r in rs)))


def misc():
    print("== misc ==")
    ep = read("edge_probe.csv")
    print("  edge probe leak pairs %d/%d  leaks %d  outside pairs %d"
          % (sum(int(r["n_delay_leaks"]) > 0 for r in ep), len(ep), sum(int(r["n_delay_leaks"]) for r in ep),
             sum(int(r["n_closed"]) < int(r["n_alive"]) for r in ep)))
    ws = read("weight_sweep.csv")
    for m in sorted({r["mode"] for r in ws}):
        rs = [r for r in ws if r["mode"] == m]
        print("  weight %-10s C1 %d/%d R1 %d R2 %d" % (m, sum(T(r["pass_C1"]) for r in rs), len(rs),
                                                     sum(T(r["R1_feasible"]) for r in rs),
                                                     sum(T(r["R2_feasible"]) for r in rs)))
    p = os.path.join(EXP, "_rerun_seg_completion.txt")
    if os.path.isfile(p):
        print("  seg_completion tail:")
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-8:]:
                print("   ", line.rstrip())


if __name__ == "__main__":
    e1()
    e2e3()
    e5()
    e6()
    phi()
    instscale()
    cheap()
    tiers()
    pub()
    misc()
