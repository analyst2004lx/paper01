"""价格协调强度 theta 的受控扫描(负面结果的证据链)。

论文主张"价格化层间接口系统性有害、且随 theta 单调恶化"。要让这句话站得住,
扫描必须满足两条,否则结论会被"价格档只是算力更少"这个平凡解释吃掉:

1. **同挂钟预算**:theta>0 每次评价要跑多标签 Pareto 搜索,实测比 theta=0 贵
   数倍。预算由 theta=0 档的自然用时标定,全部 theta 共用(规格 8.2 协议 1);
2. **多种子配对**:同一 theta 下用同一组种子,报告相对 theta=0 的配对增益与
   Wilcoxon p 值(协议 2)。

运行(clbs/ 目录下):  py -m tools.sweep_theta --n-seeds 10
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from dataclasses import replace
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.ga import GAConfig, run_ga                      # noqa: E402
from algorithm.instance import load_instance                    # noqa: E402
from algorithm.network import Network                           # noqa: E402
from algorithm.stats import describe, mean, wilcoxon_signed_rank  # noqa: E402
from algorithm.validator import validate                        # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(HERE, "input", "ext")
OUT_DIR = os.path.join(HERE, "experiments")

SEED_POOL = [42, 7, 2024, 13, 99, 314, 2718, 1618, 577, 8191,
             101, 233, 1024, 4096, 65537]
THETAS = [0.0, 0.05, 0.10, 0.15, 0.30, 0.50]
# 默认取受控对比的两档:high 有决策杠杆,funnel 的拥堵基本无法回避
DEFAULT_INSTANCES = ["S8x4x4-LD21-H0.3-F0.6-A4-s42",
                     "S8x4x4-LD11-H0.3-F0.6-A4-s42"]


def resolve(names: Sequence[str]) -> List[str]:
    out = []
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(EXT_DIR, n + ".json")
        if not os.path.exists(p):
            hits = glob.glob(os.path.join(EXT_DIR, "*%s*.json" % n))
            if len(hits) != 1:
                raise SystemExit("算例名无法唯一确定: %s -> %s" % (n, hits))
            p = hits[0]
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="theta 受控扫描(同算力)")
    ap.add_argument("--instances", nargs="+", default=DEFAULT_INSTANCES)
    ap.add_argument("--thetas", type=float, nargs="+", default=THETAS)
    ap.add_argument("--n-seeds", type=int, default=10)
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--budget-cap", type=float, default=None)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "theta_sweep.csv"))
    args = ap.parse_args()

    seeds = SEED_POOL[: args.n_seeds]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows: List[dict] = []
    t_all = time.time()

    for path in resolve(args.instances):
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        with open(path, encoding="utf-8") as f:
            feats = json.load(f).get("_features", {})

        # 预算标定:theta=0 的完整方法在默认停机规则下的自然用时
        base = GAConfig(pop=args.pop, max_gen=200, stall_gen=30, seed=seeds[0],
                        theta=0.0, dispatch="exact", use_conflict_ops=True)
        t0 = time.time()
        run_ga(inst, net, base, conflict_free=True, use_ls=True)
        natural = round(time.time() - t0, 2)
        budget = min(natural, args.budget_cap) if args.budget_cap else natural
        print("[%s] 标定预算 %.1fs (自然用时 %.1fs)" % (inst.name, budget, natural),
              flush=True)

        for theta in args.thetas:
            for s in seeds:
                # 放宽早停,否则预算根本用不完,"同算力"名存实亡
                cfg = replace(base, seed=s, theta=theta, max_gen=100000,
                              stall_gen=100000, time_budget_sec=budget,
                              max_entry_options=(1 if theta > 0 else 3))
                t1 = time.time()
                out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
                errs = validate(inst, out["best_result"].to_timetable())
                sec = round(time.time() - t1, 2)
                ev = out["evaluations"]
                rows.append({
                    "instance": inst.name,
                    "tag": feats.get("congestion_tag"),
                    "het": feats.get("target_heterogeneity"),
                    "theta": theta, "seed": s,
                    "makespan": out["best_result"].makespan,
                    "runtime_sec": sec, "evaluations": ev,
                    "ms_per_eval": round(1000.0 * sec / ev, 3) if ev else None,
                    "generations": out["generations"],
                    "stopped_by": out["stopped_by"],
                    "price_slots": out["price_slots"],
                    "budget_sec": budget, "valid": int(not errs),
                })
                print("  theta=%.2f seed=%-5d C_max=%6.1f  %5.1fs  eval=%-6d %s"
                      % (theta, s, out["best_result"].makespan, sec, ev,
                         "" if not errs else "!! 校验失败"), flush=True)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n写出 %s (%d 行,用时 %.1f min)"
          % (args.out, len(rows), (time.time() - t_all) / 60))

    # 汇总:各 theta 相对 theta=0 的配对增益(负数=更差)
    print("\n%-34s %6s %8s %8s %10s %8s" %
          ("算例", "theta", "均值", "相对0", "p", "毫秒/评价"))
    for name in dict.fromkeys(r["instance"] for r in rows):
        ref = {r["seed"]: r["makespan"] for r in rows
               if r["instance"] == name and r["theta"] == 0.0}
        for theta in args.thetas:
            cur = {r["seed"]: r["makespan"] for r in rows
                   if r["instance"] == name and r["theta"] == theta}
            common = sorted(set(ref) & set(cur))
            xs, ys = [ref[s] for s in common], [cur[s] for s in common]
            gain = mean([(x - y) / x for x, y in zip(xs, ys) if x > 0]) if xs else 0.0
            w = wilcoxon_signed_rank(xs, ys)
            mspe = mean([r["ms_per_eval"] for r in rows
                         if r["instance"] == name and r["theta"] == theta
                         and r["ms_per_eval"]])
            print("%-34s %6.2f %8.1f %+7.2f%% %10s %8.1f"
                  % (name[:34], theta, describe(ys)["mean"], 100 * gain,
                     w["p_value"], mspe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
