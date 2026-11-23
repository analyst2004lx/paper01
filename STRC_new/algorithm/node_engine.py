"""节点模型下的任务级重规划引擎(安全区间搜索,与 clbs_new 同一下层)。

clbs_new 的下层不再逐段做时间窗 Dijkstra,而是对一次运输整体做安全区间搜索
(空载段、等件、载货段、送达后停放或离场),并维护节点占用表(路口容量 1、机器节点
容量 c、净空时距 h)。本模块在其上提供 STRC 需要的三样东西:

1. 带记录的基线解码 `decode_tracked`:与 clbs_new.decode(dispatch="exact")逐位相同,
   另记下每次运输的完整落表(走廊占用、节点停留、离场与驱离行程)。
2. 有界修复重放 `bounded_replay`:改写集 W 内的运输由原车从 t_now 的状态起重规划,
   W 外的一切原样预提交;不允许驱离 W 外的车辆。
3. 固定前缀全局重算 `prefix_decode_nodes`:只冻结 t_now 前的历史,其后全部重新派车
   (RD、GR 与 A 类故障共用)。

行程归属。离场(送达后开往库区)与驱离(停放后被他车请走)都是该车在这次运输之后、
下次运输之前的行程,一律记在这次运输名下,标签为 J{j}-{i}-leave / J{j}-{i}-evict。
于是"改写一次运输"即改写它的空载段、载货段与其后的离场或驱离,与节点停留一起。

Task-level replanning engine under the node model (safe-interval search, same lower level as
clbs_new): a tracked baseline decode, a bounded repair replay, and a fixed-prefix global
re-decode. Leave and evict trips are filed under the transport that precedes them.
"""
from __future__ import annotations

import bisect
import heapq
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from algorithm.clbs_bridge import (
    NODE_EPS,
    NODE_INF as INF,
    DecodeResult,
    Instance,
    Network,
    NodeModel,
    OpRecord,
    RoutePlan,
    Router,
    Segment,
    TaskPlan,
    TransportRecord,
    dispatch_exact_nodes,
)

EPS = 1e-9
OpKey = Tuple[int, int]
PARTS = ("empty", "loaded", "leave", "evict")


class RepairInfeasible(RuntimeError):
    pass


class EvictionForbidden(RepairInfeasible):
    pass


# --------------------------------------------------------------------------
# 运输单元与节点停留记录 / Transport units and node-stay records
# --------------------------------------------------------------------------

@dataclass
class Unit:
    key: OpKey
    agv: int
    pickup: str
    dest: str
    ready: float
    empty: RoutePlan
    loaded: RoutePlan
    leave: Optional[RoutePlan] = None
    evict: Optional[RoutePlan] = None
    evict_by: Optional[OpKey] = None

    def label(self, part: str) -> str:
        return f"J{self.key[0]}-{self.key[1]}-{part}"

    def parts(self) -> Iterator[Tuple[str, RoutePlan]]:
        yield "empty", self.empty
        yield "loaded", self.loaded
        if self.leave is not None:
            yield "leave", self.leave
        if self.evict is not None:
            yield "evict", self.evict


@dataclass
class NodeStay:
    node: str
    start: float
    end: float
    agv: int
    owner: OpKey
    closer: Optional[OpKey]   # 结束这段停留的那次运输;开放停放为 None


@dataclass
class Tracked:
    units: Dict[OpKey, Unit]
    stays: List[NodeStay]
    triggers: Dict[OpKey, List[OpKey]]   # 运输 -> 它规划时驱离的车的所属运输


class _Tracker:
    """把 TaskPlan 的落表操作按运输归属整理成 Unit 与 NodeStay。"""

    def __init__(self, model: NodeModel):
        self.model = model
        self.units: Dict[OpKey, Unit] = {}
        self.stays: List[NodeStay] = []
        self.triggers: Dict[OpKey, List[OpKey]] = {}
        self.last_unit: Dict[int, OpKey] = {}
        self._open: Dict[Tuple[str, int], int] = {}

    def add(self, key: OpKey, tplan: TaskPlan, pickup: str, dest: str,
            ready: float) -> Unit:
        k = tplan.agv
        unit = Unit(key, k, pickup, dest, ready, tplan.empty, tplan.loaded)
        for a, plan in tplan.relocations:
            if a == k:
                unit.leave = plan
            else:
                owner = self.last_unit[a]
                self.units[owner].evict = plan
                self.units[owner].evict_by = key
                self.triggers.setdefault(key, []).append(owner)
        self.units[key] = unit
        for op in tplan.ops:
            if op[0] == "nadd":
                _k, node, ts, te, a, _label = op
                if self.model.cap(node) == INF:
                    continue
                owner = key if a == k else self.last_unit[a]
                if te == INF:
                    self._open[(node, a)] = len(self.stays)
                self.stays.append(NodeStay(node, ts, te, a, owner,
                                           None if te == INF else owner))
            elif op[0] == "nclose":
                _k, node, a, end = op
                idx = self._open.pop((node, a), None)
                if idx is None:
                    continue
                self.stays[idx].end = end
                self.stays[idx].closer = key if a == k else self.last_unit[a]
        self.last_unit[k] = key
        return unit

    def result(self) -> Tracked:
        return Tracked(self.units, self.stays, self.triggers)


# --------------------------------------------------------------------------
# 路由器:降速钩子、驱离许可、驱离出发下限 / Router with slowdown hook and eviction policy
# --------------------------------------------------------------------------

class _NetView:
    """只保留给定走廊的网络视图;理想距离沿用全图,作 A* 下界仍可采纳。"""

    def __init__(self, net: Network, corridors: Set[str]):
        self._net = net
        self.adj = {n: [e for e in nbrs if e[0] in corridors] for n, nbrs in net.adj.items()}

    def __getattr__(self, name):
        return getattr(self._net, name)


@dataclass
class PlanOut:
    empty_segs: List[Segment]
    loaded_segs: List[Segment]
    t_arr_pick: float
    t_pick: float
    t_deliver: float
    mode: str
    leave: Optional[RoutePlan]
    evictions: List[Tuple[int, str, RoutePlan]]
    ops: List[tuple]


