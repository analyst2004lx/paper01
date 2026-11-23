"""重写集大小随阻断时长与算例规模的变化(阻断最忙走廊,t_now = 0.35 Cmax,5 个种子)。"""
import glob
import os
import statistics as st
from collections import defaultdict

from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import release_set_r2, replay_reroute, rewrite_tasks
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _instances
from _slack_cl import slack_release

SEEDS = (42, 7, 2024, 99, 123)
LENS = (5, 15, 30, None)
insts = list(_instances()) + [
    (os.path.basename(p)[:7], p) for p in sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S1[26]*.json")))
    + sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S20*.json")))]

agg = defaultdict(list)
for name, path in insts:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in SEEDS:
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        alive = rewrite_tasks([r for r in b.reservations if r.t_end > t_now], t_now)
        for L in LENS:
            te = t1 if L is None else min(t1, t0 + L)
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=te)
            for arm, rel in (("CL", release_set_r2(b, d)),
                             ("CLr", release_set_r2(b, d, endpoint_seeds=False)),
                             ("SL", slack_release(inst, b, d))):
                W = rewrite_tasks(rel, t_now)
                rep = replay_reroute(inst, net, b, d, rel)
                agg[(name, L, arm)].append((len(W) / max(1, len(alive | W)), rep.feasible,
                                            rep.wall_ms))
    print(name, "done", flush=True)

print(f"\n{'instance':<16}{'len':>6}" + "".join(f"{a:>22}" for a in ("CL", "CLr", "SL")))
print(" " * 22 + "".join(f"{'W/alive feas ms':>22}" for _ in range(3)))
for name, _p in insts:
    for L in LENS:
        cells = []
        for arm in ("CL", "CLr", "SL"):
            v = agg[(name, L, arm)]
            cells.append(f"{st.mean(x[0] for x in v):>8.2f} {sum(x[1] for x in v):>3}/{len(v)} "
                         f"{st.median(x[2] for x in v):>7.1f}")
        print(f"{name:<16}{'full' if L is None else L:>6}" + "".join(f"{c:>22}" for c in cells))
