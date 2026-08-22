"""扰动模型:按「是否触碰任务图」分两类。

A 类(触碰任务图):RA 故障、加工时间偏差、紧急插单。
B 类(只触碰预约表):走廊阻断/降速、AGV 抛锚(同时释放该车时窗)。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

try:                                    # Literal 自 3.8 起才进 typing
    from typing import Literal
except ImportError:                     # pragma: no cover - 3.7 回退
    from typing_extensions import Literal

from algorithm.closure import ReservationRef

EPS = 1e-9

DisturbType = Literal[
    "corridor_block",
    "corridor_slowdown",
    "agv_breakdown",
    "ra_failure",
    "proc_delay",
    "urgent_job",
]

TOUCHES_TASK_GRAPH: dict[str, bool] = {
    "corridor_block": False,
    "corridor_slowdown": False,
    "agv_breakdown": True,
    "ra_failure": True,
    "proc_delay": True,
    "urgent_job": True,
}


@dataclass
class Disturbance:
    type: DisturbType
    t_now: float
    corridor: Optional[str] = None
    t_start: Optional[float] = None
    t_end: Optional[float] = None
    agv: Optional[int] = None
    machine: Optional[str] = None
    job_op: Optional[str] = None
    delay: Optional[float] = None
    tau_mult: Optional[float] = None
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def touches_task_graph(self) -> bool:
        return TOUCHES_TASK_GRAPH[self.type]

    @property
    def class_label(self) -> str:
        return "A" if self.touches_task_graph else "B"


def load_disturbance(path: str) -> Disturbance:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    known = {f.name for f in Disturbance.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    fields = {k: v for k, v in raw.items() if k in known and k != "extra"}
    extra = {k: v for k, v in raw.items() if k not in known}
    return Disturbance(**fields, extra=extra)


def seed_failed_reservations(
    dist: Disturbance,
    reservations: Sequence[ReservationRef],
) -> List[ReservationRef]:
    """由扰动生成失效预约种子集。"""
    t_now = float(dist.t_now)
    if dist.type in ("corridor_block", "corridor_slowdown"):
        if not dist.corridor:
            raise ValueError("corridor_block requires corridor")
        t0 = float(dist.t_start if dist.t_start is not None else t_now)
        t1 = float(dist.t_end if dist.t_end is not None else float("inf"))
        return [
            r for r in reservations
            if r.corridor == dist.corridor
            and r.t_end > t_now + EPS
            and r.overlaps(t0, t1)
        ]

    if dist.type == "agv_breakdown":
        if dist.agv is None:
            raise ValueError("agv_breakdown requires agv")
        return [
            r for r in reservations
            if r.agv == int(dist.agv) and r.t_end > t_now + EPS
        ]

    if dist.type == "ra_failure":
        # failed_ops: [(j,i), ...] 该机上尚未完工的工序。
        # 种子 = 各工件从该工序起(含)的全部未来预约——进站运输可能已结束,
        # 但仍须从该工序起沿工件链重规划,否则闭包会短于任务图影响域。
        failed_ops = dist.extra.get("failed_ops") or []
        prefixes = dist.extra.get("task_prefixes") or []
        if not failed_ops and not prefixes:
            return []
        # 规范化为 (j, i_min) : 同一工件取最小未完成工序号
        jmin: dict[int, int] = {}
        for item in failed_ops:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                j, i = int(item[0]), int(item[1])
                jmin[j] = min(jmin.get(j, i), i)
        for p in prefixes:
            # "J{j}-{i}"
            body = str(p)[1:] if str(p).startswith("J") else str(p)
            parts = body.split("-")
            if len(parts) >= 2:
                j, i = int(parts[0]), int(parts[1])
                jmin[j] = min(jmin.get(j, i), i)
        out = []
        for r in reservations:
            if r.t_end <= t_now + EPS:
                continue
            if not r.task.startswith("J"):
                continue
            body = r.task[1:]
            parts = body.split("-")
            if len(parts) < 2:
                continue
            j, i = int(parts[0]), int(parts[1])
            if j in jmin and i >= jmin[j]:
                out.append(r)
        return out

    if dist.type == "proc_delay" and dist.job_op:
        # "(j,i)" → 前缀 J{j}-{i}-
        inner = dist.job_op.strip().strip("()")
        parts = [x.strip() for x in inner.split(",")]
        prefix = f"J{parts[0]}-{parts[1]}-"
        return [
            r for r in reservations
            if r.task.startswith(prefix) and r.t_end > t_now + EPS
        ]

    return []


def schedule_still_valid_under_block(
    reservations: Sequence[ReservationRef],
    dist: Disturbance,
) -> bool:
    """粗检:若仍有预约落在被阻断走廊的阻断时窗内,则原排程在扰动下不可行。"""
    if dist.type != "corridor_block" or not dist.corridor:
        return True
    t0 = float(dist.t_start if dist.t_start is not None else dist.t_now)
    t1 = float(dist.t_end if dist.t_end is not None else float("inf"))
    for r in reservations:
        if r.corridor == dist.corridor and r.overlaps(t0, t1) and r.t_end > dist.t_now + EPS:
            return False
    return True
