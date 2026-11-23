"""有界修复:由释放集定出改写集 → 安装扰动 → 按原 OS 重放(外侧冻结,内侧重规划)。

下层为 clbs_new 的任务级安全区间搜索与节点模型(见 node_engine)。释放集是走廊占用集合;
改写以运输为单位——释放集里出现过的运输,其空载段、载货段、其后的离场或驱离行程,
连同沿途节点停留,一并由原车从 t_now 的状态起重规划(补全集 U+)。
R1/R2/RA 只差释放集的来源(任务图 / 时空闭包 / 全部未来占用)。

Bounded repair. The release set (corridor occupancies) determines the rewrite set at the level
of whole transports (U+); those transports are replanned by their original vehicles from the
state at t_now, everything else is precommitted. R1/R2/RA differ only in the release set.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from algorithm.clbs_bridge import DecodeResult, Instance, Network, validate
from algorithm.closure import (
    TASK_PARTS,
    ReservationRef,
    build_dependence_base,
    job_precedence_from_reservations,
    machine_chains_from_ops,
    release_set_from_tasks,
    spatiotemporal_closure,
    splice_node_refs,
    task_graph_impact,
)
from algorithm.disturbance import Disturbance, seed_failed_reservations
from algorithm.metrics import Deviation, evaluate_deviation
from algorithm.node_engine import RepairInfeasible, bounded_replay, prefix_decode_nodes
from algorithm.schedule_io import ScheduleBundle, reservations_from_result

EPS = 1e-9
REPLAY_RETRIES = 3


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


def _failed_agv(dist: Disturbance) -> Optional[int]:
    if dist.type == "agv_breakdown" and dist.agv is not None:
        return int(dist.agv)
    return None


def _failed_machine(dist: Disturbance) -> Optional[int]:
    if dist.type == "ra_failure" and dist.machine is not None:
        return int(dist.machine)
    return None


def _ma_under_failure(inst: Instance, bundle: ScheduleBundle, dist: Disturbance
                      ) -> Dict[Tuple[int, int], int]:
    """机械臂故障:未完工工序改派到工时最短的其它可行机。已完工的不动。

    Robot-arm failure: reassign unfinished operations to the other feasible machine with the shortest processing time. Finished operations stay put.
    """
    ma = dict(bundle.ma)
    dead = _failed_machine(dist)
    if dead is None:
        return ma
    for key, rec in bundle.result.ops.items():
        if rec.pseudo or rec.machine is None or rec.machine != dead:
            continue
        if rec.finish <= dist.t_now + EPS:
            continue
        alts = [m for m in inst.proc_time[key] if m != dead]
        if not alts:
            raise RuntimeError(f"no alternate machine for {key} (RA{dead} down)")
        ma[key] = min(alts, key=lambda m: inst.proc_time[key][m])
    return ma


def _op_from_task(task: str) -> Optional[Tuple[int, int]]:
    if not task.startswith("J"):
        return None
    parts = task[1:].split("-")
    if len(parts) < 2:
        return None
    return int(parts[0]), int(parts[1])


def rewrite_tasks(release: Sequence[ReservationRef], t_now: float) -> Set[Tuple[int, int]]:
    """释放集里出现过(且尚未结束)的运输,即补全集 U+ 的运输单位。"""
    out: Set[Tuple[int, int]] = set()
    for r in release:
        if r.t_end <= t_now + EPS:
            continue
        op = _op_from_task(r.task)
        if op is not None:
            out.add(op)
    return out


def completed_release(bundle: ScheduleBundle, release: Sequence[ReservationRef],
                      t_now: float) -> List[ReservationRef]:
    """U+:把释放集补全到整次运输(四类行程)后的未来走廊占用。"""
    tasks = rewrite_tasks(release, t_now)
    return [r for r in bundle.reservations
            if r.t_end > t_now + EPS and _op_from_task(r.task) in tasks]


def _validate_with_dead(inst: Instance, timetable: dict, dist: Disturbance) -> List[str]:
    """故障车按假设 A2 走完当前走廊后退出路网:它最后一段停留只到 max(到达, t_now) + h。

    clbs 的校验器把每车末段之后的停留记为 [到达, ∞);这里只对故障车截断,其余照旧。
    """
    dead = _failed_agv(dist)
    if dead is None or not inst.node_model:
        return validate(inst, timetable)
    import copy
    import sys
    lite = copy.copy(inst)
    lite.node_model = None
    errs = validate(lite, timetable)
    by_agv: Dict[int, List[dict]] = {}
    for s in timetable.get("agv_segments", []):
        by_agv.setdefault(s["agv"], []).append(s)
    for lst in by_agv.values():
        lst.sort(key=lambda x: x["enter"])
    own = by_agv.get(dead)
    if own:
        t_off = max(own[-1]["exit"], float(dist.t_now))
        own.append({"agv": dead, "u": own[-1]["v"], "v": inst.lu_node,
                    "enter": t_off, "exit": t_off, "task": "__OFF__"})
    check_nodes = sys.modules["_clbs_algorithm.validator"]._check_nodes
    return errs + check_nodes(inst, by_agv)


def _post_checks(inst: Instance, net: Network, result: DecodeResult,
                 dist: Disturbance) -> List[str]:
    from algorithm.block_context import (
        check_slowdown_durations,
        effective_block_windows,
        is_expected_slowdown_duration_error,
    )
    errs = _validate_with_dead(inst, result.to_timetable(), dist)
    errs = [e for e in errs if not is_expected_slowdown_duration_error(e, dist, net)]
    reservations = reservations_from_result(result)
    blocks = effective_block_windows(dist, reservations)
    for r in reservations:
        for cid, t0, t1 in blocks:
            if r.corridor == cid and r.overlaps(t0, t1):
                errs.append(f"post-repair still on blocked corridor: {r.task}")
    errs.extend(check_slowdown_durations(result, dist, net))
    return errs


def replay_reroute(
    inst: Instance,
    net: Network,
    bundle: ScheduleBundle,
    dist: Disturbance,
    release: Sequence[ReservationRef],
    *,
    max_retries: int = REPLAY_RETRIES,
    replan: Optional[Set[Tuple[int, int]]] = None,
    store_wait: bool = False,
) -> RepairResult:
    """第 1 级修复:释放集所涉运输由原车从 t_now 状态起重规划,其余原样保留。

    max_retries > 0 时,一遍失败后把卡住的运输提前规划,在同一释放集内至多重试这么多次。
    replan 非空时分三层:replan 内的运输在全图上重规划,释放集内其余运输先沿原路线
    只改时刻(见 bounded_replay);这样失败时,同一释放集再按全图重规划试一遍。

    A 类故障(车辆故障、机械臂故障)要换车或改派,不在本引擎的动作集合里,
    转交 repair_a5_fault。

    Level-1 repair: transports touched by the release set are replanned by their original
    vehicles from the state at t_now; everything else is kept. Class-A faults go to
    repair_a5_fault.
    """
    if dist.type in ("agv_breakdown", "ra_failure"):
        return repair_a5_fault(inst, net, bundle, dist)
    t_wall0 = time.perf_counter()
    base = bundle.result
    tasks = rewrite_tasks(release, dist.t_now)
    uplus = completed_release(bundle, release, dist.t_now)
    meta = {"closed_tasks": len(tasks), "uplus_size": len(uplus)}

    def attempt(rp):
        early: List[Tuple[int, int]] = []
        while True:
            try:
                out = bounded_replay(inst, net, bundle.tracked, bundle.ma, bundle.os_seq,
                                     dist, tasks, early=early, base_ops=base.ops, replan=rp,
                                     store_wait=store_wait)
                meta["retries"] = len(early)
                return out
            except RepairInfeasible as e:
                # 同一 W 内重试:把卡住的运输提前规划;它不满足提前条件或已提前过则放弃
                key = getattr(e, "key", None)
                if key is None or key in early or len(early) >= max_retries:
                    raise
                early.append(key)

    v_errs: Optional[List[str]] = None
    try:
        new_result = None
        if replan is not None:
            rp = set(replan) & tasks
            try:
                new_result = attempt(rp)
                v_errs = _post_checks(inst, net, new_result, dist)
                if v_errs:
                    new_result, v_errs = None, None
            except (RepairInfeasible, RuntimeError, AssertionError, KeyError,
                    StopIteration):
                new_result = None
            if new_result is not None:
                meta["replan_tasks"] = len(rp | new_result.strc_promoted)
                meta["promoted"] = len(new_result.strc_promoted)
            meta["tier_fallback"] = new_result is None
        if new_result is None:
            new_result = attempt(None)
            meta["replan_tasks"] = len(tasks)
    except (RepairInfeasible, RuntimeError, AssertionError, KeyError, StopIteration) as e:
        return RepairResult(
            feasible=False, closure_size=len(release), release_size=len(release),
            level_used=1, makespan_ref=base.makespan,
            wall_ms=(time.perf_counter() - t_wall0) * 1000,
            errors=[f"replay: {type(e).__name__}: {e}"],
            meta=dict(meta, n_frozen_overlap_block=int(
                "frozen overlaps block" in str(e)),
                eviction_forbidden=type(e).__name__ == "EvictionForbidden"),
        )
    if v_errs is None:
        v_errs = _post_checks(inst, net, new_result, dist)
    dev = evaluate_deviation(base, new_result)
    wall_ms = (time.perf_counter() - t_wall0) * 1000
    return RepairResult(
        feasible=not v_errs,
        closure_size=len(release),
        release_size=len(release),
        level_used=1,
        makespan=new_result.makespan,
        makespan_ref=base.makespan,
        deviation=dev,
        wall_ms=wall_ms,
        result=new_result,
        errors=v_errs,
        meta=dict(meta, n_frozen_overlap_block=0, eviction_forbidden=False),
    )


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

    Add, for every operation in the release set, the future reservations of its same-job successors (including itself).
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
    """把释放集内出现过的 AGV 在 t_now 之后的全部预约并入。

    Add every reservation after t_now of each AGV that appears in the release set.
    """
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
    max_retries: int = REPLAY_RETRIES,
    replan: Optional[Set[Tuple[int, int]]] = None,
    store_wait: bool = False,
) -> RepairResult:
    """第 1 级重规划 + 失败扩域再修。

    轮次:
      0  initial_release(通常是时空闭包)
      1  + 同工件后继
      2  + 同车后继
      3  全部未来预约(仍是单遍重放,不是 GA)

    Level-1 replanning, then widen the domain and repair again on failure.
    """
    t0 = time.perf_counter()
    release = list(initial_release)
    attempts: List[dict] = []
    last = RepairResult(feasible=False, errors=["no attempt"])

    for round_i in range(max_rounds + 1):
        last = replay_reroute(inst, net, bundle, dist, release, max_retries=max_retries,
                              replan=replan, store_wait=store_wait)
        attempts.append({
            "round": round_i,
            "release_size": len(release),
            "feasible": last.feasible,
            "n_errors": len(last.errors),
            "makespan": last.makespan,
            "wall_ms": last.wall_ms,
            "eviction_forbidden": bool(last.meta.get("eviction_forbidden")),
            "first_error": last.errors[0] if last.errors else "",
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
        # 按补全后的运输集判断是否真的扩大(释放集里可能含节点停留的伪预约)
        if rewrite_tasks(nxt, dist.t_now) <= rewrite_tasks(release, dist.t_now):
            # 无法再扩大 / Cannot widen any further
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


def precompute_dependence(bundle: ScheduleBundle):
    """基线排程确定时(扰动到来前)建好依赖图与节点停留表,release_set_r2 在线复用。"""
    got = getattr(bundle, "_strc_dep", None)
    if got is None:
        from algorithm.schedule_io import node_reservations
        chains = machine_chains_from_ops(bundle.result.ops)
        nodes, caps = node_reservations(bundle)
        got = (build_dependence_base(bundle.reservations, machine_chains=chains), nodes, caps)
        bundle._strc_dep = got   # type: ignore[attr-defined]
    return got


def corridor_refs(refs: Sequence[ReservationRef]) -> List[ReservationRef]:
    """去掉节点停留的伪预约(corridor 以 @ 开头),只留走廊占用;计数口径与 |R°| 一致。"""
    return [r for r in refs if not r.corridor.startswith("@")]


def strc_closure_full(bundle: ScheduleBundle, dist: Disturbance):
    """不用缓存、按默认口径(端点停留作顶点与种子)从头算一遍闭包,供 E1/E2 独立核对。

    返回 (ClosureResult, universe, machine_chains, node_caps)。
    """
    from algorithm.block_context import effective_block_windows
    from algorithm.schedule_io import node_reservations
    seeds = list(seed_failed_reservations(dist, bundle.reservations))
    blocks = effective_block_windows(dist, bundle.reservations)
    seen = set(seeds)
    for r in bundle.reservations:
        if r not in seen and any(r.corridor == c and r.overlaps(a, b) for c, a, b in blocks):
            seeds.append(r)
            seen.add(r)
    nodes, caps = node_reservations(bundle)
    ends = {"@" + n: (a, b) for cid, a, b in blocks for n in cid.split("|")}
    extra = [r for r in nodes if r.corridor in ends]
    for r in extra:
        a, b = ends[r.corridor]
        if r.overlaps(a, b) and r.t_end > dist.t_now + EPS:
            seeds.append(r)
    chains = machine_chains_from_ops(bundle.result.ops)
    universe = list(bundle.reservations) + extra
    closure = spatiotemporal_closure(seeds, universe, horizon=bundle.makespan + 1.0,
                                     t_now=dist.t_now, machine_chains=chains, node_caps=caps)
    return closure, universe, chains, caps


def strc_closure_corr(bundle: ScheduleBundle, dist: Disturbance):
    """strc_closure_full 的走廊部分:seeds 与 closed 只留走廊占用,计数与 |R|、|R°| 同口径。"""
    from dataclasses import replace as _replace
    c = strc_closure_full(bundle, dist)[0]
    return _replace(c, seeds=corridor_refs(c.seeds), closed=corridor_refs(c.closed))


def release_set_r2(bundle: ScheduleBundle, dist: Disturbance, *,
                   node_edges: bool = False,
                   endpoint_seeds: bool = True,
                   seeds_out: Optional[List[ReservationRef]] = None) -> List[ReservationRef]:
    """闭包释放集;seeds_out 给出时把种子追加进去。

    node_edges:所有有限容量节点上的停留都作为依赖图顶点(见 build_dependence_graph)。
    endpoint_seeds:只把受阻走廊两端节点上的停留并入依赖图,生效窗内的那些另作种子——
    阻断使车在走廊口等待,首先受牵连的是这两个节点上的后来者。
    """
    seeds = seed_failed_reservations(dist, bundle.reservations)
    # 多微阻断:与任一阻断重叠的预约也作种子 / Multiple micro-blockages: a reservation overlapping any blockage is also a seed
    from algorithm.block_context import effective_block_windows
    blocks = effective_block_windows(dist, bundle.reservations)
    if blocks:
        extra = []
        for r in bundle.reservations:
            for cid, a, b in blocks:
                if r.corridor == cid and r.overlaps(a, b):
                    extra.append(r)
                    break
        seen = set(seeds)
        for r in extra:
            if r not in seen:
                seeds.append(r)
                seen.add(r)
    if not node_edges:
        dep, all_nodes, node_caps = precompute_dependence(bundle)
        extra_nodes: List[ReservationRef] = []
        if endpoint_seeds:
            ends = {"@" + n: (a, b) for cid, a, b in blocks for n in cid.split("|")}
            extra_nodes = [r for r in all_nodes if r.corridor in ends]
            for r in extra_nodes:
                a, b = ends[r.corridor]
                if r.overlaps(a, b) and r.t_end > dist.t_now + EPS:
                    seeds.append(r)
        if seeds_out is not None:
            seeds_out.extend(seeds)
        closure = spatiotemporal_closure(
            seeds, list(bundle.reservations) + extra_nodes,
            horizon=bundle.makespan + 1.0, t_now=dist.t_now,
            graph=splice_node_refs(dep, extra_nodes, node_caps),
        )
        return list(closure.closed)
    chains = machine_chains_from_ops(bundle.result.ops)
    universe, caps = list(bundle.reservations), None
    if node_edges or endpoint_seeds:
        from algorithm.schedule_io import node_reservations
        extra_nodes, caps = node_reservations(bundle)
        if not node_edges:
            ends = {"@" + n: (a, b) for cid, a, b in blocks for n in cid.split("|")}
            extra_nodes = [r for r in extra_nodes if r.corridor in ends]
            for r in extra_nodes:
                a, b = ends[r.corridor]
                if r.overlaps(a, b) and r.t_end > dist.t_now + EPS:
                    seeds.append(r)
        universe += extra_nodes
    if seeds_out is not None:
        seeds_out.extend(seeds)
    closure = spatiotemporal_closure(
        seeds, universe,
        horizon=bundle.makespan + 1.0, t_now=dist.t_now,
        machine_chains=chains, node_caps=caps,
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


def repair_a5_fault(inst: Instance, net: Network, bundle: ScheduleBundle,
                    dist: Disturbance) -> RepairResult:
    """A 类故障:固定前缀 + 换车/改派(全局重算 t_now 之后的部分)。

    Class-A fault: fixed prefix plus a vehicle switch or reassignment.
    """
    t0 = time.perf_counter()
    dead = _failed_agv(dist)
    try:
        ma = _ma_under_failure(inst, bundle, dist)
    except RuntimeError as e:
        return RepairResult(
            feasible=False, makespan_ref=bundle.makespan,
            wall_ms=(time.perf_counter() - t0) * 1000, errors=[str(e)],
            meta={"arm": "R2", "a5": True},
        )
    res = prefix_decode_nodes(
        inst, net, ma, bundle.os_seq, bundle.tracked, bundle.result, dist,
        dead_agv=dead, dead_machine=_failed_machine(dist))
    dummy = res.makespan >= 1e17
    errs = [] if dummy else _post_checks(inst, net, res, dist)
    if dummy:
        errs.append(f"a5 prefix decode infeasible: {getattr(res, 'strc_error', '')}")
    wall = (time.perf_counter() - t0) * 1000
    ok = not errs
    r2 = release_set_r2(bundle, dist)
    return RepairResult(
        feasible=ok,
        closure_size=len(r2),
        release_size=len(r2),
        level_used=2 if dead is not None else 3,
        makespan=None if dummy or not ok else res.makespan,
        makespan_ref=bundle.makespan,
        deviation=None if dummy or not ok else evaluate_deviation(bundle.result, res),
        wall_ms=wall,
        result=None if dummy or not ok else res,
        errors=errs,
        meta={"arm": "R2", "a5": True, "dead_agv": dead,
              "failed_machine": _failed_machine(dist)},
    )


def repair_with_strc(inst: Instance, net: Network, bundle: ScheduleBundle,
                     dist: Disturbance, *, expand_on_fail: bool = True,
                     node_edges: bool = False, endpoint_seeds: bool = True,
                     max_retries: int = REPLAY_RETRIES, tiers: bool = True,
                     store_wait: bool = False, **_kwargs) -> RepairResult:
    """R2:时空闭包界定 + 第 1 级重规划;默认失败则扩域再修。

    tiers 为真时分三层(默认):种子所属运输在全图上重规划,闭包内其余运输先沿原路线只改时刻,
    闭包外冻结。

    R2: bound the domain by the spatiotemporal closure, then level-1 replanning; on failure, widen the domain and repair again by default.
    """
    if dist.type in ("agv_breakdown", "ra_failure"):
        return repair_a5_fault(inst, net, bundle, dist)
    t_cl = time.perf_counter()
    seeds: List[ReservationRef] = []
    release = release_set_r2(bundle, dist, node_edges=node_edges,
                             endpoint_seeds=endpoint_seeds, seeds_out=seeds)
    closure_ms = (time.perf_counter() - t_cl) * 1000
    # 重规划集只取走廊种子所属的运输:它们与阻断直接冲突,任何可行修复都必须改动;
    # 端点节点上的种子停留不与阻断冲突,其运输归平移集,需要时在重放中升级
    replan = (rewrite_tasks([r for r in seeds if not r.corridor.startswith("@")], dist.t_now)
              if tiers else None)
    if expand_on_fail:
        out = repair_with_scope_escalation(inst, net, bundle, dist, release,
                                           max_retries=max_retries, replan=replan,
                                           store_wait=store_wait)
    else:
        out = replay_reroute(inst, net, bundle, dist, release, max_retries=max_retries,
                             replan=replan, store_wait=store_wait)
        out.closure_size = len(release)
    # closure_size 只计走廊占用,与 |R°| 同口径;端点节点停留另记
    out.closure_size = sum(1 for r in release if not r.corridor.startswith("@"))
    out.meta["closure_nodes"] = len(release) - out.closure_size
    out.meta["n_W0"] = len(rewrite_tasks(release, dist.t_now))
    out.meta["n_Q0"] = None if replan is None else len(replan)
    out.meta["n_seeds_corr"] = sum(1 for r in seeds if not r.corridor.startswith("@"))
    # 在线耗时含划界;依赖图本身在基线确定时由 precompute_dependence 建好,不计入
    out.wall_ms += closure_ms
    out.meta["closure_ms"] = closure_ms
    out.meta["arm"] = "R2"
    out.meta["expand_on_fail"] = expand_on_fail
    return out


def repair_with_all_future(inst: Instance, net: Network, bundle: ScheduleBundle,
                           dist: Disturbance, *, max_retries: int = REPLAY_RETRIES,
                           tiers: bool = True, **_kwargs) -> RepairResult:
    """RA:不画边界,释放 t_now 之后的全部预约,再走同一遍重放。

    RA 与 R2 共用 bounded_replay、冻结判据、扰动安装与重规划集(走廊种子所属运输),
    唯一差别是释放集取了平凡上界。

    RA: draw no boundary; release every reservation after t_now and run the same replay.
    """
    release = expand_release_all_future(bundle.reservations, t_now=dist.t_now)
    replan = None
    if tiers and dist.type not in ("agv_breakdown", "ra_failure"):
        seeds = seed_failed_reservations(dist, bundle.reservations)
        replan = rewrite_tasks([r for r in seeds if not r.corridor.startswith("@")], dist.t_now)
    out = replay_reroute(inst, net, bundle, dist, release, max_retries=max_retries,
                         replan=replan)
    out.closure_size = len(release)
    out.meta["arm"] = "RA"
    return out


def repair_with_task_graph(inst: Instance, net: Network, bundle: ScheduleBundle,
                           dist: Disturbance, *, theta: int = 2,
                           expand_on_fail: bool = True,
                           **_kwargs) -> RepairResult:
    """R1:任务图影响域界定 + 第 1 级重规划;默认失败则扩域再修。

    R1: bound the domain by the task-graph impact set, then level-1 replanning; on failure, widen the domain and repair again by default.
    """
    release = release_set_r1(bundle, dist, theta=theta)
    if expand_on_fail:
        out = repair_with_scope_escalation(inst, net, bundle, dist, release)
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
    *,
    t_now: Optional[float] = None,
) -> List[str]:
    """E2b:补全集 U+ 之外的预约应逐字段不变。

    改写以整次运输为单位,故释放集里出现过的运输,其四类行程的标签都算在 U+ 内。

    E2b: reservations outside the completion U+ should be unchanged in every field.
    """
    t_ref = -1e18 if t_now is None else t_now
    tasks = rewrite_tasks(release, t_ref)
    closed = {f"J{j}-{i}-{part}" for j, i in tasks for part in TASK_PARTS}
    bef = {(r.task, r.corridor, r.agv, round(r.t_start, 6)): (r.t_start, r.t_end)
           for r in reservations_from_result(before) if r.task not in closed}
    aft = {(r.task, r.corridor, r.agv, round(r.t_start, 6)): (r.t_start, r.t_end)
           for r in reservations_from_result(after) if r.task not in closed}
    errs = []
    for key, ts in bef.items():
        if key not in aft:
            errs.append(f"missing outside {key}")
        elif abs(aft[key][1] - ts[1]) > EPS:
            errs.append(f"changed outside {key}: {ts} -> {aft[key]}")
    return errs