class SippRouter(Router):
    """clbs_new Router 的子类。

    tau_of 非空时走变时长的安全区间搜索(降速窗);为空时调用父类,行为逐位相同。
    evictable(x, item) 决定能否驱离机器节点 x 上的开放停放车;None 表示都可以。
    t_floor 是驱离行程的最早出发时刻:被驱离的车在 t_now 之前的停放属于历史。
    """

    def __init__(self, net: Network, model: NodeModel):
        super().__init__(net, conflict_free=True, node_model=model)
        self.tau_of: Optional[Callable[[str, float, float], float]] = None
        self.evictable: Optional[Callable[[str, tuple], bool]] = None
        self.t_floor = 0.0
        self.placeholders: Dict[int, Tuple[str, tuple]] = {}

    def _sipp(self, agv, start, t0, start_iv, pickup, ready, goal, accept,
              must_succeed=True):
        if self.tau_of is None:
            return super()._sipp(agv, start, t0, start_iv, pickup, ready, goal,
                                 accept, must_succeed)
        return _sipp_scaled(self, agv, start, t0, start_iv, pickup, ready, goal,
                            accept, must_succeed)

    def plan_ex(self, agv: int, start: str, t0: float, pickup: Optional[str],
                ready: float, dest: str, task: str, *, start_open: bool,
                route_only: Optional[Set[str]] = None) -> PlanOut:
        """从 (start, t0) 起规划并落表:必要的驱离、[空载段、等件]、载货段、停放或离场。

        pickup 为 None 时车已载货(或已送达),只剩阶段 1。
        route_only 非空时本车(含送达后的离场)只能走这些走廊,即沿原路线只改时刻;
        驱离他车的行程不受限。
        """
        assert self.nodes is not None
        model = self.nodes.model
        ops: List[tuple] = []
        evictions: List[Tuple[int, str, RoutePlan]] = []
        for x in dict.fromkeys([p for p in (pickup, dest) if p is not None]):
            if model.kinds.get(x) != "machine":
                continue
            while True:
                parked = self.nodes.open_parkers(x, exclude=agv)
                if len(parked) < model.cap(x):
                    break
                allowed = parked if self.evictable is None else [
                    it for it in parked if self.evictable(x, it)]
                if not allowed:
                    raise EvictionForbidden(
                        f"AGV{agv} {task}: would evict AGV{parked[0][2]} at {x}")
                item = min(allowed, key=lambda it: (it[0], it[2]))
                s0, _e, p_agv, _tk = item
                s0 = max(s0, self.t_floor)
                iv = self._interval_at(x, p_agv, s0)
                store, plan, _ch = self._relocate(ops, p_agv, x, s0, iv,
                                                  f"R{p_agv}-{task}", start_open=True)
                evictions.append((p_agv, store, plan))

        # 驱离行程规划时该车的占位还在,免得被驱离的车穿过它正要停靠的节点
        self.release(agv)
        start_iv = self._interval_at(start, agv, t0)
        dest_is_machine = model.kinds.get(dest) == "machine"

        def accept(node: str, iv: Tuple[float, float], t: float):
            if iv[1] == INF:
                return ("park", None)
            if not dest_is_machine:
                return None
            found = self._relocate(None, agv, node, t, iv, "", start_open=False,
                                   must_succeed=False)
            return None if found is None else ("leave", found)

        if route_only is None:
            chain, (mode, found) = self._sipp(agv, start, t0, start_iv, pickup, ready,
                                              dest, accept)
        else:
            full, self.net = self.net, _NetView(self.net, route_only)
            try:
                chain, (mode, found) = self._sipp(agv, start, t0, start_iv, pickup, ready,
                                                  dest, accept)
            finally:
                self.net = full
        self._commit_chain(ops, agv, chain, task, start_open=start_open,
                           end_open=(mode == "park"))
        if pickup is not None:
            switch = next(i for i in range(1, len(chain)) if chain[i][5] is None)
            empty_segs = [c[5] for c in chain[1:switch] if c[5] is not None]
            loaded_segs = [c[5] for c in chain[switch + 1:] if c[5] is not None]
            t_arr_pick = chain[switch - 1][3]
            t_pick = chain[switch][3]
        else:
            empty_segs = []
            loaded_segs = [c[5] for c in chain[1:] if c[5] is not None]
            t_arr_pick = t_pick = t0
        leave = None
        if mode == "leave":
            _store, plan, rchain = found
            # 链只有起点一个节点时,该车在 dest 上的停留仍是开放的,离场要收口它而不是另记一段
            single = start_open and all(c[5] is None for c in chain)
            self._commit_chain(ops, agv, rchain, f"R{agv}-{task}", start_open=single,
                               end_open=False)
            leave = plan
        return PlanOut(empty_segs, loaded_segs, t_arr_pick, t_pick, chain[-1][3],
                       mode, leave, evictions, ops)

    def plan_task(self, agv: int, loc: str, avail: float, pickup: str, dest: str,
                  ready: float, task: str) -> TaskPlan:
        """与 clbs_new Router.plan_task 同义,但遵守 evictable 与 t_floor。"""
        assert self.nodes is not None
        start_open = any(it[2] == agv for it in self.nodes.open_parkers(loc))
        po = self.plan_ex(agv, loc, avail, pickup, ready, dest, task,
                          start_open=start_open)
        empty = self._plan_from(loc, pickup, avail, po.t_arr_pick, po.empty_segs)
        loaded = self._plan_from(pickup, dest, po.t_pick, po.t_deliver, po.loaded_segs)
        relocs: List[Tuple[int, RoutePlan]] = []
        state: Dict[int, Tuple[str, float]] = {}
        for p_agv, store, plan in po.evictions:
            relocs.append((p_agv, plan))
            state[p_agv] = (store, plan.arrive)
        if po.leave is not None:
            relocs.append((agv, po.leave))
            state[agv] = (po.leave.goal, po.leave.arrive)
        else:
            state[agv] = (dest, po.t_deliver)
        return TaskPlan(agv, empty, loaded, relocs, po.ops, state)

    def relocate_from(self, agv: int, node: str, t0: float, task: str,
                      start_open: bool = True) -> RoutePlan:
        iv = self._interval_at(node, agv, t0)
        _store, plan, _ch = self._relocate([], agv, node, t0, iv, task,
                                           start_open=start_open)
        return plan

    def hold_until(self, node: str, agv: int, ts: float, te: float, label: str) -> None:
        """占位:该车按原计划停在 node 上到 te;轮到它重规划时先 release 再搜索。"""
        nodes = self.nodes
        assert nodes is not None
        if nodes.model.cap(node) == INF or te <= ts + EPS:
            return
        item = (ts, te, agv, label)
        nodes._add(node, item)
        self.placeholders[agv] = (node, item)

    def release(self, agv: int) -> None:
        got = self.placeholders.pop(agv, None)
        if got is not None:
            self.nodes._remove(got[0], got[1])   # type: ignore[union-attr]

    def hold_open(self, node: str, agv: int, since: float, label: str) -> None:
        """登记该车自 since 起停在 node 上、离开时刻待定(开放停留)。

        可能与他车后来的预提交停留在表里叠加超容:那正是该车必须赶在其前离开的约束,
        安全区间搜索对该车本身不计自己的停留,对其他车则保守地视为占满。
        """
        nodes = self.nodes
        assert nodes is not None
        if nodes.model.cap(node) == INF:
            return
        if any(it[2] == agv for it in nodes.open_parkers(node)):
            return
        nodes._add(node, (since, INF, agv, label))


def _entry_scaled(router: SippRouter, cid: str, lower: float, dep_hi: float,
                  tau0: float, arr_hi: float) -> Optional[Tuple[float, float]]:
    table = router.table
    for cand in table._entry_candidates(cid, lower):
        if cand > dep_hi + NODE_EPS:
            return None
        tau = router.tau_of(cid, cand, tau0)   # type: ignore[misc]
        if cand + tau > arr_hi + NODE_EPS:
            # 降速按进度积分,先进者先出,更晚进入只会更晚到达
            return None
        if table._is_free(cid, cand, tau):
            return cand, tau
    return None


