"""原型:小起点 + 冲突驱动扩张。

起点:
  SEED  只含种子所属运输
  SL    松弛截断的延误传播集(_slack_cl.slack_release)
  CL    当前闭包(对照)
一遍重放失败时,读出卡住的运输 k,把"k 原路线经过的走廊及其相邻走廊上、
与 k 原时段 [a-pad, z+pad] 重叠的占用"所属运输加入 W;同一 k 再次卡住则 pad 加倍。
驱离被禁止时,把被驱离车辆的下一次运输加入 W。至多 R 轮,之后退回全部未来。
"""
import glob
import os
import re
import statistics as st
import time
from collections import defaultdict

from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
from algorithm.disturbance import Disturbance
from algorithm.repair import (expand_release_all_future, release_set_r2, replay_reroute,
                              rewrite_tasks)
from algorithm.schedule_io import build_baseline, pick_busy_corridor
from tools.cheap_baselines import _instances
from _slack_cl import slack_release

KEY = re.compile(r"\((\d+), (\d+)\)")
EVICT = re.compile(r"would evict AGV(\d+)")
TASK = re.compile(r"^J(\d+)-(\d+)-")


def op_of(r):
    m = TASK.match(r.task)
    return None if m is None else (int(m.group(1)), int(m.group(2)))


def grow(inst, net, b, d, start_rel, *, rounds=8, pad0=5.0):
    t_now = d.t_now
    res = [r for r in b.reservations if r.t_end > t_now]
    by_op = defaultdict(list)
    for r in res:
        by_op[op_of(r)].append(r)
    nbr = defaultdict(set)
    for c in inst.corridors:
        cid = "|".join(sorted((c["u"], c["v"])))
        nbr[c["u"]].add(cid)
        nbr[c["v"]].add(cid)
    W = set(rewrite_tasks(start_rel, t_now))
    pad = defaultdict(lambda: pad0)
    t0 = time.perf_counter()
    for n in range(rounds + 1):
        rel = [r for r in res if op_of(r) in W]
        rep = replay_reroute(inst, net, b, d, rel)
        if rep.feasible:
            return rep, W, n, (time.perf_counter() - t0) * 1000
        msg = " ".join(rep.errors)
        added = set()
        m = EVICT.search(msg)
        if m:
            p = int(m.group(1))
            nxt = sorted((r.t_start, op_of(r)) for r in res
                         if r.agv == p and op_of(r) not in W and op_of(r) is not None)
            if nxt:
                added.add(nxt[0][1])
        m = KEY.search(msg)
        if m:
            k = (int(m.group(1)), int(m.group(2)))
            own = by_op.get(k, [])
            if own:
                a = min(r.t_start for r in own) - pad[k]
                z = max(r.t_end for r in own) + pad[k]
                cors = set()
                for r in own:
                    for v in r.corridor.split("|"):
                        cors |= nbr[v]
                for r in res:
                    if r.corridor in cors and r.overlaps(a, z) and op_of(r) is not None:
                        added.add(op_of(r))
            pad[k] *= 2
        added -= W
        if not added:
            break
        W |= added
    rel = expand_release_all_future(b.reservations, t_now=t_now)
    rep = replay_reroute(inst, net, b, d, rel)
    return rep, rewrite_tasks(rel, t_now), -1, (time.perf_counter() - t0) * 1000


if __name__ == "__main__":
    SEEDS = (42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8)
    insts = list(_instances()) + [
        (os.path.basename(p)[:7], p) for p in
        sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S1[26]*.json")))
        + sorted(glob.glob(os.path.join(CLBS_INPUT, "ext", "S20*.json")))]
    LENS = (5, None)
    agg = defaultdict(list)
    for name, path in insts:
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        for seed in SEEDS:
            b = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = 0.35 * b.makespan
            cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
            alive = rewrite_tasks([r for r in b.reservations if r.t_end > t_now], t_now)
            for L in LENS:
                te = t1 if L is None else min(t1, t0 + L)
                d = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                                t_start=t0, t_end=te)
                from algorithm.disturbance import seed_failed_reservations
                seedrel = list(seed_failed_reservations(d, b.reservations))
                for arm, rel in (("SEED", seedrel), ("SL", slack_release(inst, b, d)),
                                 ("CL", release_set_r2(b, d))):
                    rep, W, n, ms = grow(inst, net, b, d, rel)
                    dv = rep.deviation
                    agg[(name, L, arm)].append(dict(
                        w=len(W) / max(1, len(alive | W)), ok=rep.feasible, n=n, ms=ms,
                        rf=None if dv is None else dv.reservation_changed /
                        max(1, dv.reservation_total), cmax=rep.makespan))
        print(name, "done", flush=True)

    print(f"\n{'instance':<16}{'len':>5}" + "".join(f"{a:>34}" for a in ("SEED", "SL", "CL")))
    print(" " * 21 + "".join(f"{'W/alive feas rounds ms res_frac':>34}" for _ in range(3)))
    tot = defaultdict(list)
    for name, _p in insts:
        for L in LENS:
            cells = []
            for arm in ("SEED", "SL", "CL"):
                v = agg[(name, L, arm)]
                tot[(L, arm)] += v
                ok = [x for x in v if x["ok"]]
                cells.append(
                    f"{st.mean(x['w'] for x in v):>7.2f} {len(ok):>2}/{len(v)} "
                    f"{st.mean(max(x['n'], 0) for x in v):>5.1f} "
                    f"{st.median(x['ms'] for x in v):>6.1f} "
                    f"{st.mean(x['rf'] for x in ok) if ok else float('nan'):>7.3f}")
            print(f"{name:<16}{'full' if L is None else L:>5}" + "".join(f"{c:>34}" for c in cells))
    print()
    for (L, arm), v in sorted(tot.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        ok = [x for x in v if x["ok"]]
        fb = sum(1 for x in v if x["n"] < 0)
        print(f"len {'full' if L is None else L:>4} {arm:<5} feas {len(ok)}/{len(v)}  "
              f"W/alive {st.mean(x['w'] for x in v):.3f}  fallback-to-all {fb}  "
              f"ms med {st.median(x['ms'] for x in v):.1f}  "
              f"res_frac {st.mean(x['rf'] for x in ok):.3f}")
