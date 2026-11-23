"""便宜的可采纳对照臂:全局右移(RS)。

为什么需要它。本文的对照阶梯此前只有三档:R1(释放集为空,等于不动)、R2(闭包修复)、
R0+(热启动种群搜索,预算 0.2--2 s)。从"什么都不做"直接跳到"跑两秒搜索",中间缺一档
**便宜的全局重算**——而右移重调度恰是这一支文献里最标准的那一档
(见 dalcastagne2020reactive:响应快但不给出显式边界),不测它,"低两至三个数量级"
这个读数就有一部分来自对照选了种群搜索而非选了便宜方法。

机制。取一个统一延迟 Δ,把**尚未完成**的一切整体后推 Δ,已完成的部分原样保留:
路径、车辆指派、机器指派、扫描序一概不变,只是全部未来事件平移。Δ 取到刚好让
受阻走廊上所有可动的腿都落到阻断窗结束之后。

为什么这样构造通常可行。冻结集与 R2 用的是同一条判据(`t_start < t_now` 的段已开始,
不可动),故它按假设 A2 是可采纳的。平移保持一切间隔:两个都平移的事件之间间隔不变;
一个冻结、一个平移的事件之间间隔只会变大,而工序先后、机器不重叠、走廊不重叠都是
"≥"型约束。唯一的例外是节点容量:进行中的段在 t_now 后到达某节点,而原先停在该处、
本该在它到达前离开的车被推后,两者会在节点上叠加;此时校验报错,该例记为不可行。

代价在解质量与稳定性:完工时间恰好增加 Δ,而全部未来预约的时刻都变了
(按本文的偏差口径,改动比例接近未来预约的全部)。

A cheap admissible comparison arm: global right-shift (RS).

Why it is needed. The comparison ladder previously had only three rungs: R1 (empty release set, i.e. do nothing), R2 (closure repair), and R0+ (warm-start population search, budget 0.2--2 s). Jumping from "do nothing" straight to "search for two seconds" left out a rung of cheap global recomputation. Right-shift rescheduling is the standard rung in this literature (see dalcastagne2020reactive: fast response, but no explicit boundary). Without measuring it, part of the "two to three orders of magnitude lower" reading comes from comparing against population search rather than against a cheap method.

Mechanism. Take one uniform delay Δ and push everything not yet finished back by Δ, keeping the finished part unchanged: paths, vehicle assignment, machine assignment, and scan order all stay the same; only future events are translated. Δ is the smallest value that places every movable leg on the blocked corridor after the blockage window ends.

Why this construction is usually feasible. The frozen set uses the same test as R2 (a leg with `t_start < t_now` has started and is immovable), so under assumption A2 it is admissible. Translation preserves every gap: the gap between two shifted events is unchanged; the gap between one frozen event and one shifted event can only grow, and precedence, machine non-overlap and corridor non-overlap are all "≥" constraints. The one exception is node capacity: an in-progress leg may reach a node after t_now while the vehicle that should have left it first is pushed back, so the two overlap there; validation then reports it and the case counts as infeasible.

The cost is solution quality and stability: makespan increases by exactly Δ, and the times of all future reservations change (under this paper's deviation definition, the change ratio is close to all future reservations).
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

    The smallest uniform delay that places every movable leg on the blocked corridor after the blockage window.

    Look only at the blocked corridor: legs on other corridors are not in conflict, and raising Δ because of them would only lengthen the makespan for free, which is unfair to this baseline.
    """
    from algorithm.block_context import effective_block_windows
    delta = 0.0
    for cid, _t0, t1 in effective_block_windows(dist, bundle.reservations):
        movable = [
            r.t_start for r in bundle.reservations
            if r.corridor == cid and r.t_start >= dist.t_now - EPS
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
    """RS 臂:统一右移全部未完成事件,不改路径、不改指派、不改序。

    RS arm: right-shift every unfinished event by one delay, without changing paths, assignments, or sequence.
    """
    t_wall0 = time.perf_counter()
    base = bundle.result
    t_now = dist.t_now
    delta = _shift_delta(bundle, dist)

    from algorithm.node_engine import result_from_units, shift_units

    # 节点模型下离场、驱离行程随运输一起平移;节点停留由相邻走廊段导出,同样整体后移,
    # 跨越 t_now 的停留只是变长,故节点容量与走廊一样保持不违反。
    units = shift_units(list(base.strc_units), t_now, delta)  # type: ignore[attr-defined]
    arrive_of: Dict[Tuple[int, int], float] = {u.key: u.loaded.arrive for u in units}

    ops: Dict[Tuple[int, int], OpRecord] = {}
    for key, rec in base.ops.items():
        # 判「可动」用 start 而不是 finish:已开工的工序不中断,只是它之后的排程被推后。
        # "Movable" is judged by start, not finish: an operation already started is not interrupted; only the schedule after it is pushed back.
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

    new_result = result_from_units(inst, ops, units, base.dispatch_order)
    makespan = new_result.makespan

    errs = validate(inst, new_result.to_timetable())
    from algorithm.block_context import effective_block_windows
    for cid, t0, t1 in effective_block_windows(dist, bundle.reservations):
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
