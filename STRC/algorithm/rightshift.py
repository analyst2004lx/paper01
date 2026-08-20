"""便宜的可采纳对照臂:全局右移(RS)。

为什么需要它。本文的对照阶梯此前只有三档:R1(释放集为空,等于不动)、R2(闭包修复)、
R0+(热启动种群搜索,预算 0.2--2 s)。从"什么都不做"直接跳到"跑两秒搜索",中间缺一档
**便宜的全局重算**——而右移重调度恰是这一支文献里最标准的那一档
(见 dalcastagne2020reactive:响应快但不给出显式边界),不测它,"低两至三个数量级"
这个读数就有一部分来自对照选了种群搜索而非选了便宜方法。

机制。取一个统一延迟 Δ,把**尚未完成**的一切整体后推 Δ,已完成的部分原样保留:
路径、车辆指派、机器指派、扫描序一概不变,只是全部未来事件平移。Δ 取到刚好让
受阻走廊上所有可动的腿都落到阻断窗结束之后。

为什么这样构造是可行的。冻结集与 R2 用的是同一条判据(`t_end <= t_now` 不可动),
故它按假设 A2 是可采纳的。平移保持一切间隔:两个都平移的事件之间间隔不变;
一个冻结、一个平移的事件之间间隔只会变大,而所有约束(工序先后、机器不重叠、
走廊不重叠)都是"≥"型,间隔变大不会违反。于是无需重新路由即得可行解。

代价在解质量与稳定性:完工时间恰好增加 Δ,而全部未来预约的时刻都变了
(按本文的偏差口径,改动比例接近未来预约的全部)。
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from algorithm.clbs_bridge import (
    DecodeResult,
    Instance,
    Network,
    OpRecord,
    RoutePlan,
    Segment,
    TransportRecord,
    validate,
)
from algorithm.disturbance import Disturbance
from algorithm.metrics import evaluate_deviation
from algorithm.repair import RepairResult
from algorithm.schedule_io import ScheduleBundle, reservations_from_result

EPS = 1e-9


def _shift_delta(bundle: ScheduleBundle, dist: Disturbance) -> float:
    """求刚好让受阻走廊上可动的腿全部落到阻断窗之后的最小统一延迟。

    只看受阻走廊:别的走廊上的腿本来就不冲突,用它们抬高 Δ 只会白白拉长完工时间,
    对这条基线不公平。
    """
    from algorithm.block_context import block_windows_from_dist
    delta = 0.0
    for cid, _t0, t1 in block_windows_from_dist(dist):
        movable = [
            r.t_start for r in bundle.reservations
            if r.corridor == cid and r.t_end > dist.t_now + EPS
        ]
        if not movable:
            continue
        delta = max(delta, t1 - min(movable))
    return max(0.0, delta)


def _shift_plan(plan: RoutePlan, t_now: float, delta: float) -> RoutePlan:
    segs: List[Segment] = []
    for s in plan.segments:
        if s.exit > t_now + EPS:
            segs.append(Segment(s.corridor, s.u, s.v, s.enter + delta, s.exit + delta))
        else:
            segs.append(s)
    arrive = segs[-1].exit if segs else (
        plan.arrive + delta if plan.arrive > t_now + EPS else plan.arrive)
    t0 = plan.t0 + delta if plan.t0 > t_now + EPS else plan.t0
    return RoutePlan(plan.start, plan.goal, t0, arrive, segs,
                     dict(plan.wait_by_corridor), plan.price_cost)


def repair_by_right_shift(
    inst: Instance,
    net: Network,
    bundle: ScheduleBundle,
    dist: Disturbance,
    **_kwargs,
) -> RepairResult:
    """RS 臂:统一右移全部未完成事件,不改路径、不改指派、不改序。"""
    t_wall0 = time.perf_counter()
    base = bundle.result
    t_now = dist.t_now
    delta = _shift_delta(bundle, dist)

    transports: List[TransportRecord] = []
    arrive_of: Dict[Tuple[int, int], float] = {}
    for tr in base.transports:
        empty = _shift_plan(tr.empty_plan, t_now, delta)
        loaded = _shift_plan(tr.loaded_plan, t_now, delta)
        ready = tr.ready + delta if tr.ready > t_now + EPS else tr.ready
        transports.append(TransportRecord(
            tr.job, tr.i, tr.agv, tr.pickup, tr.dest, ready, empty, loaded))
        arrive_of[(tr.job, tr.i)] = loaded.arrive

    ops: Dict[Tuple[int, int], OpRecord] = {}
    for key, rec in base.ops.items():
        # 判「可动」用 start 而不是 finish:已开工的工序不中断,只是它之后的排程被推后。
        moved = rec.start > t_now + EPS
        arrive = arrive_of.get(key)
        if arrive is None:
            arrive = rec.arrive + delta if rec.arrive > t_now + EPS else rec.arrive
        start = rec.start + delta if moved else rec.start
        finish = rec.finish + delta if moved else rec.finish
        if start < arrive - EPS:
            start, finish = arrive, arrive + (rec.finish - rec.start)
        ops[key] = OpRecord(rec.job, rec.i, rec.machine, arrive, start, finish,
                            rec.bind, rec.machine_prev, rec.pseudo)

    makespan = max(r.finish for r in ops.values())
    new_result = DecodeResult(
        inst, makespan, ops, transports, list(base.dispatch_order),
        dict(base.congestion), True, 0.0, {},
    )

    errs = validate(inst, new_result.to_timetable())
    from algorithm.block_context import block_windows_from_dist
    for cid, t0, t1 in block_windows_from_dist(dist):
        for r in reservations_from_result(new_result):
            if r.corridor == cid and r.overlaps(t0, t1):
                errs.append(f"post-shift still on blocked corridor: {r.task}")

    dev = evaluate_deviation(base, new_result)
    wall_ms = (time.perf_counter() - t_wall0) * 1000
    return RepairResult(
        feasible=not errs,
        release_size=0,
        level_used=0,
        makespan=makespan,
        makespan_ref=base.makespan,
        deviation=dev,
        wall_ms=wall_ms,
        result=new_result,
        errors=errs,
        meta={"arm": "RS", "delta": delta},
    )
