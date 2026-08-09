"""偏差度量:完工时间偏差 + 预约扰动量。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from algorithm.closure import ReservationRef
from algorithm.schedule_io import reservations_from_result

EPS = 1e-9


@dataclass
class Deviation:
    makespan_abs: float
    makespan_rel: float
    reservation_changed: int
    reservation_total: int
    completion_l1: float

    @property
    def reservation_ratio(self) -> float:
        if self.reservation_total <= 0:
            return 0.0
        return self.reservation_changed / self.reservation_total


def _res_key(r: ReservationRef) -> Tuple[str, int, str]:
    return (r.corridor, r.agv, r.task)


def reservation_delta_count(
    before: Sequence[ReservationRef],
    after: Sequence[ReservationRef],
) -> Tuple[int, int]:
    """返回 (changed_or_removed, total_before)。

    以 (corridor, agv, task) 为键;时窗变化或键消失都计一次改动。
    """
    aft: Dict[Tuple[str, int, str], ReservationRef] = {_res_key(r): r for r in after}
    changed = 0
    for r in before:
        key = _res_key(r)
        r2 = aft.get(key)
        if r2 is None:
            changed += 1
        elif abs(r2.t_start - r.t_start) > EPS or abs(r2.t_end - r.t_end) > EPS:
            changed += 1
    return changed, len(before)


def evaluate_deviation(before_result, after_result) -> Deviation:
    c_before = sorted(
        ((r.job, r.i), r.finish) for r in before_result.ops.values() if not r.pseudo
    )
    c_after = {
        (r.job, r.i): r.finish for r in after_result.ops.values() if not r.pseudo
    }
    l1 = float(sum(abs(c_after.get(k, fin) - fin) for k, fin in c_before))
    ms0 = float(before_result.makespan)
    ms1 = float(after_result.makespan)
    rb = reservations_from_result(before_result)
    ra = reservations_from_result(after_result)
    ch, tot = reservation_delta_count(rb, ra)
    return Deviation(
        makespan_abs=ms1 - ms0,
        makespan_rel=(ms1 - ms0) / ms0 if ms0 > 0 else 0.0,
        reservation_changed=ch,
        reservation_total=tot,
        completion_l1=l1,
    )
