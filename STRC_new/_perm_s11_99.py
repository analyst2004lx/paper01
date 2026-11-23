import itertools

from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.node_engine import bounded_replay, snapshot
from algorithm.repair import release_set_r2, rewrite_tasks
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.expand_batch import _instances

path = dict(_instances())["S8x4x4_funnel"]
inst = load_instance(path)
net = Network(inst.nodes, inst.corridors, inst.lu_node)
bundle = build_baseline(inst, net, seed=99, mode="heuristic")
t_now = 0.35 * bundle.makespan
cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)

tr = bundle.tracked
W_cl = rewrite_tasks(release_set_r2(bundle, dist), t_now)
snaps = snapshot(tr, t_now, inst)
inprog = sorted({s.key for s in snaps.values() if s.key is not None})
print({k: (s.key, s.part, s.node, s.since) for k, s in snaps.items()})
print("in-progress (non-empty) keys:", inprog, "| |W|", len(W_cl))
alive = {k for k, u in tr.units.items()
         if max([s.exit for _p, pl in u.parts() for s in pl.segments] or [0]) > t_now}

for label, W in (("closure W", W_cl), ("all alive", alive | W_cl)):
    ok = []
    errs = {}
    for r in range(1, len(inprog) + 1):
        for perm in itertools.permutations(inprog, r):
            try:
                res = bounded_replay(inst, net, tr, bundle.ma, bundle.os_seq, dist, set(W),
                                     early=list(perm), base_ops=bundle.result.ops, replan=None)
                ok.append((perm, res.makespan))
            except Exception as e:  # noqa: BLE001
                errs.setdefault(str(e)[:110], []).append(perm)
    print(label, "feasible orders:", ok[:5], "count", len(ok))
    for m, ps in errs.items():
        print("   %3d x %s   e.g. %s" % (len(ps), m, ps[0]))
