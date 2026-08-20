"""把对照阶梯中间那一档补上:便宜的全局重算,与闭包修复同协议对比。

阶梯此前是 R1(释放集为空=不动)→ R2(闭包修复)→ R0+(种群搜索 0.2--2 s)。
中间缺两档便宜方法,而它们恰是审稿人会问的:

  RS  全局右移。不改路径/指派/序,把未完成的一切统一后推到阻断窗之后。
      按 A2 可采纳(冻结判据与 R2 相同),O(|R|)。文献里最标准的快速响应做法。
  RD  原染色体重解码。保持机器指派与扫描序,在装了阻断的路由层上从头解码一遍。
      **不保证按 A2 可采纳**——它从 t=0 重排,故本工具逐格报它改写了多少历史预约。
  RA  不画边界,释放 t_now 之后的全部预约再改路重放。它与 R2 共用同一引擎与同一
      冻结判据,唯一差别是释放集取了平凡上界,故两臂之差可全部归因于闭包本身。
      这一臂回答「既然闭包已占活预约九成,画这条边界还剩多少用」。

协议与 expand_batch 的 E1/E2/E3 完全一致(繁忙走廊单窗阻断、t_now=0.35 Cmax、
R2 关闭失败扩域),故本表可与 tab:e3 并读。

用法:
    py -m tools.cheap_baselines
    py -m tools.cheap_baselines --out experiments/cheap_baselines.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EPS = 1e-9
_SEEDS = [42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="cheap admissible baselines vs closure")
    ap.add_argument("--seeds", default=",".join(str(s) for s in _SEEDS))
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--out", default="experiments/cheap_baselines.csv")
    return ap.parse_args()


def _instances():
    from algorithm.clbs_bridge import CLBS_INPUT
    return [
        ("example_3x3x2", os.path.join(CLBS_INPUT, "example_3x3x2.json")),
        ("congested_8x4x4", os.path.join(CLBS_INPUT, "congested_8x4x4.json")),
        ("S8x4x4_high", os.path.join(
            CLBS_INPUT, "ext", "S8x4x4-LD21-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_funnel", os.path.join(
            CLBS_INPUT, "ext", "S8x4x4-LD11-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_mid", os.path.join(
            CLBS_INPUT, "ext", "S8x4x4-LD22-H0.3-F0.6-A4-s42.json")),
    ]


def _redecode(inst, net, bundle, dist):
    """RD:保持染色体,在装了阻断的路由层上重新解码一遍。"""
    from algorithm.block_context import block_windows_from_dist, corridor_block_active
    from algorithm.clbs_bridge import decode, validate
    from algorithm.metrics import evaluate_deviation
    from algorithm.repair import RepairResult
    from algorithm.schedule_io import reservations_from_result

    t0 = time.perf_counter()
    with corridor_block_active(dist):
        res = decode(inst, net, bundle.ma, bundle.os_seq,
                     conflict_free=True, dispatch="exact")
    errs = validate(inst, res.to_timetable())
    for cid, a, b in block_windows_from_dist(dist):
        for r in reservations_from_result(res):
            if r.corridor == cid and r.overlaps(a, b):
                errs.append(f"post-redecode still on blocked corridor: {r.task}")
    wall = (time.perf_counter() - t0) * 1000
    return RepairResult(
        feasible=not errs, makespan=res.makespan, makespan_ref=bundle.makespan,
        deviation=evaluate_deviation(bundle.result, res), wall_ms=wall,
        result=res, errors=errs, meta={"arm": "RD"},
    )


def _row(name, seed, arm, rep, bundle, t_now):
    from algorithm.metrics import reservation_delta_before
    from algorithm.schedule_io import reservations_from_result
    d = rep.deviation
    if rep.result is not None:
        pc, pt = reservation_delta_before(
            bundle.reservations, reservations_from_result(rep.result), t_now=t_now)
    else:
        pc, pt = None, None
    alive = sum(1 for r in bundle.reservations if r.t_end > t_now + EPS)
    return {
        "instance": name, "seed": seed, "arm": arm,
        "feasible": rep.feasible,
        "makespan": rep.makespan,
        "makespan_ref": rep.makespan_ref,
        "wall_ms": round(rep.wall_ms, 3),
        "res_frac": (None if d is None or d.reservation_total <= 0 else
                     round(d.reservation_changed / d.reservation_total, 3)),
        "past_changed": pc, "past_total": pt,
        "release_size": rep.closure_size or None,
        "alive_size": alive,
        "delta": rep.meta.get("delta"),
    }


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.repair import repair_with_all_future, repair_with_strc
    from algorithm.rightshift import repair_by_right_shift
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    seeds = [int(x) for x in args.seeds.split(",")]
    rows = []
    for name, path in _instances():
        if not os.path.isfile(path):
            print(f"  skip missing {path}")
            continue
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        for seed in seeds:
            bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = args.t_now_frac * bundle.makespan
            cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
            dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                               t_start=t0, t_end=t1)
            arms = {
                "R2": repair_with_strc(inst, net, bundle, dist, expand_on_fail=False),
                "RS": repair_by_right_shift(inst, net, bundle, dist),
                "RD": _redecode(inst, net, bundle, dist),
                "RA": repair_with_all_future(inst, net, bundle, dist),
            }
            for arm, rep in arms.items():
                rows.append(_row(name, seed, arm, rep, bundle, t_now))
            print(f"  {name:<16} s={seed:<6} ref={bundle.makespan:>6.1f}  " + "  ".join(
                f"{a}: {('%.1f' % r.makespan) if r.makespan else 'X':>6}"
                f"/{r.wall_ms:>6.2f}ms/{'ok' if r.feasible else 'FAIL'}"
                for a, r in arms.items()))

    out = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}  ({len(rows)} rows)")

    by = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    print(f"\n{'臂':<4}{'可行':>8}{'A2 越界格':>11}{'Cmax 均值':>11}"
          f"{'耗时中位/ms':>13}{'改动比例均值':>13}{'释放/活预约':>13}")
    for arm in ("R2", "RS", "RD", "RA"):
        rs = by[arm]
        feas = [r for r in rs if r["feasible"]]
        bad = sum(1 for r in rs if (r["past_changed"] or 0) > 0)
        cm = st.mean(r["makespan"] for r in feas) if feas else float("nan")
        ms = st.median(r["wall_ms"] for r in rs)
        rf = st.mean(r["res_frac"] for r in rs if r["res_frac"] is not None)
        share = [r["release_size"] / r["alive_size"] for r in rs
                 if r["release_size"] and r["alive_size"]]
        sh = f"{st.mean(share):>13.3f}" if share else f"{'--':>13}"
        print(f"{arm:<4}{len(feas)}/{len(rs):<6}{bad}/{len(rs):<9}"
              f"{cm:>11.1f}{ms:>13.2f}{rf:>13.3f}{sh}")

    print("\n逐格 Cmax 胜负(仅两臂都可行的格):")
    idx = {(r["instance"], r["seed"], r["arm"]): r for r in rows}
    keys = sorted({(r["instance"], r["seed"]) for r in rows})
    for other in ("RS", "RD", "RA"):
        win = lose = tie = 0
        for k in keys:
            a, b = idx[(k[0], k[1], "R2")], idx[(k[0], k[1], other)]
            if not (a["feasible"] and b["feasible"]):
                continue
            if a["makespan"] < b["makespan"] - EPS:
                win += 1
            elif a["makespan"] > b["makespan"] + EPS:
                lose += 1
            else:
                tie += 1
        print(f"  R2 vs {other}: 赢 {win} 平 {tie} 输 {lose}")

    # R2 vs RA 是本表的关键对照:同一引擎、同一冻结判据,只差释放集取闭包还是取
    # 平凡上界。稳定性(改动比例)而非 Cmax 才是闭包该兑现的那个量。
    print("\nR2 vs RA(画边界 vs 不画边界,同引擎):")
    d_ms, d_rf, d_rel = [], [], []
    rf_win = rf_tie = rf_lose = 0
    for k in keys:
        a, b = idx[(k[0], k[1], "R2")], idx[(k[0], k[1], "RA")]
        if not (a["feasible"] and b["feasible"]):
            continue
        if a["makespan"] and b["makespan"]:
            d_ms.append(a["makespan"] / b["makespan"])
        if a["res_frac"] is not None and b["res_frac"] is not None:
            d_rf.append(a["res_frac"] - b["res_frac"])
            if a["res_frac"] < b["res_frac"] - 1e-6:
                rf_win += 1
            elif a["res_frac"] > b["res_frac"] + 1e-6:
                rf_lose += 1
            else:
                rf_tie += 1
        if a["release_size"] and b["release_size"]:
            d_rel.append(a["release_size"] / b["release_size"])
    if d_rf:
        print(f"  改动比例 R2-RA: 均值 {st.mean(d_rf):+.3f}  "
              f"中位 {st.median(d_rf):+.3f}  (R2 更稳 {rf_win} 平 {rf_tie} 更差 {rf_lose})")
    if d_ms:
        print(f"  Cmax 比 R2/RA: 均值 {st.mean(d_ms):.4f}  "
              f"[{min(d_ms):.4f}, {max(d_ms):.4f}]")
    if d_rel:
        print(f"  释放集比 R2/RA: 均值 {st.mean(d_rel):.3f}  "
              f"[{min(d_rel):.3f}, {max(d_rel):.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
