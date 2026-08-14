"""SLID 一键运行入口:载入日志 -> 拟合 -> 注入攻击 -> 检测 -> 写结果。

用法示例(在 paper02/slid/ 目录下):
    py main.py                                        # input/ 下全部场景,默认配置
    py main.py --dataset ft_trier --attack A2 --rho 0.15
    py main.py --arm ablation                         # 完整递进消融链
    py main.py --arm baselines --alpha 0.01
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

from algorithm import (attacks, baselines, fusion, ingest, metrics,
                       procmodel)
from algorithm.detector import Detector, DetectorConfig

HERE = os.path.dirname(os.path.abspath(__file__))

DATASETS = ("ft_trier", "hai", "sim")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="SLID - Scheduling-Layer Injection Detection")
    ap.add_argument("--dataset", default="ft_trier", choices=DATASETS)
    ap.add_argument("--arm", default="full",
                    choices=("full", "ablation", "baselines"),
                    help="full = 只跑本文方法;ablation = 递进消融链;baselines = 对照方法")
    ap.add_argument("--attack", default="A3", choices=attacks.Family.__args__,
                    help="注入攻击族,编号以 新想法.md 覆盖矩阵为准;"
                         f"当前已实现 {attacks.IMPLEMENTED}")
    ap.add_argument("--rho", type=float, default=0.15,
                    help="抢跑/拖延幅度;--sweep 时忽略")
    ap.add_argument("--sweep", action="store_true", help="扫 rho 出检出率曲线")
    ap.add_argument("--knowledge", default="blackbox",
                    choices=("blackbox", "model", "model+threshold"))
    ap.add_argument("--alpha", type=float, default=0.01,
                    help="名义误报水平;须满足 alpha >= 1/(n_calib+1),否则报告会标注不可达")
    ap.add_argument("--arl0", type=int, default=1000)
    ap.add_argument("--delay-budget", type=int, nargs="+", default=[1, 3, 10, 30],
                    help="检测延迟预算(消息数),逐个报告检出率")
    ap.add_argument("--fusion", default="fisher", choices=fusion.METHODS,
                    help="默认 fisher:三通道实测近似独立,且多通道攻击下"
                         "功效最高。相关度超 0.15 应退回 simes")
    ap.add_argument("--temporal", action="store_true", default=True,
                    help="按时间序划分(唯一可部署的口径,默认开)")
    ap.add_argument("--random-split", dest="temporal", action="store_false",
                    help="改随机折划分,仅用于与既有批处理结果对照")
    ap.add_argument("--sequential", default="cusum", choices=("cusum", "eproc"))
    ap.add_argument("--two-sided", action="store_true",
                    help="时序通道改双侧(对照用;抢跑攻击下会损失约一半功效)")
    ap.add_argument("--no-online-update", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", default=None, help="输出子目录名,缺省按参数自动生成")
    return ap.parse_args()


def load(dataset: str):
    root = os.path.join(HERE, "input", dataset)
    if dataset == "ft_trier":
        path = os.path.join(root, "MainProcess_cleaned.xes")
        if not os.path.exists(path):
            path = ingest.default_log_path()
        raw = ingest.read_xes(path)
        log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
        model = procmodel.load_bpmn(procmodel.default_bpmn_glob(),
                                    log_positions=log_pos)
        return ingest.valid(raw, drop_failure=True), model
    if dataset == "hai":
        return ingest.read_hai(root), None
    return ingest.read_xes(os.path.join(root, "scenario.xes")), None


def _split_cases(acts, seed: int, temporal: bool):
    """**按 case 划分,不能按活动划分**——后者会让同一 case 的前后活动
    分落训练与测试,结构通道与令牌状态都会跨界泄漏。"""
    by_case = {}
    for a in acts:
        by_case.setdefault(a.case, []).append(a)
    keys = sorted(by_case, key=lambda k: min(
        (x.t_consume for x in by_case[k] if x.t_consume is not None),
        default=None) or 0)
    if not temporal:
        import random
        random.Random(seed).shuffle(keys)
    cut = int(len(keys) * 0.75)
    return ([a for k in keys[:cut] for a in by_case[k]],
            [a for k in keys[cut:] for a in by_case[k]])


def run_one(acts, model, args: argparse.Namespace) -> dict:
    cfg = DetectorConfig(alpha=args.alpha, arl0=args.arl0, fusion=args.fusion,
                         sequential=args.sequential,
                         one_sided_timing=not args.two_sided,
                         online_update=not args.no_online_update)
    cfg.delay_budget = tuple(args.delay_budget)
    rng = np.random.default_rng(args.seed)
    fit_acts, test = _split_cases(acts, args.seed, args.temporal)

    det = Detector(cfg).fit(fit_acts, model=model, rng=rng,
                            temporal=args.temporal)
    spec = attacks.AttackSpec(family=args.attack, rho=args.rho,
                              knowledge=args.knowledge, seed=args.seed)
    poisoned, labels = attacks.inject(test, spec)
    order = sorted(range(len(poisoned)),
                   key=lambda i: (poisoned[i].t_consume, poisoned[i].order))
    stream = [poisoned[i] for i in order]
    labels = [labels[i] for i in order]

    t0 = time.perf_counter()
    alarms = det.replay(stream, rng=rng)
    us = (time.perf_counter() - t0) * 1e6 / max(len(stream), 1)
    rep = metrics.evaluate(alarms, labels, cfg, stream=stream,
                           n_calib=det.cals["time"].n if det.cals else 0,
                           latency_us=us)
    return {"config": vars(args), "report": rep.__dict__,
            "n_alarms": len(alarms), "attack_zh": attacks.FAMILY_ZH[args.attack]}


def main() -> int:
    args = parse_args()
    acts, model = load(args.dataset)
    print(f"===== 数据集 {args.dataset}: {len(acts)} 个活动实例, "
          f"{'时间序' if args.temporal else '随机折'}划分 =====")

    t0 = time.time()
    results: dict = {}
    if args.arm == "full":
        results["full"] = run_one(acts, model, args)
    elif args.arm == "ablation":
        for arm in baselines.ABLATIONS:
            print(f"\n-- 消融档 {arm} --")
            results[arm] = baselines.run_ablation(arm, acts, args)
    else:
        for name in baselines.BASELINES:
            print(f"\n-- 基线 {name} --")
            results[name] = baselines.run_baseline(name, acts, args)

    tag = args.tag or f"{args.dataset}-{args.arm}-{args.attack}-a{args.alpha}-s{args.seed}"
    out_dir = os.path.join(HERE, "output", tag)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n===== 汇总(耗时 {time.time()-t0:.1f}s) =====")
    for name, r in results.items():
        rep = r["report"]
        dr = rep["dr_by_delay"]
        print(f"  {name:<16s} DR@1={dr.get(1, float('nan')):.3f} "
              f"DR@10={dr.get(10, float('nan')):.3f} "
              f"FPR={rep['fpr']:.4f}(名义 {rep['alpha_nominal']}, "
              f"n_calib={rep['n_calib']})")
        print(f"  {'':<16s} 逐消息时延 {rep['per_message_latency_us']:.1f} us,"
              f" 检测延迟 p50={rep['detection_delay_p50']}"
              f" p95={rep['detection_delay_p95']} 条消息")
    print(f"  结果已写入 {os.path.relpath(out_dir, HERE)}{os.sep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
