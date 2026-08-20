"""把 experiments/expanded/*.csv 汇成 paper04 正文要引的那几个数。

存在的理由与 paper01 的 tools/eval_cost.py 相同:正文里每一个百分数都要能指回
一行 CSV。扩样到 5x10 之后旧稿的 15 对读数全部作废,靠手抄极易漏改,故集中在此。

用法(在 STRC/ 下): py -m tools.paper_numbers
"""
from __future__ import annotations

import csv
import math
import os
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(os.path.dirname(HERE), "experiments", "expanded")
PUB = os.path.join(os.path.dirname(HERE), "experiments", "pub_layouts")

ORDER = ["example_3x3x2", "congested_8x4x4", "S8x4x4_high",
         "S8x4x4_funnel", "S8x4x4_mid"]

PUB_ORDER = ["LyuL2_4m", "LyuL3_5m", "LyuL4_6m", "LyuL5_7m", "LyuL6_8m"]
PUB_CONTROL = ["self_high_LD21", "self_funnel_LD11", "self_mid_LD22"]


def read(name):
    with open(os.path.join(EXP, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_pub(name):
    with open(os.path.join(PUB, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def istrue(v):
    return str(v).strip().lower() == "true"


def by_inst(rows):
    out = defaultdict(list)
    for r in rows:
        out[r["instance"]].append(r)
    return out


def main() -> int:
    e1, e2, e3 = read("e1_miss.csv"), read("e2_containment.csv"), read("e3_boundary.csv")
    e5, e6 = read("e5_cross_curve.csv"), read("e6_types.csv")
    scale = read("scale_compare.csv")

    print("== E1 (n=%d) ==" % len(e1))
    print("C1 pass %d/%d" % (sum(1 for r in e1 if istrue(r["pass_C1"])), len(e1)))
    for k in ORDER:
        rs = by_inst(e1)[k]
        if not rs:
            continue
        print("  %-16s n=%2d  |Seeds|=%5.1f  |Cl|=%5.1f  Cl/|R|=%.3f  |R|=%5.1f"
              % (k, len(rs),
                 st.mean(float(r["n_seeds"]) for r in rs),
                 st.mean(float(r["n_closure"]) for r in rs),
                 st.mean(float(r["closure_frac"]) for r in rs),
                 st.mean(float(r["n_reservations"]) for r in rs)))

    print("\n== E2 (n=%d) ==" % len(e2))
    print("E2a %d/%d   feasible %d/%d   E2b %d/%d"
          % (sum(1 for r in e2 if istrue(r["pass_E2a"])), len(e2),
             sum(1 for r in e2 if istrue(r["feasible"])), len(e2),
             sum(1 for r in e2 if istrue(r["pass_E2b"])), len(e2)))
    for k in ORDER:
        rs = by_inst(e2)[k]
        if not rs:
            continue
        print("  %-16s E2b %d/%d" % (
            k, sum(1 for r in rs if istrue(r["pass_E2b"])), len(rs)))
    drift = [int(r["outside_changes"]) for r in e2
             if istrue(r["feasible"]) and int(r["outside_changes"]) > 0]
    if drift:
        print("  drift when nonzero: n=%d  min=%d  median=%.1f  max=%d  mean=%.1f"
              % (len(drift), min(drift), st.median(drift), max(drift), st.mean(drift)))

    print("\n== E3 (n=%d) ==" % len(e3))
    print("miss_B %d/%d   R1 feasible %d/%d   R2 feasible %d/%d"
          % (sum(1 for r in e3 if istrue(r["miss_on_B"])), len(e3),
             sum(1 for r in e3 if istrue(r["R1_feasible"])), len(e3),
             sum(1 for r in e3 if istrue(r["R2_feasible"])), len(e3)))
    r2ms = [float(r["R2_wall_ms"]) for r in e3]
    print("R2 wall ms: median=%.2f  mean=%.2f  max=%.2f"
          % (st.median(r2ms), st.mean(r2ms), max(r2ms)))
    for k in ORDER:
        rs = by_inst(e3)[k]
        if not rs:
            continue
        print("  %-16s R2 ms mean=%5.2f  |R2 release|=%5.1f"
              % (k, st.mean(float(r["R2_wall_ms"]) for r in rs),
                 st.mean(float(r["R2_release"]) for r in rs)))

    print("\n== E5 ==")
    for k in ("congested_8x4x4", "example_3x3x2"):
        for bud in ("0.2", "1.0", "2.0"):
            rs = [r for r in e5 if r["instance"] == k and r["budget_sec"] == bud]
            if not rs:
                continue
            print("  %-16s bud=%-3s  R0 Cmax=%6.1f  R2 Cmax=%6.1f  "
                  "R0 resfrac=%.3f  R2 resfrac=%.3f"
                  % (k, bud,
                     st.mean(float(r["R0_makespan"]) for r in rs),
                     st.mean(float(r["R2_makespan"]) for r in rs),
                     st.mean(float(r["R0_res_frac"]) for r in rs if r["R0_res_frac"]),
                     st.mean(float(r["R2_res_frac"]) for r in rs if r["R2_res_frac"])))
    worse = [r for r in e5 if float(r["R2_makespan"]) > float(r["R0_makespan"])]
    print("  R2 worse than R0+ in %d/%d budget points (no crossing)"
          % (len(worse), len(e5)))

    print("\n== scale ==")
    sp = [float(r["speedup"]) for r in scale if r["speedup"]]
    print("  speedup min=%.0f max=%.0f" % (min(sp), max(sp)))
    for k in ("example_3x3x2", "congested_8x4x4"):
        rs = [r for r in scale if r["instance"] == k]
        s = [float(r["speedup"]) for r in rs if r["speedup"]]
        ms = [float(r["strc_wall_ms"]) for r in rs]
        print("  %-16s feas %d/%d  ms %.1f-%.1f  speedup %.0f-%.0f"
              % (k, sum(1 for r in rs if istrue(r["strc_feasible"])), len(rs),
                 min(ms), max(ms), min(s), max(s)))

    print("\n== E6 ==")
    for t in ("corridor_block", "corridor_slowdown", "agv_breakdown", "ra_failure"):
        rs = [r for r in e6 if r["dist_type"] == t]
        if not rs:
            continue
        print("  %-18s class=%s n=%d  R1 empty %d/%d  T_imp=%5.1f  |R1|=%5.1f  "
              "|Cl|=%5.1f  Cl/alive=%.3f  R2>=R1 %d/%d"
              % (t, rs[0]["dist_class"], len(rs),
                 sum(1 for r in rs if istrue(r["R1_empty"])), len(rs),
                 st.mean(float(r["n_T_impact"]) for r in rs),
                 st.mean(float(r["n_R1_release"]) for r in rs),
                 st.mean(float(r["n_closure"]) for r in rs),
                 st.mean(float(r["closure_frac"]) for r in rs),
                 sum(1 for r in rs if istrue(r["R2_covers_R1"])), len(rs)))
    ident = sum(1 for a, b in zip(
        [r for r in e6 if r["dist_type"] == "corridor_block"],
        [r for r in e6 if r["dist_type"] == "corridor_slowdown"])
        if a["n_closure"] == b["n_closure"])
    print("  block vs slowdown identical closure on %d/50 pairs "
          "(same seeding rule -> not an independent observation)" % ident)

    pub_section()
    cheap_section()
    return 0


def _read_exp(name):
    path = os.path.join(os.path.dirname(HERE), "experiments", name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _wtl(rows, other):
    """R2 对 other 臂的 Cmax 赢/平/输。只数两臂都可行的格。"""
    idx = {(r["instance"], r["seed"], r["arm"]): r for r in rows}
    keys = sorted({(r["instance"], r["seed"]) for r in rows})
    w = t = l = 0
    for k in keys:
        a, b = idx.get((k[0], k[1], "R2")), idx.get((k[0], k[1], other))
        if a is None or b is None or not (istrue(a["feasible"]) and istrue(b["feasible"])):
            continue
        x, y = float(a["makespan"]), float(b["makespan"])
        if x < y - 1e-9:
            w += 1
        elif x > y + 1e-9:
            l += 1
        else:
            t += 1
    return w, t, l


def _signrank_p(diffs) -> float:
    """Wilcoxon 符号秩检验的正态近似双侧 p(含并列秩平均)。

    样本量 33 量级,正态近似够用;这里不引 scipy 是为了让 STRC 保持零外部依赖。
    """
    nz = sorted((d for d in diffs if abs(d) > 1e-9), key=abs)
    n = len(nz)
    if n < 6:
        return float("nan")
    ranks, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and abs(abs(nz[j + 1]) - abs(nz[i])) < 1e-12:
            j += 1
        for t in range(i, j + 1):
            ranks[t] = (i + j + 2) / 2
        i = j + 1
    w = sum(ranks[t] for t in range(n) if nz[t] < 0)
    mu, sd = n * (n + 1) / 4, math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    return math.erfc(abs((w - mu) / sd) / math.sqrt(2))


def _closure_vs_all_future(cheap, idx) -> None:
    """R2 对 RA:同引擎、同冻结判据,只差释放集取闭包还是取平凡上界。

    这是「画这条边界还剩多少用」的直接读数。闭包该兑现的是稳定性(命题
    prop:outside 讲的正是外侧字段不变),不是 Cmax,也不是耗时——后两项两臂本该
    几乎相同,若不同反而说明实现有别。
    """
    d_rf, d_ms, share = [], [], []
    for k in sorted({(r["instance"], r["seed"]) for r in cheap}):
        a, b = idx.get((k[0], k[1], "R2")), idx.get((k[0], k[1], "RA"))
        if a is None or b is None:
            continue
        if not (istrue(a["feasible"]) and istrue(b["feasible"])):
            continue
        d_rf.append(float(a["res_frac"]) - float(b["res_frac"]))
        d_ms.append(float(a["makespan"]) / float(b["makespan"]))
        share.append(float(a["release_size"]) / float(b["release_size"]))
    if not d_rf:
        return
    better = sum(1 for x in d_rf if x < -1e-9)
    worse = sum(1 for x in d_rf if x > 1e-9)
    print("  R2 vs RA (closure vs no boundary, same engine):")
    print("    res_frac diff mean %+.3f median %+.3f; better/tie/worse %d/%d/%d; "
          "signrank p=%.2g"
          % (st.mean(d_rf), st.median(d_rf), better,
             len(d_rf) - better - worse, worse, _signrank_p(d_rf)))
    print("    Cmax ratio mean %.4f [%.4f, %.4f]"
          % (st.mean(d_ms), min(d_ms), max(d_ms)))
    print("    release ratio mean %.3f [%.3f, %.3f]"
          % (st.mean(share), min(share), max(share)))


def cheap_section() -> None:
    """便宜对照臂(E7)与算例规模扫描(E8)。

    两批都不并入上面的 50 对读数:E7 与 E1--E3 同协议但多了两条臂,E8 换的是算例规模。
    这里同时打出 RD 的 A2 越界格数——RD 的 Cmax 不带这个数一起读就是误导。
    """
    cheap = _read_exp("cheap_baselines.csv")
    if cheap is None:
        print("\n== cheap baselines ==\n  (缺 experiments/cheap_baselines.csv,"
              "先跑 py -m tools.cheap_baselines)")
    else:
        print("\n== cheap baselines: E7 (n=%d rows) ==" % len(cheap))
        for arm in ("RS", "RD", "RA", "R2"):
            rs = [r for r in cheap if r["arm"] == arm]
            deg = st.mean(float(r["makespan"]) / float(r["makespan_ref"]) - 1 for r in rs)
            share = [float(r["release_size"]) / float(r["alive_size"]) for r in rs
                     if r.get("release_size")]
            print("  %-3s feas %d/%d  A2 bad %d/%d  ms med %.2f  deg %.1f%%  "
                  "res_frac %.3f  rel/alive %s"
                  % (arm, sum(1 for r in rs if istrue(r["feasible"])), len(rs),
                     sum(1 for r in rs if int(r["past_changed"]) > 0), len(rs),
                     st.median(float(r["wall_ms"]) for r in rs), deg * 100,
                     st.mean(float(r["res_frac"]) for r in rs),
                     ("%.3f [%.3f, %.3f]" % (st.mean(share), min(share), max(share)))
                     if share else "--"))
        for other in ("RS", "RD", "RA"):
            print("  R2 vs %s  win/tie/loss %d/%d/%d" % ((other,) + _wtl(cheap, other)))
        # RD 越界与否分层:未越界的格才是「受 A2 约束时差距有多大」的上界估计
        idx = {(r["instance"], r["seed"], r["arm"]): r for r in cheap}
        w = t = l = 0
        for k in sorted({(r["instance"], r["seed"]) for r in cheap}):
            rd, r2 = idx[(k[0], k[1], "RD")], idx[(k[0], k[1], "R2")]
            if int(rd["past_changed"]) > 0:
                continue
            x, y = float(r2["makespan"]), float(rd["makespan"])
            w, t, l = (w + (x < y - 1e-9), t + (abs(x - y) <= 1e-9), l + (x > y + 1e-9))
        print("  R2 vs RD on A2-clean cells only (n=%d): %d/%d/%d" % (w + t + l, w, t, l))
        _closure_vs_all_future(cheap, idx)

    sc = _read_exp("scale_curve.csv")
    if sc is None:
        print("\n== scale curve ==\n  (缺 experiments/scale_curve.csv,"
              "先跑 py -m tools.scale_curve)")
        return
    print("\n== scale curve: E8 (n=%d rows) ==" % len(sc))
    for k in sorted({int(r["k"]) for r in sc}):
        g = {a: [r for r in sc if int(r["k"]) == k and r["arm"] == a]
             for a in ("R2", "RS", "RD")}
        r2 = g["R2"]
        m = {a: st.median(float(r["wall_ms"]) for r in g[a]) for a in g}
        print("  %2dx%dx%-3d |R|=%3.0f  Cl/|R|=%.3f  R2 %5.2f ms  RD %6.2f ms  "
              "RD/R2 %.2f  first-level feas %d/%d  vs RS %d/%d/%d"
              % (2 * k, k, k,
                 st.mean(float(r["n_res"]) for r in r2),
                 st.mean(int(r["closure"]) / int(r["n_res"]) for r in r2),
                 m["R2"], m["RD"], m["RD"] / m["R2"],
                 sum(1 for r in r2 if not r["esc_rounds"]), len(r2),
                 *_wtl([r for r in sc if int(r["k"]) == k], "RS")))
    r2all = [r for r in sc if r["arm"] == "R2"]
    print("  overall: first-level feas %d/%d, final feas %d/%d, "
          "Cl/|R| %.3f--%.3f, R2 ms %.2f--%.2f"
          % (sum(1 for r in r2all if not r["esc_rounds"]), len(r2all),
             sum(1 for r in r2all if istrue(r["feasible"])), len(r2all),
             min(int(r["closure"]) / int(r["n_res"]) for r in r2all),
             max(int(r["closure"]) / int(r["n_res"]) for r in r2all),
             min(float(r["wall_ms"]) for r in r2all),
             max(float(r["wall_ms"]) for r in r2all)))


def pub_section() -> None:
    """外部来源布局批次(experiments/pub_layouts/)。

    这一批是独立账本,不并入上面的 50 对。它回答的是"闭包规模的结构可预测性那条负
    结果,到底出自结构指标还是出自算例集"——两组算例逐参数同口径,只差布局来源。
    """
    if not os.path.isdir(PUB):
        print("\n== pub layouts ==\n  (无 experiments/pub_layouts/,"
              "先在 STRC/ 下跑 py -m tools.pub_batch)")
        return
    e1, e2 = read_pub("e1_miss.csv"), read_pub("e2_containment.csv")
    e3, e4 = read_pub("e3_boundary.csv"), read_pub("e4_structure.csv")
    e5 = read_pub("e5_cross_curve.csv")

    print("\n== pub layouts: E1/E2/E3 (n=%d) ==" % len(e1))
    print("  C1 pass %d/%d   E2a %d/%d   E2b %d/%d   R1 feas %d/%d   R2 feas %d/%d"
          % (sum(1 for r in e1 if istrue(r["pass_C1"])), len(e1),
             sum(1 for r in e2 if istrue(r["pass_E2a"])), len(e2),
             sum(1 for r in e2 if istrue(r["pass_E2b"])), len(e2),
             sum(1 for r in e3 if istrue(r["R1_feasible"])), len(e3),
             sum(1 for r in e3 if istrue(r["R2_feasible"])), len(e3)))
    print("  structural leaks total %d"
          % sum(int(r["structural_leaks"]) for r in e1))
    fr = [st.median([float(r["closure_frac"]) for r in by_inst(e1)[k]])
          for k in PUB_ORDER if by_inst(e1)[k]]
    print("  E1 Cl/|R| per-layout medians %.3f--%.3f" % (min(fr), max(fr)))

    print("\n== pub layouts: E4 structure (matched parameters) ==")
    g4 = by_inst(e4)
    for label, order in (("external", PUB_ORDER), ("self-built", PUB_CONTROL)):
        names = [k for k in order if g4[k]]
        if not names:
            continue
        med = [st.median([float(r["closure_frac"]) for r in g4[k]]) for k in names]
        cuts = sorted({int(g4[k][0]["lu_min_cut"]) for k in names})
        fun = sorted({float(g4[k][0]["funnel_share"]) for k in names})
        cpn = sorted({float(g4[k][0]["corridors_per_node"]) for k in names})
        print("  %-11s n_layouts=%d  Cl/|R| medians %.3f--%.3f  spread %.3f"
              % (label, len(names), min(med), max(med), max(med) - min(med)))
        print("              lu_min_cut set %s  funnel_share set %s  "
              "corridors_per_node set %s" % (cuts, fun, cpn))
        for k, m in zip(names, med):
            print("                %-18s %.3f" % (k, m))

    print("\n== pub layouts: E5 ==")
    worse = [r for r in e5 if float(r["R2_makespan"]) > float(r["R0_makespan"])]
    print("  R2 worse than R0+ in %d/%d budget points (no crossing)"
          % (len(worse), len(e5)))
    ms2 = [float(r["R2_wall_ms"]) for r in e5]
    ms0 = [float(r["R0_wall_ms"]) for r in e5]
    print("  R2 wall ms %.1f--%.1f   R0+ wall ms %.0f--%.0f"
          % (min(ms2), max(ms2), min(ms0), max(ms0)))


if __name__ == "__main__":
    raise SystemExit(main())
