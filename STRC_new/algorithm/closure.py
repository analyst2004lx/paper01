"""STRC 核心:时空预约影响闭包。

阻塞传播边 r → r' 含义:若 r 失效,则 r' 可能需要重规划。包括:
  1) 让行边: r 的占用造成 r' 在同走廊等待;
  2) 同车后继:同一 AGV 上时间上紧后的预约;
  3) 同工件后继:J{j}-{i}-* 之后的 J{j}-{i+1}-*。

走廊阻断的种子 = 落在阻断时窗内、且尚未在 t_now 前结束的走廊预约。

STRC core: the spatiotemporal reservation closure.

A blocking edge r → r' means: if r fails, r' may need replanning. That includes:
  1) yield edges: r's occupation makes r' wait on the same corridor;
  2) same-vehicle successors: the reservation that comes next in time on the same AGV;
  3) same-job successors: J{j}-{i+1}-* after J{j}-{i}-*.

Seeds of a corridor blockage = corridor reservations that fall inside the blockage window and have not finished before t_now.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

EPS = 1e-9
# leave:送达后因目的机器无停放位而开往库区;evict:停放后被他车驱离开往库区。
# 两者都是该车在这次运输之后、下次运输之前的行程,故记在这次运输名下。
# leave: the trip to a store after delivery when the destination has no parking slot; evict: the
# trip to a store when another vehicle displaces this parked one. Both happen between this
# transport and the vehicle's next one, so they are filed under this transport.
_TASK_RE = re.compile(r"^J(\d+)-(\d+)-(empty|loaded|leave|evict)$")
TASK_PARTS = ("empty", "loaded", "leave", "evict")


@dataclass(frozen=True)
class ReservationRef:
    corridor: str
    t_start: float
    t_end: float
    agv: int
    task: str

    # 哈希缓存在实例字典里而不是字段里,故不进 eq/asdict;字符串哈希随进程而变,pickle 时须重算
    def __post_init__(self):
        object.__setattr__(self, "_h", hash((self.corridor, self.t_start, self.t_end,
                                             self.agv, self.task)))

    def __hash__(self) -> int:
        return self._h   # type: ignore[attr-defined]

    def __reduce__(self):
        return (ReservationRef, (self.corridor, self.t_start, self.t_end, self.agv, self.task))

    def overlaps(self, t0: float, t1: float) -> bool:
        return self.t_end > t0 + EPS and self.t_start < t1 - EPS


@dataclass
class ClosureResult:
    seeds: list[ReservationRef]
    closed: list[ReservationRef]
    horizon: float
    n_edges_traversed: int = 0
    meta: dict = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.closed)

    def as_set(self) -> Set[ReservationRef]:
        return set(self.closed)


def _parse_task(task: str) -> Optional[Tuple[int, int, str]]:
    m = _TASK_RE.match(task)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3)


def build_dependence_graph(
    reservations: Sequence[ReservationRef],
    *,
    machine_chains: Optional[Sequence[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    node_caps: Optional[Dict[str, float]] = None,
) -> Dict[ReservationRef, List[ReservationRef]]:
    """构建 r → r' (r 失效可能牵连 r')。

    machine_chains: 同机先后工序对 ((j,i), (j2,i2)),由排程的机器时间轴导出。
    node_caps: 节点停留以 corridor="@节点" 的伪预约给出时,各节点的容量。容量为 1 的节点与走廊
    同规则;容量 c>1 的节点上两段停留重叠时,只有重叠期间节点达到满载才画让行边。

    Build r → r' (if r fails, r' may be implicated).

    machine_chains: successive operation pairs on the same machine ((j, i), (j2, i2)), taken from the schedule's machine timeline.
    """
    by_corridor: Dict[str, List[ReservationRef]] = defaultdict(list)
    by_agv: Dict[int, List[ReservationRef]] = defaultdict(list)
    by_job_op: Dict[Tuple[int, int], List[ReservationRef]] = defaultdict(list)

    for r in reservations:
        by_corridor[r.corridor].append(r)
        by_agv[r.agv].append(r)
        parsed = _parse_task(r.task)
        if parsed:
            by_job_op[(parsed[0], parsed[1])].append(r)

    for lst in by_corridor.values():
        lst.sort(key=lambda x: x.t_start)
    for lst in by_agv.values():
        lst.sort(key=lambda x: x.t_start)

    graph: Dict[ReservationRef, List[ReservationRef]] = defaultdict(list)

    for cid, lst in by_corridor.items():
        _yield_edges(graph, cid, lst, node_caps)

    # 2) 同车后继 / 2) Same-vehicle successor
    for _agv, lst in by_agv.items():
        for i in range(len(lst) - 1):
            graph[lst[i]].append(lst[i + 1])

    # 3) 同工件工序后继 / 3) Same-job operation successor
    jobs = {j for j, _i in by_job_op}
    for j in jobs:
        ops = sorted({i for jj, i in by_job_op if jj == j})
        for a, b in zip(ops, ops[1:]):
            for ra in by_job_op[(j, a)]:
                for rb in by_job_op[(j, b)]:
                    graph[ra].append(rb)

    # 4) 同机后继(修复时外侧冻结所必需) / 4) Same-machine successor (required when freezing the outside during repair)
    if machine_chains:
        for (j1, i1), (j2, i2) in machine_chains:
            for ra in by_job_op.get((j1, i1), ()):
                for rb in by_job_op.get((j2, i2), ()):
                    graph[ra].append(rb)

    for r, succs in list(graph.items()):
        seen = set()
        uniq = []
        for s in succs:
            if s not in seen and s is not r:
                seen.add(s)
                uniq.append(s)
        graph[r] = uniq
    return graph


def _yield_edges(graph, cid: str, lst: Sequence[ReservationRef],
                 node_caps: Optional[Dict[str, float]]) -> None:
    """1) 让行边:同走廊(或同节点)、异车、时间重叠或半开区间接壤;lst 已按开始时刻排序。

    接壤 (a.t_end == b.t_start) 在排他语义下合法,原先不画边;但 a 稍一延后
    b 就必须让路,差分试探里全部泄漏都是这一条。

    1) Yield edges: same corridor, different vehicles, overlapping in time or abutting on a
    half-open interval. Abutting is legal under exclusive semantics and used to draw no edge; but
    if a is delayed even slightly, b must yield. Every leak in the differential probe was this edge.
    """
    cap = 1.0
    if node_caps is not None and cid.startswith("@"):
        cap = node_caps.get(cid[1:], 1.0)
    for i, a in enumerate(lst):
        for b in lst[i + 1:]:
            gap = b.t_start - a.t_end
            if gap > EPS:
                break
            if a.agv == b.agv:
                continue
            if abs(gap) <= EPS:
                graph[a].append(b)
            elif a.overlaps(b.t_start, b.t_end):
                if cap > 1.0 and not _binding(lst, b.t_start, min(a.t_end, b.t_end), cap):
                    continue
                if a.t_start <= b.t_start + EPS:
                    graph[a].append(b)
                else:
                    graph[b].append(a)


@dataclass
class DependenceBase:
    """基线排程的依赖图及索引,扰动到来前即可建好;扰动时只接入少量节点停留再遍历。"""
    graph: Dict[ReservationRef, List[ReservationRef]]
    by_agv: Dict[int, List[ReservationRef]]
    by_job_op: Dict[Tuple[int, int], List[ReservationRef]]
    machine_chains: List[Tuple[Tuple[int, int], Tuple[int, int]]]
    agv_starts: Dict[int, List[float]] = field(default_factory=dict)
    job_ops: Dict[int, List[int]] = field(default_factory=dict)


def build_dependence_base(reservations: Sequence[ReservationRef], *,
                          machine_chains) -> DependenceBase:
    by_agv: Dict[int, List[ReservationRef]] = defaultdict(list)
    by_job_op: Dict[Tuple[int, int], List[ReservationRef]] = defaultdict(list)
    for r in reservations:
        by_agv[r.agv].append(r)
        parsed = _parse_task(r.task)
        if parsed:
            by_job_op[(parsed[0], parsed[1])].append(r)
    for lst in by_agv.values():
        lst.sort(key=lambda x: x.t_start)
    graph = build_dependence_graph(reservations, machine_chains=machine_chains)
    job_ops: Dict[int, List[int]] = defaultdict(list)
    for j, i in by_job_op:
        job_ops[j].append(i)
    return DependenceBase(dict(graph), dict(by_agv), dict(by_job_op), list(machine_chains or ()),
                          {a: [r.t_start for r in lst] for a, lst in by_agv.items()},
                          dict(job_ops))


class GraphOverlay:
    """基图加增边,不复制基图。"""

    def __init__(self, base: Dict[ReservationRef, List[ReservationRef]],
                 extra: Dict[ReservationRef, List[ReservationRef]]):
        self.base, self.extra = base, extra

    def get(self, r, default=()):
        a, b = self.base.get(r), self.extra.get(r)
        if b is None:
            return a if a is not None else default
        return list(a or ()) + b


def splice_node_refs(base: DependenceBase, node_refs: Sequence[ReservationRef],
                     node_caps: Dict[str, float]) -> GraphOverlay:
    """把少量节点停留伪预约接入基图,四类边的规则与一起重建时相同。

    同车链上,节点停留插在相邻两段之间;基图里这两段原有的直连边保留。它只在停留已结束而
    前一段仍未结束时多出可达性,而停留始于前一段的终点,这种情形不会出现,故闭包相同。
    """
    extra: Dict[ReservationRef, List[ReservationRef]] = defaultdict(list)
    by_node: Dict[str, List[ReservationRef]] = defaultdict(list)
    for r in node_refs:
        by_node[r.corridor].append(r)
    for cid, lst in by_node.items():
        lst.sort(key=lambda x: x.t_start)
        _yield_edges(extra, cid, lst, node_caps)
    mine: Dict[int, List[ReservationRef]] = defaultdict(list)
    for r in node_refs:
        mine[r.agv].append(r)
    for agv, xs in mine.items():
        chain = base.by_agv.get(agv, ())
        starts = base.agv_starts.get(agv, ())
        # 与把 xs 并入车链后按开始时刻稳定排序再连相邻对等价:同一时刻的 xs 排在车链之后
        xs.sort(key=lambda x: x.t_start)
        groups: Dict[int, List[ReservationRef]] = defaultdict(list)
        for x in xs:
            groups[bisect_right(starts, x.t_start)].append(x)
        for pos, g in groups.items():
            if pos > 0:
                extra[chain[pos - 1]].append(g[0])
            for a, b in zip(g, g[1:]):
                extra[a].append(b)
            if pos < len(chain):
                extra[g[-1]].append(chain[pos])
    by_op: Dict[Tuple[int, int], List[ReservationRef]] = defaultdict(list)
    for r in node_refs:
        parsed = _parse_task(r.task)
        if parsed:
            by_op[(parsed[0], parsed[1])].append(r)

    def refs(op):
        return list(base.by_job_op.get(op, ())) + by_op.get(op, [])

    # 同工件边连的是该工件下一道(上一道)有预约的工序,不一定是 i±1
    for (j, i), xs in by_op.items():
        idx = sorted(set(base.job_ops.get(j, ())) | {ii for jj, ii in by_op if jj == j})
        k = idx.index(i)
        nxt = refs((j, idx[k + 1])) if k + 1 < len(idx) else []
        prv = refs((j, idx[k - 1])) if k > 0 else []
        for x in xs:
            extra[x].extend(nxt)
            for r in prv:
                extra[r].append(x)
    for a, c in base.machine_chains:
        for x in by_op.get(a, ()):
            extra[x].extend(refs(c))
        for x in by_op.get(c, ()):
            for r in base.by_job_op.get(a, ()):
                extra[r].append(x)
    return GraphOverlay(base.graph, dict(extra))


def _binding(lst: Sequence[ReservationRef], lo: float, hi: float, cap: float) -> bool:
    """[lo, hi) 内该节点的同时停留数是否达到容量。"""
    points = [lo] + [r.t_start for r in lst if lo < r.t_start < hi]
    for t in points:
        if sum(1 for r in lst if r.t_start <= t + EPS and r.t_end > t + EPS) >= cap:
            return True
    return False


def machine_chains_from_ops(ops: dict) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """从 DecodeResult.ops 提取同机先后对。

    Extract successive pairs on the same machine from DecodeResult.ops.
    """
    by_m: Dict[int, list] = defaultdict(list)
    for rec in ops.values():
        if getattr(rec, "pseudo", False) or rec.machine is None:
            continue
        by_m[rec.machine].append(rec)
    chains: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for lst in by_m.values():
        lst.sort(key=lambda r: (r.start, r.job, r.i))
        for a, b in zip(lst, lst[1:]):
            chains.append(((a.job, a.i), (b.job, b.i)))
    return chains


def spatiotemporal_closure(
    seeds: Iterable[ReservationRef],
    reservations: Sequence[ReservationRef],
    *,
    horizon: float,
    t_now: float = 0.0,
    machine_chains: Optional[Sequence[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    node_caps: Optional[Dict[str, float]] = None,
    graph=None,
) -> ClosureResult:
    """对种子集沿依赖边取传递闭包;丢弃 t_end <= t_now 或 t_start >= horizon 的节点。

    graph 给出时(预建的依赖图,见 splice_node_refs)直接遍历,不再重建。

    Take the transitive closure of the seed set along dependence edges; drop nodes with t_end <= t_now or t_start >= horizon.
    """
    seed_list = list(seeds)
    lo, hi = t_now + EPS, horizon - EPS
    if graph is None:
        graph = build_dependence_graph(reservations, machine_chains=machine_chains,
                                       node_caps=node_caps)
        universe = set(reservations)

        def alive(r):
            return r.t_end > lo and r.t_start < hi and r in universe
    else:
        # 预建图的顶点都取自 reservations,只需按时间判断
        def alive(r):
            return r.t_end > lo and r.t_start < hi

    closed: List[ReservationRef] = []
    seen: Set[ReservationRef] = set()
    q: deque[ReservationRef] = deque()
    n_edges = 0

    for s in seed_list:
        if s not in seen and alive(s):
            seen.add(s)
            q.append(s)

    get = graph.get
    while q:
        r = q.popleft()
        closed.append(r)
        for nxt in get(r, ()):
            n_edges += 1
            if nxt in seen or not alive(nxt):
                continue
            seen.add(nxt)
            q.append(nxt)

    return ClosureResult(
        seeds=seed_list,
        closed=closed,
        horizon=horizon,
        n_edges_traversed=n_edges,
        meta={
            "n_reservations": len(reservations),
            "n_seeds": len(seed_list),
        },
    )


def task_graph_direct(dist, schedule_meta: Optional[dict] = None) -> Set[str]:
    """NOSR 的 T_direct:被故障智能体直接命中的任务 id 集。

    走廊阻断/降速:无智能体 → 空集。

    NOSR's T_direct: the set of task ids hit directly by the failed agent.

    Corridor blockage / slowdown: no agent, so the set is empty.
    """
    if dist.type in ("corridor_block", "corridor_slowdown"):
        return set()
    if dist.type == "agv_breakdown":
        # 需要排程里该车未来任务;由调用方传入 schedule_meta["agv_tasks"]
        # Needs that vehicle's future tasks from the schedule; the caller passes schedule_meta["agv_tasks"].
        agv = dist.agv
        tasks = (schedule_meta or {}).get("agv_tasks", {}).get(agv, [])
        return set(tasks)
    if dist.type == "ra_failure":
        mac = dist.machine
        tasks = (schedule_meta or {}).get("machine_tasks", {}).get(str(mac), [])
        return set(tasks)
    if dist.type == "proc_delay" and dist.job_op:
        return {f"J{dist.job_op.strip('()').replace(',', '-').replace(' ', '')}"}
    if dist.type == "urgent_job":
        return set()  # 新工件不在原图上,影响域另议;E1 不依赖此类
        # A new job is not on the original graph; its impact set is separate. E1 does not depend on this class.
    return set()


def task_graph_impact(
    dist,
    job_succ: Dict[str, List[str]],
    *,
    theta: int = 2,
    schedule_meta: Optional[dict] = None,
) -> Set[str]:
    """从 T_direct 在任务依赖图上 BFS θ 跳。

    BFS θ hops from T_direct on the task-dependence graph.
    """
    direct = task_graph_direct(dist, schedule_meta)
    if not direct or theta <= 0:
        return set(direct)
    seen = set(direct)
    q = deque([(t, 0) for t in direct])
    while q:
        u, d = q.popleft()
        if d >= theta:
            continue
        for v in job_succ.get(u, ()):
            if v not in seen:
                seen.add(v)
                q.append((v, d + 1))
    return seen


def job_precedence_from_reservations(
    reservations: Sequence[ReservationRef],
) -> Dict[str, List[str]]:
    """粗粒度任务图:J{j}-{i} → J{j}-{i+1}(忽略 empty/loaded 细分)。

    Coarse task graph: J{j}-{i} → J{j}-{i+1} (ignoring the empty/loaded split).
    """
    ops: Set[Tuple[int, int]] = set()
    for r in reservations:
        p = _parse_task(r.task)
        if p:
            ops.add((p[0], p[1]))
    succ: Dict[str, List[str]] = defaultdict(list)
    jobs = {j for j, _i in ops}
    for j in jobs:
        seq = sorted(i for jj, i in ops if jj == j)
        for a, b in zip(seq, seq[1:]):
            succ[f"J{j}-{a}"].append(f"J{j}-{b}")
    return succ


def release_set_from_tasks(
    reservations: Sequence[ReservationRef],
    tasks: Set[str],
    *,
    t_now: float = 0.0,
) -> List[ReservationRef]:
    """R1:任务影响域映射到预约释放集(task 前缀匹配 J{j}-{i})。

    只计 t_end > t_now 的未来预约,与闭包的 alive 口径一致。

    R1: map the task impact set onto the reservation release set (task prefix match J{j}-{i}).

    Count only future reservations with t_end > t_now, the same alive convention as the closure.
    """
    if not tasks:
        return []
    out = []
    for r in reservations:
        if r.t_end <= t_now + EPS:
            continue
        p = _parse_task(r.task)
        if not p:
            continue
        tid = f"J{p[0]}-{p[1]}"
        if tid in tasks:
            out.append(r)
    return out


def assert_containment_structural(
    closure: ClosureResult,
    reservations: Sequence[ReservationRef],
    *,
    t_now: float = 0.0,
    machine_chains: Optional[Sequence[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    node_caps: Optional[Dict[str, float]] = None,
) -> List[str]:
    """E2a:结构抽检——闭包外节点不应有从种子集可达的依赖边漏网。

    口径与 spatiotemporal_closure 的 alive 过滤一致。

    E2a: structural spot check — a node outside the closure should not be reachable from the seed set along a dependence edge that was missed.

    The convention matches the alive filter in spatiotemporal_closure.
    """
    graph = build_dependence_graph(reservations, machine_chains=machine_chains,
                                   node_caps=node_caps)
    closed = closure.as_set()
    alive = {
        r for r in reservations
        if r.t_end > t_now + EPS and r.t_start < closure.horizon - EPS
    }
    seeds = [s for s in closure.seeds if s in alive]
    seen: Set[ReservationRef] = set()
    q: deque[ReservationRef] = deque()
    for s in seeds:
        seen.add(s)
        q.append(s)
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in alive or v in seen:
                continue
            seen.add(v)
            q.append(v)
    leaks = [r for r in seen if r not in closed]
    return [
        f"leak {r.task}@{r.corridor}[{r.t_start},{r.t_end})"
        for r in leaks
    ]
