"""预建依赖图 + 接入端点节点停留,与每次整图重建的闭包逐个比较。"""
import glob
import os
import time

from algorithm.block_context import effective_block_windows
from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
from algorithm.closure import machine_chains_from_ops, spatiotemporal_closure
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, release_set_r2
from algorithm.schedule_io import build_baseline, node_reservations, pick_busy_corridor

paths = sorted(glob.glob(os.path.join(CLBS_INPUT, "**", "*.json"), recursive=True))
bad = n = 0
t_old = t_new = t_pre = 0.0
for p in paths:
    inst = load_instance(p)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in (42, 7, 1):
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        t = time.perf_counter()
        precompute_dependence(b)
        t_pre += time.perf_counter() - t
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        for L in (5, None):
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0,
                            t_end=t1 if L is None else min(t1, t0 + L))
            seeds = []
            t = time.perf_counter()
            new = set(release_set_r2(b, d, seeds_out=seeds))
            t_new += time.perf_counter() - t
            t = time.perf_counter()
            blocks = effective_block_windows(d, b.reservations)
            ends = {"@" + x for c, _a, _z in blocks for x in c.split("|")}
            nodes, caps = node_reservations(b)
            universe = list(b.reservations) + [r for r in nodes if r.corridor in ends]
            old = set(spatiotemporal_closure(
                seeds, universe, horizon=b.makespan + 1.0, t_now=t_now,
                machine_chains=machine_chains_from_ops(b.result.ops), node_caps=caps).closed)
            t_old += time.perf_counter() - t
            n += 1
            if old != new:
                bad += 1
                print(os.path.basename(p)[:28], seed, L, "old", len(old), "new", len(new),
                      "only-old", len(old - new), "only-new", len(new - old))
print(f"cases {n}, mismatches {bad}")
print(f"closure ms per case: rebuild {t_old / n * 1000:.2f}, precomputed {t_new / n * 1000:.2f}; "
      f"offline precompute {t_pre / (n / 2) * 1000:.2f} per baseline")
