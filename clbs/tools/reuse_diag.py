"""增量解码的可省比例:改派一道工序,有多少解码工作其实不必重做?

三次尝试(价格路由、冲突凭证、探询打分)都停在同一处:神谕约 17%,任何局部打分
约 10%。既然"预测一步改派的 makespan 影响"做不到,剩下的出路是不再预测、直接把
候选解码出来比。这条路成不成立只取决于一个数——改派一道工序,前面多少解码结果
可以原样复用。

事件驱动解码按 OS 序列推进。把工序 (j,i) 改派到别的臂上,只会影响它自己及其之后
的事件;排在它前面的工序、运输、预约全部不变。故可省比例的上界就是该工序在 OS
序列中的归一化位置。局部搜索只在**关键链**工序上做改派,而关键链工序未必均匀
分布——若它们普遍靠前,可省比例就低,这条路直接不成立。

本工具跑真实 GA,记录局部搜索实际选中的那些工序的归一化 OS 位置分布。

运行(clbs/ 目录下):  py -m tools.reuse_diag [--gens N] [--seeds a,b]
"""
from __future__ import annotations

import os
import random
import sys
from typing import Dict, List, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import Instance, parse_instance
from algorithm.network import Network
from algorithm.decoder import decode, critical_real_ops
from algorithm.ga import (GAConfig, Chromosome, clone, init_population, mutate,
                          ma_uniform_crossover, pox_crossover)
from algorithm.generator import build_instance, make_spec
from tools.probe_diag import os_positions

CONFIGS = [
    dict(tag="high", nm=8, na=12, jobs=16),
    dict(tag="low", nm=8, na=12, jobs=16),
    dict(tag="scatter", nm=8, na=12, jobs=16),
    dict(tag="low", nm=12, na=16, jobs=16),
    dict(tag="scatter", nm=12, na=16, jobs=24),
]


def collect(inst: Instance, net: Network, seeds: Sequence[int],
            gens: int) -> List[float]:
    """局部搜索会改派的那些工序,其在 OS 序列中的归一化位置。"""
    cfg = GAConfig(pop=40, seed=seeds[0], theta=0.0, dispatch="rule",
                   use_conflict_ops=True)
    out: List[float] = []

    for seed in seeds:
        rng = random.Random(seed)
        pop = init_population(inst, cfg, rng)
        res = [decode(inst, net, ch["ma"], ch["os"],          # type: ignore
                      conflict_free=True, dispatch=cfg.dispatch) for ch in pop]

        for _gen in range(gens):
            order = sorted(range(len(pop)), key=lambda x: res[x].makespan)
            elite, elite_res = pop[order[0]], res[order[0]]

            positions = os_positions(elite["os"])             # type: ignore
            n = len(elite["os"])                              # type: ignore
            for op in critical_real_ops(elite_res)[: cfg.L_ls]:
                if len([m for m in inst.eligible(*op)
                        if m != elite["ma"][op]]) == 0:       # type: ignore
                    continue
                idx = positions.get(op)
                if idx is not None and n > 0:
                    out.append(idx / n)

            new_pop: List[Chromosome] = [clone(pop[k]) for k in order[: cfg.elite]]
            while len(new_pop) < cfg.pop:
                a1 = pop[min(rng.sample(range(len(pop)), 2),
                             key=lambda x: res[x].makespan)]
                b1 = pop[min(rng.sample(range(len(pop)), 2),
                             key=lambda x: res[x].makespan)]
                if rng.random() < cfg.pc:
                    os1, os2 = pox_crossover(a1["os"], b1["os"], inst.job_ids, rng)  # type: ignore
                    ma1, ma2 = ma_uniform_crossover(a1["ma"], b1["ma"], rng)         # type: ignore
                    kids = [{"ma": ma1, "os": os1}, {"ma": ma2, "os": os2}]
                else:
                    kids = [clone(a1), clone(b1)]
                for kid in kids:
                    if rng.random() < cfg.pm:
                        mutate(inst, kid, rng)
                    new_pop.append(kid)
                    if len(new_pop) >= cfg.pop:
                        break
            pop = new_pop
            res = [decode(inst, net, ch["ma"], ch["os"],      # type: ignore
                          conflict_free=True, dispatch=cfg.dispatch) for ch in pop]
    return out


def quantile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> int:
    args = sys.argv[1:]
    gens = int(args[args.index("--gens") + 1]) if "--gens" in args else 20
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 13, 101])

    print(f"代数={gens} 种子={seeds}\n")
    print(f"{'配置':<24s} {'情形':>6s} {'均值':>7s} {'中位':>7s} "
          f"{'四分位':>7s} {'前 1/4 内':>9s} {'后 1/2 外':>9s}")
    print("-" * 78)

    allxs: List[float] = []
    for c in CONFIGS:
        spec = make_spec(c["tag"], 0.3, 0.6, c["jobs"], c["nm"], c["na"], 3,
                         seed=42, tt_tp_target=3.0, grid_rows=4, grid_cols=4)
        inst = parse_instance(build_instance(spec))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        xs = collect(inst, net, seeds, gens)
        allxs += xs
        label = f"{c['tag']} J{c['jobs']} M{c['nm']} A{c['na']}"
        print(f"{label:<24s} {len(xs):>6d} {sum(xs) / max(len(xs), 1):>7.1%} "
              f"{quantile(xs, 0.5):>7.1%} {quantile(xs, 0.25):>7.1%} "
              f"{sum(1 for x in xs if x < 0.25) / max(len(xs), 1):>9.1%} "
              f"{sum(1 for x in xs if x > 0.5) / max(len(xs), 1):>9.1%}")

    print("-" * 78)
    print(f"{'合计':<24s} {len(allxs):>6d} {sum(allxs) / max(len(allxs), 1):>7.1%} "
          f"{quantile(allxs, 0.5):>7.1%} {quantile(allxs, 0.25):>7.1%} "
          f"{sum(1 for x in allxs if x < 0.25) / max(len(allxs), 1):>9.1%} "
          f"{sum(1 for x in allxs if x > 0.5) / max(len(allxs), 1):>9.1%}")
    print()
    print("归一化位置 = 被改派工序在 OS 序列中的下标 / 序列长度")
    print("它同时是增量解码可省比例的上界:位置越靠后,可原样复用的前缀越长")
    print("「前 1/4 内」占比高则可省比例低,这条方法线不成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
