import glob, os
from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance, validate
from algorithm.schedule_io import build_baseline, reservations_from_result
from algorithm.disturbance import Disturbance
from algorithm.node_engine import bounded_replay, prefix_decode_nodes
paths = sorted(glob.glob(os.path.join(CLBS_INPUT, "**", "*.json"), recursive=True))
bad = 0
for p in paths:
    inst = load_instance(p); net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in (1, 7, 42):
        b = build_baseline(inst, net, seed=seed)
        cid = inst.corridors[0]["u"] + "|" + inst.corridors[0]["v"]
        cid = min(cid, "|".join(reversed(cid.split("|"))))
        for frac in (0.2, 0.35, 0.6):
            t_now = frac * b.makespan
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=net.adj[inst.lu_node][0][0], t_start=b.makespan+50, t_end=b.makespan+60)
            r0 = bounded_replay(inst, net, b.tracked, b.ma, b.os_seq, d, set())
            same = reservations_from_result(r0) == b.reservations and abs(r0.makespan-b.makespan)<1e-9
            e0 = validate(inst, r0.to_timetable())
            W = {u.key for u in b.tracked.units.values() if any(s.exit > t_now for _, pl in u.parts() for s in pl.segments)}
            try:
                r1 = bounded_replay(inst, net, b.tracked, b.ma, b.os_seq, d, W); e1 = validate(inst, r1.to_timetable()); c1 = r1.makespan
            except Exception as ex:
                e1 = [repr(ex)]; c1 = None
            r2 = prefix_decode_nodes(inst, net, b.ma, b.os_seq, b.tracked, b.result, d)
            e2 = [getattr(r2, "strc_error", "")] if r2.makespan > 1e17 else validate(inst, r2.to_timetable())
            ok = same and not e0 and not e1 and not e2
            bad += not ok
            if not ok:
                print(os.path.basename(p)[:30], seed, frac, "same", same, "e0", e0[:1], "e1", e1[:2], "e2", e2[:2])
print("bad", bad)
