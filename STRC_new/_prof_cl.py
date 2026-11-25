import cProfile
import pstats

from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, release_set_r2
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.scale_curve import _path

cases = []
for k in (8, 10):
    inst = load_instance(_path(k))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in (42, 7, 2024):
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        precompute_dependence(b)
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        cases.append((b, Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                                     t_start=t0, t_end=min(t1, t0 + 5))))

pr = cProfile.Profile()
pr.enable()
for _ in range(20):
    for b, d in cases:
        release_set_r2(b, d)
pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(18)
