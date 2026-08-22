"""按「是否满足假设 A2」把 E5 的预算点分层,再看完工时间谁赢。

动机:E5 原先只按 Cmax 比较 R0+ 与 R2,而 R0+ 是从 t=0 重新解码的,并不受
「已完成占用不回溯修改」的约束。把它改写了多少条 t_now 之前已执行完的预约
(e5_cross_curve 的 R0_past_changed 列)拿出来分层之后,才能分清它的优势有多少
来自更好的协调、多少来自越界重排历史。

用法:
    py -m tools.e5_admissible experiments/e5_repro_ga_cong.csv ...
"""
from __future__ import annotations

import csv
import sys
from collections import Counter


def _num(x):
    if x is None or x == "" or x == "None":
        return None
    return float(x)


def load(paths):
    rows = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["_src"] = p
                rows.append(row)
    return rows


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    rows = load(argv[1:])
    print(f"总行数 {len(rows)}")

    by_mode = Counter(r["baseline_mode"] for r in rows)
    print(f"基线模式分布 {dict(by_mode)}\n")

    # ---- 1. R0+ 的挂钟下限:预算守不住的那些点上它实际花了多久 ----
    print("== R0+ 挂钟下限(按算例) ==")
    insts = sorted({r["instance"] for r in rows})
    for inst in insts:
        sub = [r for r in rows if r["instance"] == inst]
        unhon = [r for r in sub if r["budget_honored"] == "False"]
        if not unhon:
            continue
        walls = [_num(r["R0_wall_ms"]) for r in unhon]
        r2walls = [_num(r["R2_wall_ms"]) for r in sub]
        gens = {r["R0_gens"] for r in unhon}
        print(f"  {inst}: 预算未守住 {len(unhon)}/{len(sub)} 个点; "
              f"R0+ 实际 {min(walls):.0f}-{max(walls):.0f}ms (代数 {sorted(gens)}); "
              f"R2 {min(r2walls):.2f}-{max(r2walls):.2f}ms; "
              f"下限比 {min(walls)/max(r2walls):.0f}x-{max(walls)/min(r2walls):.0f}x")
    print()

    # ---- 2. 按 A2 可采纳性分层,看 Cmax 谁赢 ----
    print("== 按 A2 可采纳性分层的完工时间胜负 ==")
    adm, viol = [], []
    for r in rows:
        pc = _num(r["R0_past_changed"])
        if pc is None:
            continue
        (adm if pc == 0 else viol).append(r)

    for label, grp in (("R0+ 未改写历史(A2 可采纳)", adm),
                       ("R0+ 改写了历史(A2 不可采纳)", viol)):
        if not grp:
            print(f"  {label}: 0 个点")
            continue
        w = Counter(r["makespan_winner"] for r in grp)
        print(f"  {label}: {len(grp)} 个点 -> {dict(w)}")
    print()

    # ---- 3. R2 自身的 A2 合规性 ----
    print("== R2 的 A2 合规性 ==")
    for mode in sorted(by_mode):
        sub = [r for r in rows if r["baseline_mode"] == mode]
        bad = [r for r in sub if (_num(r["R2_past_changed"]) or 0) > 0]
        tot = {(r["instance"], r["seed"]) for r in sub}
        badk = {(r["instance"], r["seed"]) for r in bad}
        print(f"  baseline={mode}: {len(badk)}/{len(tot)} 个算例-种子上 R2 改写了历史")
        for inst, seed in sorted(badk):
            one = next(r for r in bad if r["instance"] == inst and r["seed"] == seed)
            print(f"      {inst} seed={seed}: "
                  f"{one['R2_past_changed']}/{one['R2_past_total']}")
    print()

    # ---- 4. 逐算例-种子的 Cmax 对比(取 R0+ 在可采纳点上的最好值) ----
    print("== 每个算例-种子:R2 vs R0+ 在可采纳点上的最好 Cmax ==")
    # 键必须带 baseline_mode:同一算例-种子在两种基线下是两组完全不同的读数
    keys = sorted({(r["instance"], r["seed"], r["baseline_mode"]) for r in rows},
                  key=lambda t: (t[0], t[2], int(t[1])))
    for inst, seed, mode in keys:
        sub = [r for r in rows if r["instance"] == inst and r["seed"] == seed
               and r["baseline_mode"] == mode]
        r2 = _num(sub[0]["R2_makespan"])
        ref = _num(sub[0]["ref_makespan"])
        ok = [r for r in sub if (_num(r["R0_past_changed"]) or 0) == 0
              and r["R0_feasible"] == "True"]
        best_ok = min((_num(r["R0_makespan"]) for r in ok), default=None)
        best_any = min((_num(r["R0_makespan"]) for r in sub
                        if r["R0_feasible"] == "True"), default=None)
        s_ok = "无可采纳解" if best_ok is None else f"{best_ok:g}"
        print(f"  {inst:>18} seed={seed:>4} mode={mode:>9} "
              f"ref={ref:g}  R2={r2:g}  R0+可采纳={s_ok:>10}  R0+不设限={best_any:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
