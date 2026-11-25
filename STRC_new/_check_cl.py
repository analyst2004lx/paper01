import pickle
import statistics as st
import time

from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, release_set_r2, strc_closure_full
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _instances
from tools.scale_curve import _path

paths = [p for _n, p in _instances()] + [_path(k) for k in (6, 8, 10)]
n = bad = 0
ms = []
for path in paths:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in (42, 7, 2024, 99, 123):
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        precompute_dependence(b)
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        for te in (min(t1, t0 + 2), min(t1, t0 + 5), t1):
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=te)
            t = time.perf_counter()
            got = release_set_r2(b, d)
            ms.append((time.perf_counter() - t) * 1000)
            ref = strc_closure_full(b, d)[0].closed
            n += 1
            if set(got) != set(ref):
                bad += 1
                print("MISMATCH", path[-40:], seed, te, len(got), len(ref))
r = b.reservations[0]
assert pickle.loads(pickle.dumps(r)) == r and hash(pickle.loads(pickle.dumps(r))) == hash(r)
print(f"cases {n} mismatches {bad}  release_set_r2 ms median {st.median(ms):.2f} max {max(ms):.2f}")
