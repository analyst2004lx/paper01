"""从 clbs DecodeResult 提取预约列表,并构造带染色体的基线可行排程。

Extract the reservation list from a clbs DecodeResult, and build a feasible baseline schedule that carries its chromosome.
"""
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
    # 节点模型下每次运输的完整落表(走廊占用、节点停留、离场与驱离),修复引擎据此预提交
    # Full per-transport record under the node model; the repair engine precommits from it
    tracked: Optional[object] = None

    @property
    def makespan(self) -> float:
        return float(self.result.makespan)


def node_reservations(bundle: ScheduleBundle) -> Tuple[List[ReservationRef], dict]:
    """有限容量节点上的停留,写成 corridor="@节点" 的伪预约,标签取其所属运输;另返回各节点容量。"""
    from algorithm.clbs_bridge import NodeModel
    model = NodeModel.from_instance(bundle.result.instance)
    out: List[ReservationRef] = []
    caps: dict = {}
    for st in getattr(bundle.tracked, "stays", ()):
        cap = model.cap(st.node)
        if cap == float("inf"):
            continue
        caps[st.node] = float(cap)
        out.append(ReservationRef(
            corridor="@" + st.node, t_start=float(st.start), t_end=float(st.end),
            agv=int(st.agv), task=f"J{st.owner[0]}-{st.owner[1]}-loaded"))
    return out, caps


def reservations_from_result(result: DecodeResult) -> List[ReservationRef]:
    """走廊占用列表。节点模型下含离场(J{j}-{i}-leave)与驱离(J{j}-{i}-evict)行程。

    Corridor occupancies; under the node model this includes leave and evict trips.
    """
    out: List[ReservationRef] = []
    units = getattr(result, "strc_units", None)
    if units is not None:
        for u in units:
            for part, plan in u.parts():
                task = u.label(part)
                for s in plan.segments:
                    out.append(ReservationRef(
                        corridor=s.corridor, t_start=float(s.enter), t_end=float(s.exit),
                        agv=int(u.agv), task=task))
    else:
        for tr in result.transports:
            for kind, plan in (("empty", tr.empty_plan), ("loaded", tr.loaded_plan)):
                task = f"J{tr.job}-{tr.i}-{kind}"
                for s in plan.segments:
                    out.append(ReservationRef(
                        corridor=s.corridor, t_start=float(s.enter), t_end=float(s.exit),
                        agv=int(tr.agv), task=task))
        for n, (k, plan) in enumerate(getattr(result, "relocations", []) or [], start=1):
            for s in plan.segments:
                out.append(ReservationRef(
                    corridor=s.corridor, t_start=float(s.enter), t_end=float(s.exit),
                    agv=int(k), task=f"R{n}-reloc"))
    out.sort(key=lambda r: (r.t_start, r.corridor, r.agv, r.task))
    return out


def bundle_from_chromosome(inst: Instance, net: Network, ma: dict, os_seq: list
                           ) -> ScheduleBundle:
    from algorithm.node_engine import decode_tracked
    result, tracked = decode_tracked(inst, net, ma, os_seq)
    return ScheduleBundle(result, dict(ma), list(os_seq),
                          reservations_from_result(result), tracked)


def build_baseline(
    inst: Instance,
    net: Network,
    *,
    seed: int = 42,
    mode: str = "heuristic",
    budget_sec: float = 5.0,
) -> ScheduleBundle:
    """构造冲突自由的可行基线排程(含染色体,供局部重放)。

    下层为 clbs_new 的任务级安全区间搜索与节点模型;decode_tracked 与
    clbs_new.decode(dispatch="exact")同一过程,另记下每次运输的落表。

    Build a conflict-free feasible baseline schedule (chromosome included, for local replay).
    """
    if mode == "heuristic":
        rng = random.Random(seed)
        ma = _clbs_ga.ma_min_time(inst)
        os_seq = _clbs_ga.random_os(inst, rng)
        return bundle_from_chromosome(inst, net, ma, os_seq)

    if mode == "ga":
        cfg = GAConfig(
            pop=40, max_gen=500, stall_gen=80, seed=seed,
            dispatch="exact", use_conflict_ops=False,
            time_budget_sec=budget_sec,
        )
        out = run_ga(inst, net, cfg, conflict_free=True, use_ls=False)
        chrom = out["best_chrom"]
        return bundle_from_chromosome(inst, net, chrom["ma"], list(chrom["os"]))

    raise ValueError(f"unknown mode {mode!r}")


def pick_busy_corridor(
    reservations: List[ReservationRef],
    *,
    t_now: float,
    prefer: Optional[str] = None,
) -> Tuple[str, float, float, int]:
    hits: dict[str, list[ReservationRef]] = defaultdict(list)
    for r in reservations:
        # 已开始的段按 A2 走完,不受阻断,不计入
        if r.t_start < t_now:
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
