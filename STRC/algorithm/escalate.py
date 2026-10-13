"""升级阶梯:在闭包内逐级放开决策自由度。

级别(命中偏差预算即停):
  1 只改路径   ← corridor
  2 改派车     ← vehicle(闭环排程上 paper01 已测为正向)
  3 改指派     ← machine
  4 改排序     ← 动 OS

与 clbs 凭证制导局部搜索共享「走法」、不共享「策略」:
那里从可行解搜改进;这里从不可行方案恢复可行且尽量少动。

Escalation ladder: inside the closure, decision freedom is opened one level at a time.

Levels (stop when the deviation budget is met):
  1 reroute only        ← corridor
  2 reassign vehicle    ← vehicle (already measured as beneficial on closed-loop schedules in paper01)
  3 reassign machine    ← machine
  4 resequence          ← change the operation sequence (OS)

Shares the moves of clbs certificate-guided local search, but not the policy:
there the search improves a feasible solution; here an infeasible plan is restored to feasibility while moving as little as possible.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class EscalationLevel(IntEnum):
    REROUTE = 1
    REASSIGN_AGV = 2
    REASSIGN_MACHINE = 3
    RESEQUENCE = 4


LEVEL_LABELS = {
    EscalationLevel.REROUTE: "reroute",
    EscalationLevel.REASSIGN_AGV: "reassign_agv",
    EscalationLevel.REASSIGN_MACHINE: "reassign_machine",
    EscalationLevel.RESEQUENCE: "resequence",
}


@dataclass
class EscalationOutcome:
    level: EscalationLevel
    feasible: bool
    makespan: Optional[float] = None
    reservation_delta: Optional[float] = None
    note: str = ""


def try_level(level: EscalationLevel, closure, schedule, inst, net, **kwargs
              ) -> EscalationOutcome:
    """在给定级别上尝试恢复。占位。

    Try to recover at the given level. Placeholder.
    """
    raise NotImplementedError(f"try_level({LEVEL_LABELS[level]})")


def escalate_until_feasible(closure, schedule, inst, net, *,
                            max_level: EscalationLevel = EscalationLevel.RESEQUENCE,
                            deviation_budget: float | None = None,
                            ) -> EscalationOutcome:
    """从 1 级爬到 max_level,首个可行且满足偏差预算的级别即返回。

    Climb from level 1 up to max_level, and return the first level that is feasible and meets the deviation budget.
    """
    raise NotImplementedError("escalate_until_feasible")
