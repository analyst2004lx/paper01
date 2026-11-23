"""原型:延误上界截断闭包(DB)与可达性闭包(CL)、ALL(RA)在扩展规模算例与短阻断下的对比。

DB 的改写集 = slack_release 给出的预约所属运输;重规划集为其中的走廊种子所属运输。
失败阶梯:DB 一遍(含同集重排与 W 全图重规划) -> CL(即 R2,含扩域)。耗时为两者之和。
DB 变体:d0 取 min(等阻断, 绕行)或只取等阻断(w);margin 把每条边的松弛减去该余量。
"""
import statistics as st
import sys
import time
from collections import defaultdict

from _slack_cl import slack_release
from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance, seed_failed_reservations
from algorithm.repair import (precompute_dependence, repair_with_all_future, repair_with_strc,
                              replay_reroute, rewrite_tasks)
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _instances, _row
from tools.scale_curve import _path

SEEDS = (42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8)
LENS = (2.0, 5.0, None)
VARIANTS = {"DB": dict(wait_d0=False, margin=0.0), "DBw": dict(wait_d0=True, margin=0.0),
            "DBw1": dict(wait_d0=True, margin=1.0), "DBw3": dict(wait_d0=True, margin=3.0)}
ARMS = ["CL", *VARIANTS, "RA"]
which = sys.argv[1] if len(sys.argv) > 1 else "scale"
if which == "scale":
    cases = [(f"k{k}", _path(k)) for k in (4, 5, 6, 7, 8, 9, 10)]
else:
    cases = list(_instances())

agg = defaultdict(list)
for name, path in cases:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in SEEDS:
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        precompute_dependence(b)
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        alive = len(rewrite_tasks([r for r in b.reservations if r.t_end > t_now], t_now))
        for L in LENS:
            te = t1 if L is None else min(t1, t0 + L)
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=te)
            seeds = seed_failed_reservations(d, b.reservations)
            q0 = rewrite_tasks([r for r in seeds if not r.corridor.startswith("@")], t_now)
            cl = repair_with_strc(inst, net, b, d, expand_on_fail=True)
            reps = {"CL": cl, "RA": repair_with_all_future(inst, net, b, d)}
            W = {"CL": cl.meta.get("n_W0", alive) / alive, "RA": 1.0}
            fb, clms = {}, {}
            for arm, kw in VARIANTS.items():
                tc = time.perf_counter()
                rel = slack_release(inst, b, d, **kw)
                clms[arm] = (time.perf_counter() - tc) * 1000
                rt = rewrite_tasks(rel, t_now)
                W[arm] = len(rt) / alive
                rep = replay_reroute(inst, net, b, d, rel, replan=q0 & rt)
                fb[arm] = not rep.feasible
                if not rep.feasible:
                    ms = rep.wall_ms
                    rep = repair_with_strc(inst, net, b, d, expand_on_fail=True)
                    rep.wall_ms += ms
                reps[arm] = rep
            rec = {"alive": alive, "W": W, "fb": fb, "clms": clms,
                   "ok": {}, "res": {}, "cmax": {}, "ms": {}}
            for arm, rep in reps.items():
                rec["ok"][arm] = rep.feasible
                rec["ms"][arm] = rep.wall_ms
                if rep.feasible:
                    row = _row(name, seed, arm, rep, b, t_now)
                    rec["res"][arm] = row["res_frac"]
                    rec["cmax"][arm] = rep.makespan
                    if arm == "RA":
                        rec["changed"] = row["route_frac"] + row["time_frac"]
            agg[L].append(rec)
    print(name, "done", flush=True)


def wtl(xs, tol=1e-3):
    return f"{sum(x < -tol for x in xs)}/{sum(abs(x) <= tol for x in xs)}/{sum(x > tol for x in xs)}"


for L, recs in agg.items():
    tag = "full" if L is None else L
    ch = [r["changed"] for r in recs if "changed" in r]
    print(f"\n=== L={tag}  pairs {len(recs)}  RA changed share {st.mean(ch):.3f}")
    for arm in ARMS:
        ok = sum(r["ok"][arm] for r in recs)
        nfb = sum(r["fb"].get(arm, False) for r in recs)
        extra = (f"  fallback {nfb:>2}  closure-proto ms {st.median(r['clms'][arm] for r in recs):5.2f}"
                 if arm in VARIANTS else "")
        print(f"  {arm:<5} feas {ok}/{len(recs)}  W/alive {st.mean(r['W'][arm] for r in recs):.3f}  "
              f"ms med {st.median(r['ms'][arm] for r in recs):6.2f}{extra}")
    for a in ARMS[:-1]:
        both = [r for r in recs if r["ok"][a] and r["ok"]["RA"]]
        dr = [r["res"][a] - r["res"]["RA"] for r in both]
        dc = [r["cmax"][a] / r["cmax"]["RA"] - 1 for r in both]
        tr = st.median(r["ms"][a] / r["ms"]["RA"] for r in both)
        print(f"  {a:<5} vs RA on {len(both)}: dres {st.mean(dr):+.3f} W/T/L {wtl(dr):>9}  "
              f"Cmax {1 + st.mean(dc):.4f} W/T/L {wtl(dc, 1e-6):>9}  time ratio {tr:.2f}")
