"""划界何时省时间:按算例规模 k 与阻断时长 L,比较 R2 与 RA(同为分层)的 W/活跃运输、耗时与改动。"""
import statistics as st
import sys
from collections import defaultdict

from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, repair_with_all_future, repair_with_strc
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _row
from tools.scale_curve import _path

SEEDS = (42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8)
LENS = (2.0, 5.0, None)
ks = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [4, 6, 8, 10]

agg = defaultdict(list)
for k in ks:
    inst = load_instance(_path(k))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in SEEDS:
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        precompute_dependence(b)
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        for L in LENS:
            te = t1 if L is None else min(t1, t0 + L)
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=te)
            r2 = repair_with_strc(inst, net, b, d, expand_on_fail=False)
            ra = repair_with_all_future(inst, net, b, d)
            if not (r2.feasible and ra.feasible):
                continue
            a, c = _row("x", seed, "R2", r2, b, t_now), _row("x", seed, "RA", ra, b, t_now)
            changed = c["route_frac"] + c["time_frac"]
            agg[(k, L)].append((a["n_W"] / a["alive_tasks"], changed, r2.wall_ms, ra.wall_ms,
                                r2.meta.get("closure_ms", 0.0), a["res_frac"] - c["res_frac"],
                                r2.makespan / ra.makespan))
    print("k", k, "done", flush=True)

def wtl(xs, tol):
    return f"{sum(x < -tol for x in xs)}/{sum(abs(x) <= tol for x in xs)}/{sum(x > tol for x in xs)}"


def line(tag, v):
    print(f"{tag:>9}{len(v):>4}"
          f"{st.mean(x[0] for x in v):>9.3f}{st.mean(x[1] for x in v):>9.3f}"
          f"{st.median(x[2] for x in v):>8.2f}{st.median(x[3] for x in v):>8.2f}"
          f"{st.median(x[4] for x in v):>7.2f}{st.median(x[2] / x[3] for x in v):>7.2f}"
          f"{st.mean(x[5] for x in v):>+8.3f}{wtl([x[5] for x in v], 1e-3):>10}"
          f"{st.mean(x[6] for x in v):>8.3f}{wtl([x[6] - 1 for x in v], 1e-6):>10}")


print(f"\n{'k  L':>9}{'n':>4}{'W/alive':>9}{'changed':>9}{'R2 ms':>8}{'RA ms':>8}{'cl ms':>7}"
      f"{'R2/RA':>7}{'dres':>8}{'res W/T/L':>10}{'Cmax':>8}{'Cmx W/T/L':>10}")
for (k, L), v in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1] or 1e9)):
    line(f"{k} {'full' if L is None else L}", v)
for L in LENS:
    line(f"all {'full' if L is None else L}", [x for (k, l), v in agg.items() if l == L for x in v])
