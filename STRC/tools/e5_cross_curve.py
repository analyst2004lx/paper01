"""E5 预算–质量–稳定性权衡:R0/R0+ 重解 vs R2 闭包修复。

第 1 级 R2(只改路)在 Cmax 上通常弱于热启动 GA,但在以下两维占优:
  - 挂钟:毫秒级 vs 预算秒级
  - 预约扰动量:只动闭包,R0 往往改写全部未来预约

因此 E5 报告三条曲线,而非单一 Cmax 交叉:
  1) Cmax(budget) — 预期宽预算 R0 更优
  2) reservation_changed — 预期 R2 始终更小
  3) 综合门禁:R2 可行且更稳;高预算下 R0 Cmax 不差于 R2(互补)

用法:
    py -m tools.e5_cross_curve
    py -m tools.e5_cross_curve --instance ../clbs/input/congested_8x4x4.json
    py -m tools.e5_cross_curve --budgets 0.05,0.2,1,5 --seeds 42,7
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_DEFAULT_BUDGETS = "0.05,0.2,1,5"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC E5: budget / quality / stability")
    ap.add_argument("--instance", default=None)
    ap.add_argument("--seeds", default="42,7")
    ap.add_argument("--budgets", default=_DEFAULT_BUDGETS)
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--cold", action="store_true", help="用 R0 冷启动(默认 R0+ 热启动)")
    ap.add_argument(
        "--baseline-mode", choices=("heuristic", "ga"), default="heuristic",
        help="初始排程的来源。heuristic 是未优化解,ga 是收敛后的解;"
             "两者会给出完全不同的 R0+/R2 差距,见 experiments/README",
    )
    ap.add_argument("--baseline-budget", type=float, default=5.0,
                    help="--baseline-mode ga 时构造初始解的挂钟预算")
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "e5_cross_curve.csv"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.metrics import reservation_delta_before
    from algorithm.repair import repair_with_strc
    from algorithm.resolve import resolve_r0
    from algorithm.schedule_io import (
        build_baseline,
        pick_busy_corridor,
        reservations_from_result,
    )

    def past_delta(bundle, rep, t_now: float):
        """该臂改写了多少条 t_now 之前已执行完的预约(按 A2 应为 0)。"""
        if not rep.feasible or rep.result is None:
            return None, None
        return reservation_delta_before(
            bundle.reservations, reservations_from_result(rep.result), t_now=t_now
        )

    inst_path = args.instance or os.path.join(CLBS_INPUT, "congested_8x4x4.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()

    seeds = [int(x) for x in args.seeds.split(",")]
    budgets = [float(x) for x in args.budgets.split(",")]
    hot = not args.cold
    arm_r0 = "R0+" if hot else "R0"

    rows = []
    print(f"=== STRC E5: {arm_r0} vs R2 (Cmax + stability) ===")
    print(f"instance={inst.name}  seeds={seeds}  budgets={budgets}")
    print(f"baseline_mode={args.baseline_mode}")

    for seed in seeds:
        bundle = build_baseline(
            inst, net, seed=seed, mode=args.baseline_mode,
            budget_sec=args.baseline_budget,
        )
        t_now = args.t_now_frac * bundle.makespan
        cid, _, _, n_hit = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(
            type="corridor_block", t_now=t_now, corridor=cid,
            t_start=t_now, t_end=bundle.makespan + 1.0,
        )
        rep2 = repair_with_strc(inst, net, bundle, dist)
        d2 = rep2.deviation
        r2_past_ch, r2_past_tot = past_delta(bundle, rep2, t_now)
        print(f"\n  seed={seed} corridor={cid} hits={n_hit}")
        print(f"    R2  feas={rep2.feasible} Cmax={rep2.makespan} "
              f"RΔ={None if d2 is None else d2.reservation_changed}/"
              f"{None if d2 is None else d2.reservation_total} "
              f"past={r2_past_ch}/{r2_past_tot} "
              f"wall={rep2.wall_ms:.2f}ms  ref={bundle.makespan}")

        for b in budgets:
            rep0 = resolve_r0(
                inst, net, bundle, dist,
                budget_sec=b, seed=seed, hot=hot, pop=args.pop,
            )
            d0 = rep0.deviation
            ms_winner = "none"
            if rep0.feasible and not rep2.feasible:
                ms_winner = arm_r0
            elif rep2.feasible and not rep0.feasible:
                ms_winner = "R2"
            elif rep0.feasible and rep2.feasible:
                if rep0.makespan < rep2.makespan - 1e-9:
                    ms_winner = arm_r0
                elif rep2.makespan < rep0.makespan - 1e-9:
                    ms_winner = "R2"
                else:
                    ms_winner = "tie"

            stab_winner = "none"
            if d0 is not None and d2 is not None:
                if d2.reservation_changed < d0.reservation_changed:
                    stab_winner = "R2"
                elif d0.reservation_changed < d2.reservation_changed:
                    stab_winner = arm_r0
                else:
                    stab_winner = "tie"

            r0_past_ch, r0_past_tot = past_delta(bundle, rep0, t_now)
            row = {
                "instance": inst.name,
                "seed": seed,
                "corridor": cid,
                "t_now": round(t_now, 4),
                "baseline_mode": args.baseline_mode,
                "budget_sec": b,
                # 挂钟是否守住预算。GA 至少要跑完一代才检查终止条件,故小预算下
                # 这一列会是 False,而 R0_wall_ms 就是该臂的响应时间下界。
                "budget_honored": rep0.wall_ms <= b * 1000.0 * 1.05,
                "R0_stopped_by": rep0.meta.get("stopped_by"),
                "arm_r0": arm_r0,
                "R0_feasible": rep0.feasible,
                "R0_makespan": rep0.makespan,
                "R0_res_changed": (None if d0 is None else d0.reservation_changed),
                "R0_res_total": (None if d0 is None else d0.reservation_total),
                "R0_wall_ms": round(rep0.wall_ms, 2),
                "R0_gens": rep0.meta.get("generations"),
                "R0_decodes": rep0.meta.get("decodes"),
                "R0_past_changed": r0_past_ch,
                "R0_past_total": r0_past_tot,
                "R2_feasible": rep2.feasible,
                "R2_makespan": rep2.makespan,
                "R2_res_changed": (None if d2 is None else d2.reservation_changed),
                "R2_res_total": (None if d2 is None else d2.reservation_total),
                "R2_wall_ms": round(rep2.wall_ms, 2),
                "R2_release": rep2.release_size,
                "R2_past_changed": r2_past_ch,
                "R2_past_total": r2_past_tot,
                "makespan_winner": ms_winner,
                "stability_winner": stab_winner,
                "ref_makespan": bundle.makespan,
            }
            rows.append(row)
            print(f"    budget={b:6.2f}s  {arm_r0}: Cmax={rep0.makespan} "
                  f"RΔ={row['R0_res_changed']} past={r0_past_ch}/{r0_past_tot} "
                  f"wall={rep0.wall_ms:.0f}ms honored={row['budget_honored']} "
                  f"gens={row['R0_gens']}  "
                  f"ms_win={ms_winner} stab_win={stab_winner}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow(row)

    r2_feas = all(r["R2_feasible"] for r in rows)
    stab_r2 = all(r["stability_winner"] == "R2" for r in rows
                  if r["R0_feasible"] and r["R2_feasible"])
    # 高预算上 R0 应在 Cmax 上不全面落败(体现重解的质量潜力)
    bmax = max(budgets)
    high = [r for r in rows if r["budget_sec"] == bmax]
    r0_quality = any(r["makespan_winner"] == arm_r0 for r in high)

    summary = {
        "instance": inst.name,
        "arm_r0": arm_r0,
        "seeds": seeds,
        "budgets": budgets,
        "R2_always_feasible": r2_feas,
        "R2_always_stabler": stab_r2,
        "R0_wins_makespan_at_max_budget": r0_quality,
        "complementary": bool(r2_feas and stab_r2 and r0_quality),
        "n_rows": len(rows),
    }
    detail = os.path.join(ROOT, "experiments", "e5_last.json")
    with open(detail, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)

    print(f"\n[E5] wrote {args.out}")
    print(f"[E5] wrote {detail}")
    print(f"[E5] R2_feasible={r2_feas}  R2_stabler={stab_r2}  "
          f"R0_Cmax_at_maxB={r0_quality}  complementary={summary['complementary']}")
    return 0 if summary["complementary"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
