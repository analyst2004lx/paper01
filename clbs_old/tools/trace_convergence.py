"""记录若干档位的收敛轨迹(最优 C_max 随挂钟时间的变化)。

为什么横轴必须是挂钟而不是代数:两阶段档每次评价 0.4 ms、闭环档 15.7 ms,
按代数画会让最贵的档看起来"收敛得最快",而那只是它每代做了更多工作。
GA 现在逐代记录 `history_sec`,本工具把它与 `history` 对齐后落盘。

运行(clbs/ 目录下):  py -m tools.trace_convergence --n-seeds 5
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from typing import List, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.baseline import solve_arm                        # noqa: E402
from algorithm.ga import GAConfig, run_ga                       # noqa: E402
from algorithm.instance import load_instance                    # noqa: E402
from algorithm.network import Network                           # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(HERE, "input", "ext")
OUT_DIR = os.path.join(HERE, "experiments")

SEED_POOL = [42, 7, 2024, 13, 99, 314, 2718, 1618, 577, 8191]
ARMS = ["twostage", "nofeedback", "closed"]
DEFAULT_INSTANCE = "S8x4x4-LD21-H0.3-F0.6-A4-s42"


def resolve(name: str) -> str:
    p = name if os.path.isabs(name) else os.path.join(EXT_DIR, name + ".json")
    if os.path.exists(p):
        return p
    hits = glob.glob(os.path.join(EXT_DIR, "*%s*.json" % name))
    if len(hits) != 1:
        raise SystemExit("算例名无法唯一确定: %s -> %s" % (name, hits))
    return hits[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="收敛轨迹(挂钟横轴)")
    ap.add_argument("--instance", default=DEFAULT_INSTANCE)
    ap.add_argument("--arms", nargs="+", default=ARMS)
    ap.add_argument("--n-seeds", type=int, default=5)
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--budget", type=float, default=None,
                    help="挂钟预算(秒);缺省则用 closed 的自然用时标定")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "convergence.csv"))
    args = ap.parse_args()

    path = resolve(args.instance)
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    with open(path, encoding="utf-8") as f:
        feats = json.load(f).get("_features", {})
    seeds = SEED_POOL[: args.n_seeds]

    budget = args.budget
    if budget is None:
        base = GAConfig(pop=args.pop, max_gen=200, stall_gen=30, seed=seeds[0],
                        dispatch="exact", use_conflict_ops=True)
        t0 = time.time()
        run_ga(inst, net, base, conflict_free=True, use_ls=True)
        budget = round(time.time() - t0, 2)
    print("[%s] 预算 %.1fs,种子 %s" % (inst.name, budget, seeds), flush=True)

    rows: List[dict] = []
    for arm in args.arms:
        for s in seeds:
            cfg = GAConfig(pop=args.pop, max_gen=100000, stall_gen=100000,
                           seed=s, time_budget_sec=budget)
            out = solve_arm(arm, inst, net, cfg)
            hist = out.get("history") or []
            secs = out.get("history_sec") or []
            if not hist:
                print("  %-12s seed=%-5d 无轨迹(该档不含 GA 搜索)" % (arm, s))
                continue
            # 两阶段档的 history 来自它的第一阶段(理想运输模型),系统性低估;
            # surrogate 列把这件事记录在数据里,而不是只写在图注里
            surrogate = int(bool(out.get("history_is_surrogate")))
            for gen, (v, t) in enumerate(zip(hist, secs), start=1):
                rows.append({"instance": inst.name,
                             "tag": feats.get("congestion_tag"),
                             "arm": arm, "seed": s, "gen": gen,
                             "sec": t, "best_makespan": v,
                             "surrogate": surrogate,
                             "final_true_makespan": out["makespan"],
                             "budget_sec": budget})
            print("  %-12s seed=%-5d %4d 代,末值 %.1f,用时 %.1fs"
                  % (arm, s, len(hist), hist[-1], secs[-1] if secs else -1),
                  flush=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n写出 %s (%d 行)" % (args.out, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
