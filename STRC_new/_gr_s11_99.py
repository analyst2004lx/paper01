from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import repair_with_strc
from algorithm.resolve import resolve_r0
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.expand_batch import _instances

path = dict(_instances())["S8x4x4_funnel"]
seed = 99
inst = load_instance(path)
net = Network(inst.nodes, inst.corridors, inst.lu_node)
bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
t_now = 0.35 * bundle.makespan
cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)
print("ref Cmax", bundle.makespan, "t_now", round(t_now, 1), "block", cid, t0, t1)
rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=True)
print("STRC+escalation feasible", rep.feasible, (rep.errors or [])[:3])
for b, gs in ((2.0, 42), (10.0, 42), (10.0, 7)):
    r = resolve_r0(inst, net, bundle, dist, budget_sec=b, seed=gs, hot=True, pop=40)
    print("GR budget", b, "seed", gs, "feasible", r.feasible, "Cmax", r.makespan, (r.errors or [])[:2])
