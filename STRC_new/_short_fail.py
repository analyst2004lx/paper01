from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, repair_with_strc
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.expand_batch import _instances

insts = dict(_instances())
for L in (5, 2):
    for name, seed in (("S8x4x4_funnel", 99), ("S8x4x4_high", 99)):
        inst = load_instance(insts[name])
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
        t_now = 0.35 * bundle.makespan
        cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        t1 = min(t1, t0 + L)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)
        precompute_dependence(bundle)
        r0 = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
        r1 = repair_with_strc(inst, net, bundle, dist, expand_on_fail=True)
        print("L=%d %s %d first=%s err=%s" % (L, name, seed, r0.feasible, (r0.errors or [""])[0][:160]))
        for a in r1.meta.get("scope_attempts", []):
            print("     round", a["round"], a["release_size"], a["feasible"], a["first_error"][:120])
