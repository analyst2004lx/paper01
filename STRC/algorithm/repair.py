"""有界修复:释放影响域内预约 → 安装扰动 → 按原 OS 重放(外侧冻结,内侧改路)。

Phase B 最小引擎 = 升级阶梯第 1 级(只改路径、原车不变)。
R1/R2 只差 release_set 的来源(任务图 vs 时空闭包)。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from algorithm.clbs_bridge import (
    DecodeResult,
    Instance,
    Network,
    OpRecord,
    RoutePlan,
    Router,
    TransportRecord,
    validate,
)
from algorithm.closure import (
    ReservationRef,
    job_precedence_from_reservations,
    machine_chains_from_ops,
    release_set_from_tasks,
    spatiotemporal_closure,
    task_graph_impact,
)
from algorithm.disturbance import Disturbance, seed_failed_reservations
from algorithm.metrics import Deviation, evaluate_deviation
from algorithm.schedule_io import ScheduleBundle, reservations_from_result

EPS = 1e-9


@dataclass
class RepairResult:
    feasible: bool
    closure_size: int = 0
    release_size: int = 0
    level_used: Optional[int] = None
    makespan: Optional[float] = None
    makespan_ref: Optional[float] = None
    deviation: Optional[Deviation] = None
    wall_ms: float = 0.0
    result: Optional[DecodeResult] = None
    errors: List[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def _tr_map(result: DecodeResult) -> Dict[Tuple[int, int], TransportRecord]:
    return {(tr.job, tr.i): tr for tr in result.transports}


def _segments_to_reroute(
    j: int, i: int, closed_tasks: Set[str]
) -> Tuple[bool, bool]:
    """决定该工序的空载段/满载段各自是否重路。

    释放集是\u4e00个**预约**集合,而不是工序集合。早先这里按工序判定——两段里任一段
    落在闭包内就整道重规划——于是当只有满载段进闭包时,空载段也被改写,而它的
    task 标签并不在释放集里,E2b 便记为「外侧漂移」。实测 26 个失败格里 84 条漂移
    预约无一例外都是这种同工序的空载段,其中 71 条在 t_now 之前就已执行完毕,
    改写它同时违反假设 A2。故改为按段判定。

    空载段进闭包必然带着满载段一起(两者是同车相邻预约,同车后继边由前者指向
    后者),反之不成立。第二个返回值里的 or 只是防御:若边集将来变动导致这个
    蕴含不再成立,重路空载段而冻结满载段会让满载段的起点失去依据。
    """
    need_empty = f"J{j}-{i}-empty" in closed_tasks
    need_loaded = f"J{j}-{i}-loaded" in closed_tasks
    return need_empty, need_loaded or need_empty


def _install_block(router: Router, dist: Disturbance) -> None:
    from algorithm.block_context import block_windows_from_dist
    for cid, t0, t1 in block_windows_from_dist(dist):
        router.table.reserve(cid, t0, t1, 0, "__BLOCK__")


def _precommit_frozen(
    router: Router,
    reservations: Sequence[ReservationRef],
    closed_tasks: Set[str],
    dist: Disturbance,
) -> List[str]:
    """预提交闭包外预约;若外侧与阻断冲突则记错误(闭包漏网)。"""
    from algorithm.block_context import block_windows_from_dist
    errs: List[str] = []
    blocks = block_windows_from_dist(dist)
    for r in reservations:
        if r.task in closed_tasks:
            continue
        hit = any(
            r.corridor == cid and r.overlaps(t0, t1) for cid, t0, t1 in blocks
        )
        if hit:
            errs.append(
                f"frozen overlaps block: {r.task}@{r.corridor}[{r.t_start},{r.t_end})"
            )
            continue
        try:
            router.table.reserve(r.corridor, r.t_start, r.t_end, r.agv, r.task)
        except AssertionError as e:
            errs.append(f"precommit fail {r.task}: {e}")
    return errs


def replay_reroute(
    inst: Instance,
    net: Network,
    bundle: ScheduleBundle,
    dist: Disturbance,
    release: Sequence[ReservationRef],
) -> RepairResult:
    """第 1 级修复:释放 release 内任务的运输,原车强制改路重放。"""
    t_wall0 = time.perf_counter()
    base = bundle.result
    closed_tasks = {r.task for r in release}
    tr_old = _tr_map(base)

    router = Router(net, conflict_free=True)
    _install_block(router, dist)
    pre_errs = _precommit_frozen(router, bundle.reservations, closed_tasks, dist)

    free: Dict[int, float] = {m: 0.0 for m in inst.machine_node}
    last_on_machine: Dict[int, Tuple[int, int]] = {}
    pos: Dict[int, str] = {j: inst.lu_node for j in inst.job_ids}
    ready: Dict[int, float] = {j: 0.0 for j in inst.job_ids}
    loc: Dict[int, str] = {k: inst.lu_node for k in range(1, inst.num_agvs + 1)}
    avail: Dict[int, float] = {k: 0.0 for k in loc}
    op_counter: Dict[int, int] = {j: 0 for j in inst.job_ids}

    ops: Dict[Tuple[int, int], OpRecord] = {}
    transports: List[TransportRecord] = []
    dispatch_order: List[int] = []
    congestion: Dict[str, float] = {}
    replay_errs: List[str] = list(pre_errs)

    try:
        for j in bundle.os_seq:
            op_counter[j] += 1
            i = op_counter[j]
            pseudo = inst.is_pseudo(j, i)
            if pseudo:
                m, dest, p = None, inst.lu_node, 0.0
            else:
                m = bundle.ma[(j, i)]
                dest = inst.machine_node[m]
                p = inst.proc_time[(j, i)][m]

            if pos[j] == dest:
                arrive = ready[j]
            else:
                pickup = pos[j]
                key = (j, i)
                old = tr_old.get(key)
                if old is None:
                    raise RuntimeError(f"missing original transport for {key}")
                re_empty, re_loaded = _segments_to_reroute(j, i, closed_tasks)
                k = old.agv
                dispatch_order.append(k)
                if not (re_empty or re_loaded):
                    # 外侧冻结:沿用原路径(已在表中),只推进车辆/工件状态
                    empty, loaded = old.empty_plan, old.loaded_plan
                    arrive = loaded.arrive
                    loc[k], avail[k] = dest, arrive
                    transports.append(TransportRecord(
                        j, i, k, pickup, dest, ready[j], empty, loaded))
                else:
                    # 内侧改路:被释放的段表中无旧预约,原车重规划;
                    # 未被释放的段已由 _precommit_frozen 占位,沿用原计划。
                    if re_empty:
                        empty = router.route(
                            loc[k], pickup, max(avail[k], dist.t_now),
                            k, f"J{j}-{i}-empty")
                    else:
                        empty = old.empty_plan
                    t_load = max(empty.arrive, ready[j], dist.t_now, avail[k])
                    if re_loaded:
                        loaded = router.route(pickup, dest, t_load, k,
                                              f"J{j}-{i}-loaded")
                    else:
                        loaded = old.loaded_plan
                    arrive = loaded.arrive
                    loc[k], avail[k] = dest, arrive
                    transports.append(TransportRecord(
                        j, i, k, pickup, dest, ready[j], empty, loaded))
                    for plan, fresh in ((empty, re_empty), (loaded, re_loaded)):
                        if not fresh:
                            continue
                        for cid, w in plan.wait_by_corridor.items():
                            congestion[cid] = congestion.get(cid, 0.0) + w

            if pseudo:
                start = finish = arrive
                bind, mprev = "arrive", None
            else:
                mf = free[m]  # type: ignore[index]
                bind = "machine" if mf > arrive else "arrive"
                start = max(arrive, mf)
                finish = start + p
                mprev = last_on_machine.get(m)  # type: ignore[arg-type]
                free[m] = finish  # type: ignore[index]
                last_on_machine[m] = (j, i)  # type: ignore[index]

            ops[(j, i)] = OpRecord(j, i, m, arrive, start, finish, bind, mprev, pseudo)
            pos[j], ready[j] = dest, finish
    except Exception as e:  # noqa: BLE001 — 修复失败统一收口
        wall_ms = (time.perf_counter() - t_wall0) * 1000
        return RepairResult(
            feasible=False, release_size=len(release), level_used=1,
            makespan_ref=base.makespan, wall_ms=wall_ms,
            errors=replay_errs + [f"replay exception: {e}"],
            meta={"closed_tasks": len(closed_tasks)},
        )

    makespan = max(r.finish for r in ops.values())
    new_result = DecodeResult(
        inst, makespan, ops, transports, dispatch_order, congestion, True, 0.0, {}
    )
    v_errs = validate(inst, new_result.to_timetable())
    from algorithm.block_context import block_windows_from_dist
    for cid, t0, t1 in block_windows_from_dist(dist):
        for r in reservations_from_result(new_result):
            if r.corridor == cid and r.overlaps(t0, t1):
                v_errs.append(
                    f"post-repair still on blocked corridor: {r.task}"
                )

    dev = evaluate_deviation(base, new_result)
    wall_ms = (time.perf_counter() - t_wall0) * 1000
    ok = (not v_errs) and (not replay_errs)
    return RepairResult(
        feasible=ok,
        closure_size=len(release),
        release_size=len(release),
        level_used=1,
        makespan=makespan,
        makespan_ref=base.makespan,
        deviation=dev,
        wall_ms=wall_ms,
        result=new_result,
        errors=replay_errs + v_errs,
        meta={"closed_tasks": len(closed_tasks), "n_frozen_overlap_block": sum(
            1 for e in replay_errs if e.startswith("frozen overlaps"))},
    )


def _op_from_task(task: str) -> Optional[Tuple[int, int]]:
    if not task.startswith("J"):
        return None
    parts = task[1:].split("-")
    if len(parts) < 2:
        return None
    return int(parts[0]), int(parts[1])


def _merge_release(
    base: Sequence[ReservationRef],
    extra: Sequence[ReservationRef],
) -> List[ReservationRef]:
    seen = set(base)
    out = list(base)
    for r in extra:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def expand_release_job_suffix(
    release: Sequence[ReservationRef],
    all_res: Sequence[ReservationRef],
    *,
    t_now: float,
) -> List[ReservationRef]:
    """把释放集内每个工序的同工件后继(含自身)未来预约并入。

    用于消除校验 (f) 运输-工序衔接在「只放中间、冻后缀」时的不一致。
    """
    mins: Dict[int, int] = {}
    for r in release:
        op = _op_from_task(r.task)
        if op is None:
            continue
        j, i = op
        mins[j] = min(mins.get(j, i), i)
    extra = []
    for r in all_res:
        if r.t_end <= t_now + EPS:
            continue
        op = _op_from_task(r.task)
        if op is None:
            continue
        j, i = op
        if j in mins and i >= mins[j]:
            extra.append(r)
    return _merge_release(release, extra)


def expand_release_agv_suffix(
    release: Sequence[ReservationRef],
    all_res: Sequence[ReservationRef],
    *,
    t_now: float,
) -> List[ReservationRef]:
    """把释放集内出现过的 AGV 在 t_now 之后的全部预约并入。"""
    agvs = {r.agv for r in release}
    t0 = {a: min(r.t_start for r in release if r.agv == a) for a in agvs}
    extra = [
        r for r in all_res
        if r.agv in agvs and r.t_end > t_now + EPS and r.t_start >= t0[r.agv] - EPS
    ]
    return _merge_release(release, extra)


def expand_release_all_future(
    all_res: Sequence[ReservationRef],
    *,
    t_now: float,
) -> List[ReservationRef]:
    return [r for r in all_res if r.t_end > t_now + EPS]


def repair_with_scope_escalation(
    inst: Instance,
    net: Network,
    bundle: ScheduleBundle,
    dist: Disturbance,
    initial_release: Sequence[ReservationRef],
    *,
    max_rounds: int = 3,
) -> RepairResult:
    """第 1 级改路 + 失败扩域再修。

    轮次:
      0  initial_release(通常是时空闭包)
      1  + 同工件后继
      2  + 同车后继
      3  全部未来预约(仍是单遍改路,不是 GA)
    """
    t0 = time.perf_counter()
    release = list(initial_release)
    attempts: List[dict] = []
    last = RepairResult(feasible=False, errors=["no attempt"])

    for round_i in range(max_rounds + 1):
        last = replay_reroute(inst, net, bundle, dist, release)
        attempts.append({
            "round": round_i,
            "release_size": len(release),
            "feasible": last.feasible,
            "n_errors": len(last.errors),
            "makespan": last.makespan,
            "wall_ms": last.wall_ms,
        })
        if last.feasible:
            break
        if round_i == 0:
            nxt = expand_release_job_suffix(
                release, bundle.reservations, t_now=dist.t_now)
        elif round_i == 1:
            nxt = expand_release_agv_suffix(
                release, bundle.reservations, t_now=dist.t_now)
        else:
            nxt = expand_release_all_future(
                bundle.reservations, t_now=dist.t_now)
        if len(nxt) <= len(release):
            # 无法再扩大
            if round_i >= 2:
                break
            release = nxt
            continue
        release = nxt

    last.closure_size = len(initial_release)
    last.release_size = attempts[-1]["release_size"] if attempts else len(release)
    last.wall_ms = (time.perf_counter() - t0) * 1000
    last.meta = dict(last.meta or {})
    last.meta.update({
        "scope_attempts": attempts,
        "scope_rounds": len(attempts) - 1,
        "final_release_size": last.release_size,
        "initial_release_size": len(initial_release),
    })
    return last


def release_set_r2(bundle: ScheduleBundle, dist: Disturbance) -> List[ReservationRef]:
    seeds = seed_failed_reservations(dist, bundle.reservations)
    # 多微阻断:与任一阻断重叠的预约也作种子
    from algorithm.block_context import block_windows_from_dist
    blocks = block_windows_from_dist(dist)
    if blocks:
        extra = []
        for r in bundle.reservations:
            if r.t_end <= dist.t_now + EPS:
                continue
            for cid, a, b in blocks:
                if r.corridor == cid and r.overlaps(a, b):
                    extra.append(r)
                    break
        # 去重合并
        seen = set(seeds)
        for r in extra:
            if r not in seen:
                seeds.append(r)
                seen.add(r)
    chains = machine_chains_from_ops(bundle.result.ops)
    closure = spatiotemporal_closure(
        seeds, bundle.reservations,
        horizon=bundle.makespan + 1.0, t_now=dist.t_now,
        machine_chains=chains,
    )
    return list(closure.closed)


def release_set_r1(bundle: ScheduleBundle, dist: Disturbance, *, theta: int = 2
                   ) -> List[ReservationRef]:
    meta = {"machine_tasks": {}, "agv_tasks": {}}
    from collections import defaultdict
    mtasks: dict = defaultdict(list)
    atasks: dict = defaultdict(list)
    for opk, rec in bundle.result.ops.items():
        if rec.pseudo or rec.machine is None:
            continue
        if rec.finish > dist.t_now:
            mtasks[str(rec.machine)].append(f"J{rec.job}-{rec.i}")
    for tr in bundle.result.transports:
        if tr.arrive > dist.t_now:
            atasks[tr.agv].append(f"J{tr.job}-{tr.i}")
    meta["machine_tasks"] = mtasks
    meta["agv_tasks"] = atasks
    job_succ = job_precedence_from_reservations(bundle.reservations)
    impact = task_graph_impact(dist, job_succ, theta=theta, schedule_meta=meta)
    return release_set_from_tasks(bundle.reservations, impact, t_now=dist.t_now)


def repair_with_strc(inst: Instance, net: Network, bundle: ScheduleBundle,
                     dist: Disturbance, *, expand_on_fail: bool = True,
                     **_kwargs) -> RepairResult:
    """R2:时空闭包界定 + 第 1 级改路;默认失败则扩域再修。"""
    release = release_set_r2(bundle, dist)
    if expand_on_fail:
        out = repair_with_scope_escalation(
            inst, net, bundle, dist, release)
    else:
        out = replay_reroute(inst, net, bundle, dist, release)
        out.closure_size = len(release)
    out.meta["arm"] = "R2"
    out.meta["expand_on_fail"] = expand_on_fail
    return out


def repair_with_task_graph(inst: Instance, net: Network, bundle: ScheduleBundle,
                           dist: Disturbance, *, theta: int = 2,
                           expand_on_fail: bool = True,
                           **_kwargs) -> RepairResult:
    """R1:任务图影响域界定 + 第 1 级改路;默认失败则扩域再修。"""
    release = release_set_r1(bundle, dist, theta=theta)
    if expand_on_fail:
        out = repair_with_scope_escalation(
            inst, net, bundle, dist, release)
    else:
        out = replay_reroute(inst, net, bundle, dist, release)
        out.closure_size = len(release)
    out.meta["arm"] = "R1"
    out.meta["theta"] = theta
    out.meta["expand_on_fail"] = expand_on_fail
    return out


def outside_reservations_unchanged(
    before: DecodeResult,
    after: DecodeResult,
    release: Sequence[ReservationRef],
) -> List[str]:
    """E2b:闭包外预约应逐字段不变。"""
    closed = {r.task for r in release}
    bef = {(r.task, r.corridor, r.agv): (r.t_start, r.t_end)
           for r in reservations_from_result(before) if r.task not in closed}
    aft = {(r.task, r.corridor, r.agv): (r.t_start, r.t_end)
           for r in reservations_from_result(after) if r.task not in closed}
    errs = []
    for key, ts in bef.items():
        if key not in aft:
            errs.append(f"missing outside {key}")
        elif abs(aft[key][0] - ts[0]) > EPS or abs(aft[key][1] - ts[1]) > EPS:
            errs.append(f"changed outside {key}: {ts} -> {aft[key]}")
    return errs
