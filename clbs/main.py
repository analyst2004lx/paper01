"""CLBS 一键运行入口:载入算例 -> 求解(闭环/两阶段/规则)-> 独立校验 -> 写结果。

用法示例(在 clbs/ 目录下):
    py main.py                                       # input/ 全部算例,三种模式
    py main.py --instance input/example_3x3x2.json   # 指定算例
    py main.py --mode closed --seed 7 --pop 100 --gen 200
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

from algorithm.instance import load_instance, feature_params
from algorithm.network import Network
from algorithm.ga import GAConfig, run_ga
from algorithm.baseline import (two_stage_baseline, rule_baseline,
                                ablation_no_feedback, ablation_open_dispatch,
                                ablation_no_stagger, ablation_priced)
from algorithm.pricing import default_bucket_width
from algorithm.validator import validate
from algorithm.report import gantt_text, occupancy_profile, summary_line

HERE = os.path.dirname(os.path.abspath(__file__))

# 递进式消融链(论文骨架):每一档只比上一档多闭合一个环节;
# priced 一档是如实报告的负面对照,不属于递进链的一部分。
ABLATION_MODES = ["rule", "twostage", "nofeedback", "opendispatch",
                  "nostagger", "closed", "priced"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="CLBS - Closed-Loop Bilevel Scheduler")
    ap.add_argument("--instance", default=None,
                    help="算例 JSON 路径;缺省跑 input/ 下全部 *.json")
    ap.add_argument("--mode", default="both",
                    choices=["closed", "twostage", "rule", "nofeedback", "opendispatch",
                             "nostagger", "priced", "both", "ablation"],
                    help="求解模式(both = 闭环/两阶段/规则;ablation = 完整递进消融链)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pop", type=int, default=100, help="GA 种群规模")
    ap.add_argument("--gen", type=int, default=200, help="GA 最大代数")
    ap.add_argument("--stall", type=int, default=30, help="GA 早停代数")
    ap.add_argument("--theta", type=float, default=0.0,
                    help="价格协调强度(无量纲);默认 0,诊断显示 >0 有害")
    ap.add_argument("--dispatch", default="exact", choices=["rule", "exact"],
                    help="派车决策:exact = 查预约表试探(闭环);rule = 理想最短路估算(开环)")
    ap.add_argument("--entry-options", type=int, default=3,
                    help="多标签路由每条弧考察的进入时刻数;1 = 只考虑最早到达")
    ap.add_argument("--fd-calibrate", action="store_true",
                    help="用有限差分定义式价格校准代理价(代价高,报告价格一致性用)")
    return ap.parse_args()


def solve_one(path: str, args: argparse.Namespace) -> dict:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    features = feature_params(inst, net.ideal_dist, net)
    cfg = GAConfig(pop=args.pop, max_gen=args.gen, stall_gen=args.stall, seed=args.seed,
                   theta=args.theta, max_entry_options=args.entry_options,
                   fd_calibrate=args.fd_calibrate, dispatch=args.dispatch)

    print(f"\n===== 算例 {inst.name}  "
          f"({features['num_jobs']} 工件 / {features['num_machines']} RA / "
          f"{features['num_agvs']} AGV, delta_return={inst.delta_return}) =====")
    print(f"  特征: Tt/Tp={features['Tt_over_Tp']}, 异构度={features['heterogeneity']}, "
          f"柔性度={features['flexibility']}")

    if args.mode == "both":
        modes = ["closed", "twostage", "rule"]
    elif args.mode == "ablation":
        modes = list(ABLATION_MODES)
    else:
        modes = [args.mode]
    results: dict = {}

    for mode in modes:
        print(f"\n-- 模式 {mode} --")
        if mode == "closed":
            out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True, log=print)
            out["makespan"] = out["best_result"].makespan
        elif mode == "twostage":
            out = two_stage_baseline(inst, net, cfg, log=print)
        elif mode == "nofeedback":
            out = ablation_no_feedback(inst, net, cfg, log=print)
        elif mode == "opendispatch":
            out = ablation_open_dispatch(inst, net, cfg, log=print)
        elif mode == "nostagger":
            out = ablation_no_stagger(inst, net, cfg, log=print)
        elif mode == "priced":
            out = ablation_priced(inst, net, cfg, theta=max(0.15, args.theta), log=print)
        else:
            out = rule_baseline(inst, net)

        timetable = out["best_result"].to_timetable()
        errors = validate(inst, timetable)
        out["valid"] = not errors
        if errors:
            print(f"  !! 校验失败({len(errors)} 条):")
            for e in errors[:10]:
                print(f"     {e}")
        results[mode] = {"out": out, "timetable": timetable, "errors": errors}
        print(summary_line(mode, out) + ("  [校验通过]" if not errors else "  [校验失败]"))

    # ---- 落盘 ----
    out_dir = os.path.join(HERE, "output", inst.name)
    os.makedirs(out_dir, exist_ok=True)
    bucket_w = default_bucket_width(inst)   # rule/twostage 档没有 GA 给的桶宽,用默认值
    summary = {
        "instance": inst.name,
        "delta_return": inst.delta_return,
        "features": features,
        "ga_config": {"pop": cfg.pop, "max_gen": cfg.max_gen,
                      "stall_gen": cfg.stall_gen, "seed": cfg.seed,
                      "theta": cfg.theta, "max_entry_options": cfg.max_entry_options,
                      "price_top_k": cfg.price_top_k,
                      "price_refresh": cfg.price_refresh,
                      "fd_calibrate": cfg.fd_calibrate,
                      "dispatch": cfg.dispatch,
                      "use_conflict_ops": cfg.use_conflict_ops},
        "results": {},
    }
    for mode, r in results.items():
        o = r["out"]
        entry = {
            "makespan": o["makespan"],
            "runtime_sec": o.get("runtime_sec"),
            "valid": o["valid"],
            "validation_errors": r["errors"],
        }
        if "stage1_makespan" in o:
            entry["stage1_ideal_makespan"] = o["stage1_makespan"]
        for key in ("bucket_width", "price_slots", "price_agreement", "price_cost_total"):
            if o.get(key) is not None:
                entry[key] = o[key]
        if "history" in o:
            entry["generations"] = o["generations"]
            entry["evaluations"] = o["evaluations"]
            entry["convergence_history"] = o["history"]
        # 占用率画像:只对该模式的**最终最优解**算一次(报告用,不参与搜索)
        prof = occupancy_profile(r["timetable"], o.get("bucket_width") or bucket_w)
        if prof is not None:
            entry["occupancy"] = prof
        summary["results"][mode] = entry

        with open(os.path.join(out_dir, f"timetable_{mode}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(r["timetable"], f, ensure_ascii=False, indent=2)
        g = gantt_text(inst, r["timetable"])
        if g is not None:
            with open(os.path.join(out_dir, f"gantt_{mode}.txt"), "w",
                      encoding="utf-8") as f:
                f.write(g + "\n")

    if "closed" in results and "twostage" in results:
        c = results["closed"]["out"]["makespan"]
        t = results["twostage"]["out"]["makespan"]
        summary["improvement_closed_vs_twostage"] = round((t - c) / t, 4) if t > 0 else None

    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    ref = summary["results"].get("closed") or next(iter(summary["results"].values()))
    prof = ref.get("occupancy")
    if prof and prof.get("bottleneck_corridor"):
        cid = prof["bottleneck_corridor"]
        st = prof["by_corridor"][cid]
        print(f"\n  瓶颈走廊 {cid}: 平均占用 {st['mean']:.2f}, 峰值 {st['peak']:.2f} "
              f"(桶宽 {prof['bucket_width']:.1f}, 共 {prof['num_buckets']} 桶)")
    print(f"  结果已写入 {os.path.relpath(out_dir, HERE)}{os.sep}")
    return summary


def main() -> int:
    args = parse_args()
    if args.instance:
        paths = [args.instance]
    else:
        paths = sorted(glob.glob(os.path.join(HERE, "input", "*.json")))
    if not paths:
        print("input/ 下没有算例 JSON,退出。")
        return 1

    t0 = time.time()
    summaries = [solve_one(p, args) for p in paths]

    print(f"\n===== 汇总({len(summaries)} 个算例, 总耗时 {time.time()-t0:.1f}s) =====")
    for s in summaries:
        parts = [f"{m}: {r['makespan']:.1f}{'' if r['valid'] else ' [校验失败!]'}"
                 for m, r in s["results"].items()]
        imp = s.get("improvement_closed_vs_twostage")
        if imp is not None:
            parts.append(f"闭环改进 {imp*100:.1f}%")
        print(f"  {s['instance']:<24s} " + " | ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
