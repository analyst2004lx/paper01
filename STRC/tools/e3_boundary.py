"""E3 边界消融:规模版 + 质量版(第 1 级改路)。

  规模: |R1_release| vs |R2_closure|
  质量: 同 replay_reroute 引擎下 feasible / Cmax / 预约扰动量

用法:
    py -m tools.e3_boundary
    py -m tools.e3_boundary --also-ra-failure
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC E3: R1 vs R2 boundary")
    ap.add_argument("--instance", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--theta", type=int, default=2)
    ap.add_argument("--also-ra-failure", action="store_true")
    ap.add_argument("--expand-on-fail", action="store_true",
                    help="打开失败扩域(默认关:纯边界消融)")
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "e3_boundary.csv"))
    return ap.parse_args()


def _row_for(inst, net, bundle, dist, theta: int, *, expand_on_fail: bool) -> dict:
    from algorithm.repair import repair_with_strc, repair_with_task_graph, release_set_r1, release_set_r2

    r1_set = release_set_r1(bundle, dist, theta=theta)
    r2_set = release_set_r2(bundle, dist)
    # E3 归因边界:默认关闭扩域,否则 R1 可靠「释放全部未来」偶然可行
    rep1 = repair_with_task_graph(
        inst, net, bundle, dist, theta=theta, expand_on_fail=expand_on_fail)
    rep2 = repair_with_strc(
        inst, net, bundle, dist, expand_on_fail=expand_on_fail)

    def _pack(prefix, release, rep):
        dev = rep.deviation
        return {
            f"{prefix}_release": len(release),
            f"{prefix}_feasible": rep.feasible,
            f"{prefix}_makespan": rep.makespan,
            f"{prefix}_ms_delta": (None if dev is None else round(dev.makespan_abs, 4)),
            f"{prefix}_res_changed": (None if dev is None else dev.reservation_changed),
            f"{prefix}_wall_ms": round(rep.wall_ms, 2),
            f"{prefix}_n_errors": len(rep.errors),
        }

    row = {
        "instance": inst.name,
        "seed": bundle.result.instance.name and None,  # placeholder overwritten
        "disturb_type": dist.type,
        "disturb_class": dist.class_label,
        "expand_on_fail": expand_on_fail,
        "miss_on_B": (dist.class_label == "B"
                      and len(r1_set) == 0 and len(r2_set) > 0),
        "R2_covers_R1": set(r1_set).issubset(set(r2_set)),
        "R1_scope_rounds": rep1.meta.get("scope_rounds"),
        "R2_scope_rounds": rep2.meta.get("scope_rounds"),
        "R1_final_release": rep1.meta.get("final_release_size", len(r1_set)),
        "R2_final_release": rep2.meta.get("final_release_size", len(r2_set)),
    }
    row.update(_pack("R1", r1_set, rep1))
    row.update(_pack("R2", r2_set, rep2))
    # 质量胜者:可行优先,其次 makespan,再次预约改动更少
    winner = "tie"
    if rep1.feasible and not rep2.feasible:
        winner = "R1"
    elif rep2.feasible and not rep1.feasible:
        winner = "R2"
    elif rep1.feasible and rep2.feasible:
        if rep2.makespan is not None and rep1.makespan is not None:
            if rep2.makespan < rep1.makespan - 1e-9:
                winner = "R2"
            elif rep1.makespan < rep2.makespan - 1e-9:
                winner = "R1"
            else:
                c1 = rep1.deviation.reservation_changed if rep1.deviation else 1 << 30
                c2 = rep2.deviation.reservation_changed if rep2.deviation else 1 << 30
                winner = "R2" if c2 < c1 else ("R1" if c1 < c2 else "tie")
    row["quality_winner"] = winner
    return row


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst_path = args.instance or os.path.join(CLBS_INPUT, "example_3x3x2.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=args.seed)
    t_now = args.t_now_frac * bundle.makespan

    rows = []
    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist_b = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                         t_start=t0, t_end=t1)
    row_b = _row_for(inst, net, bundle, dist_b, args.theta,
                     expand_on_fail=args.expand_on_fail)
    row_b["seed"] = args.seed
    row_b["corridor"] = cid
    rows.append(row_b)

    if args.also_ra_failure and inst.machine_node:
        mac = None
        for _opk, rec in bundle.result.ops.items():
            if not rec.pseudo and rec.machine is not None and rec.finish > t_now:
                mac = rec.machine
                break
        if mac is not None:
            failed_ops = [
                (rec.job, rec.i)
                for _opk, rec in bundle.result.ops.items()
                if not rec.pseudo and rec.machine == mac and rec.finish > t_now
            ]
            dist_a = Disturbance(
                type="ra_failure", t_now=t_now, machine=str(mac),
                extra={"failed_ops": failed_ops},
            )
            # A 类暂不跑质量版修复(无走廊阻断安装逻辑);只报规模
            from algorithm.repair import release_set_r1, release_set_r2
            r1_set = release_set_r1(bundle, dist_a, theta=args.theta)
            r2_set = release_set_r2(bundle, dist_a)
            rows.append({
                "instance": inst.name,
                "seed": args.seed,
                "disturb_type": dist_a.type,
                "disturb_class": dist_a.class_label,
                "corridor": f"machine:{mac}",
                "miss_on_B": False,
                "R2_covers_R1": set(r1_set).issubset(set(r2_set)),
                "R1_release": len(r1_set),
                "R2_release": len(r2_set),
                "R1_feasible": None,
                "R2_feasible": None,
                "R1_makespan": None,
                "R2_makespan": None,
                "quality_winner": "n/a",
            })

    print("=== STRC E3: R1 vs R2 ===")
    for row in rows:
        print(
            f"  [{row['disturb_type']}] class={row['disturb_class']}  "
            f"R1_rel={row.get('R1_release')} feas={row.get('R1_feasible')}  "
            f"R2_rel={row.get('R2_release')} feas={row.get('R2_feasible')}  "
            f"miss_B={row.get('miss_on_B')} winner={row.get('quality_winner')}"
        )
        if row.get("R2_feasible") is False:
            print("    (R2 errors suppressed; see experiments detail if needed)")

    # 统一字段
    keys = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_header = not os.path.isfile(args.out)
    with open(args.out, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"  wrote {args.out}")

    ok = all(r.get("miss_on_B") for r in rows if r["disturb_class"] == "B")
    # 质量:B 类上 R2 应可行(否则修复引擎未就绪)
    for r in rows:
        if r["disturb_class"] == "B" and r.get("R2_feasible") is False:
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
