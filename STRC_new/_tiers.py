"""三档(冻结 / 沿原路线平移 / 全图重规划)对比现行闭包。

CL   现行:闭包 W 内全部在全图上重规划(重试 + 端点种子 + 扩域)
CLT  三档:种子所属运输全图重规划,W 内其余先沿原路线只改时刻,搜不到再升级;
     这样仍失败则同一 W 全图重规划,再按原阶梯扩域
指标(按 t_now 时未完成的运输计):
  R     实际在全图上搜索的运输占比(CL 即 W)
  W     允许改动的运输占比
  route 修复后路线变了的占比;time 只是时刻变了的占比
"""
import glob
import os
import statistics as st
from collections import defaultdict

from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import precompute_dependence, repair_with_strc
from algorithm.schedule_io import build_baseline, pick_busy_corridor, reservations_from_result
from tools.cheap_baselines import _instances
from _what_changed import profile

SEEDS = (42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8)
LENS = (5, None)
insts = list(_instances()) + [
    (os.path.basename(p)[:7], p) for p in
    sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S1[26]*.json")))
    + sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S20*.json")))]

agg = defaultdict(list)
for name, path in insts:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in SEEDS:
        b = build_baseline(inst, net, seed=seed, mode="heuristic")
        precompute_dependence(b)
        t_now = 0.35 * b.makespan
        cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
        base = profile(b.reservations, t_now)
        n = max(1, len(base))
        for L in LENS:
            te = t1 if L is None else min(t1, t0 + L)
            d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid, t_start=t0, t_end=te)
            for arm, kw in (("CL", dict(tiers=False)),
                            ("CLT0", dict(tiers=True, store_wait=False)),
                            ("CLT", dict(tiers=True, store_wait=True))):
                rep = repair_with_strc(inst, net, b, d, **kw)
                m = rep.meta
                row = dict(k=(name, seed, L), ok=rep.feasible, ms=rep.wall_ms,
                           cmax=rep.makespan, W=m.get("closed_tasks", 0) / n,
                           R=m.get("replan_tasks", m.get("closed_tasks", 0)) / n,
                           fb=bool(m.get("tier_fallback")), esc=m.get("scope_rounds", 0),
                           prom=m.get("promoted", 0))
                if rep.feasible:
                    new = profile(reservations_from_result(rep.result), t_now)
                    row["route"] = sum(1 for k in base if k in new and new[k][0] != base[k][0]) / n
                    row["time"] = sum(1 for k in base if k in new and new[k][0] == base[k][0]
                                      and new[k][1] != base[k][1]) / n
                    dv = rep.deviation
                    row["rf"] = dv.reservation_changed / max(1, dv.reservation_total)
                agg[(name, L, arm)].append(row)
    print(name, "done", flush=True)


def summ(v):
    ok = [x for x in v if x["ok"]]
    f = lambda key: st.mean(x[key] for x in ok) if ok else float("nan")
    return (len(ok), len(v), st.mean(x["R"] for x in v), st.mean(x["W"] for x in v),
            f("route"), f("time"), f("rf"), st.median(x["ms"] for x in v),
            sum(x["fb"] for x in v), sum(1 for x in v if x["esc"]))


ARMS = ("CL", "CLT0", "CLT")
print(f"\n{'instance':<16}{'len':>5}  per arm: feas  R(full-graph)  route  ms")
tot = defaultdict(list)
for name, _ in insts:
    for L in LENS:
        cells = []
        for arm in ARMS:
            v = agg[(name, L, arm)]
            tot[(L, arm)] += v
            s = summ(v)
            cells.append(f"{arm} {s[0]:>2}/{s[1]:<2} {s[2]:.2f} {s[4]:.3f} {s[7]:>5.1f}")
        print(f"{name:<16}{'full' if L is None else L:>5}  " + "   ".join(cells))
print()
for (L, arm), v in sorted(tot.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
    s = summ(v)
    print(f"len {'full' if L is None else L:>4} {arm:<4} feas {s[0]}/{s[1]}  R {s[2]:.3f}  "
          f"W {s[3]:.3f}  route {s[4]:.3f}  time-only {s[5]:.3f}  res_frac {s[6]:.3f}  "
          f"ms med {s[7]:.1f}  tier-fallback {s[8]}  escalated {s[9]}")
idx = {(r["k"], a): r for (n_, L, a), v in agg.items() for r in v}
for arm in ("CLT0", "CLT"):
    for L in LENS:
        both = [k for (k, a) in idx if a == "CL" and k[2] == L and idx[(k, "CL")]["ok"]
                and idx[(k, arm)]["ok"]]
        print(f"{arm}/CL len {'full' if L is None else L}: {len(both)} both-feasible, Cmax ratio "
              f"{st.mean(idx[(k, arm)]['cmax'] / idx[(k, 'CL')]['cmax'] for k in both):.4f}, "
              f"ms ratio (median) "
              f"{st.median(idx[(k, arm)]['ms'] / idx[(k, 'CL')]['ms'] for k in both):.2f}")
    for k in sorted({k for (k, a) in idx}, key=str):
        if idx[(k, "CL")]["ok"] != idx[(k, arm)]["ok"]:
            print(f"  differs {k} CL {idx[(k, 'CL')]['ok']} {arm} {idx[(k, arm)]['ok']}")
