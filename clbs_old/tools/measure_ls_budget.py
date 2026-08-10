# -*- coding: utf-8 -*-
"""局部搜索的成本账:它花掉了多少解码预算,又有多少邻居真的改进了 makespan。

同挂钟对比只能告诉我们"这个机制不划算",说不出它为何不划算。本脚本把 run_ga 内部
的局部搜索计数取出来,给出两个可写进论文的数字:局部搜索占掉的解码次数份额,以及
每个算子族的命中率。命中率极低而份额很大,就解释了为何把算力还给主循环更值。
"""
from __future__ import annotations

import argparse
import glob
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.ga import GAConfig, run_ga           # noqa: E402
from algorithm.instance import load_instance        # noqa: E402
from algorithm.network import Network               # noqa: E402

EXT = os.path.join(HERE, "input", "ext")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", nargs="+",
                    default=["S8x4x4-LD21-H0.3-F0.6-A4-s42",
                             "S8x4x4-LD11-H0.3-F0.6-A4-s42",
                             "S8x4x4-LG21-H0.3-F0.6-A4-s42"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 7, 2024, 13, 99])
    ap.add_argument("--gen", type=int, default=60)
    ap.add_argument("--pop", type=int, default=60)
    args = ap.parse_args()

    share, reas, stag, plateau, rounds = [], [], [], [], []
    for name in args.instances:
        p = os.path.join(EXT, name + ".json")
        if not os.path.exists(p):
            hits = glob.glob(os.path.join(EXT, "*%s*.json" % name))
            if len(hits) != 1:
                raise SystemExit("算例名无法唯一确定:%s" % name)
            p = hits[0]
        inst = load_instance(p)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        for seed in args.seeds:
            cfg = GAConfig(pop=args.pop, max_gen=args.gen, stall_gen=10 ** 9,
                           seed=seed)
            out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
            stt = out.get("ls_stats") or {}
            total = float(out.get("decodes") or 0)
            ls = float(out.get("ls_evaluations") or 0)
            if total > 0:
                share.append(ls / total)
            rt = float(stt.get("reassign_tried") or 0)
            sg = float(stt.get("stagger_tried") or 0)
            if rt:
                reas.append(float(stt.get("reassign_hit") or 0) / rt)
            if sg:
                stag.append(float(stt.get("stagger_hit") or 0) / sg)
            if stt.get("rounds"):
                rounds.append(float(stt["rounds"]))
            plateau.append(float(stt.get("plateau_hit") or 0))
            print("  %-30s seed=%-5d C_max=%6.1f  解码 %6.0f 其中局搜 %6.0f "
                  "(%4.1f%%)  改派命中 %5.1f%%  错峰命中 %5.1f%%"
                  % (inst.name[:30], seed, out["best_result"].makespan,
                     total, ls, 100 * ls / max(1.0, total),
                     100 * (float(stt.get("reassign_hit") or 0) / rt) if rt else 0.0,
                     100 * (float(stt.get("stagger_hit") or 0) / sg) if sg else 0.0))

    print()
    print("=" * 74)
    print("局部搜索占解码预算    %.1f%%  (%d 次运行)" % (100 * st.mean(share), len(share)))
    print("改派算子命中率        %.1f%%" % (100 * st.mean(reas) if reas else 0.0))
    print("错峰算子命中率        %.1f%%" % (100 * st.mean(stag) if stag else 0.0))
    print("=" * 74)
    print("判读:命中率 = 被解码的邻居中改进了 makespan 的比例。份额大而命中率低,"
          "意味着这些解码若还给主循环会产出更多有效搜索。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
