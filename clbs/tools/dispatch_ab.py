"""降本之后,派车试探能否在同挂钟口径下赢下规则派车?

三个创新点里只有派车试探被证实有决策增益:同代数下相对规则派车好约 3%
(output/matrix/gen100:拥堵档 +3.39%、漏斗档 +2.42%,S8x4x4-LD11-H0 一格 p=0.0246),
但每次评价贵 4.6 倍(15.9 vs 3.5 毫秒),于是同挂钟下增益被算力吃光
(output/matrix/p3:-0.12%,40 胜 39 负,p=0.53)。

decoder.dispatch_exact 随后做了两处**可证明等价**的降本改造(见其文档字符串与
tools/dispatch_speedup.py 的逐位等价验证):可采纳下界剪枝 + 胜者路径复用,路由调用减半、
挂钟提速 1.82 倍,成本倍数从 4.6x 降到约 2.5x。若那 3% 的决策增益是实的,提速后就该在同
挂钟口径下显形——这是本工具要判的事。

口径为**同挂钟**:这是对试探派车最不利、也最贴近实用的口径。同时记录各档达到的代数,
以便把"赢在哪"说清楚:是决策更好,还是仅仅代数追平了。

运行(clbs/ 目录下):
  py -u -m tools.dispatch_ab [--budget 秒] [--seeds a,b,c] [--only 名字片段,...]
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.ga import GAConfig, run_ga
from algorithm.stats import spearman, wilcoxon_signed_rank
from algorithm.validator import validate
from tools.price_matrix import CASES, build, instance_contention

ARMS = [("规则派车", "rule"), ("试探派车", "exact")]


def main() -> int:
    args = sys.argv[1:]
    budget = float(args[args.index("--budget") + 1]) if "--budget" in args else 20.0
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 2024, 13, 101])
    # 20 秒预算下高争用格的代数塌到 8~16 代,pop=60 的 GA 那时几乎还没离开随机初始化,
    # 失利可能只是预算假象。--only 用于在这些格上单独加大预算复核。
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    cases = [c for c in CASES if only is None or any(k in c["name"] for k in only)]

    print(f"同挂钟预算 {budget:.0f}s/次,种子={seeds},theta=0,错峰算子开")
    print(f"档位:{', '.join(a for a, _ in ARMS)};算例 {len(cases)} 个\n")

    mk: Dict[str, Dict[str, List[float]]] = {a: {} for a, _ in ARMS}
    gen: Dict[str, Dict[str, List[int]]] = {a: {} for a, _ in ARMS}
    cont: Dict[str, float] = {}
    t0 = time.time()

    for case in cases:
        inst, net = build(case)
        cont[case["name"]] = instance_contention(inst, net, "exact")
        base = GAConfig(pop=60, max_gen=1000, stall_gen=300, use_conflict_ops=True,
                        theta=0.0, max_entry_options=3, time_budget_sec=budget)
        for label, disp in ARMS:
            mk[label][case["name"]], gen[label][case["name"]] = [], []
            for s in seeds:
                out = run_ga(inst, net, replace(base, seed=s, dispatch=disp),
                             conflict_free=True, use_ls=True)
                res = out["best_result"]
                errs = validate(inst, res.to_timetable())
                if errs:
                    print(f"  !! 校验失败 {case['name']} {label} seed={s}: {errs[:1]}")
                mk[label][case["name"]].append(res.makespan)
                gen[label][case["name"]].append(out["generations"])
        print(f"  已完成 {case['name']:<14s} 争用强度 {cont[case['name']]:.1%}  "
              f"累计 {time.time() - t0:.0f}s")

    names = [c["name"] for c in cases]
    a_rule, a_exact = ARMS[0][0], ARMS[1][0]

    print(f"\n{'算例':<14s} {'争用强度':>8s} {'规则 C':>8s} {'代数':>6s} "
          f"{'试探 C':>8s} {'代数':>6s} {'Δ(负=试探更好)':>16s}")
    print("-" * 74)
    gains: List[float] = []
    for nm in names:
        r, e = mk[a_rule][nm], mk[a_exact][nm]
        rel = sum((x - y) / y for x, y in zip(e, r)) / len(r)
        gains.append(rel)
        print(f"{nm:<14s} {cont[nm]:>8.1%} "
              f"{sum(r) / len(r):>8.2f} {sum(gen[a_rule][nm]) / len(seeds):>6.0f} "
              f"{sum(e) / len(e):>8.2f} {sum(gen[a_exact][nm]) / len(seeds):>6.0f} "
              f"{rel:>15.2%} ")

    print("-" * 74)
    flat_r = [v for nm in names for v in mk[a_rule][nm]]
    flat_e = [v for nm in names for v in mk[a_exact][nm]]
    rel = sum((x - y) / y for x, y in zip(flat_e, flat_r)) / len(flat_r)
    win = sum(1 for x, y in zip(flat_e, flat_r) if x < y - 1e-9)
    loss = sum(1 for x, y in zip(flat_e, flat_r) if x > y + 1e-9)
    w = wilcoxon_signed_rank(flat_e, flat_r)
    print(f"\n配对检验({len(flat_r)} 对 = {len(names)} 算例 x {len(seeds)} 种子):")
    print(f"  试探派车 vs 规则派车:平均 {rel:+.2%}"
          f"({'更好' if rel < 0 else '更差'})  "
          f"{win} 胜 / {loss} 负 / {len(flat_r) - win - loss} 平  "
          f"n_eff={w['n_eff']}  p={w['p_value']:.4f}")

    g_rule = sum(sum(gen[a_rule][nm]) for nm in names) / (len(names) * len(seeds))
    g_exact = sum(sum(gen[a_exact][nm]) for nm in names) / (len(names) * len(seeds))
    print(f"  平均代数:规则 {g_rule:.0f} vs 试探 {g_exact:.0f}"
          f"(比值 {g_rule / max(g_exact, 1e-9):.2f}x)——同挂钟下试探仍少跑这么多代")

    rho = spearman([cont[nm] for nm in names], gains)
    print(f"\n争用强度 vs 试探派车收益的秩相关:"
          f"{f'{rho:+.3f}' if rho is not None else 'n/a'}"
          f"(**负**相关才是想要的:争用越强、试探越值)")
    print("\n对照基线:降本改造前,同挂钟口径下试探派车为 -0.12%(40 胜 39 负,p=0.53,")
    print("见 output/matrix/p3);同代数口径下为 +3.4% / +2.4%(见 output/matrix/gen100)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