def _sipp_scaled(self: SippRouter, agv, start, t0, start_iv, pickup, ready, goal,
                 accept, must_succeed=True):
    """Router._sipp 的变时长版本:进入时刻与该时刻的有效通行时长一并确定。"""
    assert self.nodes is not None
    Router.total_route_calls += 1
    pool: List[tuple] = []
    best: Dict[Tuple[str, float, int], float] = {}
    heap: list = []
    dist = self.net.ideal_dist
    to_goal = dist[goal] if goal in dist else {}
    d_pg = dist[pickup][goal] if pickup is not None else 0.0

    def f_key(node, ph, t):
        if ph == 0:
            rem = dist[node][pickup] + d_pg
            return max(t + dist[node][pickup], ready) + d_pg, rem
        rem = to_goal.get(node, 0.0)
        return t + rem, rem

    def push(node, iv, ph, t, parent, seg):
        key = (node, iv[0], ph)
        if t < best.get(key, INF) - NODE_EPS:
            best[key] = t
            pool.append((node, iv, ph, t, parent, seg))
            heapq.heappush(heap, (f_key(node, ph, t), t, node, ph, len(pool) - 1))
            return len(pool) - 1
        return -1

    siblings: Dict[int, tuple] = {}
    need_of = self.nodes.need_of
    safe = self.nodes.safe_intervals

    def expand_edge(parent, cid, v, tau0, first, ivs=None):
        node, iv_p, ph, t, _p, _s = pool[parent]
        dep_hi = iv_p[1] - need_of[node]
        need_v = need_of[v]
        if ivs is None:
            ivs = safe(v, agv)
        for n in range(first, len(ivs)):
            lo2, hi2 = ivs[n]
            lower = max(t, lo2 - tau0)
            if lower > dep_hi + NODE_EPS:
                return
            res = _entry_scaled(self, cid, lower, dep_hi, tau0, hi2 - need_v)
            if res is None:
                continue
            dep, tau = res
            child = push(v, ivs[n], ph, dep + tau, parent, (cid, node, v, dep, dep + tau))
            if child >= 0:
                siblings[child] = (parent, cid, v, tau0, n + 1)
                return

    push(start, start_iv, 0 if pickup is not None else 1, t0, -1, None)
    expanded = 0
    while heap:
        _f, _t, _n, _p, idx = heapq.heappop(heap)
        sib = siblings.pop(idx, None)
        if sib is not None:
            expand_edge(*sib)
        node, iv, ph, t, _parent, _seg = pool[idx]
        if t > best[(node, iv[0], ph)] + NODE_EPS:
            continue
        expanded += 1
        if expanded > self.label_budget * 50:
            break
        if ph == 0 and node == pickup:
            tp = max(t, ready)
            if tp + need_of[node] <= iv[1] + NODE_EPS:
                push(node, iv, 1, tp, idx, None)
        if ph == 1 and node == goal:
            res = accept(node, iv, t)
            if res is not None:
                chain = []
                k = idx
                while k >= 0:
                    n_, iv_, ph_, t_, p_, s_ = pool[k]
                    chain.append((n_, iv_, ph_, t_, p_,
                                  Segment(*s_) if s_ is not None else None))
                    k = p_
                chain.reverse()
                return chain, res
        if iv[1] - need_of[node] < t - NODE_EPS:
            continue
        for cid, v, tau in self.net.adj[node]:
            ivs = safe(v, agv)
            first = bisect.bisect_right(ivs, (t + tau, INF)) - 1 if len(ivs) > 1 else 0
            expand_edge(idx, cid, v, tau, max(0, first), ivs)
    if must_succeed:
        raise RuntimeError(f"任务路由失败: AGV{agv} {start}->{pickup}->{goal}")
    return None


def make_router(inst: Instance, net: Network, dist=None) -> SippRouter:
    router = SippRouter(net, NodeModel.from_instance(inst))
    if dist is not None:
        from algorithm.block_context import attach_slowdown
        attach_slowdown(router, dist)
    return router


# --------------------------------------------------------------------------
# 带记录的基线解码 / Tracked baseline decode
# --------------------------------------------------------------------------

def _process_op(inst, ops, free, last_on, pos, ready, j, i, m, dest, p, arrive, pseudo):
    if pseudo:
        start = finish = arrive
        bind, mprev = "arrive", None
    else:
        mf = free[m]
        bind = "machine" if mf > arrive else "arrive"
        start = max(arrive, mf)
        finish = start + p
        mprev = last_on.get(m)
        free[m] = finish
        last_on[m] = (j, i)
    ops[(j, i)] = OpRecord(j, i, m, arrive, start, finish, bind, mprev, pseudo)
    pos[j], ready[j] = dest, finish


def _op_target(inst: Instance, ma, j: int, i: int):
    if inst.is_pseudo(j, i):
        return None, inst.out_node, 0.0, True
    m = ma[(j, i)]
    return m, inst.machine_node[m], inst.proc_time[(j, i)][m], False


def _result(inst: Instance, ops, units: List[Unit], dispatch_order) -> DecodeResult:
    makespan = max(r.finish for r in ops.values())
    transports = [TransportRecord(u.key[0], u.key[1], u.agv, u.pickup, u.dest, u.ready,
                                  u.empty, u.loaded) for u in units]
    relocs: List[Tuple[int, RoutePlan]] = []
    for u in units:
        if u.leave is not None:
            relocs.append((u.agv, u.leave))
        if u.evict is not None:
            relocs.append((u.agv, u.evict))
    res = DecodeResult(inst, makespan, ops, transports, list(dispatch_order), {}, True,
                       0.0, {}, relocs)
    res.strc_units = units   # type: ignore[attr-defined]
    return res


def decode_tracked(inst: Instance, net: Network, ma, os_seq) -> Tuple[DecodeResult, Tracked]:
    """与 clbs_new decode(dispatch="exact", 节点模型)同一过程,另记下每次运输的落表。"""
    model = NodeModel.from_instance(inst)
    router = SippRouter(net, model)
    tracker = _Tracker(model)
    free = {m: 0.0 for m in inst.machine_node}
    last_on: Dict[int, OpKey] = {}
    pos = {j: inst.lu_node for j in inst.job_ids}
    ready = {j: 0.0 for j in inst.job_ids}
    loc = {k: inst.lu_node for k in range(1, inst.num_agvs + 1)}
    avail = {k: 0.0 for k in loc}
    counter = {j: 0 for j in inst.job_ids}
    ops: Dict[OpKey, OpRecord] = {}
    order: List[int] = []
    for j in os_seq:
        counter[j] += 1
        i = counter[j]
        m, dest, p, pseudo = _op_target(inst, ma, j, i)
        if pos[j] == dest:
            arrive = ready[j]
        else:
            pickup = pos[j]
            k, tplan = dispatch_exact_nodes(router, net, loc, dict(avail), pickup, dest,
                                            ready[j], f"J{j}-{i}", prune=True, reuse=True)
            router.replay(tplan)
            order.append(k)
            tracker.add((j, i), tplan, pickup, dest, ready[j])
            for kk, (where, when) in tplan.state.items():
                loc[kk], avail[kk] = where, when
            arrive = tplan.loaded.arrive
        _process_op(inst, ops, free, last_on, pos, ready, j, i, m, dest, p, arrive, pseudo)
    tracked = tracker.result()
    return _result(inst, ops, list(tracked.units.values()), order), tracked


