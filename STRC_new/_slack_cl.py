"""原型:按延误量传播的划界(松弛截断),与当前可达性闭包对比(E7 协议,5 算例 x 10 种子)。

可达性闭包:只要有依赖边相连就整条牵连。
松弛截断:种子带初始延误 d0,沿边传到后继时扣掉这条边上的松弛,
    d(b) = max_a [ d(a) - slack(a, b) ],只把 d > 0 的运输放进重写集。
松弛取自基线排程本身:
    同走廊/端点节点让行边   b.t_start - a.t_end
    同车后继              同车相邻两段之间的空档
    同工件后继            到达后等机器的时间 + 完工后等车来取的时间
    同机后继              前道完工到本道开工之间的空档
d0 取 min(等阻断结束, 绕行多花的时间);margin 把每条边的松弛统一减去一个余量,换取稳妥。
"""
import heapq
import re
import statistics as st
from collections import defaultdict

from algorithm.block_context import effective_block_windows
from algorithm.clbs_bridge import Network, load_instance
from algorithm.closure import machine_chains_from_ops
from algorithm.disturbance import Disturbance, seed_failed_reservations
from algorithm.repair import (release_set_r2, replay_reroute, repair_with_scope_escalation,
                              repair_with_all_future, rewrite_tasks)
from algorithm.schedule_io import build_baseline, node_reservations, pick_busy_corridor
from tools.cheap_baselines import _SEEDS, _instances

TASK = re.compile(r"^J(\d+)-(\d+)-(empty|loaded|leave|evict)$")
EPS = 1e-9


def sp_without(inst, cut):
    """去掉走廊 cut 后各点对的最短行驶时间(Floyd,小图够用)。"""
    nodes = sorted({c["u"] for c in inst.corridors} | {c["v"] for c in inst.corridors})
    INF = float("inf")
    d = {(a, b): (0.0 if a == b else INF) for a in nodes for b in nodes}
    for c in inst.corridors:
        cid = "|".join(sorted((c["u"], c["v"])))
        if cid == cut:
            continue
        d[c["u"], c["v"]] = d[c["v"], c["u"]] = min(d[c["u"], c["v"]], float(c["time"]))
    for k in nodes:
        for a in nodes:
            for b in nodes:
                if d[a, k] + d[k, b] < d[a, b]:
                    d[a, b] = d[a, k] + d[k, b]
    return d


def slack_release(inst, b, dist, *, margin=0.0, endpoints=True, wait_d0=False):
    res = list(b.reservations)
    blocks = effective_block_windows(dist, res)
    seeds = list(seed_failed_reservations(dist, res))
    for r in res:
        if any(r.corridor == c and r.overlaps(a, z) for c, a, z in blocks) and r not in seeds:
            seeds.append(r)
    d0 = {}
    for r in seeds:
        for c, a, z in blocks:
            if r.corridor != c:
                continue
            u, v = c.split("|")
            ctime = r.t_end - r.t_start
            det = sp_without(inst, c)[u, v] - ctime
            dr = z - r.t_start if wait_d0 else min(z - r.t_start, det)
            d0[r] = max(d0.get(r, 0.0), dr)
    nodes_extra = []
    if endpoints:
        extra, _caps = node_reservations(b)
        ends = {"@" + n: (a, z) for c, a, z in blocks for n in c.split("|")}
        nodes_extra = [r for r in extra if r.corridor in ends]
        dmax = max(d0.values(), default=0.0)
        for r in nodes_extra:
            a, z = ends[r.corridor]
            if r.overlaps(a, z) and r.t_end > dist.t_now + EPS:
                d0[r] = max(d0.get(r, 0.0), min(dmax, z - r.t_start))
    universe = res + nodes_extra

    edges = defaultdict(list)          # a -> [(b, slack)]
    by_cor, by_agv, loaded = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in universe:
        by_cor[r.corridor].append(r)
        if not r.corridor.startswith("@"):
            by_agv[r.agv].append(r)
        m = TASK.match(r.task)
        if m and m.group(3) == "loaded" and not r.corridor.startswith("@"):
            loaded[(int(m.group(1)), int(m.group(2)))].append(r)
    for lst in by_cor.values():
        lst.sort(key=lambda x: x.t_start)
        for i, a in enumerate(lst):
            for c in lst[i + 1:]:
                if c.agv != a.agv:
                    edges[a].append((c, max(0.0, c.t_start - a.t_end)))
    for lst in by_agv.values():
        lst.sort(key=lambda x: x.t_start)
        for a, c in zip(lst, lst[1:]):
            edges[a].append((c, max(0.0, c.t_start - a.t_end)))
    ops = b.result.ops
    # 运输 (j,i) 的最后一段载货 -> 工序 (j,i) -> 运输 (j,i+1) 的各段载货;同机前道 -> 本道
    opnode = {k: ("op", k) for k in ops}
    for k, rec in ops.items():
        if getattr(rec, "pseudo", False):
            continue
        if loaded.get(k):
            last = max(loaded[k], key=lambda r: r.t_end)
            edges[last].append((opnode[k], max(0.0, rec.start - rec.arrive)))
        nxt = (k[0], k[1] + 1)
        for r in loaded.get(nxt, ()):
            edges[opnode[k]].append((r, max(0.0, r.t_start - rec.finish)))
    for (a, c) in machine_chains_from_ops(ops):
        edges[opnode[a]].append((opnode[c], max(0.0, ops[c].start - ops[a].finish)))
    # 同一运输内:前段延误必然推后后段(由同车边覆盖),这里不再加

    delay = {}
    heap = [(-d, id(r), r) for r, d in d0.items() if d > EPS]
    for nd, _i, r in heap:
        delay[r] = -nd
    heapq.heapify(heap)
    while heap:
        nd, _i, r = heapq.heappop(heap)
        d = -nd
        if d < delay.get(r, 0.0) - EPS:
            continue
        for c, s in edges.get(r, ()):
            dc = d - max(0.0, s - margin)
            if dc > EPS and dc > delay.get(c, 0.0) + EPS:
                delay[c] = dc
                heapq.heappush(heap, (-dc, id(c), c))
    hit = [r for r in delay if not isinstance(r, tuple) and r.t_end > dist.t_now + EPS]
    return hit



