"""对比闭包与重试变体(E7 协议,5 算例 x 10 种子)。

CL   走廊闭包,一遍重放
CLR  走廊闭包,失败后把卡住的运输提前规划再试(至多 3 次)
CLE  走廊闭包 + 受阻走廊两端节点停留作种子
CLER 两项都加
CLN  全部有限容量节点停留进依赖图(上一轮对照)
*x   同一释放集起步,失败按 工件后缀/车辆后缀/全部未来 逐级扩域
ALL  全部未来(RA),ALLR 加重试
"""
import statistics as st
from collections import defaultdict

from algorithm.clbs_bridge import Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import (release_set_r2, repair_with_all_future, repair_with_strc,
                              rewrite_tasks)
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _SEEDS, _instances

ARMS = {
    "CL": dict(endpoint_seeds=False, max_retries=0),
    "CLR": dict(endpoint_seeds=False, max_retries=3),
    "CLE": dict(endpoint_seeds=True, max_retries=0),
    "CLER": dict(endpoint_seeds=True, max_retries=3),
    "CLN": dict(node_edges=True, endpoint_seeds=False, max_retries=0),
}
REL = {"CL": dict(endpoint_seeds=False), "CLE": dict(endpoint_seeds=True),
       "CLN": dict(node_edges=True, endpoint_seeds=False)}

rows = defaultdict(list)
for name, path in _instances():
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in _SEEDS:
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=t1)
        alive = rewrite_tasks([r for r in b.reservations if r.t_end > t_now], t_now)
        share = {k: len(rewrite_tasks(release_set_r2(b, d, **kw), t_now)) / max(1, len(alive))
                 for k, kw in REL.items()}
        line = [f"{name:<16}s={seed:<6}"]
        runs = []
        for arm, kw in ARMS.items():
            runs.append((arm, lambda kw=kw: repair_with_strc(inst, net, b, d,
                                                             expand_on_fail=False, **kw)))
            runs.append((arm + "x", lambda kw=kw: repair_with_strc(inst, net, b, d,
                                                                   expand_on_fail=True, **kw)))
        runs.append(("ALL", lambda: repair_with_all_future(inst, net, b, d, max_retries=0)))
        runs.append(("ALLR", lambda: repair_with_all_future(inst, net, b, d, max_retries=3)))
        for arm, fn in runs:
            rep = fn()
            dv = rep.deviation
            rf = None if dv is None or dv.reservation_total <= 0 else \
                dv.reservation_changed / dv.reservation_total
            sh = share.get(arm.rstrip("R").rstrip("x").rstrip("R")) if not arm.endswith("x") \
                else None
            retries = (rep.meta or {}).get("retries") if hasattr(rep, "meta") else None
            rows[arm].append(dict(key=(name, seed), ok=rep.feasible, cmax=rep.makespan,
                                  ms=rep.wall_ms, rf=rf, share=sh, retries=retries))
            if not arm.endswith("x"):
                line.append(f"{arm}:{'ok' if rep.feasible else 'X'}")
        print("  ".join(line), flush=True)

print()
for arm, rs in rows.items():
    ok = [r for r in rs if r["ok"]]
    sh = [r["share"] for r in rs if r["share"] is not None]
    rfs = [r["rf"] for r in ok if r["rf"] is not None]
    print(f"{arm:<6} feas {len(ok)}/{len(rs)}  "
          f"Cmax {st.mean(r['cmax'] for r in ok):.1f}  "
          f"ms med {st.median(r['ms'] for r in rs):.2f}  "
          f"res_frac {st.mean(rfs):.3f}"
          + (f"  U+/alive {st.mean(sh):.3f}" if sh else ""))
idx = {(arm, r["key"]): r for arm, rs in rows.items() for r in rs}
keys = [r["key"] for r in rows["CL"]]
for arm in ("CLR", "CLE", "CLER", "ALLR"):
    ref = "ALL" if arm == "ALLR" else "CL"
    both = [k for k in keys if idx[(ref, k)]["ok"] and idx[(arm, k)]["ok"]]
    dd = [idx[(arm, k)]["rf"] - idx[(ref, k)]["rf"] for k in both]
    dc = [idx[(arm, k)]["cmax"] / idx[(ref, k)]["cmax"] for k in both]
    print(f"{arm}-{ref} on {len(both)} both-feasible: d res_frac {st.mean(dd):+.4f}, "
          f"Cmax ratio {st.mean(dc):.4f}")
    for k in keys:
        a, c = idx[(ref, k)]["ok"], idx[(arm, k)]["ok"]
        if a != c:
            print(f"    differs {k}: {ref}={a} {arm}={c}")
for arm in ("CL", "CLR", "CLE", "CLER", "ALL", "ALLR"):
    bad = [k for k in keys if not idx[(arm, k)]["ok"]]
    print(f"{arm:<5} fails: {bad}")
