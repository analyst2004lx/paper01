# -*- coding: utf-8 -*-
"""定价为何对 theta 不敏感:直接量它到底改动了多少条路径。

theta 扫描给出的事实是:同代数下 theta 从 0.05 到 0.50(十倍量程)结果完全相同,
而每次评价的成本比 theta=0 高约 5 倍。这排除了"定价把车导向坏路径"这类解释——
若真如此,同代数下也该变差,且随 theta 加剧。本脚本检验另一种解释:

  价格表太稀疏,以致绝大多数候选路径的价格同为 0。此时标量化键 t + theta*g
  退化为 t,多标签搜索返回的仍是最早到达路径,theta 再大也没有落点可作用;
  而多标签的簿记开销与价格是否非零无关,照收不误。

做法:固定同一条染色体,分别在 theta=0 与若干 theta>0 下解码,比较每个运输任务
的路径是否真的变了、以及付出的价格总额相对行驶时间有多大。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.decoder import critical_corridor_slots, decode      # noqa: E402
from algorithm.ga import GAConfig, init_population, run_ga         # noqa: E402
from algorithm.instance import load_instance                       # noqa: E402
from algorithm.network import Network                              # noqa: E402
from algorithm.pricing import default_bucket_width, surrogate_prices  # noqa: E402

EXT_DIR = os.path.join(HERE, "input", "ext")
DEFAULT = "S8x4x4-LD21-H0.3-F0.6-A4-s42"


def sig(res):
    """每个运输任务的路径签名:(任务, 走廊序列)。"""
    out = {}
    for tr in res.transports:
        out[(tr.job, tr.i)] = (
            tuple(s.corridor for s in tr.empty_plan.segments),
            tuple(s.corridor for s in tr.loaded_plan.segments))
    return out


def travel_total(res):
    return sum(tr.empty_plan.travel_time + tr.loaded_plan.travel_time
               for tr in res.transports)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default=DEFAULT)
    ap.add_argument("--thetas", type=float, nargs="+",
                    default=[0.05, 0.15, 0.50, 5.0, 50.0])
    ap.add_argument("--warm-gen", type=int, default=15,
                    help="先跑若干代拿一个像样的incumbent,价格表由它生成")
    ap.add_argument("--top-k", type=int, nargs="+", default=[24],
                    help="价格表保留的槽位数;可给多个值考察稀疏度的影响")
    args = ap.parse_args()

    p = os.path.join(EXT_DIR, args.instance + ".json")
    if not os.path.exists(p):
        hits = glob.glob(os.path.join(EXT_DIR, "*%s*.json" % args.instance))
        if len(hits) != 1:
            raise SystemExit("算例名无法唯一确定")
        p = hits[0]
    inst = load_instance(p)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    bw = default_bucket_width(inst)

    # 拿一个有代表性的 incumbent:价格表必须来自像样的解,否则测的是随机解的拥堵
    cfg = GAConfig(pop=60, max_gen=args.warm_gen, stall_gen=10 ** 9, seed=42)
    warm = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
    chrom, base_res = warm["best_chrom"], warm["best_result"]
    print("incumbent C_max = %.1f,桶宽 %.2f,行驶总时长 %.1f"
          % (base_res.makespan, bw, travel_total(base_res)))

    n_corr = len(inst.corridors)
    n_buckets = max(1, int(base_res.makespan // bw) + 1)
    print("走廊 %d 条 x 时段 %d 个 = %d 个走廊-时段格子;运输任务 %d 个"
          % (n_corr, n_buckets, n_corr * n_buckets, len(base_res.transports)))

    base_sig = sig(base_res)
    crit = critical_corridor_slots(base_res, bw)

    for top_k in args.top_k:
        prices = surrogate_prices(inst, base_res, bw, top_k, crit)
        slots = list(prices.items())
        cover = len(slots) / max(1, n_corr * n_buckets)
        print()
        print("--- price_top_k = %d:价格表 %d 个槽位,覆盖 %.2f%% 的走廊-时段格子 ---"
              % (top_k, len(slots), 100 * cover))
        print("  %6s %9s %9s %9s %9s %9s"
              % ("theta", "C_max", "改路任务", "价格总额", "占行驶", "毫秒"))
        for theta in [0.0] + list(args.thetas):
            t0 = time.time()
            res = decode(inst, net, chrom["ma"], chrom["os"],
                         conflict_free=True,
                         prices=(prices if theta > 0 else None),
                         theta=theta, bucket_width=bw if theta > 0 else 0.0,
                         max_entry_options=3, dispatch="exact")
            ms = 1000.0 * (time.time() - t0)
            s = sig(res)
            changed = sum(1 for k in base_sig if s.get(k) != base_sig[k])
            tt = travel_total(res)
            print("  %6.2f %9.1f %9d %9.2f %8.2f%% %9.1f"
                  % (theta, res.makespan, changed, res.price_cost_total,
                     100.0 * res.price_cost_total / max(1e-9, tt), ms))

    print()
    print("判读:'改路任务'为 0 意味着价格根本没有改变任何一条路径——此时 theta 的"
          "量程再宽也不会有任何效果,而多标签簿记的开销照付。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
