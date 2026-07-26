"""路网、理想最短路 t*、预约表与时间窗 Dijkstra(规格文档 5.1–5.4)。

冲突模型(规格 5.1):
- 通行资源 = 物理走廊,双向共用一个独占预约资源;
- 占用时窗为半开区间 [t, t+τ);
- 等待发生在节点停靠位(容量充足,不设预约),节点穿越为零测度不预约。
"""
from __future__ import annotations

import bisect
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Segment:
    """一次走廊穿越:从 u 于 enter 时刻进入,exit = enter + τ 时刻到达 v。"""
    corridor: str
    u: str
    v: str
    enter: float
    exit: float


@dataclass
class RoutePlan:
    start: str
    goal: str
    t0: float                      # 最早出发时刻
    arrive: float                  # 到达 goal 的时刻
    segments: List[Segment] = field(default_factory=list)
    wait_by_corridor: Dict[str, float] = field(default_factory=dict)

    @property
    def total_wait(self) -> float:
        return sum(self.wait_by_corridor.values())

    @property
    def travel_time(self) -> float:
        return sum(s.exit - s.enter for s in self.segments)


def corridor_id(u: str, v: str) -> str:
    """双向走廊的规范 id(与方向无关)。"""
    return f"{u}|{v}" if u <= v else f"{v}|{u}"


class Network:
    def __init__(self, nodes: List[str], corridors: List[dict], lu_node: str):
        self.nodes = list(nodes)
        self.lu_node = lu_node
        self.corridor_time: Dict[str, float] = {}
        self.adj: Dict[str, List[Tuple[str, str, float]]] = {n: [] for n in nodes}
        for c in corridors:
            cid = corridor_id(c["u"], c["v"])
            tau = float(c["time"])
            self.corridor_time[cid] = tau
            self.adj[c["u"]].append((cid, c["v"], tau))
            self.adj[c["v"]].append((cid, c["u"], tau))
        self.ideal_dist = self._all_pairs_shortest()

    def _all_pairs_shortest(self) -> Dict[str, Dict[str, float]]:
        """无预约理想最短路矩阵 t*(规格 5.4)。"""
        dist_all: Dict[str, Dict[str, float]] = {}
        for src in self.nodes:
            dist = {src: 0.0}
            heap = [(0.0, src)]
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist.get(u, float("inf")):
                    continue
                for _cid, v, tau in self.adj[u]:
                    nd = d + tau
                    if nd < dist.get(v, float("inf")):
                        dist[v] = nd
                        heapq.heappush(heap, (nd, v))
            dist_all[src] = dist
        return dist_all

    def incident_corridors(self, node: str) -> List[str]:
        return [cid for cid, _v, _t in self.adj[node]]

    def check_reachability(self) -> None:
        for a in self.nodes:
            for b in self.nodes:
                if b not in self.ideal_dist[a]:
                    raise ValueError(f"路网不连通: {a} 无法到达 {b}(违反 D1)")


class ReservationTable:
    """每条走廊的半开占用时窗列表(规格 5.2)。"""

    def __init__(self):
        # cid -> 按 t_start 排序的 [t_start, t_end, agv, task]
        self._res: Dict[str, List[Tuple[float, float, int, str]]] = {}

    def earliest_entry(self, cid: str, t: float, tau: float) -> float:
        """从 t 起最早可占用 [t', t'+tau) 的时刻(区间空隙查找)。"""
        cand = t
        for ts, te, _agv, _task in self._res.get(cid, []):
            if cand + tau <= ts:
                break
            cand = max(cand, te)
        return cand

    def reserve(self, cid: str, ts: float, te: float, agv: int, task: str) -> None:
        lst = self._res.setdefault(cid, [])
        idx = bisect.bisect_left(lst, (ts, te, agv, task))
        # 半开区间互斥断言(防隐性 bug)
        if idx > 0 and lst[idx - 1][1] > ts:
            raise AssertionError(f"预约冲突 {cid}: {lst[idx-1]} 与 [{ts},{te})")
        if idx < len(lst) and lst[idx][0] < te:
            raise AssertionError(f"预约冲突 {cid}: {lst[idx]} 与 [{ts},{te})")
        lst.insert(idx, (ts, te, agv, task))

    def all_reservations(self) -> Dict[str, List[Tuple[float, float, int, str]]]:
        return self._res


class Router:
    """路由层:时间窗 Dijkstra + 预约落表(规格 5.3);conflict_free=False 时退化为查 t*。"""

    def __init__(self, network: Network, conflict_free: bool = True):
        self.net = network
        self.conflict_free = conflict_free
        self.table = ReservationTable()

    def route(self, start: str, goal: str, t0: float, agv: int, task: str,
              commit: bool = True) -> RoutePlan:
        if start == goal:
            return RoutePlan(start, goal, t0, t0)

        if not self.conflict_free:
            # 退化模式(规格 12.2 第一层对标):运输时间 = 理想最短路,无预约
            arrive = t0 + self.net.ideal_dist[start][goal]
            return RoutePlan(start, goal, t0, arrive)

        # 时间窗 Dijkstra:标签 = (到达时刻, 节点);等待被 earliest_entry 天然涵盖
        best: Dict[str, float] = {start: t0}
        prev: Dict[str, Tuple[str, str, float, float]] = {}  # v -> (u, cid, enter, exit)
        heap: List[Tuple[float, str]] = [(t0, start)]
        while heap:
            t, u = heapq.heappop(heap)
            if t > best.get(u, float("inf")):
                continue
            if u == goal:
                break
            for cid, v, tau in self.net.adj[u]:
                enter = self.table.earliest_entry(cid, t, tau)
                arr = enter + tau
                if arr < best.get(v, float("inf")):
                    best[v] = arr
                    prev[v] = (u, cid, enter, arr)
                    heapq.heappush(heap, (arr, v))

        if goal not in best:
            raise RuntimeError(f"路由失败: {start} -> {goal}(路网不连通?)")

        # 回溯路径
        segs: List[Segment] = []
        node = goal
        while node != start:
            u, cid, enter, exit_ = prev[node]
            segs.append(Segment(cid, u, node, enter, exit_))
            node = u
        segs.reverse()

        # 等待统计:进入某走廊前在其上游节点停靠的时长,记到该走廊头上
        waits: Dict[str, float] = {}
        at_time = t0
        for s in segs:
            w = s.enter - at_time
            if w > 0:
                waits[s.corridor] = waits.get(s.corridor, 0.0) + w
            at_time = s.exit

        if commit:
            for s in segs:
                self.table.reserve(s.corridor, s.enter, s.exit, agv, task)

        return RoutePlan(start, goal, t0, best[goal], segs, waits)
