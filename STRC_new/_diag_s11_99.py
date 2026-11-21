import traceback

from algorithm import node_engine
from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import repair_with_strc
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.expand_batch import _instances

path = dict(_instances())["S8x4x4_funnel"]
inst = load_instance(path)
net = Network(inst.nodes, inst.corridors, inst.lu_node)
bundle = build_baseline(inst, net, seed=99, mode="heuristic")
t_now = 0.35 * bundle.makespan
cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)

print("nodes:", inst.nodes)
print("corridors:", inst.corridors)
print("lu_node:", inst.lu_node, "block:", cid, t0, t1, "t_now", t_now)
print("node kinds:", getattr(net, "kinds", None))

orig = node_engine.SippRouter._sipp
dumped = []


def wrapped(self, agv, start, t0_, start_iv, pickup, ready, goal, accept, must_succeed=True):
    try:
        return orig(self, agv, start, t0_, start_iv, pickup, ready, goal, accept, must_succeed)
    except RuntimeError:
        dumped.append(1)
        print("\n=== FAIL #%d agv" % len(dumped), agv, "start", start, "t0", t0_, "start_iv", start_iv,
              "pickup", pickup, "ready", ready, "goal", goal, "netview", type(self.net).__name__)
        if agv == 2:
            m = self.nodes.model
            for n in ("g1", "h1", "h2", "r3", "r4", "f1"):
                print("  node %-4s kind %-8s cap %s need %.1f safe(agv%d) %s" % (
                    n, m.kinds.get(n), m.cap(n), self.nodes.need_of[n], agv,
                    [(round(a, 1), round(b, 1)) for a, b in self.nodes.safe_intervals(n, agv) if b > 40 and a < 150]))
                print("       parkers", [(round(a, 1), b if b == float("inf") else round(b, 1), g, k)
                                         for a, b, g, k in self.nodes.open_parkers(n)])
            print("  adj of start:", self.net.adj.get(start))
            for c, lst in sorted(self.table._res.items()):
                near = [(round(a, 1), round(b, 1), g, k) for a, b, g, k in lst if b > 44 and a < 75]
                if near:
                    print("  corr %-6s %s" % (c, near))
            for n in ("e1", "h1", "g1", "h2", "r1", "r2", "r3", "r4", "f1"):
                items = [(round(a, 1), b if b == float("inf") else round(b, 1), g, k)
                         for a, b, g, k in self.nodes._items.get(n, []) if b > 44 and a < 75] \
                    if hasattr(self.nodes, "_items") else "?"
                print("  nodeitems %-3s %s" % (n, items))
            raise SystemExit
        raise


node_engine.SippRouter._sipp = wrapped
rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
print("\nfeasible", rep.feasible, rep.errors[:2] if rep.errors else None)