# --------------------------------------------------------------------------
# t_now 时刻各车状态 / Vehicle snapshot at t_now
# --------------------------------------------------------------------------

@dataclass
class Snap:
    node: str
    since: float
    key: Optional[OpKey]
    part: Optional[str]
    in_progress: bool


def snapshot(tracked: Tracked, t_now: float, inst: Instance) -> Dict[int, Snap]:
    """每辆车在 t_now 之后可以重新决策的位置与时刻,以及所处运输。

    t_now 时已驶入的走廊段走完(车不能在走廊中途折返,也不能退回已让给后车的路口),
    故决策点是最后一条已开始走廊段的终点,时刻为其驶出时刻(可能晚于 t_now)。
    """
    legs: Dict[int, List[Tuple[Segment, OpKey, str]]] = {}
    for key, u in tracked.units.items():
        for part, plan in u.parts():
            for s in plan.segments:
                legs.setdefault(u.agv, []).append((s, key, part))
    out: Dict[int, Snap] = {}
    for k in range(1, inst.num_agvs + 1):
        lst = sorted(legs.get(k, []), key=lambda x: x[0].enter)
        started = [n for n, x in enumerate(lst) if x[0].enter < t_now - EPS]
        if not started:
            out[k] = Snap(inst.lu_node, 0.0, None, None, False)
            continue
        s, key, part = lst[started[-1]]
        out[k] = Snap(s.v, s.exit, key, part, s.exit > t_now + EPS)
    return out


def _started(s: Segment, t_now: float) -> bool:
    return s.enter < t_now - EPS


def _all_started(plan: Optional[RoutePlan], t_now: float) -> bool:
    return plan is not None and bool(plan.segments) and _started(plan.segments[-1], t_now)


def _effective_blocks(dist, units) -> List[Tuple[str, float, float]]:
    from algorithm.block_context import effective_block_windows
    from algorithm.closure import ReservationRef
    refs = [ReservationRef(s.corridor, s.enter, s.exit, u.agv, u.label(part))
            for u in units for part, plan in u.parts() for s in plan.segments]
    return effective_block_windows(dist, refs)


def _fill_stay(router: SippRouter, node: str, agv: int, since: float, t0: float,
               label: str) -> None:
    """保证节点表里该车自 since 起连续停在 node 上直到 t0(改路从 t0 接着走)。"""
    nodes = router.nodes
    assert nodes is not None
    if nodes.model.cap(node) == INF or t0 <= since + EPS:
        return
    own = [it for it in nodes.all_occupancy().get(node, ())
           if it[2] == agv and it[0] >= since - EPS and it[0] <= t0 + EPS]
    lo = max((it[1] for it in own), default=since)
    if lo >= t0 - EPS:
        return
    try:
        nodes.reserve(node, lo, t0, agv, label)
    except AssertionError as e:
        raise RepairInfeasible(f"AGV{agv} cannot hold {node} until {t0}: {e}")


def _reserve_node(router: SippRouter, node: str, ts: float, te: float, agv: int,
                  label: str) -> None:
    try:
        router.nodes.reserve(node, ts, te, agv, label)   # type: ignore[union-attr]
    except AssertionError as e:
        raise RepairInfeasible(f"node precommit {label}@{node}: {e}")


def _join(old: RoutePlan, keep: List[Segment], new: RoutePlan) -> RoutePlan:
    return RoutePlan(old.start, new.goal, old.t0, new.arrive, list(keep) + list(new.segments),
                     dict(new.wait_by_corridor), 0.0)


def _done(plan: Optional[RoutePlan], t_now: float) -> List[Segment]:
    """已开始(含进行中)的走廊段:它们不再改写。"""
    if plan is None:
        return []
    return [s for s in plan.segments if _started(s, t_now)]


# --------------------------------------------------------------------------
# 有界修复重放 / Bounded repair replay
# --------------------------------------------------------------------------

def _tag_plan(key: OpKey, fn, *args, **kwargs):
    """规划失败时把出错的运输记在异常上,供上层按它调整规划次序后重试。"""
    try:
        return fn(*args, **kwargs)
    except EvictionForbidden:
        raise
    except (RuntimeError, RepairInfeasible) as e:
        err = RepairInfeasible(f"{key}: {e}")
        err.key = key   # type: ignore[attr-defined]
        raise err from e


