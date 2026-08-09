"""实验档位 R0 / R0+ / R1 / R2。"""
from __future__ import annotations

from typing import Callable, Dict

from algorithm.repair import repair_with_strc, repair_with_task_graph
from algorithm.resolve import resolve_r0

SOLVERS: Dict[str, Callable] = {}
R_ARMS = ("R0", "R0+", "R1", "R2")


def register(name: str, fn: Callable) -> None:
    SOLVERS[name] = fn


def _ensure_defaults() -> None:
    if SOLVERS:
        return

    def r0(inst, net, bundle, dist, **kw):
        return resolve_r0(inst, net, bundle, dist, hot=False,
                          budget_sec=kw.get("budget_sec", 1.0),
                          seed=kw.get("seed", 42),
                          pop=kw.get("pop", 40))

    def r0p(inst, net, bundle, dist, **kw):
        return resolve_r0(inst, net, bundle, dist, hot=True,
                          budget_sec=kw.get("budget_sec", 1.0),
                          seed=kw.get("seed", 42),
                          pop=kw.get("pop", 40))

    def r1(inst, net, bundle, dist, **kw):
        return repair_with_task_graph(inst, net, bundle, dist,
                                      theta=kw.get("theta", 2))

    def r2(inst, net, bundle, dist, **kw):
        return repair_with_strc(inst, net, bundle, dist)

    register("R0", r0)
    register("R0+", r0p)
    register("R1", r1)
    register("R2", r2)


def solve_arm(name: str, *args, **kwargs):
    _ensure_defaults()
    if name not in SOLVERS:
        raise NotImplementedError(f"ladder arm {name!r} not registered")
    return SOLVERS[name](*args, **kwargs)
