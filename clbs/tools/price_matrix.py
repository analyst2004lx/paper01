"""定价协调的多算例复检:修正混淆对照后,价格制导到底值多少,又在哪些参数区间值钱。

为什么要重跑。GAConfig.theta 默认 0,依据是 tools/sweep_price.py 判定"价格加权路由系统性
有害"。但在那份扫描里,唯一的定价档也是唯一把 max_entry_options 设成 1 的档,而
network.feasible_entries 在 limit<=1 时只返回最早可行进入时刻——价格感知路由于是表达不出
"多等一会儿、进一个更便宜的时段",这恰是多标签路由存在的理由。该档因此只剩空间绕行,
与对照档的差异同时压在"开不开价格"和"能不能选进入时刻"两件事上,归因不成立。
tools/entry_options_ab.py 在单个算例上已证实:改回选项=3 后,同代数口径下价格从更差 0.74%
变为更好 0.46%(对被削档则好 1.20%)。本工具把该结论推广到多算例、多布局。

口径。**同代数**为主口径:价格感知路由每次解码贵 2~4 倍,同挂钟下代数会被榨干(实测
35 / 18 / 9 代),那样量到的是算力成本而非制导质量。要判断机制本身是否成立,必须先抹平
吞吐差异;吞吐是另一条可工程解决的线。

矩阵覆盖三个因素,每次只动一个:
  A 布局      high / funnel(哑铃,出口与车道数递减)、low(网格)、scatter(错落网格)
  B 车臂比    NA/NM = 0.5 / 1.0 / 2.0
  C 柔性      F = 0.6 / 1.0
外加一个大规模高争用算例——若定价有用,那里最该看得出来。

同时报告每个算例的争用占比,并对"争用占比 vs 定价收益"做秩相关:论文要的不是"定价平均
有用",而是"定价在争用强的区间有用",后者才是可辩护的主张。

运行(clbs/ 目录下):
  py -u -m tools.price_matrix --probe          # 只量各算例的争用占比,秒级,先确认梯度
  py -u -m tools.price_matrix [--gens N] [--seeds a,b,c] [--thetas 0.15,0.3]
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from typing import Dict, List, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.decoder import decode
from algorithm.ga import GAConfig, init_population, run_ga
from algorithm.generator import build_instance, make_spec
from algorithm.instance import Instance, parse_instance
from algorithm.network import Network
from algorithm.stats import spearman, wilcoxon_signed_rank
from algorithm.validator import validate

# 算例集必须张开一个真实的**争用梯度**,否则秩相关无从谈起。首轮冒烟发现 low /
# scatter / 全柔性三格的争用占比恰为 0.0%——那里根本没有走廊让行,定价再准也无处施展,
# 把它们混进平均值只会把结论稀释成"定价无用"。故按争用从低到高铺开:布局(出口与车道
# 数)、车数、Tt/Tp 与规模四个旋钮一起用来拉开梯度,并保留两个近零争用格作为下端锚点。
CASES: List[dict] = [
    # 下端锚点:几乎无争用,定价理应无效,用于确认收益不是凭空来的
    dict(name="低 low",        tag="low",     jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
    dict(name="低 scatter",    tag="scatter", jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
    # 中段:哑铃布局,出口/车道数递减
    dict(name="中 high",       tag="high",    jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
    dict(name="中 funnel",     tag="funnel",  jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
    # 上段:加车、加运输占比、加规模
    dict(name="高 funnel A8",  tag="funnel",  jobs=8,  nm=4, na=8,  flex=0.6, tt=3.0),
    dict(name="高 funnel tt4", tag="funnel",  jobs=12, nm=4, na=8,  flex=0.6, tt=4.0),
    dict(name="高 high M8",    tag="high",    jobs=12, nm=8, na=12, flex=0.6, tt=3.0),
    dict(name="高 funnel M8",  tag="funnel",  jobs=12, nm=8, na=12, flex=0.6, tt=4.0),
    # C 柔性对照:放在有争用的布局上才有意义
    dict(name="C 全柔 funnel", tag="funnel",  jobs=8,  nm=4, na=8,  flex=1.0, tt=3.0),
]


def contention_share(inst: Instance, net: Network, chrom, dispatch: str) -> float:
    """同一染色体在无冲突路由与理想最短路下的 makespan 之差占比。

    两次解码必须用**同一派车规则**,否则差值里混进了派车决策的变化:exact 派车会按预约
    表挑车,rule 派车按理想最短路估算挑车,两者选出的车可能不同,于是"理想"一侧反而可能
    更差,被 max(0,·) 夹成 0。regime_curve 里 GA 本身就跑 rule 派车故无此问题,照抄到
    exact 派车的场景就成了错的——首轮矩阵九格里争用占比全为 0 即由此而来。
    """
    real = decode(inst, net, chrom["ma"], chrom["os"],
                  conflict_free=True, dispatch=dispatch)
    ideal = decode(inst, net, chrom["ma"], chrom["os"],
                   conflict_free=False, dispatch=dispatch)
    if real.makespan <= 1e-9:
        return 0.0
    return max(0.0, (real.makespan - ideal.makespan) / real.makespan)


def instance_contention(inst: Instance, net: Network, dispatch: str,
                        n: int = 20, seed: int = 42) -> float:
    """算例层面的争用强度:初始随机种群上争用占比的均值。

    不用"优化后的最优解"来衡量,因为那量的是解而不是算例——优化器本就会绕开拥堵走廊,
    收敛解上的争用趋近于零,反而抹掉了算例之间的差别。
    """
    import random
    rng = random.Random(seed)
    pop = init_population(inst, GAConfig(pop=n, seed=seed), rng)
    vals = [contention_share(inst, net, ch, dispatch) for ch in pop]
    return sum(vals) / len(vals) if vals else 0.0


def build(case: dict):
    extra = {}
    if case["tag"] in ("low", "scatter"):
        extra = dict(grid_rows=4, grid_cols=4)
    spec = make_spec(case["tag"], 0.3, case["flex"], case["jobs"],
                     case["nm"], case["na"], 3, seed=42,
                     tt_tp_target=case["tt"], **extra)
    inst = parse_instance(build_instance(spec))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    return inst, net


def probe() -> int:
    """只量各算例的争用强度,秒级确认梯度是否张开。"""
    print("算例层面的争用强度 = 初始随机种群(20 个)上争用占比的均值,派车 exact\n")
    print(f"{'算例':<16s} {'布局':>9s} {'NA/NM':>7s} {'柔性':>6s} {'Tt/Tp':>7s} {'争用强度':>9s}")
    print("-" * 62)
    for case in CASES:
        inst, net = build(case)
        cs = instance_contention(inst, net, "exact")
        print(f"{case['name']:<16s} {case['tag']:>9s} "
              f"{case['na'] / case['nm']:>7.2f} {case['flex']:>6.1f} "
              f"{case['tt']:>7.1f} {cs:>9.1%}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    gens = int(args[args.index("--gens") + 1]) if "--gens" in args else 20
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 2024])
    thetas = ([float(x) for x in args[args.index("--thetas") + 1].split(",")]
              if "--thetas" in args else [0.15, 0.3])

    if "--probe" in args:
        return probe()

    arms = [("theta=0", 0.0)] + [(f"theta={t:g}", t) for t in thetas]
    print(f"同代数口径 {gens} 代/次,种子={seeds},派车=exact,错峰算子开,"
          f"进入时刻选项=3(全部档位一致)")
    print(f"档位:{', '.join(a for a, _ in arms)}\n")

    # (档位, 算例, 种子) -> makespan;按 (算例,种子) 配对
    vals: Dict[str, Dict[str, List[float]]] = {a: {} for a, _ in arms}
    cont: Dict[str, float] = {}
    t0 = time.time()

    for case in CASES:
        inst, net = build(case)
        cont[case["name"]] = instance_contention(inst, net, "exact")
        base = GAConfig(pop=60, max_gen=gens, stall_gen=gens, dispatch="exact",
                        use_conflict_ops=True, max_entry_options=3,
                        time_budget_sec=None)
        for label, th in arms:
            vals[label][case["name"]] = []
            for s in seeds:
                out = run_ga(inst, net, replace(base, seed=s, theta=th),
                             conflict_free=True, use_ls=True)
                res = out["best_result"]
                errs = validate(inst, res.to_timetable())
                if errs:
                    print(f"  !! 校验失败 {case['name']} {label} seed={s}: {errs[:1]}")
                vals[label][case["name"]].append(res.makespan)
        print(f"  已完成 {case['name']:<14s} 争用强度 {cont[case['name']]:.1%}  "
              f"累计 {time.time() - t0:.0f}s")

    names = [c["name"] for c in CASES]
    base_label = arms[0][0]

    print(f"\n{'算例':<14s} {'争用占比':>8s} "
          + "".join(f"{a:>12s}" for a, _ in arms)
          + "".join(f"{'Δ ' + a:>12s}" for a, _ in arms[1:]))
    print("-" * (24 + 12 * (2 * len(arms) - 1)))
    for nm in names:
        b = vals[base_label][nm]
        row = f"{nm:<14s} {cont[nm]:>8.1%} "
        row += "".join(f"{sum(vals[a][nm]) / len(vals[a][nm]):>12.2f}"
                       for a, _ in arms)
        for a, _ in arms[1:]:
            rel = sum((x - y) / y for x, y in zip(vals[a][nm], b)) / len(b)
            row += f"{rel:>11.2%} "
        print(row)

    print("-" * (24 + 12 * (2 * len(arms) - 1)))
    flat_b = [v for nm in names for v in vals[base_label][nm]]
    print(f"\n配对检验(全部 {len(flat_b)} 对 = {len(names)} 算例 x {len(seeds)} 种子),"
          f"负号表示定价更好:")
    gains: Dict[str, List[float]] = {}
    for a, _ in arms[1:]:
        flat_a = [v for nm in names for v in vals[a][nm]]
        rel = sum((x - y) / y for x, y in zip(flat_a, flat_b)) / len(flat_b)
        win = sum(1 for x, y in zip(flat_a, flat_b) if x < y - 1e-9)
        loss = sum(1 for x, y in zip(flat_a, flat_b) if x > y + 1e-9)
        w = wilcoxon_signed_rank(flat_a, flat_b)
        print(f"  {a:<12s} vs {base_label}: 平均 {rel:+.2%}  "
              f"{win} 胜 / {loss} 负 / {len(flat_b) - win - loss} 平  "
              f"n_eff={w['n_eff']}  p={w['p_value']:.4f}")
        gains[a] = [
            sum((x - y) / y for x, y in zip(vals[a][nm], vals[base_label][nm]))
            / len(vals[base_label][nm])
            for nm in names
        ]

    print(f"\n争用占比 vs 定价收益的秩相关(按 {len(names)} 个算例;"
          f"**负**相关才是想要的结果,即争用越强、定价越省):")
    xs = [cont[nm] for nm in names]
    for a, _ in arms[1:]:
        rho = spearman(xs, gains[a])
        print(f"  {a:<12s}: {f'{rho:+.3f}' if rho is not None else 'n/a'}")

    print("\n口径说明:同代数抹平了吞吐差异,故此处量的是**制导质量**而非实用收益;")
    print("价格感知路由每次解码贵 2~4 倍,同挂钟下的实用结论另需吞吐改造后再测。")
    print("争用占比 = (无冲突路由 C_max - 理想最短路 C_max) / 无冲突路由 C_max。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