def bounded_replay(inst: Instance, net: Network, tracked: Tracked, ma, os_seq,
                   dist, rewrite: Set[OpKey], *, early: Sequence[OpKey] = (),
                   base_ops: Optional[Dict[OpKey, OpRecord]] = None,
                   replan: Optional[Set[OpKey]] = None,
                   store_wait: bool = False) -> DecodeResult:
    """W = rewrite 内的运输由原车从 t_now 状态起重规划,W 外原样预提交。

    early 中的运输若出发状态与工件就绪时刻在 t_now 已经确定,就先于 OS 序回放规划
    (一轮失败后,把卡住的运输提前再试一次);需要 base_ops 判断前道工序是否已开工。

    replan 为 None 时 W 内全部在全图上搜索。否则只有 replan 内的运输在全图上搜索,
    W 内其余运输先只沿原路线的走廊搜索(路线不变、只改时刻),搜不到才升级为全图搜索;
    升级者记在结果的 strc_promoted 上。store_wait 为真时,原路线上各节点到最近库区的
    最短支路也可走:延误长时车可以进库等,而路口与机器节点上的等待会挡住别的车。

    W 内运输已开始的走廊段(含进行中的)不改写,重规划从最后一段的终点接着走。
    节点停留随运输走:W 外运输的停留原样保留;若结束它的下一次运输在 W 内且尚未出发,
    该停留改为开放,由重规划后的出发收口。W 内运输的停留只保留已经确定的部分。
    驱离只许针对本次修复中新停下的车(其停放属于 W);要驱离 W 外的车即判本轮失败。
    """
    t_now = float(dist.t_now)
    router = make_router(inst, net, dist)
    router.t_floor = t_now
    model = router.nodes.model   # type: ignore[union-attr]
    units = tracked.units
    W = {k for k in rewrite if k in units}

    blocks = _effective_blocks(dist, units.values())
    for cid, a, b in blocks:
        router.table.reserve(cid, a, b, 0, "__BLOCK__")
    for key, u in units.items():
        rw = key in W
        for part, plan in u.parts():
            for s in plan.segments:
                if rw and not _started(s, t_now):
                    continue
                for cid, a, b in blocks:
                    if s.corridor == cid and s.enter < b - EPS and s.exit > a + EPS:
                        raise RepairInfeasible(
                            f"frozen overlaps block: {u.label(part)}@{cid}"
                            f"[{s.enter},{s.exit})")
                try:
                    router.table.reserve(s.corridor, s.enter, s.exit, u.agv, u.label(part))
                except AssertionError as e:
                    raise RepairInfeasible(f"precommit {u.label(part)}: {e}")

    snaps = snapshot(tracked, t_now, inst)
    opened: List[NodeStay] = []
    for st in tracked.stays:
        label = f"J{st.owner[0]}-{st.owner[1]}"
        departed = st.end != INF and st.end - model.need(st.node) < t_now - EPS
        if st.owner in W:
            if departed:
                _reserve_node(router, st.node, st.start, st.end, st.agv, label)
                continue
            sn = snaps[st.agv]
            if sn.node != st.node or st.start > sn.since + EPS:
                continue
            # 车此刻(或进行中的一段到达后)停在这里:t_now 前是历史,其后按原计划占位,
            # 轮到该运输重规划时释放,免得 OS 序上先轮到的运输占走这个节点
            if st.start < t_now - EPS:
                _reserve_node(router, st.node, st.start, t_now, st.agv, label)
            router.hold_until(st.node, st.agv, max(st.start, t_now), st.end, label)
            continue
        if (st.end != INF and not departed and st.closer is not None
                and st.closer != st.owner and st.closer in W):
            opened.append(st)
            continue
        _reserve_node(router, st.node, st.start, st.end, st.agv, label)
    # 停留属于 W 外运输、但结束它的下一次运输在 W 内:该车下一次离开本就在重规划之列,
    # 可以被驱离;驱离行程记作那次运输空驶段的开头,W 外预约不变。
    opened_at: Dict[Tuple[int, str], OpKey] = {}
    for st in opened:
        router.hold_open(st.node, st.agv, st.start, f"J{st.owner[0]}-{st.owner[1]}")
        opened_at[(st.agv, st.node)] = st.closer   # type: ignore[assignment]
    detour: Dict[OpKey, RoutePlan] = {}

    repair_open: Dict[int, str] = {}
    router.evictable = lambda x, item: (repair_open.get(item[2]) == x
                                        or (item[2], x) in opened_at)

    free = {m: 0.0 for m in inst.machine_node}
    last_on: Dict[int, OpKey] = {}
    pos = {j: inst.lu_node for j in inst.job_ids}
    ready = {j: 0.0 for j in inst.job_ids}
    loc = {k: inst.lu_node for k in range(1, inst.num_agvs + 1)}
    avail = {k: 0.0 for k in loc}
    counter = {j: 0 for j in inst.job_ids}
    ops: Dict[OpKey, OpRecord] = {}
    out: Dict[OpKey, Unit] = {}
    last_unit: Dict[int, OpKey] = {}
    order: List[int] = []

    # 已载货(或送达后待定、离场途中)的车不再依赖任何工件就绪时刻,其余路线先于 OS 序
    # 回放规划;否则 OS 序上先轮到的运输会按它的原离开时刻安排,而阻断可能使它走不了。
    # 簿记(位置、工序)仍在 OS 序轮到它时落账。
    pre: Dict[OpKey, Tuple[Unit, Optional[PlanOut]]] = {}
    pre_agv: Dict[int, OpKey] = {}
    promoted: Set[OpKey] = set()
    spur: Dict[str, Set[str]] = {}

    def store_spur(n: str) -> Set[str]:
        if n not in spur:
            spur[n] = set(net.shortest_path_corridors(n, router._nearest_store(n)))
        return spur[n]

    def route_plan(key: OpKey, *args, **kwargs) -> PlanOut:
        if replan is None or key in replan:
            return router.plan_ex(*args, **kwargs)
        segs = [s for _p, pl in units[key].parts() for s in pl.segments]
        keep = {s.corridor for s in segs}
        if store_wait:
            for n in {args[1], units[key].empty.start} | {s.u for s in segs} | {s.v for s in segs}:
                keep |= store_spur(n)
        token, held = router.checkpoint(), dict(router.placeholders)
        try:
            return router.plan_ex(*args, route_only=keep, **kwargs)
        except RuntimeError:
            router.rollback(token)
            router.placeholders = held
            promoted.add(key)
            return router.plan_ex(*args, **kwargs)

    def apply_evictions(key: OpKey, evictions) -> None:
        for p_agv, store, plan in evictions:
            repair_open.pop(p_agv, None)
            closer = opened_at.pop((p_agv, plan.start), None)
            if closer is not None:
                detour[closer] = plan
                continue
            if p_agv in pre_agv:
                pk = pre_agv[p_agv]
                unit, po = pre[pk]
                pre[pk] = (replace(unit, evict=plan, evict_by=key), po)
                continue
            owner = last_unit[p_agv]
            out[owner] = replace(out[owner], evict=plan, evict_by=key)
            loc[p_agv], avail[p_agv] = store, plan.arrive

    def settle(unit: Unit, po: Optional[PlanOut]) -> None:
        k = unit.agv
        if unit.evict is not None:
            loc[k], avail[k] = unit.evict.goal, unit.evict.arrive
        elif po is None:
            trip = unit.leave
            loc[k], avail[k] = trip.goal, trip.arrive   # type: ignore[union-attr]
        elif po.mode == "park":
            loc[k], avail[k] = unit.dest, po.t_deliver
        else:
            loc[k], avail[k] = po.leave.goal, po.leave.arrive   # type: ignore[union-attr]

    def finish_plan(key: OpKey, unit: Unit, po: PlanOut) -> None:
        apply_evictions(key, po.evictions)
        if po.mode == "park":
            repair_open[unit.agv] = unit.dest
        else:
            unit.leave = po.leave
            repair_open.pop(unit.agv, None)
        settle(unit, po)

    def known_ready(key: OpKey) -> Optional[float]:
        """前道工序已在 t_now 前开工时,工件就绪时刻已经确定。"""
        j, i = key
        if i == 1:
            return 0.0
        rec = (base_ops or {}).get((j, i - 1))
        if rec is None or rec.start >= t_now - EPS:
            return None
        return rec.finish

    def known_start(key: OpKey) -> Optional[Tuple[str, float]]:
        """该车此前的运输都在 W 外或已提前规划时,它出发的位置与时刻已经确定。"""
        k = units[key].agv
        where, when = inst.lu_node, 0.0
        for kk, uu in units.items():
            if uu.agv != k:
                continue
            if kk == key:
                return where, when
            if kk in pre:
                unit, po = pre[kk]
                last = unit.evict or unit.leave
                if last is not None:
                    where, when = last.goal, last.arrive
                else:
                    where, when = unit.dest, po.t_deliver if po else unit.loaded.arrive
            elif kk in W:
                return None
            else:
                last = uu.evict or uu.leave
                where, when = (last.goal, last.arrive) if last is not None \
                    else (uu.dest, uu.loaded.arrive)
        return None

    def plan_early(key: OpKey, phase0: bool) -> None:
        u0 = units[key]
        k = u0.agv
        snap = snaps[k]
        label = f"J{key[0]}-{key[1]}"
        t0 = max(snap.since, t_now)
        po: Optional[PlanOut] = None
        start_open = False
        if snap.key == key and snap.part in ("leave", "evict"):
            trip = u0.leave if snap.part == "leave" else u0.evict
            if _all_started(trip, t_now):
                unit = replace(u0)
            else:
                router.release(k)
                _fill_stay(router, snap.node, k, snap.since, t0, label)
                new = router.relocate_from(k, snap.node, t0, f"R{k}-{label}",
                                           start_open=False)
                unit = replace(u0, **{snap.part: _join(trip, _done(trip, t_now), new)})
            if snap.part == "leave":
                unit.evict = None
            pre[key] = (unit, po)
            pre_agv[k] = key
            return
        if snap.key == key and not phase0:
            _fill_stay(router, snap.node, k, snap.since, t0, label)
            po = route_plan(key, k, snap.node, t0, None, 0.0, u0.dest, label,
                            start_open=False)
            loaded = (u0.loaded if _all_started(u0.loaded, t_now) and not po.loaded_segs
                      else _join(u0.loaded, _done(u0.loaded, t_now),
                                 router._plan_from(snap.node, u0.dest, t0, po.t_deliver,
                                                   po.loaded_segs)))
            unit = Unit(key, k, u0.pickup, u0.dest, u0.ready, u0.empty, loaded)
        else:
            rdy = known_ready(key)
            if snap.key == key:
                _fill_stay(router, snap.node, k, snap.since, t0, label)
                start = snap.node
            else:
                start, when = known_start(key)   # type: ignore[misc]
                t0 = max(when, t_now)
                start_open = any(it[2] == k for it in router.nodes.open_parkers(start))
            po = route_plan(key, k, start, t0, u0.pickup, rdy, u0.dest, label,
                            start_open=start_open)
            empty = router._plan_from(start, u0.pickup, t0, po.t_arr_pick, po.empty_segs)
            if snap.key == key:
                empty = _join(u0.empty, _done(u0.empty, t_now), empty)
            loaded = router._plan_from(u0.pickup, u0.dest, po.t_pick, po.t_deliver,
                                       po.loaded_segs)
            unit = Unit(key, k, u0.pickup, u0.dest, rdy, empty, loaded)   # type: ignore[arg-type]
        apply_evictions(key, po.evictions)
        if start_open:
            repair_open.pop(k, None)
        if po.mode == "park":
            repair_open[k] = u0.dest
        else:
            unit.leave = po.leave
        pre[key] = (unit, po)
        pre_agv[k] = key

    def plan_flagged() -> None:
        for key in early:
            if key not in W or key in pre or known_ready(key) is None:
                continue
            snap = snaps[units[key].agv]
            if snap.key != key and known_start(key) is None:
                continue
            _tag_plan(key, plan_early, key, not (snap.key == key and snap.part != "empty"))

    # 被标记的运输排在在途件之前:在途件的新路线常会占掉它离开当前节点的唯一时段;
    # 起点要等在途件定下才知道的,在途件之后再试一次
    plan_flagged()
    for key, u0 in units.items():
        snap = snaps[u0.agv]
        if key in W and key not in pre and snap.key == key and snap.part != "empty":
            _tag_plan(key, plan_early, key, False)
    plan_flagged()

    for j in os_seq:
        counter[j] += 1
        i = counter[j]
        m, dest, p, pseudo = _op_target(inst, ma, j, i)
        key = (j, i)
        if pos[j] == dest:
            arrive = ready[j]
        else:
            u0 = units.get(key)
            if u0 is None or u0.dest != dest or u0.pickup != pos[j]:
                raise RepairInfeasible(f"{key}: transport differs from baseline")
            for owner in tracked.triggers.get(key, ()):
                if owner in W:
                    continue
                ou = units[owner]
                loc[ou.agv], avail[ou.agv] = ou.evict.goal, ou.evict.arrive  # type: ignore[union-attr]
            k = u0.agv
            order.append(k)
            label = f"J{j}-{i}"
            if key not in W:
                legs = u0.empty.segments + u0.loaded.segments
                if loc[k] != u0.empty.start:
                    raise RepairInfeasible(
                        f"frozen {key}: AGV{k} at {loc[k]}, unit starts at {u0.empty.start}")
                if avail[k] > legs[0].enter + EPS:
                    raise RepairInfeasible(
                        f"frozen {key}: AGV{k} free at {avail[k]:.2f} > departure {legs[0].enter:.2f}")
                if ready[j] > u0.loaded.t0 + EPS:
                    raise RepairInfeasible(f"frozen {key}: loads before the job is ready")
                if k not in pre_agv and repair_open.pop(k, None) is not None:
                    router.nodes.close_open(loc[k], k, legs[0].enter + model.need(loc[k]))
                out[key] = replace(u0)
                if u0.leave is not None:
                    loc[k], avail[k] = u0.leave.goal, u0.leave.arrive
                else:
                    loc[k], avail[k] = dest, u0.loaded.arrive
                arrive = u0.loaded.arrive
            else:
                snap = snaps[k]
                pickup = u0.pickup
                t0 = max(snap.since, t_now)
                if key in pre:
                    unit, po = pre.pop(key)
                    if pre_agv.get(k) == key:
                        del pre_agv[k]
                    settle(unit, po)
                elif snap.key == key:
                    _fill_stay(router, snap.node, k, snap.since, t0, label)
                    po = _tag_plan(key, route_plan, key, k, snap.node, t0, pickup, ready[j],
                                   dest, label, start_open=False)
                    empty = _join(u0.empty, _done(u0.empty, t_now),
                                  router._plan_from(snap.node, pickup, t0,
                                                    po.t_arr_pick, po.empty_segs))
                    loaded = router._plan_from(pickup, dest, po.t_pick, po.t_deliver,
                                               po.loaded_segs)
                    unit = Unit(key, k, pickup, dest, ready[j], empty, loaded)
                    finish_plan(key, unit, po)
                else:
                    pre_move = detour.pop(key, None)
                    if pre_move is not None:
                        start, t0 = pre_move.goal, max(pre_move.arrive, t_now)
                    else:
                        start, t0 = loc[k], max(avail[k], t_now)
                    start_open = any(it[2] == k for it in router.nodes.open_parkers(start))
                    po = _tag_plan(key, route_plan, key, k, start, t0, pickup, ready[j], dest,
                                   label, start_open=start_open)
                    if start_open:
                        repair_open.pop(k, None)
                    empty = router._plan_from(start, pickup, t0, po.t_arr_pick, po.empty_segs)
                    if pre_move is not None:
                        empty = _join(pre_move, pre_move.segments, empty)
                    loaded = router._plan_from(pickup, dest, po.t_pick, po.t_deliver,
                                               po.loaded_segs)
                    unit = Unit(key, k, pickup, dest, ready[j], empty, loaded)
                    finish_plan(key, unit, po)
                out[key] = unit
                arrive = unit.loaded.arrive
            last_unit[k] = key
        _process_op(inst, ops, free, last_on, pos, ready, j, i, m, dest, p, arrive, pseudo)
    res = _result(inst, ops, list(out.values()), order)
    res.strc_promoted = promoted   # type: ignore[attr-defined]
    return res


