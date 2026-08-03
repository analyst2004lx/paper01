# -*- coding: utf-8 -*-
"""局部搜索诊断:两族算子各生成了多少邻居、命中了多少、吃掉了多少算力。

同挂钟预算下完整方法反而略差于"只闭评估回路"(p3:-2.5%,p=0.016),有两种互斥
的解释:邻域方向不对(没信号),或方向对但太贵(有信号、买不起)。本脚本回答前半部分
——把改派族与错峰族的生成/命中分开计数,并给出局部搜索占总解码数的比例。

用法:
    py tools/diagnose_ls.py                  # 默认 4 个算例 x 3 种子,短跑
    py tools/diagnose_ls.py --gen 30 --pop 60
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.generator import measure              # noqa: E402
from algorithm.ga import GAConfig, run_ga            # noqa: E402
from algorithm.instance import parse_instance        # noqa: E402
from algorithm.network import Network                # noqa: E402

EXT_DIR = os.path.join(HERE, "input", "ext")


def discover(tags, het):
    found = []
    for path in sorted(glob.glob(os.path.join(EXT_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        feat = data.get("_features") or measure(data)
        h = feat.get("target_heterogeneity")
        if feat.get("congestion_tag") not in tags:
            continue
        if h is None or not any(abs(h - t) < 1e-9 for t in het):
            continue
        found.append((data.get("name", os.path.basename(path)),
                      feat.get("congestion_tag"), data))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, default=25)
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 7, 2024])
    ap.add_argument("--tags", nargs="+", default=["high", "funnel"])
    ap.add_argument("--het", type=float, nargs="+", default=[0.0, 0.3])
    args = ap.parse_args()

    found = discover(args.tags, args.het)
    if not found:
        print("没有匹配的算例", flush=True)
        return 1

    agg = defaultdict(float)
    for name, tag, data in found:
        inst = parse_instance(data)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        for seed in args.seeds:
            cfg = GAConfig(pop=args.pop, max_gen=args.gen, stall_gen=10 ** 9,
                           seed=seed)
            out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
            st = out["ls_stats"]
            ga_ev, ls_ev = out["evaluations"], out["ls_evaluations"]
            for k, v in st.items():
                agg[k] += v
            agg["ga_eval"] += ga_ev
            agg["ls_eval"] += ls_ev
            print(f"  {name:34s} seed={seed:<5d} "
                  f"C_max={out['best_result'].makespan:6.1f} "
                  f"GA评价={ga_ev:6d} LS解码={ls_ev:6d} "
                  f"({ls_ev / max(1, ga_ev + ls_ev):5.1%} 的算力)", flush=True)

    print()
    print("=" * 74)
    tot = agg["ga_eval"] + agg["ls_eval"]
    print(f"总解码 {tot:.0f} 次:种群评价 {agg['ga_eval']:.0f} "
          f"({agg['ga_eval'] / tot:.1%}),局部搜索 {agg['ls_eval']:.0f} "
          f"({agg['ls_eval'] / tot:.1%})")
    print()
    print(f"局部搜索轮数 {agg['rounds']:.0f};其中关键链含走廊争用(错峰族可触发)的轮数 "
          f"{agg['chain_corridor']:.0f} ({agg['chain_corridor'] / max(1.0, agg['rounds']):.1%})")
    print()
    print(f"{'算子族':<12}{'生成邻居':>10}{'被接受':>10}{'命中率':>10}")
    for fam, label in (("reassign", "改派"), ("stagger", "错峰")):
        t, h = agg[fam + "_tried"], agg[fam + "_hit"]
        print(f"{label:<12}{t:>10.0f}{h:>10.0f}{h / max(1.0, t):>10.1%}")
    print()
    print("判读:错峰族的触发轮占比就是'凭证有多常有话可说';两族命中率之比就是"
          "'凭证制导相对普通关键路径改派的增量'。若错峰族既少触发又低命中,"
          "则决策回路名不副实,应先修信号而非先降成本。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
