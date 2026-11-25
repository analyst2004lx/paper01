"""三档下全图重规划集的构成:种子所属运输 vs 运行中升级的运输。"""
import glob
import os
import statistics as st

from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, release_set_r2, repair_with_strc, rewrite_tasks
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _instances

insts = list(_instances()) + [
    (os.path.basename(p)[:7], p) for p in
    sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S1[26]*.json")))
    + sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S20*.json")))]
for name, p in insts:
    inst = load_instance(p)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    out = {5: [], None: []}
    for s in (42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8):
        b = build_baseline(inst, net, seed=s, mode="heuristic")
        precompute_dependence(b)
        t = 0.35 * b.makespan
        c, a, z, _ = pick_busy_corridor(b.reservations, t_now=t)
        alive = rewrite_tasks([r for r in b.reservations if r.t_end > t], t)
        for L in (5, None):
            d = Disturbance(type="corridor_block", t_now=t, corridor=c, t_start=a,
                            t_end=z if L is None else min(z, a + L))
            sd = []
            release_set_r2(b, d, seeds_out=sd)
            rep = repair_with_strc(inst, net, b, d, tiers=True)
            out[L].append((len(rewrite_tasks([r for r in sd if not r.corridor.startswith("@")],
                                             t)) / len(alive),
                           rep.meta.get("promoted", 0) / len(alive), (z - a) / b.makespan))
    cells = [f"len {'full' if L is None else L}: seeds {st.mean(x[0] for x in v):.2f} "
             f"promoted {st.mean(x[1] for x in v):.2f}" for L, v in out.items()]
    print(f"{name:<16}" + "   ".join(cells)
          + f"   full block / Cmax {st.mean(x[2] for x in out[None]):.2f}")