# --------------------------------------------------------------------------
# 固定前缀全局重算 / Fixed-prefix global re-decode
# --------------------------------------------------------------------------

def _dummy(inst: Instance, err: str = "") -> DecodeResult:
    res = DecodeResult(inst, 1e18, {}, [], [], {}, True, 0.0, {})
    res.strc_units = []          # type: ignore[attr-defined]
    res.strc_error = err         # type: ignore[attr-defined]
    return res


def prefix_decode_nodes(inst: Instance, net: Network, ma, os_seq, tracked: Tracked,
                        base: DecodeResult, dist, *, dead_agv: Optional[int] = None,
                        dead_machine: Optional[int] = None) -> DecodeResult:
    try:
        return _prefix_decode(inst, net, ma, os_seq, tracked, base, dist,
                              dead_agv, dead_machine)
    except (RepairInfeasible, RuntimeError, AssertionError, KeyError,
            StopIteration) as e:
        return _dummy(inst, f"{type(e).__name__}: {e}")


def _prefix_decode(inst, net, ma, os_seq, tracked: Tracked, base: DecodeResult, dist,
                   dead_agv, dead_machine) -> DecodeResult:
    """只冻结 t_now 前的历史,其后重新派车;允许驱离(全局重算不设边界)。

    t_now 时各车分三类:空闲(停在某处,可派)、承诺中(正执行一次运输,必须由原车
    完成,完成前不参与派车)、行程中(离场或驱离途中,先开到库区)。故障车自 t_now
    起离开路网,它承担的运输改由他车从取货点重新执行。
    """
    t_now = float(dist.t_now)
    router = make_router(inst, net, dist)
    router.t_floor = t_now
    model = router.nodes.model
    units = tracked.units

    for cid, a, b in _effective_blocks(dist, units.values()):
        router.table.reserve(cid, a, b, 0, "__BLOCK__")
    for u in units.values():
        for part, plan in u.parts():
            for s in plan.segments:
                if _started(s, t_now):
                    router.table.reserve(s.corridor, s.enter, s.exit, u.agv, u.label(part))

    snaps = snapshot(tracked, t_now, inst)
    kind: Dict[int, str] = {}
    for k, sn in snaps.items():
        if k == dead_agv:
            kind[k] = "dead"
        elif sn.key is None:
            kind[k] = "idle"
        elif sn.part == "empty":
            kind[k] = "task"
        elif sn.part == "loaded":
            u = units[sn.key]
            # 末段已在途但尚未送达:送达后停放还是离场仍待决定,按承诺处理
            kind[k] = "idle" if u.loaded.arrive <= t_now + EPS else "task"
        elif _all_started(units[sn.key].leave if sn.part == "leave"
                          else units[sn.key].evict, t_now):
            kind[k] = "idle"
        else:
            kind[k] = "trip"

    opened = []
    for st in tracked.stays:
        label = f"J{st.owner[0]}-{st.owner[1]}"
        if st.end != INF and st.end - model.need(st.node) < t_now - EPS:
            _reserve_node(router, st.node, st.start, st.end, st.agv, label)
            continue
        sn = snaps[st.agv]
        here = sn.node == st.node and st.start <= sn.since + EPS
        if st.start >= t_now - EPS:
            # 进行中一段的到达:承诺中/行程中的车按原计划占位,等轮到它时释放
            if here and kind[st.agv] in ("task", "trip"):
                router.hold_until(st.node, st.agv, st.start, st.end, label)
            continue
        if kind[st.agv] == "idle" and here:
            opened.append((st, label))
            continue
        _reserve_node(router, st.node, st.start, t_now, st.agv, label)
        if here and kind[st.agv] in ("task", "trip"):
            router.hold_until(st.node, st.agv, t_now, st.end, label)
    for st, label in opened:
        router.hold_open(st.node, st.agv, st.start, label)
    router.evictable = lambda x, item: item[2] not in pending.values()

    fixed: Set[OpKey] = set()
    for key, rec in base.ops.items():
        if rec.start <= t_now + EPS and not (
                dead_machine is not None and rec.machine == dead_machine
                and rec.finish > t_now + EPS):
            fixed.add(key)
    abort: Set[OpKey] = set()
    delivered: Dict[OpKey, float] = {}
    for key, u in units.items():
        if key in fixed or u.loaded.arrive > t_now + EPS:
            continue
        if dead_machine is not None and base.ops[key].machine == dead_machine:
            abort.add(key)
        else:
            delivered[key] = u.loaded.arrive

    out: List[Unit] = []
    last_unit: Dict[int, Unit] = {}
    pending: Dict[OpKey, int] = {}
    for key, u in units.items():
        if u.loaded.arrive <= t_now + EPS:
            def hist(trip):
                if trip is None or trip.segments[0].enter >= t_now - EPS:
                    return None
                return trip
            nu = replace(u, leave=hist(u.leave), evict=hist(u.evict))
            out.append(nu)
            if snaps[u.agv].key == key:
                last_unit[u.agv] = nu
    for k, sn in snaps.items():
        if kind[k] == "task":
            pending[sn.key] = k   # type: ignore[index]
        elif kind[k] == "dead" and sn.key is not None:
            u = units[sn.key]
            if u.loaded.arrive > t_now + EPS:
                stub_e, stub_l = _done(u.empty, t_now), _done(u.loaded, t_now)
                if stub_e or stub_l:
                    out.append(replace(
                        u,
                        empty=RoutePlan(u.empty.start, stub_e[-1].v if stub_e else u.pickup,
                                        u.empty.t0, stub_e[-1].exit if stub_e else u.empty.t0,
                                        stub_e, {}, 0.0),
                        loaded=RoutePlan(u.pickup, stub_l[-1].v if stub_l else u.pickup,
                                         u.loaded.t0,
                                         stub_l[-1].exit if stub_l else u.loaded.t0,
                                         stub_l, {}, 0.0),
                        leave=None, evict=None))

    loc: Dict[int, str] = {}
    avail: Dict[int, float] = {}
    for k, sn in snaps.items():
        if kind[k] in ("idle", "task", "trip"):
            loc[k], avail[k] = sn.node, max(sn.since, t_now)

    free = {m: 0.0 for m in inst.machine_node}
    last_on: Dict[int, OpKey] = {}
    pos = {j: inst.lu_node for j in inst.job_ids}
    ready = {j: 0.0 for j in inst.job_ids}
    ops: Dict[OpKey, OpRecord] = {}
    order: List[int] = []

    # base.ops 按原扫描序写入,冻结工序按此次序回放
    for key, rec in base.ops.items():
        if key not in fixed:
            continue
        j = key[0]
        dest = inst.out_node if rec.pseudo else inst.machine_node[rec.machine]
        ops[key] = rec
        pos[j], ready[j] = dest, rec.finish
        if rec.machine is not None:
            free[rec.machine] = max(free[rec.machine], rec.finish)
            last_on[rec.machine] = key
    for key in abort:
        j = key[0]
        pos[j] = inst.machine_node[dead_machine]
        ready[j] = max(t_now, ready[j])

    def apply_evictions(key, evictions):
        for p_agv, store, plan in evictions:
            owner = last_unit[p_agv]
            owner.evict, owner.evict_by = plan, key
            loc[p_agv], avail[p_agv] = store, plan.arrive

    for k, sn in snaps.items():
        if kind[k] != "trip":
            continue
        u = next(x for x in out if x.key == sn.key and x.agv == k)
        trip = u.leave if sn.part == "leave" else u.evict
        t0 = max(sn.since, t_now)
        router.release(k)
        _fill_stay(router, sn.node, k, sn.since, t0, f"J{u.key[0]}-{u.key[1]}")
        new = router.relocate_from(k, sn.node, t0, f"R{k}-J{u.key[0]}-{u.key[1]}",
                                   start_open=False)
        setattr(u, sn.part, _join(trip, _done(trip, t_now), new))
        loc[k], avail[k] = new.goal, new.arrive

    def target(j, i):
        key = (j, i)
        if (key in delivered or key in pending) and not (
                dead_machine is not None and base.ops[key].machine == dead_machine):
            rec = base.ops[key]
            if rec.pseudo:
                return None, inst.out_node, 0.0, True
            return rec.machine, inst.machine_node[rec.machine], \
                inst.proc_time[key][rec.machine], False
        return _op_target(inst, ma, j, i)

    def run_pending(key):
        j, i = key
        k = pending.pop(key)
        u0 = units[key]
        sn = snaps[k]
        m, dest, p, pseudo = target(j, i)
        label = f"J{j}-{i}"
        ph1 = sn.part == "loaded"
        pickup = pos[j]
        t0 = max(sn.since, t_now)
        _fill_stay(router, sn.node, k, sn.since, t0, label)
        po = router.plan_ex(k, sn.node, t0, None if ph1 else pickup, ready[j], dest,
                            label, start_open=False)
        if ph1:
            empty = u0.empty
            loaded = _join(u0.loaded, _done(u0.loaded, t_now),
                           router._plan_from(sn.node, dest, t0, po.t_deliver,
                                             po.loaded_segs))
        else:
            empty = _join(u0.empty, _done(u0.empty, t_now),
                          router._plan_from(sn.node, pickup, t0, po.t_arr_pick,
                                            po.empty_segs))
            loaded = router._plan_from(pickup, dest, po.t_pick, po.t_deliver, po.loaded_segs)
        unit = Unit(key, k, u0.pickup, dest, ready[j], empty, loaded)
        apply_evictions(key, po.evictions)
        if po.mode == "park":
            loc[k], avail[k] = dest, po.t_deliver
        else:
            unit.leave = po.leave
            loc[k], avail[k] = po.leave.goal, po.leave.arrive
        out.append(unit)
        last_unit[k] = unit
        order.append(k)
        _process_op(inst, ops, free, last_on, pos, ready, j, i, m, dest, p,
                    po.t_deliver, pseudo)

    rank = {key: n for n, key in enumerate(base.ops)}

    def drain():
        # 按原解码的扫描次序收尾承诺,与原计划里各车占用节点/走廊的先后一致
        progressed = True
        while progressed:
            progressed = False
            for key in sorted(pending, key=lambda x: rank.get(x, len(rank))):
                j, i = key
                if i == 1 or (j, i - 1) in ops:
                    run_pending(key)
                    progressed = True
                    break

    counter = {j: 0 for j in inst.job_ids}
    for j in os_seq:
        counter[j] += 1
        i = counter[j]
        key = (j, i)
        drain()
        if key in ops:
            continue
        m, dest, p, pseudo = target(j, i)
        if key in delivered:
            arrive = delivered[key]
        elif pos[j] == dest:
            arrive = ready[j]
        else:
            held = set(pending.values())
            allowed = {k: loc[k] for k in loc if k not in held}
            if not allowed:
                raise RepairInfeasible("no free AGV")
            sub_avail = {k: max(avail[k], t_now) for k in allowed}
            pickup = pos[j]
            k, tplan = dispatch_exact_nodes(router, net, allowed, sub_avail, pickup, dest,
                                            ready[j], f"J{j}-{i}", prune=True, reuse=True)
            router.replay(tplan)
            unit = Unit(key, k, pickup, dest, ready[j], tplan.empty, tplan.loaded)
            for a, plan in tplan.relocations:
                if a == k:
                    unit.leave = plan
                else:
                    owner = last_unit[a]
                    owner.evict, owner.evict_by = plan, key
            for kk, (where, when) in tplan.state.items():
                loc[kk], avail[kk] = where, when
            out.append(unit)
            last_unit[k] = unit
            order.append(k)
            arrive = tplan.loaded.arrive
        _process_op(inst, ops, free, last_on, pos, ready, j, i, m, dest, p, arrive, pseudo)
    drain()
    if pending:
        raise RepairInfeasible(f"unfinished commitments {sorted(pending)}")
    return _result(inst, ops, out, order)


