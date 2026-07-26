"""事件驱动解码器、车辆派工规则、拥堵统计与关键路径(规格文档 6.2、6.3)。

解码保证(建模文档 B4 三重保证):任意合法染色体解码必得可行方案且 C_max 有限;
同一染色体解码结果完全确定(预约顺序 = OS 扫描中任务产生的顺序)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .instance import Instance, OpKey
from .network import Network, Router, RoutePlan


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


@dataclass
class DecodeResult:
    instance: Instance
    makespan: float
    ops: Dict[OpKey, OpRecord]
    transports: List[TransportRecord]
    dispatch_order: List[int]     # 任务产生顺序下所选车辆(供两阶段基线回放)
    congestion: Dict[str, float]  # 走廊 -> 累计进入前等待(规格 6.5 反馈信号)
    conflict_free: bool

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


def dispatch_rule(inst: Instance, net: Network,
                  loc: Dict[int, str], avail: Dict[int, float],
                  pickup: str, dest: str, ready: float) -> int:
    """派工规则(规格 6.3):以 t* 估算送达时刻最早者,并列取小车号。"""
    best_k, best_est = None, float("inf")
    for k in sorted(loc.keys()):
        est = max(avail[k] + net.ideal_dist[loc[k]][pickup], ready) + net.ideal_dist[pickup][dest]
        if est < best_est - 1e-12:
            best_k, best_est = k, est
    return best_k


def decode(inst: Instance, net: Network, ma: Dict[OpKey, int], os_seq: List[int],
           conflict_free: bool = True,
           forced_dispatch: Optional[List[int]] = None) -> DecodeResult:
    """事件驱动解码(规格 6.2)。os_seq 为工件号重复序列(δ_return=1 时含伪工序)。"""
    router = Router(net, conflict_free)

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
            if forced_dispatch is not None:
                k = forced_dispatch[len(dispatch_order)]
            else:
                k = dispatch_rule(inst, net, loc, avail, pickup, dest, ready[j])
            dispatch_order.append(k)
            empty = router.route(loc[k], pickup, avail[k], k, f"J{j}-{i}-empty")
            t_load = max(empty.arrive, ready[j])          # 车等件或件等车(B4)
            loaded = router.route(pickup, dest, t_load, k, f"J{j}-{i}-loaded")
            arrive = loaded.arrive
            loc[k], avail[k] = dest, arrive               # 卸货即走/即空闲(B5、C5)
            transports.append(TransportRecord(j, i, k, pickup, dest, ready[j], empty, loaded))
            for plan in (empty, loaded):
                for cid, w in plan.wait_by_corridor.items():
                    congestion[cid] = congestion.get(cid, 0.0) + w

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
    return DecodeResult(inst, makespan, ops, transports, dispatch_order,
                        congestion, conflict_free)


def critical_real_ops(result: DecodeResult) -> List[OpKey]:
    """从决定 C_max 的最后事件反向追溯关键路径,返回其上的实工序(规格 6.5 第 1 步)。"""
    ops = result.ops
    cur: Optional[OpKey] = max(ops, key=lambda k: (ops[k].finish, k))
    chain: List[OpKey] = []
    seen = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        rec = ops[cur]
        if not rec.pseudo:
            chain.append(cur)
        if rec.bind == "machine" and rec.machine_prev is not None:
            cur = rec.machine_prev
        elif rec.i > 1:
            cur = (rec.job, rec.i - 1)
        else:
            cur = None
    return chain
