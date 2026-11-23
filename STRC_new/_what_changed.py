"""闭包修复后,未完成运输里:路线变了 / 只是时间变了 / 完全没变 各占多少。"""
import glob
import os
import statistics as st
from collections import defaultdict

from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import release_set_r2, replay_reroute, rewrite_tasks, \
    repair_with_all_future
from algorithm.schedule_io import build_baseline, pick_busy_corridor, reservations_from_result
from tools.cheap_baselines import _instances
from _grow import op_of

SEEDS = (42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8)
insts = list(_instances()) + [
    (os.path.basename(p)[:7], p) for p in
    sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S1[26]*.json")))
    + sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S20*.json")))]


def profile(res, t_now):
    out = defaultdict(list)
    for r in res:
        if r.t_end > t_now:
            out[op_of(r)].append(r)
    return {k: (tuple(r.corridor for r in sorted(v, key=lambda r: r.t_start)),
                tuple(round(r.t_start, 6) for r in sorted(v, key=lambda r: r.t_start)))
            for k, v in out.items() if k is not None}


agg = defaultdict(list)
for name, path in insts:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in SEEDS:
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        for L in (5, None):
            te = t1 if L is None else min(t1, t0 + L)
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=te)
            base = profile(b.reservations, t_now)
            for arm in ("CL", "ALL"):
                if arm == "CL":
                    rel = release_set_r2(b, d)
                    W = rewrite_tasks(rel, t_now)
                    rep = replay_reroute(inst, net, b, d, rel)
                else:
                    rep = repair_with_all_future(inst, net, b, d)
                    W = set(base)
                if not rep.feasible:
                    continue
                new = profile(reservations_from_result(rep.result), t_now)
                n = max(1, len(base))
                route = sum(1 for k in base if k in new and new[k][0] != base[k][0])
                timing = sum(1 for k in base if k in new and new[k][0] == base[k][0]
                             and new[k][1] != base[k][1])
                agg[(name, L, arm)].append((len(W & set(base)) / n, route / n, timing / n))
    print(name, "done", flush=True)

print(f"\n{'instance':<16}{'len':>5}   {'CL: W  route  time-only':>26}   {'ALL: route  time-only':>24}")
tot = defaultdict(list)
for name, _ in insts:
    for L in (5, None):
        c, a = agg[(name, L, "CL")], agg[(name, L, "ALL")]
        tot[(L, "CL")] += c
        tot[(L, "ALL")] += a
        print(f"{name:<16}{'full' if L is None else L:>5}   "
              f"{st.mean(x[0] for x in c):>8.2f} {st.mean(x[1] for x in c):>6.2f} "
              f"{st.mean(x[2] for x in c):>10.2f}   "
              f"{st.mean(x[1] for x in a):>10.2f} {st.mean(x[2] for x in a):>10.2f}")
print()
for (L, arm), v in sorted(tot.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
    print(f"len {'full' if L is None else L:>4} {arm:<4} W {st.mean(x[0] for x in v):.3f}  "
          f"route changed {st.mean(x[1] for x in v):.3f}  time-only {st.mean(x[2] for x in v):.3f}  "
          f"untouched {1 - st.mean(x[1] + x[2] for x in v):.3f}")
