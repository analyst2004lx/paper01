"""事件驱动解码器、车辆派工规则、拥堵/价格统计与关键路径归因(规格 6.2、6.3、6.5)。

解码保证(建模文档 B4 三重保证):任意合法染色体解码必得可行方案且 C_max 有限;
给定染色体与价格表,解码结果完全确定(预约顺序 = OS 扫描中任务产生的顺序)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .instance import Instance, OpKey
from .network import BucketKey, Network, PriceTable, RoutePlan, Router

EPS = 1e-9
# 空载段中让行等待占比超过此阈值时,瓶颈归因于走廊而非车辆可用性
CORRIDOR_SHARE = 0.5


@dataclass
class OpRecord:
    job: int
    i: int
    machine: Optional[int]        # 伪工序(回运)为 None
    arrive: float                 # 工件到达时刻
    start: float
    finish: float
    bind: str                     # 'arrive' | 'machine':start 由哪一支决定
    machine_prev: Optional[OpKey]  # 同机前一工序
    pseudo: bool


@dataclass
class TransportRecord:
    job: int
    i: int
    agv: int
    pickup: str
    dest: str
    ready: float                  # 工件就绪时刻(前道完工;首道为 0)
    empty_plan: RoutePlan
    loaded_plan: RoutePlan

    @property
    def arrive(self) -> float:
        return self.loaded_plan.arrive

    @property
    def price_cost(self) -> float:
        return self.empty_plan.price_cost + self.loaded_plan.price_cost


@dataclass
class CriticalItem:
    """关键链上的一个环节及其归因类型。

    kind 取值与含义(规格 6.5 第 1 步):
    - 'operation' 该工序自身的加工占用;
    - 'machine'   开工被同机前一工序占用所卡;
    - 'upstream'  开工被上游工序完工所卡(车已先到,件未好);
    - 'vehicle'   开工被车辆可用性所卡(件已好,车未到且非路网所致);
    - 'corridor'  运输途中在某走廊的让行等待,带具体走廊与时段。

    原实现只有 'machine' 与隐式的上游回溯两支,运输段完全不在链上,导致被
    "工件到达"卡住时无法区分是上游慢、车不够、还是路上堵——反馈算子因此无的放矢。
    """
    kind: str
    op: Optional[OpKey] = None
    corridor: Optional[str] = None
    t_start: float = 0.0
    t_end: float = 0.0
    amount: float = 0.0
    agv: Optional[int] = None


@dataclass
class DecodeResult:
    instance: Instance
    makespan: float
    ops: Dict[OpKey, OpRecord]
    transports: List[TransportRecord]
    dispatch_order: List[int]     # 任务产生顺序下所选车辆(供两阶段基线回放)
    congestion: Dict[str, float]  # 走廊 -> 累计进入前等待(回顾性信号)
    conflict_free: bool
    price_cost_total: float = 0.0  # 全部路径的影子价格总额(层间接口的"账单")
    occupancy: Dict[BucketKey, float] = field(default_factory=dict)  # 前瞻性信号

    def agv_stats(self) -> Dict[int, dict]:
        stats: Dict[int, dict] = {}
        for tr in self.transports:
            s = stats.setdefault(tr.agv, {"loaded_time": 0.0, "empty_time": 0.0, "wait_time": 0.0})
            s["loaded_time"] += tr.loaded_plan.travel_time
            s["empty_time"] += tr.empty_plan.travel_time
            s["wait_time"] += tr.empty_plan.total_wait + tr.loaded_plan.total_wait
        return stats

    def to_timetable(self) -> dict:
        """统一时刻表格式(校验器/甘特图/落盘共用)。"""
        operations = [
            {"job": r.job, "i": r.i, "machine": r.machine,
             "start": r.start, "finish": r.finish}
            for r in self.ops.values() if not r.pseudo
        ]
        returns = [
            {"job": r.job, "complete": r.finish}
            for r in self.ops.values() if r.pseudo
        ]
        agv_segments = []
        for tr in self.transports:
            for kind, plan in (("empty", tr.empty_plan), ("loaded", tr.loaded_plan)):
                task = f"J{tr.job}-{tr.i}-{kind}"
                for s in plan.segments:
                    agv_segments.append({
                        "agv": tr.agv, "u": s.u, "v": s.v,
                        "enter": s.enter, "exit": s.exit, "task": task,
                    })
        agv_segments.sort(key=lambda x: (x["agv"], x["enter"]))
        return {
            "instance": self.instance.name,
            "delta_return": self.instance.delta_return,
            "makespan": self.makespan,
            "operations": sorted(operations, key=lambda x: (x["job"], x["i"])),
            "returns": sorted(returns, key=lambda x: x["job"]),
            "agv_segments": agv_segments,
        }


# --------------------------------------------------------------------------
# 派工规则(规格 6.3)
# --------------------------------------------------------------------------

def dispatch_rule(inst: Instance, net: Network,
                  loc: Dict[int, str], avail: Dict[int, float],
                  pickup: str, dest: str, ready: float,
                  prices: Optional[PriceTable] = None,
                  theta: float = 0.0) -> int:
    """派工规则:以估算送达时刻最早者为准,并列取小车号。

    当价格表可用时,估算值加入"沿理想路径要买的通行权价格",使派车决策也感知
    路网的时空紧张程度——这是原实现中唯一仍活在"无冲突理想世界"里的环节。
    价格项与时间同量纲,故可直接相加。
    """
    best_k, best_est = None, float("inf")
    for k in sorted(loc.keys()):
        t_pick = max(avail[k] + net.ideal_dist[loc[k]][pickup], ready)
        est = t_pick + net.ideal_dist[pickup][dest]
        if prices is not None and theta > 0.0 and not prices.is_empty():
            # 以节点价格 x 行驶时长近似两段路径要买的通行权
            est += theta * (
                prices.node_price(net, pickup, avail[k]) * net.ideal_dist[loc[k]][pickup]
                + prices.node_price(net, dest, t_pick) * net.ideal_dist[pickup][dest])
        if est < best_est - 1e-12:
            best_k, best_est = k, est
    return best_k


# --------------------------------------------------------------------------
# 解码(规格 6.2)
# --------------------------------------------------------------------------

def dispatch_exact(router: Router, net: Network,
                   loc: Dict[int, str], avail: Dict[int, float],
                   pickup: str, dest: str, ready: float
                   ) -> Tuple[int, Optional[Tuple[RoutePlan, RoutePlan]]]:
    """派车试探:对每辆候选车做一次真实的两段路由,取实际送达最早者。

    这是补上"全框架唯一开环残余"的直接做法——原规则用理想最短路矩阵估算送达时刻,
    完全不查预约表,于是可能选中一辆"看起来近、实际路上全被占住"的车。

    实现依赖预约表的检查点/回滚:空载段必须先真实落表,载货段才能看到它占用的时窗,
    否则两段可能被规划到同一走廊的同一时段;评估完毕后整体回滚,不留痕迹。

    代价与剪枝。试探把每个运输任务的路由调用数从 2 抬到 2*NA,实测单次评价成本约为规则
    派车的 4.6 倍(output/matrix/gen100:15.9 vs 3.5 毫秒)。而同代数下试探派车比规则派车
    好约 3%,同挂钟下这 3% 恰好被算力吃光(output/matrix/p3:-0.12%)。故降本即增效。

    这里用一个**可采纳下界**做剪枝:无冲突路由只会因让行而更晚,绝不会快过理想最短路,
    所以 dispatch_rule 用的理想估算是实际送达时刻的下界。若某辆车的下界都赢不了当前最优
    实测值,它的实测值必然也赢不了,于是无需为它跑路由。原实现按车号升序保留首个严格更优
    者,被剪掉的车在原实现中同样不会成为最优者,故**输出与全量试探逐位相同**,只是省去
    注定失败的试探。

    另返回胜者的两段路径:原先胜者的路径在试探时已经算过一遍,回滚后又被 decode 重算,
    白费两次路由调用。route(commit=True) 不过是把各段 reserve 一遍,故缓存即可复用。
    """
    best_k, best_est = None, float("inf")
    best_plans: Optional[Tuple[RoutePlan, RoutePlan]] = None
    for k in sorted(loc.keys()):
        lb = (max(avail[k] + net.ideal_dist[loc[k]][pickup], ready)
              + net.ideal_dist[pickup][dest])
        if lb >= best_est - 1e-12:
            continue                    # 下界已不优于现任,实测值必然也不优
        token = router.table.checkpoint()
        try:
            empty = router.route(loc[k], pickup, avail[k], k, f"probe{k}-empty", commit=True)
            t_load = max(empty.arrive, ready)
            loaded = router.route(pickup, dest, t_load, k, f"probe{k}-loaded", commit=False)
            est = loaded.arrive
        finally:
            router.table.rollback(token)
        if est < best_est - 1e-12:
            best_k, best_est, best_plans = k, est, (empty, loaded)
    return best_k, best_plans


def decode(inst: Instance, net: Network, ma: Dict[OpKey, int], os_seq: List[int],
           conflict_free: bool = True,
           forced_dispatch: Optional[List[int]] = None,
           prices: Optional[PriceTable] = None,
           theta: float = 0.0,
           bucket_width: float = 0.0,
           capacity_override: Optional[Dict[BucketKey, int]] = None,
           max_entry_options: int = 3,
           collect_occupancy: bool = False,
           dispatch: str = "rule",
           forbid: Optional[Dict[OpKey, Set[int]]] = None) -> DecodeResult:
    """事件驱动解码。os_seq 为工件号重复序列(delta_return=1 时含伪工序)。

    theta=0 或 prices 为空时,路由退化为纯最早到达搜索,结果与价格协调前完全一致。
    """
    router = Router(net, conflict_free, prices=prices, theta=theta,
                    max_entry_options=max_entry_options,
                    bucket_width=bucket_width, capacity_override=capacity_override)

    free: Dict[int, float] = {m: 0.0 for m in inst.machine_node}
    last_on_machine: Dict[int, OpKey] = {}
    pos: Dict[int, str] = {j: inst.lu_node for j in inst.job_ids}
    ready: Dict[int, float] = {j: 0.0 for j in inst.job_ids}
    loc: Dict[int, str] = {k: inst.lu_node for k in range(1, inst.num_agvs + 1)}
    avail: Dict[int, float] = {k: 0.0 for k in loc}
    op_counter: Dict[int, int] = {j: 0 for j in inst.job_ids}

    ops: Dict[OpKey, OpRecord] = {}
    transports: List[TransportRecord] = []
    dispatch_order: List[int] = []
    congestion: Dict[str, float] = {}
    price_total = 0.0

    for j in os_seq:
        op_counter[j] += 1
        i = op_counter[j]
        pseudo = inst.is_pseudo(j, i)
        if pseudo:
            m, dest, p = None, inst.lu_node, 0.0
        else:
            m = ma[(j, i)]
            dest = inst.machine_node[m]
            p = inst.proc_time[(j, i)][m]

        # ---- 运输阶段 ----
        if pos[j] == dest:
            arrive = ready[j]          # 同机连续工序,无运输任务(C4)
        else:
            pickup = pos[j]
            probed = None            # 仅派车试探会产出可复用的路径
            if forced_dispatch is not None:
                k = forced_dispatch[len(dispatch_order)]
            else:
                allowed = loc
                if forbid:
                    banned = forbid.get((j, i))
                    if banned:
                        rest = {kk: vv for kk, vv in loc.items() if kk not in banned}
                        if rest:
                            allowed = rest     # 至少留一辆,保持可解码性
                sub_avail = {kk: avail[kk] for kk in allowed}
                if dispatch == "exact" and conflict_free:
                    k, probed = dispatch_exact(router, net, allowed, sub_avail,
                                               pickup, dest, ready[j])
                else:
                    k = dispatch_rule(inst, net, allowed, sub_avail,
                                      pickup, dest, ready[j], prices, theta)
            dispatch_order.append(k)
            if probed is not None:
                # 试探时已在同一预约表状态下算过这两段,直接落表,省去两次重复路由
                empty, loaded = probed
                for plan, tag in ((empty, "empty"), (loaded, "loaded")):
                    for s in plan.segments:
                        router.table.reserve(s.corridor, s.enter, s.exit, k,
                                             f"J{j}-{i}-{tag}")
            else:
                empty = router.route(loc[k], pickup, avail[k], k, f"J{j}-{i}-empty")
                t_load = max(empty.arrive, ready[j])      # 车等件或件等车(B4)
                loaded = router.route(pickup, dest, t_load, k, f"J{j}-{i}-loaded")
            arrive = loaded.arrive
            loc[k], avail[k] = dest, arrive               # 卸货即走/即空闲(B5、C5)
            transports.append(TransportRecord(j, i, k, pickup, dest, ready[j], empty, loaded))
            for plan in (empty, loaded):
                for cid, w in plan.wait_by_corridor.items():
                    congestion[cid] = congestion.get(cid, 0.0) + w
                price_total += plan.price_cost

        # ---- 加工阶段 ----
        if pseudo:
            start = finish = arrive
            bind, mprev = "arrive", None
        else:
            mf = free[m]
            bind = "machine" if mf > arrive else "arrive"
            start = max(arrive, mf)                       # B4 核心公式
            finish = start + p
            mprev = last_on_machine.get(m)
            free[m] = finish
            last_on_machine[m] = (j, i)

        ops[(j, i)] = OpRecord(j, i, m, arrive, start, finish, bind, mprev, pseudo)
        pos[j], ready[j] = dest, finish

    makespan = max(r.finish for r in ops.values())
    occ = router.table.occupancy(router.bucket_width) if collect_occupancy else {}
    return DecodeResult(inst, makespan, ops, transports, dispatch_order,
                        congestion, conflict_free, price_total, occ)


# --------------------------------------------------------------------------
# 关键路径归因(规格 6.5 第 1 步)
# --------------------------------------------------------------------------

def critical_chain(result: DecodeResult) -> List[CriticalItem]:
    """从决定 C_max 的最后事件反向追溯,产出带归因类型的关键链。

    与只回溯工序链的原实现相比,本函数把运输段纳入链上,并在开工被"工件到达"
    卡住时进一步分解到底是上游工序慢、车辆不够、还是某条走廊某个时段堵。
    """
    ops = result.ops
    tr_by_op: Dict[OpKey, TransportRecord] = {(t.job, t.i): t for t in result.transports}
    # 每辆车按任务产生顺序的任务链,用于"车辆可用性"分支的回溯
    prev_task_of: Dict[OpKey, OpKey] = {}
    last_of_agv: Dict[int, OpKey] = {}
    for tr in result.transports:
        key = (tr.job, tr.i)
        if tr.agv in last_of_agv:
            prev_task_of[key] = last_of_agv[tr.agv]
        last_of_agv[tr.agv] = key

    items: List[CriticalItem] = []
    cur: Optional[OpKey] = max(ops, key=lambda k: (ops[k].finish, k))
    seen: Set[OpKey] = set()

    while cur is not None and cur not in seen:
        seen.add(cur)
        rec = ops[cur]
        if not rec.pseudo:
            items.append(CriticalItem("operation", op=cur, t_start=rec.start,
                                      t_end=rec.finish, amount=rec.finish - rec.start))

        if rec.bind == "machine" and rec.machine_prev is not None:
            items.append(CriticalItem("machine", op=cur, t_start=rec.arrive,
                                      t_end=rec.start, amount=rec.start - rec.arrive))
            cur = rec.machine_prev
            continue

        tr = tr_by_op.get(cur)
        if tr is None:
            cur = (rec.job, rec.i - 1) if rec.i > 1 else None
            continue

        # 载货段的让行等待:无论瓶颈在哪一侧,这部分都实际拖长了到达时刻
        for cid, wf, wt, amt in tr.loaded_plan.wait_events():
            items.append(CriticalItem("corridor", op=cur, corridor=cid, t_start=wf,
                                      t_end=wt, amount=amt, agv=tr.agv))

        if tr.ready >= tr.empty_plan.arrive - EPS:
            # 车先到、件未好 -> 瓶颈在上游工序
            items.append(CriticalItem("upstream", op=cur, t_start=tr.empty_plan.arrive,
                                      t_end=tr.ready, amount=max(0.0, tr.ready - tr.empty_plan.arrive)))
            cur = (rec.job, rec.i - 1) if rec.i > 1 else None
            continue

        # 件已好、车后到 -> 分解空载段:是路上堵,还是车本身腾不出来
        for cid, wf, wt, amt in tr.empty_plan.wait_events():
            items.append(CriticalItem("corridor", op=cur, corridor=cid, t_start=wf,
                                      t_end=wt, amount=amt, agv=tr.agv))
        w_empty = tr.empty_plan.total_wait
        travel = tr.empty_plan.travel_time
        if w_empty <= CORRIDOR_SHARE * max(EPS, w_empty + travel):
            items.append(CriticalItem("vehicle", op=cur, t_start=tr.ready,
                                      t_end=tr.empty_plan.arrive, agv=tr.agv,
                                      amount=max(0.0, tr.empty_plan.arrive - tr.ready)))
        cur = prev_task_of.get(cur) or ((rec.job, rec.i - 1) if rec.i > 1 else None)

    return items


def critical_real_ops(result: DecodeResult) -> List[OpKey]:
    """关键链上的实工序(去重、保持追溯顺序),供改派算子挑选候选。"""
    out: List[OpKey] = []
    for it in critical_chain(result):
        if it.op is not None and not result.ops[it.op].pseudo and it.op not in out:
            out.append(it.op)
    return out


def critical_corridor_slots(result: DecodeResult, bucket_width: float
                            ) -> List[BucketKey]:
    """关键链上出现的走廊-时段槽位,供影子价格加权与错峰算子定位。"""
    if bucket_width <= 0:
        return []
    out: List[BucketKey] = []
    for it in critical_chain(result):
        if it.kind == "corridor" and it.corridor is not None:
            key = (it.corridor, int(it.t_start // bucket_width))
            if key not in out:
                out.append(key)
    return out


def blocking_opponents(result: DecodeResult, cid: str, t_start: float, t_end: float
                       ) -> List[OpKey]:
    """在 [t_start, t_end) 占用走廊 cid、从而造成让行的对手任务。

    这是"冲突凭证"的具体内容:下层解冲突时天然知道是谁挡了谁,把这一对操作对象
    交给上层,上层的邻域就不再是随机变异,而是定向修复。
    """
    out: List[OpKey] = []
    for tr in result.transports:
        for plan in (tr.empty_plan, tr.loaded_plan):
            for s in plan.segments:
                if s.corridor != cid:
                    continue
                if s.exit > t_start + EPS and s.enter < t_end - EPS:
                    key = (tr.job, tr.i)
                    if key not in out:
                        out.append(key)
    return out
