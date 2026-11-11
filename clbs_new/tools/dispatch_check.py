# -*- coding: utf-8 -*-
"""同一染色体上,规则派车与试探派车的单次解码对照(不经 GA)。

若试探派车在单次解码上就不优于规则派车,问题在派车本身(实现或贪心目标),
与算力无关;若单次解码上更优,闭环内的差距只能来自评价次数。

Single-decode contrast of rule vs probe dispatch on the same chromosomes (no GA).

  py -3 -m tools.dispatch_check [--n 30]
"""
from __future__ import annotations

import dataclasses
import random
import sys

from algorithm.decoder import decode
from algorithm.ga import random_ma, random_os
from algorithm.validator import validate
from tools.abc_matrix import CASES, build

WANT = ["A funnel", "A high", "A mid", "B NA/NM 1.0"]


def main() -> int:
    args = sys.argv[1:]
    n = int(args[args.index("--n") + 1]) if "--n" in args else 30
    settings = [("节点 c=2", dict(node_model=True, machine_capacity=2)),
                ("节点 c=inf", dict(node_model=True, machine_capacity=None)),
                ("仅走廊", dict(node_model=False))]
    print(f"{'算例':<14s} {'设定':<10s} {'规则':>8s} {'试探':>8s} {'相对差':>8s} "
          f"{'胜/负/平':>10s}")
    for case in [c for c in CASES if c["name"] in WANT]:
        base, net, _ = build(case)
        for label, kw in settings:
            inst = dataclasses.replace(base, **kw)
            rng = random.Random(20261108)
            rs, es, win, lose = [], [], 0, 0
            for _ in range(n):
                ma, os_seq = random_ma(inst, rng), random_os(inst, rng)
                r = decode(inst, net, ma, os_seq, conflict_free=True, dispatch="rule")
                e = decode(inst, net, ma, os_seq, conflict_free=True, dispatch="exact")
                for res in (r, e):
                    errs = validate(inst, res.to_timetable())
                    if errs:
                        print(f"  !! 校验失败 {case['name']} {label}: {errs[:1]}")
                rs.append(r.makespan)
                es.append(e.makespan)
                win += e.makespan < r.makespan - 1e-9
                lose += e.makespan > r.makespan + 1e-9
            rel = sum((e - r) / r for r, e in zip(rs, es)) / n
            print(f"{case['name']:<14s} {label:<10s} {sum(rs)/n:>8.2f} {sum(es)/n:>8.2f} "
                  f"{rel:>+8.2%} {win:>3d}/{lose:>2d}/{n - win - lose:<3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
