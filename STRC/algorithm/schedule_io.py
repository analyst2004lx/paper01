"""从 clbs DecodeResult 提取预约列表,并构造带染色体的基线可行排程。"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple

from algorithm.clbs_bridge import (
    DecodeResult,
    GAConfig,
    Instance,
    Network,
    clbs_ga as _clbs_ga,
    decode,
    run_ga,
)
from algorithm.closure import ReservationRef


@dataclass
class ScheduleBundle:
    result: DecodeResult
    ma: dict
    os_seq: list
    reservations: List[ReservationRef]

    @property
    def makespan(self) -> float:
        return float(self.result.makespan)


def reservations_from_result(result: DecodeResult) -> List[ReservationRef]:
    out: List[ReservationRef] = []
    for tr in result.transports:
        for kind, plan in (("empty", tr.empty_plan), ("loaded", tr.loaded_plan)):
            task = f"J{tr.job}-{tr.i}-{kind}"
            for s in plan.segments:
                out.append(ReservationRef(
                    corridor=s.corridor,
                    t_start=float(s.enter),
                    t_end=float(s.exit),
                    agv=int(tr.agv),
                    task=task,
                ))
    out.sort(key=lambda r: (r.t_start, r.corridor, r.agv, r.task))
    return out


def build_baseline(
    inst: Instance,
    net: Network,
    *,
    seed: int = 42,
    mode: str = "heuristic",
    budget_sec: float = 5.0,
) -> ScheduleBundle:
    """构造冲突自由的可行基线排程(含染色体,供局部重放)。"""
    if mode == "heuristic":
        rng = random.Random(seed)
        ma = _clbs_ga.ma_min_time(inst)
        os_seq = _clbs_ga.random_os(inst, rng)
        result = decode(inst, net, ma, os_seq, conflict_free=True, dispatch="exact")
        return ScheduleBundle(result, ma, os_seq, reservations_from_result(result))

    if mode == "ga":
        cfg = GAConfig(
            pop=40, max_gen=500, stall_gen=80, seed=seed,
            dispatch="exact", use_conflict_ops=False,
            time_budget_sec=budget_sec,
        )
        out = run_ga(inst, net, cfg, conflict_free=True, use_ls=False)
        result = out["best_result"]
        chrom = out["best_chrom"]
        return ScheduleBundle(
            result, chrom["ma"], list(chrom["os"]), reservations_from_result(result)
        )

    raise ValueError(f"unknown mode {mode!r}")


def pick_busy_corridor(
    reservations: List[ReservationRef],
    *,
    t_now: float,
    prefer: Optional[str] = None,
) -> Tuple[str, float, float, int]:
    hits: dict[str, list[ReservationRef]] = defaultdict(list)
    for r in reservations:
        if r.t_end <= t_now:
            continue
        hits[r.corridor].append(r)
    if prefer and prefer in hits and hits[prefer]:
        cid = prefer
    else:
        if not hits:
            raise ValueError("no future reservations to block")
        cid = max(hits, key=lambda c: len(hits[c]))
    rs = hits[cid]
    return cid, min(r.t_start for r in rs), max(r.t_end for r in rs), len(rs)


def save_schedule_bundle(path: str, bundle: ScheduleBundle) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "timetable": bundle.result.to_timetable(),
        "ma": {f"({j},{i})": m for (j, i), m in bundle.ma.items()},
        "os": bundle.os_seq,
        "reservations": [
            {
                "corridor": r.corridor,
                "t_start": r.t_start,
                "t_end": r.t_end,
                "agv": r.agv,
                "task": r.task,
            }
            for r in bundle.reservations
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