# --------------------------------------------------------------------------
# 右移 / Right shift
# --------------------------------------------------------------------------

def shift_plan(plan: RoutePlan, t_now: float, delta: float) -> RoutePlan:
    """已开始(含进行中)的段不动,其余后移 delta。"""
    segs: List[Segment] = []
    for s in plan.segments:
        if not _started(s, t_now):
            segs.append(Segment(s.corridor, s.u, s.v, s.enter + delta, s.exit + delta))
        else:
            segs.append(s)
    arrive = segs[-1].exit if segs else (
        plan.arrive + delta if plan.arrive > t_now + EPS else plan.arrive)
    t0 = plan.t0 + delta if plan.t0 > t_now + EPS else plan.t0
    return RoutePlan(plan.start, plan.goal, t0, arrive, segs,
                     dict(plan.wait_by_corridor), plan.price_cost)


def shift_units(units: List[Unit], t_now: float, delta: float) -> List[Unit]:
    out = []
    for u in units:
        out.append(replace(
            u,
            ready=u.ready + delta if u.ready > t_now + EPS else u.ready,
            empty=shift_plan(u.empty, t_now, delta),
            loaded=shift_plan(u.loaded, t_now, delta),
            leave=shift_plan(u.leave, t_now, delta) if u.leave is not None else None,
            evict=shift_plan(u.evict, t_now, delta) if u.evict is not None else None,
        ))
    return out


def result_from_units(inst: Instance, ops, units: List[Unit], order) -> DecodeResult:
    return _result(inst, ops, units, order)
