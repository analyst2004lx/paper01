from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, repair_with_all_future, repair_with_strc
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _instances
from tools.scale_curve import _path

cases = [(dict(_instances())["S8x4x4_funnel"], 99, None), (_path(7), 777, None), (_path(9), 13, None),
         (dict(_instances())["S8x4x4_funnel"], 1, 2.0), (dict(_instances())["S8x4x4_high"], 7, 2.0),
         (dict(_instances())["S8x4x4_high"], 13, 2.0), (dict(_instances())["S8x4x4_funnel"], 13, 2.0)]
for path, seed, L in cases:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    b = build_baseline(inst, net, seed=seed, mode="heuristic")
    precompute_dependence(b)
    t_now = 0.35 * b.makespan
    cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
    if L:
        t1 = min(t1, t0 + L)
    d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)
    r1 = repair_with_strc(inst, net, b, d, expand_on_fail=False)
    r2 = repair_with_strc(inst, net, b, d, expand_on_fail=True)
    ra = repair_with_all_future(inst, net, b, d)
    print(path[-36:], seed, L, "first", r1.feasible, "esc", r2.feasible, r2.meta.get("scope_rounds"),
          "RA", ra.feasible)
    for rep in (r1, r2):
        if not rep.feasible:
            print("    ", (rep.errors or ["?"])[0][:200])
            for a in rep.meta.get("scope_attempts", []):
                print("       round", a["round"], a["feasible"], a["first_error"][:150])
