"""STRC 核心:时空预约影响闭包。

阻塞传播边 r → r' 含义:若 r 失效,则 r' 可能需要重规划。包括:
  1) 让行边: r 的占用造成 r' 在同走廊等待;
  2) 同车后继:同一 AGV 上时间上紧后的预约;
  3) 同工件后继:J{j}-{i}-* 之后的 J{j}-{i+1}-*。

走廊阻断的种子 = 落在阻断时窗内、且尚未在 t_now 前结束的走廊预约。
"""
from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

EPS = 1e-9
_TASK_RE = re.compile(r"^J(\d+)-(\d+)-(empty|loaded)$")


@dataclass(frozen=True)
class ReservationRef:
    corridor: str
    t_start: float
    t_end: float
    agv: int
    task: str

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
) -> Dict[ReservationRef, List[ReservationRef]]:
    """构建 r → r' (r 失效可能牵连 r')。

    machine_chains: 同机先后工序对 ((j,i), (j2,i2)),由排程的机器时间轴导出。
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

    # 1) 让行边:同走廊时间重叠 → 先到者挡后到者(按 enter 次序)
    for cid, lst in by_corridor.items():
        for i, a in enumerate(lst):
            for b in lst[i + 1:]:
                if b.t_start >= a.t_end - EPS:
                    break
                if a.overlaps(b.t_start, b.t_end) and a.agv != b.agv:
                    if a.t_start <= b.t_start + EPS:
                        graph[a].append(b)
                    else:
                        graph[b].append(a)

    # 2) 同车后继
    for _agv, lst in by_agv.items():
        for i in range(len(lst) - 1):
            graph[lst[i]].append(lst[i + 1])

    # 3) 同工件工序后继
    jobs = {j for j, _i in by_job_op}
    for j in jobs:
        ops = sorted({i for jj, i in by_job_op if jj == j})
        for a, b in zip(ops, ops[1:]):
            for ra in by_job_op[(j, a)]:
                for rb in by_job_op[(j, b)]:
                    graph[ra].append(rb)

    # 4) 同机后继(修复时外侧冻结所必需)
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


def machine_chains_from_ops(ops: dict) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """从 DecodeResult.ops 提取同机先后对。"""
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
) -> ClosureResult:
    """对种子集沿依赖边取传递闭包;丢弃 t_end <= t_now 或 t_start >= horizon 的节点。"""
    seed_list = list(seeds)
    graph = build_dependence_graph(reservations, machine_chains=machine_chains)
    alive = {
        r for r in reservations
        if r.t_end > t_now + EPS and r.t_start < horizon - EPS
    }

    closed: List[ReservationRef] = []
    seen: Set[ReservationRef] = set()
    q: deque[ReservationRef] = deque()
    n_edges = 0

    for s in seed_list:
        if s in alive and s not in seen:
            seen.add(s)
            q.append(s)

    while q:
        r = q.popleft()
        closed.append(r)
        for nxt in graph.get(r, ()):
            n_edges += 1
            if nxt not in alive or nxt in seen:
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
            "n_alive": len(alive),
            "n_seeds": len(seed_list),
        },
    )


def task_graph_direct(dist, schedule_meta: Optional[dict] = None) -> Set[str]:
    """NOSR 的 T_direct:被故障智能体直接命中的任务 id 集。

    走廊阻断/降速:无智能体 → 空集。
    """
    if dist.type in ("corridor_block", "corridor_slowdown"):
        return set()
    if dist.type == "agv_breakdown":
        # 需要排程里该车未来任务;由调用方传入 schedule_meta["agv_tasks"]
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
    return set()


def task_graph_impact(
    dist,
    job_succ: Dict[str, List[str]],
    *,
    theta: int = 2,
    schedule_meta: Optional[dict] = None,
) -> Set[str]:
    """从 T_direct 在任务依赖图上 BFS θ 跳。"""
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
    """粗粒度任务图:J{j}-{i} → J{j}-{i+1}(忽略 empty/loaded 细分)。"""
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
) -> List[str]:
    """E2a:结构抽检——闭包外节点不应有从种子集可达的依赖边漏网。

    口径与 spatiotemporal_closure 的 alive 过滤一致。
    """
    graph = build_dependence_graph(reservations, machine_chains=machine_chains)
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
