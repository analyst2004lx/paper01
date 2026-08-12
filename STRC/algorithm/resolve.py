"""R0 / R0+:在走廊阻断下用 clbs GA 重解(与 R2 共享下层路由)。"""
from __future__ import annotations

import time
from typing import List, Optional

from algorithm.block_context import corridor_block_active
from algorithm.clbs_bridge import (
    GAConfig,
    Instance,
    Network,
    clbs_ga,
    run_ga,
    validate,
)
from algorithm.disturbance import Disturbance
from algorithm.metrics import evaluate_deviation
from algorithm.repair import RepairResult
from algorithm.schedule_io import ScheduleBundle, reservations_from_result


def _check_block_free(result, dist: Disturbance) -> List[str]:
    from algorithm.block_context import block_windows_from_dist
    blocks = block_windows_from_dist(dist)
    if not blocks:
        return []
    errs = []
    for r in reservations_from_result(result):
        if r.task == "__BLOCK__":
            continue
        for cid, t0, t1 in blocks:
            if r.corridor == cid and r.overlaps(t0, t1):
                errs.append(f"uses blocked corridor: {r.task}")
                break
    return errs


def resolve_r0(
    inst: Instance,
    net: Network,
    bundle: ScheduleBundle,
    dist: Disturbance,
    *,
    budget_sec: float,
    seed: int = 42,
    hot: bool = False,
    pop: int = 40,
) -> RepairResult:
    """R0 冷启动 / R0+ 热启动:同挂钟预算下在阻断后的网络上跑闭环 GA。"""
    t0 = time.perf_counter()
    cfg = GAConfig(
        pop=pop,
        max_gen=10_000,
        stall_gen=10_000,
        seed=seed,
        dispatch="exact",
        use_conflict_ops=False,
        time_budget_sec=float(budget_sec),
    )
    seed_chrom = {"ma": dict(bundle.ma), "os": list(bundle.os_seq)}

    # 热启动:把原方案放进初始种群第 0 位
    orig_init = clbs_ga.init_population

    def hot_init(inst_, cfg_, rng):
        pop_list = orig_init(inst_, cfg_, rng)
        pop_list[0] = clbs_ga.clone(seed_chrom)
        return pop_list

    try:
        if hot:
            clbs_ga.init_population = hot_init
        with corridor_block_active(dist):
            out = run_ga(inst, net, cfg, conflict_free=True, use_ls=False)
    finally:
        clbs_ga.init_population = orig_init

    result = out["best_result"]
    errs = validate(inst, result.to_timetable())
    errs.extend(_check_block_free(result, dist))
    wall_ms = (time.perf_counter() - t0) * 1000
    # 挂钟可能略超预算(代末检查);如实记录
    ok = not errs
    dev = evaluate_deviation(bundle.result, result) if ok else None
    return RepairResult(
        feasible=ok,
        closure_size=0,
        release_size=0,
        level_used=None,
        makespan=result.makespan if ok else None,
        makespan_ref=bundle.makespan,
        deviation=dev,
        wall_ms=wall_ms,
        result=result if ok else None,
        errors=errs,
        meta={
            "arm": "R0+" if hot else "R0",
            "budget_sec": budget_sec,
            "generations": out.get("generations"),
            "decodes": out.get("decodes"),
            "stopped_by": out.get("stopped_by"),
            "runtime_sec": out.get("runtime_sec"),
            "raw_makespan": result.makespan,
        },
    )
