"""价格协调的诊断扫描:theta x 进入时刻选项数 x 价格估计器。

用途:回答"价格化层间接口是否真的带来增益,以及增益来自哪一部分"。
运行(clbs/ 目录下):  py -m tools.sweep_price [算例路径]
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import load_instance, feature_params
from algorithm.network import Network
from algorithm.ga import GAConfig, run_ga
from algorithm.validator import validate

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(HERE, "input", "congested_8x4x4.json")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    feat = feature_params(inst, net.ideal_dist)
    print(f"算例 {inst.name}: Tt/Tp={feat['Tt_over_Tp']}, 异构度={feat['heterogeneity']}, "
          f"柔性度={feat['flexibility']}, NA/NM={feat['NA_over_NM']}")

    base = GAConfig(pop=60, max_gen=120, stall_gen=30, seed=42)
    seeds = [42, 7, 2024]

    # 机制分解:先在 theta=0(不用价格)下逐一开关与价格无关的两个机制;
    # 派车试探显著更慢,故对开环派车档额外给出**同算力预算**的复核档(A'、B'),
    # 否则"闭环派车更好"这一结论无法排除"只是多花了算力"这个平凡解释。
    configs = [
        ("A 规则派车+无错峰", dict(theta=0.0, use_conflict_ops=False, dispatch="rule")),
        ("B A+错峰算子", dict(theta=0.0, use_conflict_ops=True, dispatch="rule")),
        ("A' A 同算力(放宽早停)", dict(theta=0.0, use_conflict_ops=False, dispatch="rule",
                                 max_gen=600, stall_gen=200)),
        ("B' B 同算力(放宽早停)", dict(theta=0.0, use_conflict_ops=True, dispatch="rule",
                                 max_gen=600, stall_gen=200)),
        ("C A+派车试探", dict(theta=0.0, use_conflict_ops=False, dispatch="exact")),
        ("D C+错峰算子(完整版)", dict(theta=0.0, use_conflict_ops=True, dispatch="exact")),
        ("E D+价格 theta=0.15", dict(theta=0.15, use_conflict_ops=True,
                                     dispatch="exact", max_entry_options=1)),
    ]

    print(f"\n{'配置':<24s} {'均值':>6s} {'最好':>6s} {'最差':>6s} {'秒/次':>7s} {'评估数':>8s}  各种子")
    print("-" * 84)
    for label, kw in configs:
        vals, secs, evals = [], [], []
        for s in seeds:
            cfg = replace(base, seed=s, **kw)
            out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
            errs = validate(inst, out["best_result"].to_timetable())
            assert not errs, f"{label} seed={s} 校验失败: {errs[:2]}"
            vals.append(out["best_result"].makespan)
            secs.append(out["runtime_sec"])
            evals.append(out["evaluations"])
        print(f"{label:<24s} {sum(vals)/len(vals):>6.1f} {min(vals):>6.1f} {max(vals):>6.1f} "
              f"{sum(secs)/len(secs):>7.1f} {sum(evals)//len(evals):>8d}  {[round(v,1) for v in vals]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
