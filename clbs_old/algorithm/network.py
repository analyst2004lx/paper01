"""路网、理想最短路 t*、容量化预约表、走廊-时段影子价格与价格感知多标签路由。

冲突模型(规格 5.1):
- 通行资源 = 物理走廊,双向共用一个预约资源,默认容量 1(独占);
- 占用时窗为半开区间 [t, t+tau);
- 等待发生在节点停靠位(容量充足,不设预约),节点穿越为零测度不预约。

层间接口(价格协调版,规格 5.5):
下层不再只回答"最早何时到达",而是在"到达时刻"与"占用他人资源的代价"之间取
Pareto 前沿,并按 arrive + theta * price_cost 择优。price_cost 由上层下发的
影子价格 PriceTable 计价,与 makespan 同量纲,因此 theta 是无量纲协调强度:
theta = 0 时退化为纯最早到达(与价格协调前的实现逐字节等价)。
"""
from __future__ import annotations

import bisect
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

BucketKey = Tuple[str, int]  # (corridor_id, bucket_index)


@dataclass(frozen=True)
class Segment:
    """一次走廊穿越:从 u 于 enter 时刻进入,exit = enter + tau 时刻到达 v。"""
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
    price_cost: float = 0.0        # 本条路径占用的走廊-时段的影子价格总额

    @property
    def total_wait(self) -> float:
        return sum(self.wait_by_corridor.values())

    @property
    def travel_time(self) -> float:
        return sum(s.exit - s.enter for s in self.segments)

    def wait_events(self) -> List[Tuple[str, float, float, float]]:
        """逐次让行事件 (走廊, 等待起, 等待止, 等待时长)。

        与 wait_by_corridor 的区别是保留了**时刻**,关键路径归因与影子价格的时段
        定位都需要它——只有标量总量无法回答"哪个时段的通行权更值钱"。
        """
        out: List[Tuple[str, float, float, float]] = []
        at_time = self.t0
        for s in self.segments:
            if s.enter > at_time + 1e-12:
                out.append((s.corridor, at_time, s.enter, s.enter - at_time))
            at_time = s.exit
        return out


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

    # ---------------- 结构指标(算例特征;规格 12.3) ----------------

    def shortest_path_corridors(self, a: str, b: str) -> List[str]:
        """a→b 一条最短路上的走廊序列(并列时取字典序最小,保证确定性)。"""
        dist = {a: 0.0}
        prev: Dict[str, Tuple[str, str]] = {}      # node -> (前驱节点, 走廊)
        heap = [(0.0, a)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, float("inf")):
                continue
            if u == b:
                break
            for cid, v, tau in sorted(self.adj[u]):
                nd = d + tau
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = (u, cid)
                    heapq.heappush(heap, (nd, v))
        if b not in dist:
            return []
        path: List[str] = []
        cur = b
        while cur != a:
            p, cid = prev[cur]
            path.append(cid)
            cur = p
        path.reverse()
        return path

    def funnel_share(self, machine_nodes: Sequence[str]) -> float:
        """**决策无关拥堵**的结构占比 ∈ [0,1]:典型 LU→RA 行程中落在
        "所有 LU→RA 最短路共用走廊"上的时间比例。

        动机:每个工件的首道送达与成品回运都必须穿过 LU 出口侧的共用走廊,
        不论工序派给哪台 RA——这部分拥堵**不含决策杠杆**,只抬高所有方案的
        基线延误,不为改派/错峰提供可利用的差异。该值越低,机制可利用的信号
        越强。局限:只刻画 LU 侧的强制流量,不含机器间换机运输。
        """
        targets = [m for m in dict.fromkeys(machine_nodes) if m != self.lu_node]
        if not targets:
            return 0.0
        paths = [self.shortest_path_corridors(self.lu_node, m) for m in targets]
        if any(not p for p in paths):
            return 0.0
        common = set(paths[0])
        for p in paths[1:]:
            common &= set(p)
        t_common = sum(self.corridor_time[c] for c in common)
        t_mean = sum(sum(self.corridor_time[c] for c in p) for p in paths) / len(paths)
        return t_common / t_mean if t_mean > 0 else 0.0

    def lu_cut(self, machine_nodes: Sequence[str]) -> Tuple[int, List[str]]:
        """**漏斗**:使 LU 与全部 RA 失联所需的最小走廊集合,返回 (宽度, 走廊列表)。

        = LU 到"全体 RA 超汇"的走廊连通度(单位容量最大流 / 最小割)。宽度给出
        LU 同时能发出的车辆数上限:值为 1 意味着存在单点漏斗,该走廊上的排队与
        指派决策无关(参见 funnel_share 与 lu_cut_bound)。
        """
        targets = [m for m in dict.fromkeys(machine_nodes) if m != self.lu_node]
        if not targets or self.lu_node in targets:
            return 0, []
        # 每条物理走廊建一对反向弧,各容量 1(无向单位容量走廊)
        cap: Dict[Tuple[str, str], int] = {}
        for cid in self.corridor_time:
            u, v = cid.split("|", 1)
            cap[(u, v)] = 1
            cap[(v, u)] = 1
        sink = "__sink__"
        big = len(self.corridor_time) + 1
        for m in targets:
            cap[(m, sink)] = big                               # 汇侧不设限
            cap[(sink, m)] = 0
        adj: Dict[str, set] = {}
        for (u, v) in cap:
            adj.setdefault(u, set()).add(v)
            adj.setdefault(v, set()).add(u)

        flow = 0
        while True:                                            # Edmonds-Karp
            parent: Dict[str, Optional[str]] = {self.lu_node: None}
            queue = [self.lu_node]
            while queue and sink not in parent:
                u = queue.pop(0)
                for v in sorted(adj.get(u, ())):
                    if v not in parent and cap.get((u, v), 0) > 0:
                        parent[v] = u
                        queue.append(v)
            if sink not in parent:
                break
            nodes_on_path = _path_nodes(parent, sink)
            push = min(cap[(parent[v], v)] for v in nodes_on_path)
            for v in nodes_on_path:
                u = parent[v]
                cap[(u, v)] -= push
                cap[(v, u)] = cap.get((v, u), 0) + push
            flow += push

        # 残量图中从源可达的一侧 S,割边即 S→V\S 且原容量>0 的物理走廊
        reach = {self.lu_node}
        queue = [self.lu_node]
        while queue:
            u = queue.pop(0)
            for v in adj.get(u, ()):
                if v not in reach and cap.get((u, v), 0) > 0:
                    reach.add(v)
                    queue.append(v)
        cut = sorted({corridor_id(u, v) for cid in self.corridor_time
                      for u, v in [cid.split("|", 1)]
                      if (u in reach) != (v in reach)})
        return flow, cut

    def lu_cut_bound(self, machine_nodes: Sequence[str], num_jobs: int,
                     delta_return: int = 1) -> float:
        """LU 漏斗给出的 makespan 下界(与任何调度决策无关的硬地板)。

        论证:δ_return=1 时每个工件必须**穿越漏斗两次**(首道送达出、成品回运
        入),δ_return=0 时至少一次;漏斗由 k 条独占走廊组成,一次穿越占用走廊 c
        达 tau(c)。把 X 次穿越分配到各割边、令 x_c 为落在 c 上的次数,则耗时
        >= max_c x_c*tau(c);在 sum(x_c)=X 下最小化该上界得 X / sum_c (1/tau(c))。
        故 C_max >= X / sum_c (1/tau(c))。这是零成本可得的合法下界。
        """
        _k, cut = self.lu_cut(machine_nodes)
        if not cut:
            return 0.0
        crossings = num_jobs * (2 if delta_return else 1)
        inv = sum(1.0 / self.corridor_time[c] for c in cut
                  if self.corridor_time[c] > 0)
        return crossings / inv if inv > 0 else 0.0

    def far_group_cut(self, machine_nodes: Sequence[str]) -> int:
        """**深层瓶颈容量**:隔离"远端 RA 组"所需的最小走廊数。

        `lu_min_cut` 只看 LU 出口,看不到路网深处的争用;而单台 RA 的连通度恒被
        它自己那条支线卡成 1,也没有区分力。故取"到 LU 的理想距离高于中位数"的
        RA 作为一组求最小割:哑铃布局下它恰等于中段并行通道数。
        """
        ds = {m: self.ideal_dist[self.lu_node].get(m, float("inf"))
              for m in dict.fromkeys(machine_nodes) if m != self.lu_node}
        if not ds:
            return 0
        vals = sorted(ds.values())
        mid = vals[len(vals) // 2]
        far = [m for m, d in ds.items() if d > mid]
        if not far:                                   # 全等距时退化为取最远的一组
            mx = max(vals)
            far = [m for m, d in ds.items() if d >= mx]
        k, _cut = self.lu_cut(far)
        return k

    def structural_features(self, machine_nodes: Sequence[str]) -> dict:
        k, cut = self.lu_cut(machine_nodes)
        return {
            "funnel_share": round(self.funnel_share(machine_nodes), 4),
            "lu_min_cut": k,
            "lu_cut_corridors": cut,
            "far_group_cut": self.far_group_cut(machine_nodes),
            "corridors_per_node": round(len(self.corridor_time) / len(self.nodes), 4),
        }


def _path_nodes(parent: Dict[str, Optional[str]], sink: str) -> List[str]:
    """增广路上除源点外的节点序列(自源向汇)。"""
    out: List[str] = []
    cur = sink
    while parent[cur] is not None:
        out.append(cur)
        cur = parent[cur]
    out.reverse()
    return out


# --------------------------------------------------------------------------
# 走廊-时段影子价格(规格 5.5)
# --------------------------------------------------------------------------

class PriceTable:
    """影子价格 pi(c,b):走廊 c 在时间桶 b 内**每单位占用时长**的边际 makespan 代价。

    量纲说明(这是价格化接口成立的关键):pi = (松弛该时空槽位一个容量单位所换来的
    makespan 改善) / 桶宽,是"时间/时间"的无量纲比率;于是一条路径的
    price_cost = sum(pi * 占用时长) 具有**时间量纲**,可与到达时刻直接相加。
    因此 arrive + theta * price_cost 是量纲一致的标量化,theta 为无量纲协调强度。

    这一点正是价格化接口替代原"lam * 累计让行等待"启发式的理由:后者把一个随算例
    规模增长的全局累计量与单道工序尺度的量相加,lam 无法跨算例可比。
    """

    def __init__(self, bucket_width: float):
        if bucket_width <= 0:
            raise ValueError("bucket_width 必须为正")
        self.bucket_width = float(bucket_width)
        self._pi: Dict[BucketKey, float] = {}

    def bucket(self, t: float) -> int:
        return int(t // self.bucket_width)

    def bucket_span(self, b: int) -> Tuple[float, float]:
        return b * self.bucket_width, (b + 1) * self.bucket_width

    def is_empty(self) -> bool:
        return not self._pi

    def set(self, cid: str, b: int, value: float) -> None:
        if value > 0:
            self._pi[(cid, b)] = value
        else:
            self._pi.pop((cid, b), None)

    def get(self, cid: str, b: int) -> float:
        return self._pi.get((cid, b), 0.0)

    def items(self):
        return self._pi.items()

    def interval_cost(self, cid: str, ts: float, te: float) -> float:
        """一次占用 [ts, te) 的价格总额:跨桶按各桶内的重叠时长加权。"""
        if te <= ts:
            return 0.0
        total = 0.0
        b = self.bucket(ts)
        while b * self.bucket_width < te:
            lo, hi = self.bucket_span(b)
            overlap = min(te, hi) - max(ts, lo)
            if overlap > 0:
                total += self.get(cid, b) * overlap
            b += 1
        return total

    def node_price(self, net: Network, node: str, t: float) -> float:
        """节点在 t 时刻的"通行权价格":相邻走廊在该时段价格的均值。

        用于上层评分(规格 6.5):衡量"把工序放到该 RA 处,其进出运输要买多贵的路"。
        取均值而非求和,使不同度数的节点可比。
        """
        cids = net.incident_corridors(node)
        if not cids:
            return 0.0
        b = self.bucket(t)
        return sum(self.get(cid, b) for cid in cids) / len(cids)


# --------------------------------------------------------------------------
# 容量化预约表(规格 5.2)
# --------------------------------------------------------------------------

class ReservationTable:
    """每条走廊的占用时窗列表,支持按走廊-时段设置容量、撤销与检查点回滚。

    容量默认为 1(与独占语义等价)。容量提升仅用于影子价格的有限差分探测
    (pricing.finite_difference_prices):把某个 (c,b) 的容量临时加 1,重解一次,
    makespan 的改善量即该槽位的边际价值。
    """

    def __init__(self, bucket_width: float = 0.0,
                 capacity_override: Optional[Dict[BucketKey, int]] = None):
        # cid -> 按 t_start 排序的 [t_start, t_end, agv, task];容量 > 1 时允许重叠
        self._res: Dict[str, List[Tuple[float, float, int, str]]] = {}
        self.bucket_width = float(bucket_width)
        self._cap: Dict[BucketKey, int] = dict(capacity_override or {})
        self._undo: List[Tuple[str, Tuple[float, float, int, str]]] = []

    # ---- 容量 ----

    def _bucket(self, t: float) -> int:
        return int(t // self.bucket_width) if self.bucket_width > 0 else 0

    def capacity(self, cid: str, ts: float, te: float) -> int:
        """占用区间跨越的所有时段中的最小容量(保守取法)。"""
        if not self._cap:
            return 1
        cap = 1 << 30
        b = self._bucket(ts)
        b_end = self._bucket(max(ts, te - 1e-9))
        while b <= b_end:
            cap = min(cap, self._cap.get((cid, b), 1))
            b += 1
        return max(1, cap)

    # ---- 查询 ----

    def _overlap_count(self, cid: str, ts: float, te: float) -> int:
        cnt = 0
        for a, b, _agv, _task in self._res.get(cid, []):
            if a >= te - 1e-12:
                break                       # 列表按 a 升序,后续不可能重叠
            if b > ts + 1e-12:
                cnt += 1
        return cnt

    def _is_free(self, cid: str, ts: float, tau: float) -> bool:
        te = ts + tau
        return self._overlap_count(cid, ts, te) < self.capacity(cid, ts, te)

    def earliest_entry(self, cid: str, t: float, tau: float) -> float:
        """从 t 起最早可占用 [t', t'+tau) 的时刻。"""
        for cand in self._entry_candidates(cid, t):
            if self._is_free(cid, cand, tau):
                return cand
        # 所有既有占用结束之后必然可行
        ends = [b for _a, b, _agv, _task in self._res.get(cid, [])]
        return max([t] + ends)

    def _entry_candidates(self, cid: str, t: float) -> List[float]:
        cands = {t}
        for _a, b, _agv, _task in self._res.get(cid, []):
            if b > t:
                cands.add(b)
        return sorted(cands)

    def feasible_entries(self, cid: str, t: float, tau: float,
                         limit: int, horizon_buckets: int = 3) -> List[float]:
        """从 t 起若干个可行进入时刻(升序,首个即最早)。

        除"最早可行"外,还给出后续时间桶的边界时刻——价格感知路由据此可以选择
        "多等一会儿,进一个更便宜的时段",这是单标签最早到达搜索无法表达的决策。
        """
        first = self.earliest_entry(cid, t, tau)
        out = [first]
        if limit <= 1:
            return out
        cands = set(self._entry_candidates(cid, t))
        if self.bucket_width > 0:
            b0 = self._bucket(first)
            for k in range(1, horizon_buckets + 1):
                cands.add((b0 + k) * self.bucket_width)
        for cand in sorted(cands):
            if len(out) >= limit:
                break
            if cand <= first + 1e-12:
                continue
            if self._is_free(cid, cand, tau):
                out.append(cand)
        return out

    # ---- 修改 ----

    def reserve(self, cid: str, ts: float, te: float, agv: int, task: str) -> None:
        lst = self._res.setdefault(cid, [])
        if self._overlap_count(cid, ts, te) >= self.capacity(cid, ts, te):
            raise AssertionError(f"预约冲突 {cid}: [{ts},{te}) 超出容量")
        item = (ts, te, agv, task)
        bisect.insort(lst, item)
        self._undo.append((cid, item))

    def release_all(self, task: str) -> int:
        """撤销某任务的全部占用(规格 5.2);返回撤销的区间数。"""
        removed = 0
        for cid, lst in self._res.items():
            keep = [r for r in lst if r[3] != task]
            if len(keep) != len(lst):
                removed += len(lst) - len(keep)
                self._res[cid] = keep
        if removed:
            self._undo = [(c, it) for c, it in self._undo if it[3] != task]
        return removed

    def checkpoint(self) -> int:
        """记录当前状态令牌,供 rollback 回退(供派车试探与价格探测使用)。"""
        return len(self._undo)

    def rollback(self, token: int) -> None:
        while len(self._undo) > token:
            cid, item = self._undo.pop()
            lst = self._res.get(cid)
            if not lst:
                continue
            idx = bisect.bisect_left(lst, item)
            if idx < len(lst) and lst[idx] == item:
                lst.pop(idx)

    # ---- 统计 ----

    def all_reservations(self) -> Dict[str, List[Tuple[float, float, int, str]]]:
        return self._res

    def occupancy(self, bucket_width: float) -> Dict[BucketKey, float]:
        """各走廊-时段的占用率 util[c][b] = 桶内被占用时长 / 桶宽,取值 [0,1]。

        这是**前瞻性**拥堵信号(我若此刻前往可能受阻),与解码器统计的实际让行
        等待(**回顾性**信号:这里已经真的堵了)含义不同,不可混用。
        """
        util: Dict[BucketKey, float] = {}
        if bucket_width <= 0:
            return util
        for cid, lst in self._res.items():
            for ts, te, _agv, _task in lst:
                b = int(ts // bucket_width)
                while b * bucket_width < te:
                    lo, hi = b * bucket_width, (b + 1) * bucket_width
                    overlap = min(te, hi) - max(ts, lo)
                    if overlap > 0:
                        util[(cid, b)] = util.get((cid, b), 0.0) + overlap / bucket_width
                    b += 1
        return util


# --------------------------------------------------------------------------
# 路由层(规格 5.3)
# --------------------------------------------------------------------------

@dataclass
class _Label:
    t: float          # 到达该节点的时刻
    g: float          # 累计价格代价
    node: str
    parent: int       # 上一个 label 在 pool 中的下标,-1 表示起点
    seg: Optional[Segment]


class Router:
    """时间窗路由:价格为空或 theta=0 时为单标签最早到达;否则为价格加权多标签搜索。

    conflict_free=False 时退化为查理想最短路 t*(规格 12.2 第一层对标)。
    """

    def __init__(self, network: Network, conflict_free: bool = True,
                 prices: Optional[PriceTable] = None, theta: float = 0.0,
                 max_entry_options: int = 3, label_budget: int = 3000,
                 bucket_width: float = 0.0,
                 capacity_override: Optional[Dict[BucketKey, int]] = None):
        self.net = network
        self.conflict_free = conflict_free
        self.prices = prices
        self.theta = float(theta)
        self.max_entry_options = int(max_entry_options)
        self.label_budget = int(label_budget)
        bw = bucket_width or (prices.bucket_width if prices is not None else 0.0)
        self.bucket_width = bw
        self.table = ReservationTable(bucket_width=bw,
                                      capacity_override=capacity_override)

    # ---- 是否启用价格感知搜索 ----
    def _price_aware(self) -> bool:
        return (self.conflict_free and self.theta > 0.0
                and self.prices is not None and not self.prices.is_empty())

    def route(self, start: str, goal: str, t0: float, agv: int, task: str,
              commit: bool = True) -> RoutePlan:
        if start == goal:
            return RoutePlan(start, goal, t0, t0)

        if not self.conflict_free:
            # 退化模式:运输时间 = 理想最短路,无预约
            arrive = t0 + self.net.ideal_dist[start][goal]
            return RoutePlan(start, goal, t0, arrive)

        segs, arrive, price_cost = (self._search_priced(start, goal, t0)
                                    if self._price_aware()
                                    else self._search_earliest(start, goal, t0))

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

        return RoutePlan(start, goal, t0, arrive, segs, waits, price_cost)

    # ---- 单标签最早到达(价格协调前的原始行为) ----

    def _search_earliest(self, start: str, goal: str,
                         t0: float) -> Tuple[List[Segment], float, float]:
        best: Dict[str, float] = {start: t0}
        prev: Dict[str, Tuple[str, str, float, float]] = {}
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

        segs: List[Segment] = []
        node = goal
        while node != start:
            u, cid, enter, exit_ = prev[node]
            segs.append(Segment(cid, u, node, enter, exit_))
            node = u
        segs.reverse()
        cost = 0.0
        if self.prices is not None:
            cost = sum(self.prices.interval_cost(s.corridor, s.enter, s.exit) for s in segs)
        return segs, best[goal], cost

    # ---- 价格加权多标签 Pareto 搜索 ----

    def _search_priced(self, start: str, goal: str,
                       t0: float) -> Tuple[List[Segment], float, float]:
        """在 (到达时刻 t, 累计价格 g) 上做 Pareto 支配剪枝,按 t + theta*g 出队。

        正确性:每条弧使 t 与 g 均非减,故 key = t + theta*g 沿路径单调非减,
        首次弹出 goal 即该标量化下的最优;支配关系 (t1<=t2 且 g1<=g2) 有效,
        因为节点可无限等待(停靠位不占通行资源),早到者能模拟晚到者的任何后续。
        """
        prices = self.prices
        assert prices is not None
        theta = self.theta

        pool: List[_Label] = [_Label(t0, 0.0, start, -1, None)]
        frontier: Dict[str, List[Tuple[float, float]]] = {start: [(t0, 0.0)]}
        heap: List[Tuple[float, float, float, int]] = [(t0, t0, 0.0, 0)]
        goal_idx: Optional[int] = None
        expanded = 0

        def dominated(node: str, t: float, g: float) -> bool:
            for ti, gi in frontier.get(node, ()):
                if ti <= t + 1e-12 and gi <= g + 1e-12:
                    return True
            return False

        def insert_frontier(node: str, t: float, g: float) -> None:
            lst = [p for p in frontier.get(node, []) if not (t <= p[0] + 1e-12 and g <= p[1] + 1e-12)]
            lst.append((t, g))
            frontier[node] = lst

        while heap:
            _key, t, g, idx = heapq.heappop(heap)
            lab = pool[idx]
            if lab.node == goal:
                goal_idx = idx
                break
            if expanded >= self.label_budget:
                break
            expanded += 1
            for cid, v, tau in self.net.adj[lab.node]:
                for enter in self.table.feasible_entries(cid, t, tau, self.max_entry_options):
                    arr = enter + tau
                    ng = g + prices.interval_cost(cid, enter, arr)
                    if dominated(v, arr, ng):
                        continue
                    insert_frontier(v, arr, ng)
                    pool.append(_Label(arr, ng, v, idx, Segment(cid, lab.node, v, enter, arr)))
                    heapq.heappush(heap, (arr + theta * ng, arr, ng, len(pool) - 1))

        if goal_idx is None:
            # 预算耗尽或未达:回退到最早到达搜索,保证解码永不失败(建模文档 B4)
            return self._search_earliest(start, goal, t0)

        segs: List[Segment] = []
        idx = goal_idx
        while pool[idx].seg is not None:
            segs.append(pool[idx].seg)      # type: ignore[arg-type]
            idx = pool[idx].parent
        segs.reverse()
        return segs, pool[goal_idx].t, pool[goal_idx].g
