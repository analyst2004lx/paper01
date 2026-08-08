"""定价机制被判死时,它的时间维自由度是不是本来就被关掉了?

背景。GAConfig.theta 默认 0,注释给的依据是 tools/sweep_price.py 显示"价格加权路由
系统性有害"。但在那份扫描里,唯一的定价档 E 也是唯一把 max_entry_options 设成 1 的
档。而 network.feasible_entries 在 limit<=1 时只返回最早可行进入时刻,于是价格感知
路由再也表达不出"多等一会儿、进一个更便宜的时段"——按该函数自己的注释,这恰是多标签
路由存在的理由。E 因此只剩空间绕行,与 A~D 的差异同时压在"开不开价格"和"能不能选
进入时刻"两件事上,归因不成立。

本工具只比三档,每档只差一个开关:

  D   theta=0            进入时刻选项=3   (不开价格)
  E   theta=0.15         进入时刻选项=1   (原扫描里的定价档)
  E'  theta=0.15         进入时刻选项=3   (只把那一处改回默认)

E' 减 D 才是"开价格"的干净效应;E' 减 E 是进入时刻选择本身值多少。

两种口径都要跑,否则结论不可归因:
- 同挂钟(默认):贴近实用,但价格感知路由每次解码贵 2~4 倍,代数会被榨干,于是
  "制导得不好"与"跑得太慢"混在一起;
- 同代数(--samegen):把吞吐差异抹平,单独量制导质量。若同代数下价格档不再更差,
  则 theta=0 该归因于算力成本而非重复计价。

运行(clbs/ 目录下):
  py -u -m tools.entry_options_ab [算例路径] [--budget 秒] [--samegen 代数]
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import load_instance, feature_params
from algorithm.network import Network
from algorithm.ga import GAConfig, run_ga
from algorithm.validator import validate

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(HERE, "input", "congested_8x4x4.json")

ARMS = [
    ("D  theta=0    选项=3", dict(theta=0.0, max_entry_options=3)),
    ("E  theta=0.15 选项=1", dict(theta=0.15, max_entry_options=1)),
    ("E' theta=0.15 选项=3", dict(theta=0.15, max_entry_options=3)),
]


def main() -> int:
    args = sys.argv[1:]
    budget = 20.0
    samegen = 0
    if "--budget" in args:
        k = args.index("--budget")
        budget = float(args[k + 1])
        del args[k:k + 2]
    if "--samegen" in args:
        k = args.index("--samegen")
        samegen = int(args[k + 1])
        del args[k:k + 2]
    path = args[0] if args else DEFAULT

    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    feat = feature_params(inst, net.ideal_dist)
    print(f"算例 {inst.name}: Tt/Tp={feat['Tt_over_Tp']}, 异构度={feat['heterogeneity']}, "
          f"柔性度={feat['flexibility']}, NA/NM={feat['NA_over_NM']}")
    seeds = [42, 7, 2024, 13, 101]
    if samegen:
        print(f"同代数口径 {samegen} 代/次(不设挂钟上限),派车=exact,错峰算子开\n")
        base = GAConfig(pop=60, max_gen=samegen, stall_gen=samegen,
                        dispatch="exact", use_conflict_ops=True,
                        time_budget_sec=None)
    else:
        print(f"同挂钟预算 {budget:.0f}s/次,派车=exact,错峰算子开\n")
        base = GAConfig(pop=60, max_gen=400, stall_gen=120, dispatch="exact",
                        use_conflict_ops=True, time_budget_sec=budget)

    print(f"{'档位':<22s} {'均值':>7s} {'最好':>6s} {'最差':>6s} {'代数':>6s}  各种子")
    print("-" * 76)
    table = {}
    for label, kw in ARMS:
        vals: List[float] = []
        gens: List[int] = []
        for s in seeds:
            cfg = replace(base, seed=s, **kw)
            out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
            res = out["best_result"]
            errs = validate(inst, res.to_timetable())
            if errs:
                print(f"  !! 校验失败 {label} seed={s}: {errs[:1]}")
            vals.append(res.makespan)
            gens.append(out["generations"])
        table[label] = vals
        print(f"{label:<22s} {sum(vals) / len(vals):>7.2f} {min(vals):>6.1f} "
              f"{max(vals):>6.1f} {sum(gens) / len(gens):>6.0f}  "
              + " ".join(f"{v:.0f}" for v in vals))

    print("-" * 76)
    d = table[ARMS[0][0]]
    for label, _kw in ARMS[1:]:
        v = table[label]
        rel = sum((a - b) / b for a, b in zip(v, d)) / len(d)
        win = sum(1 for a, b in zip(v, d) if a < b - 1e-9)
        loss = sum(1 for a, b in zip(v, d) if a > b + 1e-9)
        print(f"{label} vs D:  makespan 平均 {rel:+.2%}"
              f"({'更差' if rel > 0 else '更好'})  "
              f"{win} 胜 / {loss} 负 / {len(d) - win - loss} 平")
    e, ep = table[ARMS[1][0]], table[ARMS[2][0]]
    rel = sum((a - b) / b for a, b in zip(ep, e)) / len(e)
    print(f"E' vs E   :  makespan 平均 {rel:+.2%}"
          f"({'更差' if rel > 0 else '更好'})  ← 进入时刻选择本身值多少")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