if __name__ == "__main__":
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
            sets = {
                "CL": release_set_r2(b, d),
                "SL0": slack_release(inst, b, d, margin=0.0),
                "SL2": slack_release(inst, b, d, margin=2.0),
                "SL5": slack_release(inst, b, d, margin=5.0),
            }
            line = [f"{name:<16}s={seed:<6}"]
            for arm, rel in sets.items():
                share = len(rewrite_tasks(rel, t_now)) / max(1, len(alive))
                for esc in (False, True):
                    rep = (repair_with_scope_escalation(inst, net, b, d, rel) if esc
                           else replay_reroute(inst, net, b, d, rel))
                    dv = rep.deviation
                    rf = None if dv is None or dv.reservation_total <= 0 else \
                        dv.reservation_changed / dv.reservation_total
                    key = arm + ("x" if esc else "")
                    rows[key].append(dict(k=(name, seed), ok=rep.feasible, cmax=rep.makespan,
                                          ms=rep.wall_ms, rf=rf, share=share,
                                          lvl=rep.meta.get("rounds") if esc else None))
                    if not esc:
                        line.append(f"{arm}:{'ok' if rep.feasible else 'X'}/{share:.2f}")
            rep = repair_with_all_future(inst, net, b, d)
            dv = rep.deviation
            rows["ALL"].append(dict(k=(name, seed), ok=rep.feasible, cmax=rep.makespan,
                                    ms=rep.wall_ms, share=1.0,
                                    rf=None if dv is None else dv.reservation_changed /
                                    max(1, dv.reservation_total)))
            print("  ".join(line), flush=True)

    print()
    idx = {(a, r["k"]): r for a, rs in rows.items() for r in rs}
    keys = [r["k"] for r in rows["CL"]]
    for arm, rs in rows.items():
        ok = [r for r in rs if r["ok"]]
        print(f"{arm:<5} feas {len(ok)}/{len(rs)}  W/alive {st.mean(r['share'] for r in rs):.3f}  "
              f"Cmax {st.mean(r['cmax'] for r in ok):.1f}  ms med {st.median(r['ms'] for r in rs):.2f}  "
              f"res_frac {st.mean(r['rf'] for r in ok if r['rf'] is not None):.3f}")
    by_inst = defaultdict(lambda: defaultdict(list))
    for arm in ("CL", "SL0", "SL2", "SL5"):
        for r in rows[arm]:
            by_inst[r["k"][0]][arm].append(r["share"])
    print("\nW/alive by instance:")
    for n, dd in by_inst.items():
        print(f"  {n:<16} " + "  ".join(f"{a} {st.mean(v):.2f}" for a, v in dd.items()))
    common = [k for k in keys if all(idx[(a, k)]["ok"] for a in ("CL", "SL0", "SL2", "ALL"))]
    for a in ("SL0", "SL2", "SL5", "ALL"):
        cm = [k for k in common if idx[(a, k)]["ok"]]
        print(f"{a} vs CL on {len(cm)} common-feasible: Cmax ratio "
              f"{st.mean(idx[(a, k)]['cmax'] / idx[('CL', k)]['cmax'] for k in cm):.4f}  "
              f"d res_frac {st.mean(idx[(a, k)]['rf'] - idx[('CL', k)]['rf'] for k in cm):+.4f}")
    for a in ("CL", "SL0", "SL2", "SL5", "SL0x", "SL2x", "SL5x"):
        print(f"{a:<5} fails: {[k for k in keys if not idx[(a, k)]['ok']]}")
