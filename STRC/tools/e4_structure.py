"""E4 结构预测:阻断 LU 最小割走廊时,funnel(割=1) 闭包占比应大于 high(割=2)。

用法:
    py -m tools.e4_structure
    py -m tools.e4_structure --seeds 42,7,2024
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_BASE = dict(jobs=12, nm=8, na=12, flex=0.6, tt=4.0)
_CASES = [
    dict(name="A funnel", tag="funnel"),
    dict(name="A high", tag="high"),
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC E4: closure size vs layout cut")
    ap.add_argument("--seeds", default="42,7,2024")
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "e4_structure.csv"))
    return ap.parse_args()


def _build(tag: str):
    from algorithm.clbs_bridge import Network, build_instance, make_spec, parse_instance

    c = dict(_BASE)
    extra = dict(grid_rows=4, grid_cols=4) if tag in ("low", "scatter") else {}
    spec = make_spec(tag, 0.3, c["flex"], c["jobs"], c["nm"], c["na"], 3,
                     seed=42, tt_tp_target=c["tt"], **extra)
    inst = parse_instance(build_instance(spec))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    return inst, net


def main() -> int:
    args = parse_args()
    from algorithm.closure import machine_chains_from_ops, spatiotemporal_closure
    from algorithm.disturbance import Disturbance, seed_failed_reservations
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    seeds = [int(x) for x in args.seeds.split(",")]
    rows = []
    print("=== STRC E4: funnel vs high (block LU-cut corridor) ===")
    for case in _CASES:
        inst, net = _build(case["tag"])
        feats = net.structural_features(list(inst.machine_node.values()))
        cut_cids = list(feats.get("lu_cut_corridors") or [])
        for seed in seeds:
            bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = args.t_now_frac * bundle.makespan
            prefer = None
            for c in cut_cids:
                hits = [r for r in bundle.reservations
                        if r.corridor == c and r.t_end > t_now]
                if hits:
                    prefer = c
                    break
            cid, t0, _t1, n_hit = pick_busy_corridor(
                bundle.reservations, t_now=t_now, prefer=prefer)
            # 结构性断路:从 t_now 起封死该走廊至视界末端(而非只封其繁忙子窗)
            dist = Disturbance(
                type="corridor_block", t_now=t_now, corridor=cid,
                t_start=t_now, t_end=bundle.makespan + 1.0,
            )
            seeds_r = seed_failed_reservations(dist, bundle.reservations)
            chains = machine_chains_from_ops(bundle.result.ops)
            closure = spatiotemporal_closure(
                seeds_r, bundle.reservations, horizon=bundle.makespan + 1.0,
                t_now=t_now, machine_chains=chains,
            )
            row = {
                "case": case["name"],
                "tag": case["tag"],
                "seed": seed,
                "lu_min_cut": feats["lu_min_cut"],
                "far_group_cut": feats["far_group_cut"],
                "cut_corridors": "|".join(cut_cids),
                "blocked_on_cut": cid in cut_cids,
                "makespan": round(bundle.makespan, 4),
                "n_reservations": len(bundle.reservations),
                "n_hits": n_hit,
                "n_seeds": len(seeds_r),
                "n_closure": closure.size,
                "closure_frac": round(
                    closure.size / max(1, len(bundle.reservations)), 4),
                "corridor": cid,
            }
            rows.append(row)
            print(f"  {case['name']:10s} seed={seed} cut={feats['lu_min_cut']} "
                  f"on_cut={row['blocked_on_cut']} "
                  f"|cl|={closure.size} frac={row['closure_frac']:.3f}")

    from statistics import median

    def _agg(tag, key):
        xs = [r[key] for r in rows if r["tag"] == tag]
        return mean(xs), median(xs)

    f_mean, f_med = _agg("funnel", "closure_frac")
    h_mean, h_med = _agg("high", "closure_frac")
    fs_mean, fs_med = _agg("funnel", "n_seeds")
    hs_mean, hs_med = _agg("high", "n_seeds")
    # 主判据:中位数(抗单种子尖峰);种子命中数作辅证
    pred_ok = (f_med > h_med) or (f_med >= h_med and fs_med > hs_med)
    print(f"[E4] closure_frac funnel mean/med={f_mean:.3f}/{f_med:.3f}  "
          f"high={h_mean:.3f}/{h_med:.3f}")
    print(f"[E4] n_seeds      funnel mean/med={fs_mean:.1f}/{fs_med:.1f}  "
          f"high={hs_mean:.1f}/{hs_med:.1f}")
    print(f"[E4] pred (med funnel>high or seeds)={'PASS' if pred_ok else 'FAIL / inconclusive'}")

    out = args.out
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"  wrote {out}")
    return 0 if pred_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
