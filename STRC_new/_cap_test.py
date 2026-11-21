import dataclasses

from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import repair_with_strc
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.expand_batch import _instances

SEEDS = [42, 7, 2024, 1, 13, 99, 123, 777, 31415, 8]


def pair(path, seed, cap_base, cap_rep):
    inst0 = load_instance(path)
    ib = dataclasses.replace(inst0, machine_capacity=cap_base)
    net = Network(ib.nodes, ib.corridors, ib.lu_node)
    bundle = build_baseline(ib, net, seed=seed, mode="heuristic")
    t_now = 0.35 * bundle.makespan
    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)
    ir = dataclasses.replace(inst0, machine_capacity=cap_rep)
    rep = repair_with_strc(ir, net, bundle, dist, expand_on_fail=False)
    return rep.feasible, bundle.makespan, rep.makespan


insts = dict(_instances())
p = insts["S8x4x4_funnel"]
print("== S11 seed 99 ==")
for cb, cr in ((2, 2), (2, 3), (2, 4), (2, None), (3, 3), (4, 4), (None, None)):
    print("  base c=%s repair c=%s ->" % (cb, cr), pair(p, 99, cb, cr))

print("== all 50 pairs, baseline and repair with the same c ==")
for c in (2, 3, None):
    fails = []
    for name, path in insts.items():
        for s in SEEDS:
            try:
                ok = pair(path, s, c, c)[0]
            except Exception as e:  # noqa: BLE001
                ok = False
            if not ok:
                fails.append((name, s))
    print("  c=%s feasible %d/50 fails %s" % (c, 50 - len(fails), fails))
