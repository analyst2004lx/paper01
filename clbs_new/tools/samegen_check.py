# -*- coding: utf-8 -*-
"""同代数对照:B1(闭环+规则派车)与 B2(闭环+试探派车)跑相同代数、不设挂钟上限。

同挂钟下 B2 的单次评价约为 B1 的 8 倍,完成的代数少得多。本工具去掉这一差别,
检验试探派车在相同评价次数下是否降低 C_max。

Equal-generation contrast of B1 and B2 with no wall-clock cap.

  py -3 -u -m tools.samegen_check --only "A funnel" [--gen 30] [--seeds 42,7,2024]
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import replace

from algorithm.ga import GAConfig, run_ga
from algorithm.validator import validate
from tools.abc_matrix import CASES, build


def main() -> int:
    args = sys.argv[1:]
    opt = lambda k, d: args[args.index(k) + 1] if k in args else d  # noqa: E731
    gen = int(opt("--gen", "30"))
    seeds = [int(x) for x in opt("--seeds", "42,7,2024").split(",")]
    want = set(opt("--only", "A funnel").split(","))
    cases = [c for c in CASES if c["name"] in want]
    out = os.path.join(os.path.dirname(__file__), "..", "output",
                       opt("--out", "samegen_check.csv"))
    new = not os.path.exists(out)
    with open(out, "a", encoding="utf-8") as f:
        if new:
            f.write("case,arm,seed,gen,makespan,decodes,runtime_sec\n")
        for case in cases:
            inst, net, _c = build(case)
            base = GAConfig(pop=60, max_gen=gen, stall_gen=10 ** 9, use_conflict_ops=True,
                            theta=0.0, max_entry_options=3, time_budget_sec=None)
            for s in seeds:
                for arm, disp in (("B1", "rule"), ("B2", "exact")):
                    t0 = time.time()
                    res = run_ga(inst, net, replace(base, seed=s, dispatch=disp),
                                 conflict_free=True, use_ls=True)
                    best = res["best_result"]
                    if validate(inst, best.to_timetable()):
                        print(f"  !! 校验失败 {case['name']} {arm} seed={s}")
                    dt = time.time() - t0
                    f.write(f"{case['name']},{arm},{s},{gen},{best.makespan:.4f},"
                            f"{res['decodes']},{dt:.1f}\n")
                    f.flush()
                    print(f"{case['name']:<14s} {arm} seed={s:<6d} Cmax={best.makespan:7.2f} "
                          f"decodes={res['decodes']:>6d}  {dt:6.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
