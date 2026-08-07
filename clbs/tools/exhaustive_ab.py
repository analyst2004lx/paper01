"""同挂钟 A/B:改派算子该"打分选一台"还是"穷举全部候选真解码"?

前情。三次尝试(价格路由、冲突凭证、探询打分)都停在同一处(tools/regime_curve.py
--attrib,约 1000 个收敛期情形):随机挑一个候选命中 7.0%,任何局部打分只能到
10.0%,而存在可改进候选的情形占 17.4%。以随机为原点算,打分只捕获了可争取区间的
四分之一强,后悔口径给出同一个比例。剩下的四分之三预测不出来,只能靠真解码去拿。

注意不能拿 17.4% 直接减 10.0% 来衡量打分:神谕允许在全部 4~6 个候选里挑,打分只
能选一个,那 7.0% 的随机基线正是"多试几次"本身值多少。但本脚本不受此影响——穷举
档是真的去试全部候选,也真的被记了这 4~6 次解码的账。

代价这一侧。穷举一个情形要解码 4~6 个候选而非 1 个;增量解码的可省比例实测
46.8%(tools/reuse_diag.py),即最多把这笔开销减半。两边一乘,穷举大约合现行的
2~3 倍成本,换来 1.8 倍的命中率——账面上勉强打平,只能实测。

故本脚本不比代数、只比**同一挂钟预算下的最终 makespan**:两档共用 time_budget_sec,
超时即停。穷举档跑的代数必然更少,若它仍然赢,才说明这笔钱花得值。

运行(clbs/ 目录下):  py -m tools.exhaustive_ab [--budget 15] [--seeds a,b,c]
"""
from __future__ import annotations

import os
import statistics as st
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import parse_instance
from algorithm.network import Network
from algorithm.ga import GAConfig, run_ga
from algorithm.generator import build_instance, make_spec
from algorithm.stats import stars, wilcoxon_signed_rank

CONFIGS = [
    dict(tag="high", nm=8, na=12, jobs=16),
    dict(tag="low", nm=8, na=12, jobs=16),
    dict(tag="scatter", nm=8, na=12, jobs=16),
    dict(tag="low", nm=12, na=16, jobs=16),
    dict(tag="scatter", nm=12, na=16, jobs=24),
]


def main() -> int:
    args = sys.argv[1:]
    budget = (float(args[args.index("--budget") + 1])
              if "--budget" in args else 15.0)
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 13])

    print(f"挂钟预算={budget:g}s/次  种子={seeds}\n")
    print(f"{'算例':<22s} {'种子':>4s} {'现行 C_max':>10s} {'穷举 C_max':>10s} "
          f"{'改善':>7s} {'现行代数':>8s} {'穷举代数':>8s} {'解码比':>7s}")
    print("-" * 84)

    pairs: List[Tuple[float, float]] = []
    ratios: List[float] = []
    by_inst: Dict[str, List[float]] = {}

    for c in CONFIGS:
        spec = make_spec(c["tag"], 0.3, 0.6, c["jobs"], c["nm"], c["na"], 3,
                         seed=42, tt_tp_target=3.0, grid_rows=4, grid_cols=4)
        inst = parse_instance(build_instance(spec))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        label = f"{c['tag']} J{c['jobs']} M{c['nm']} A{c['na']}"

        for seed in seeds:
            got = {}
            for exh in (False, True):
                cfg = GAConfig(pop=40, max_gen=10 ** 6, stall_gen=10 ** 6,
                               seed=seed, theta=0.0, dispatch="rule",
                               use_conflict_ops=True, ls_exhaustive=exh,
                               time_budget_sec=budget)
                got[exh] = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)

            a = got[False]["best_result"].makespan
            b = got[True]["best_result"].makespan
            gain = (a - b) / a if a > 0 else 0.0
            ratio = got[True]["decodes"] / max(got[False]["decodes"], 1)
            pairs.append((a, b))
            ratios.append(ratio)
            by_inst.setdefault(label, []).append(gain)
            print(f"{label:<22s} {seed:>4d} {a:>10.1f} {b:>10.1f} {gain:>+6.2%} "
                  f"{got[False]['generations']:>8d} {got[True]['generations']:>8d} "
                  f"{ratio:>7.2f}")

    print("-" * 84)
    for label, gains in by_inst.items():
        print(f"  {label:<22s} 平均改善 {st.mean(gains):+.2%}")

    g = st.mean([(a - b) / a for a, b in pairs if a > 0])
    w = wilcoxon_signed_rank([a for a, _ in pairs], [b for _, b in pairs])
    wins = sum(1 for a, b in pairs if b < a)
    loss = sum(1 for a, b in pairs if b > a)
    print()
    print(f"总体:穷举相对现行 {g:+.2%} {stars(w['p_value'])}  p={w['p_value']:.4g}  "
          f"胜/负/平 = {wins}/{loss}/{len(pairs) - wins - loss}")
    print(f"      穷举档的解码次数是现行的 {st.mean(ratios):.2f} 倍(同挂钟下代数更少)")
    print()
    print("正数 = 穷举更好。同挂钟预算下比较,故此处的差已经扣掉了穷举多花的算力。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
