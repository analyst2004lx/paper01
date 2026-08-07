"""评估吞吐提高一倍,makespan 能降多少?——增量解码的收益上限。

同挂钟 A/B(tools/exhaustive_ab.py)的胜负写在代数栏里:穷举档 27 代、现行档 53 代,
穷举输 2.49%。既然边际上"多走几步"比"选得更准"值钱,那么该优化的对象就是每一步的
成本,而不是着法质量。增量解码的可省比例实测 46.8%(tools/reuse_diag.py),对应约
1.9 倍吞吐。写解码器之前,先把这 1.9 倍值多少钱估出来。

做法上不跑两档,而是跑一次长的、再从**同一条收敛轨迹**上读出各个时刻的至今最优:
run_ga 逐代记下 history(至今最优 makespan)与 history_sec(对应挂钟)。这既省一半
算力,又是严格的同轨迹配对,没有跑次间噪声。

两个必须一起看的数:

  收益曲线  预算放大 r 倍后 makespan 的降幅。r=1.9 那一列即增量解码的收益上限。
  可省份额  局部搜索解码 / 全部解码。增量解码只对"单点改动"的邻居解码有效;交叉
            之后的种群解码整条 OS 都变了,前缀无从复用。故整体加速约为
            1 / (1 - 0.468 * 可省份额)。若局部搜索只占两成,整体只有 1.1 倍,
            这条方法线当场不成立——收益曲线再好看也够不着。

运行(clbs/ 目录下):  py -m tools.throughput_gain [--base 12] [--seeds a,b,c]
"""
from __future__ import annotations

import os
import statistics as st
import sys
from typing import Dict, List, Sequence, Tuple

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

RATIOS = (1.0, 1.3, 1.6, 1.9, 2.5)
REUSE = 0.468            # tools/reuse_diag.py 实测的增量解码可省比例


def best_at(history: Sequence[float], secs: Sequence[float], t: float) -> float:
    """至今最优 makespan 在挂钟时刻 t 的取值。"""
    out = history[0]
    for v, s in zip(history, secs):
        if s > t:
            break
        out = v
    return out


def main() -> int:
    args = sys.argv[1:]
    base = (float(args[args.index("--base") + 1])
            if "--base" in args else 12.0)
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 13, 101, 5])
    horizon = base * max(RATIOS)

    print(f"基准预算={base:g}s  跑到={horizon:g}s  种子={seeds}\n")
    print(f"{'算例':<22s} " + "".join(f"{f'x{r:g}':>8s}" for r in RATIOS)
          + f" {'局搜占比':>8s} {'整体加速':>8s}")
    print("-" * 74)

    at: Dict[float, List[float]] = {r: [] for r in RATIOS}
    ls_shares: List[float] = []

    for c in CONFIGS:
        spec = make_spec(c["tag"], 0.3, 0.6, c["jobs"], c["nm"], c["na"], 3,
                         seed=42, tt_tp_target=3.0, grid_rows=4, grid_cols=4)
        inst = parse_instance(build_instance(spec))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        label = f"{c['tag']} J{c['jobs']} M{c['nm']} A{c['na']}"

        cell: Dict[float, List[float]] = {r: [] for r in RATIOS}
        shares: List[float] = []
        for seed in seeds:
            cfg = GAConfig(pop=40, max_gen=10 ** 6, stall_gen=10 ** 6,
                           seed=seed, theta=0.0, dispatch="rule",
                           use_conflict_ops=True, time_budget_sec=horizon)
            r = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
            for ratio in RATIOS:
                v = best_at(r["history"], r["history_sec"], base * ratio)
                cell[ratio].append(v)
                at[ratio].append(v)
            shares.append(r["ls_evaluations"] / max(r["decodes"], 1))
        ls_shares += shares

        sh = st.mean(shares)
        speed = 1.0 / (1.0 - REUSE * sh)
        print(f"{label:<22s} "
              + "".join(f"{st.mean(cell[r]):>8.1f}" for r in RATIOS)
              + f" {sh:>8.1%} {speed:>7.2f}x")

    print("-" * 74)
    b = at[1.0]
    print(f"{'相对 x1 的降幅':<22s} "
          + "".join(f"{st.mean([(x - y) / x for x, y in zip(b, at[r])]):>7.2%}"
                   for r in RATIOS))

    w = wilcoxon_signed_rank(b, at[1.9])
    gain = st.mean([(x - y) / x for x, y in zip(b, at[1.9])])
    wins = sum(1 for x, y in zip(b, at[1.9]) if y < x)
    loss = sum(1 for x, y in zip(b, at[1.9]) if y > x)
    print()
    print(f"x1.9(增量解码的收益上限):{gain:+.2%} {stars(w['p_value'])}  "
          f"p={w['p_value']:.4g}  胜/负/平 = {wins}/{loss}/{len(b) - wins - loss}")

    sh = st.mean(ls_shares)
    speed = 1.0 / (1.0 - REUSE * sh)
    print(f"但局部搜索仅占全部解码的 {sh:.1%},按可省 {REUSE:.1%} 折算,"
          f"整体加速只有 {speed:.2f}x")
    eff = st.mean([(x - y) / x for x, y in
                   zip(b, at[min(RATIOS, key=lambda r: abs(r - speed))])])
    print(f"故实际可期的降幅约为 x{min(RATIOS, key=lambda r: abs(r - speed)):g} "
          f"那一档,即 {eff:+.2%}")
    print()
    print("同一条收敛轨迹上读取不同时刻的至今最优,故各档严格配对、无跑次间噪声。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
