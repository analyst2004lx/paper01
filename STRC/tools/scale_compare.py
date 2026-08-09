"""独立实验:受扰动任务比例 φ ∈ (0,1] 下 paper01(R0+) vs paper04(STRC) 对照。

结果只写入 experiments/scale_compare/,不与 e1–e5 表格混放。

协议见 experiments/scale_compare/README.md。

用法(在 STRC/ 下):
    py -m tools.scale_compare
    py -m tools.scale_compare --scales 0.1,0.25,0.5,0.75,1.0 --budget-sec 2
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "experiments", "scale_compare")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OpKey = Tuple[int, int]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Independent scale sweep: paper01 R0+ vs paper04 STRC")
    ap.add_argument("--instance", default=None,
                    help="默认 congested_8x4x4")
    ap.add_argument("--scales", default="0.1,0.25,0.5,0.75,1.0",
                    help="受扰动未来工序比例,逗号分隔,含 1.0 表示极端全扰动")
    ap.add_argument("--seeds", default="42,7")
    ap.add_argument("--budget-sec", type=float, default=2.0,
                    help="paper01(R0+) 同挂钟预算(秒)")
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--out-dir", default=OUT_DIR)
    return ap.parse_args()


def _op_key_from_task(task: str) -> OpKey | None:
    if not task.startswith("J"):
        return None
    body = task[1:].split("-")
    if len(body) < 2:
        return None
    return int(body[0]), int(body[1])


def _future_ops_by_reservation(reservations, t_now: float) -> List[OpKey]:
    """仍有未来预约的工序,按该工序最早未来预约时刻排序。"""
    best: Dict[OpKey, float] = {}
    for r in reservations:
        if r.t_end <= t_now:
            continue
        key = _op_key_from_task(r.task)
        if key is None:
            continue
        best[key] = min(best.get(key, r.t_start), r.t_start)
    return [k for k, _ in sorted(best.items(), key=lambda kv: (kv[1], kv[0]))]


def _reservations_of_ops(reservations, op_set: Set[OpKey], *, t_now: float):
    """只取受扰工序在 t_now 之后仍有效的预约(作微阻断种子)。"""
    out = []
    for r in reservations:
        if r.t_end <= t_now:
            continue
        key = _op_key_from_task(r.task)
        if key is not None and key in op_set:
            out.append(r)
    return out


def _make_dist(t_now: float, seed_res) -> "Disturbance":
    """逐条微阻断(不合并),避免合并后误伤未选中工序的预约。"""
    from algorithm.disturbance import Disturbance
    blocks = [(r.corridor, float(r.t_start), float(r.t_end)) for r in seed_res]
    if not blocks:
        raise ValueError("no blocks from affected ops")
    cid0, a0, b0 = blocks[0]
    return Disturbance(
        type="corridor_block",
        t_now=t_now,
        corridor=cid0,
        t_start=a0,
        t_end=b0,
        note="scale_compare micro-blocks",
        extra={"blocks": blocks},
    )


def _release_covering_blocks(reservations, blocks, t_now: float, horizon: float, chains):
    """种子=与任一微阻断重叠的预约,再取时空闭包(保证外侧可冻结)。"""
    from algorithm.closure import spatiotemporal_closure
    seeds = []
    for r in reservations:
        if r.t_end <= t_now:
            continue
        for cid, a, b in blocks:
            if r.corridor == cid and r.overlaps(a, b):
                seeds.append(r)
                break
    return spatiotemporal_closure(
        seeds, reservations, horizon=horizon, t_now=t_now, machine_chains=chains,
    )


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.closure import machine_chains_from_ops
    from algorithm.repair import repair_with_scope_escalation
    from algorithm.resolve import resolve_r0
    from algorithm.schedule_io import build_baseline

    inst_path = args.instance or os.path.join(CLBS_INPUT, "congested_8x4x4.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()

    scales = [float(x) for x in args.scales.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]
    os.makedirs(args.out_dir, exist_ok=True)

    rows = []
    print("=== scale_compare: paper01(R0+) vs paper04(STRC) ===")
    print(f"instance={inst.name} scales={scales} budget={args.budget_sec}s")

    for seed in seeds:
        bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
        t_now = args.t_now_frac * bundle.makespan
        future = _future_ops_by_reservation(bundle.reservations, t_now)
        n_future = len(future)
        if n_future == 0:
            print(f"  seed={seed}: no future ops, skip")
            continue
        chains = machine_chains_from_ops(bundle.result.ops)

        for phi in scales:
            k = max(1, int(math.ceil(phi * n_future)))
            k = min(k, n_future)
            affected = set(future[:k])
            seed_res = _reservations_of_ops(
                bundle.reservations, affected, t_now=t_now)
            if not seed_res:
                print(f"  seed={seed} phi={phi}: no reservations, skip")
                continue
            dist = _make_dist(t_now, seed_res)
            # paper04: 所有与微阻断重叠的预约作种子 + 时空闭包
            closure = _release_covering_blocks(
                bundle.reservations, dist.extra["blocks"],
                t_now, bundle.makespan + 1.0, chains,
            )
            rep4 = repair_with_scope_escalation(
                inst, net, bundle, dist, closure.closed)
            # paper01: 热启动 GA
            rep1 = resolve_r0(
                inst, net, bundle, dist,
                budget_sec=args.budget_sec, seed=seed, hot=True, pop=args.pop,
            )

            d4 = rep4.deviation
            d1 = rep1.deviation
            row = {
                "instance": inst.name,
                "seed": seed,
                "phi": phi,
                "n_future_ops": n_future,
                "n_affected_ops": k,
                "affected_frac_ops": round(k / n_future, 4),
                "n_micro_blocks": len(dist.extra["blocks"]),
                "n_seed_res": len(seed_res),
                "n_closure": closure.size,
                "p04_scope_rounds": rep4.meta.get("scope_rounds"),
                "p04_final_release": rep4.meta.get("final_release_size"),
                # paper04 / STRC
                "p04_feasible": rep4.feasible,
                "p04_makespan": rep4.makespan,
                "p04_wall_ms": round(rep4.wall_ms, 2),
                "p04_res_changed": (None if d4 is None else d4.reservation_changed),
                # paper01 / R0+
                "p01_feasible": rep1.feasible,
                "p01_makespan": rep1.makespan,
                "p01_wall_ms": round(rep1.wall_ms, 2),
                "p01_res_changed": (None if d1 is None else d1.reservation_changed),
                "p01_gens": rep1.meta.get("generations"),
                "ref_makespan": bundle.makespan,
                "speedup_p01_over_p04": (
                    None if rep4.wall_ms <= 0 else round(rep1.wall_ms / rep4.wall_ms, 1)
                ),
                "makespan_winner": (
                    "none" if not (rep1.feasible or rep4.feasible) else
                    "paper01" if (rep1.feasible and not rep4.feasible) else
                    "paper04" if (rep4.feasible and not rep1.feasible) else
                    "paper01" if (rep1.makespan < rep4.makespan - 1e-9) else
                    "paper04" if (rep4.makespan < rep1.makespan - 1e-9) else
                    "tie"
                ),
            }
            rows.append(row)
            print(
                f"  seed={seed} φ={phi:.2f} affected={k}/{n_future}  "
                f"P04 feas={rep4.feasible} rounds={rep4.meta.get('scope_rounds')} "
                f"rel={rep4.meta.get('final_release_size')} "
                f"Cmax={rep4.makespan} {rep4.wall_ms:.1f}ms  "
                f"P01 feas={rep1.feasible} Cmax={rep1.makespan} {rep1.wall_ms:.0f}ms  "
                f"speedup×{row['speedup_p01_over_p04']} win={row['makespan_winner']}"
            )

    csv_path = os.path.join(args.out_dir, "scale_compare.csv")
    md_path = os.path.join(args.out_dir, "scale_compare.md")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow(row)

    # 按 φ 聚合均值表
    by_phi: Dict[float, List[dict]] = defaultdict(list)
    for row in rows:
        by_phi[row["phi"]].append(row)

    lines = [
        "# paper01 vs paper04：扰动规模对照",
        "",
        f"- 算例: `{inst.name}`",
        f"- paper01: R0+ 热启动闭环 GA，预算 `{args.budget_sec}` s",
        f"- paper04: STRC 时空闭包 + 第 1 级改路 + 失败扩域再修"
        f"（工件后缀→同车后缀→全部未来）",
        f"- 种子: {seeds}",
        "",
        "| φ | 受扰工序 | P04 可行率 | P04 Cmax(均) | P04 耗时ms(均) | "
        "P01 可行率 | P01 Cmax(均) | P01 耗时ms(均) | 耗时比 P01/P04 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for phi in sorted(by_phi):
        rs = by_phi[phi]
        def avg(key, pred=None):
            xs = [r[key] for r in rs if r[key] is not None and (pred is None or pred(r))]
            return sum(xs) / len(xs) if xs else float("nan")
        n_aff = avg("n_affected_ops")
        lines.append(
            "| {phi:.2f} | {na:.0f} | {f4:.0%} | {m4:.1f} | {t4:.1f} | "
            "{f1:.0%} | {m1:.1f} | {t1:.0f} | {sp:.0f}× |".format(
                phi=phi,
                na=n_aff,
                f4=sum(1 for r in rs if r["p04_feasible"]) / len(rs),
                m4=avg("p04_makespan", lambda r: r["p04_feasible"]),
                t4=avg("p04_wall_ms"),
                f1=sum(1 for r in rs if r["p01_feasible"]) / len(rs),
                m1=avg("p01_makespan", lambda r: r["p01_feasible"]),
                t1=avg("p01_wall_ms"),
                sp=avg("speedup_p01_over_p04"),
            )
        )
    lines.append("")
    lines.append(f"明细 CSV: `{os.path.basename(csv_path)}`")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nwrote {csv_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
