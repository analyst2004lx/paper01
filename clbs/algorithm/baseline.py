"""对比基线(规格文档第八节):两阶段 open-loop、消融(GA 无反馈算子)、派工规则。"""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Dict, List

from .instance import Instance, OpKey
from .network import Network
from .decoder import decode
from .ga import GAConfig, run_ga, ma_min_time


def two_stage_baseline(inst: Instance, net: Network, cfg: GAConfig,
                       log=None) -> dict:
    """8.1 两阶段 open-loop:
    阶段一在退化模式(运输时间取常数 t*、无冲突约束)下运行同一 GA;
    阶段二冻结阶段一的机器指派、工序顺序与派车序列,在真实冲突模型下重放修复,
    报告修复后的真实 C_max。"""
    t0 = time.time()
    stage1 = run_ga(inst, net, cfg, conflict_free=False, use_ls=True, log=log)
    chrom = stage1["best_chrom"]
    res1 = stage1["best_result"]
    res2 = decode(inst, net, chrom["ma"], chrom["os"], conflict_free=True,
                  forced_dispatch=res1.dispatch_order)
    return {
        "name": "two_stage",
        "stage1_makespan": res1.makespan,   # 理想(低估)值,仅供参考
        "makespan": res2.makespan,          # 修复后真实值,用于论文对比
        "best_chrom": chrom,
        "best_result": res2,
        "runtime_sec": round(time.time() - t0, 2),
        "generations": stage1["generations"],
        "evaluations": stage1["evaluations"],
    }


def ablation_no_feedback(inst: Instance, net: Network, cfg: GAConfig,
                         log=None) -> dict:
    """8.2 消融:同一闭环框架但关闭拥堵反馈局部搜索。"""
    out = run_ga(inst, net, cfg, conflict_free=True, use_ls=False, log=log)
    out["name"] = "no_feedback"
    out["makespan"] = out["best_result"].makespan
    return out


def rule_baseline(inst: Instance, net: Network) -> dict:
    """8.4 派工规则基线:机器取最小加工时间,顺序按 SPT 贪心,闭环解码一次。"""
    t0 = time.time()
    ma: Dict[OpKey, int] = ma_min_time(inst)
    counts = dict(inst.os_job_counts())
    done = {j: 0 for j in inst.job_ids}
    os_seq: List[int] = []

    def next_op_time(j: int) -> float:
        i = done[j] + 1
        if inst.is_pseudo(j, i):
            return 0.0
        return inst.proc_time[(j, i)][ma[(j, i)]]

    while any(done[j] < counts[j] for j in inst.job_ids):
        candidates = [j for j in inst.job_ids if done[j] < counts[j]]
        j = min(candidates, key=lambda x: (next_op_time(x), x))
        os_seq.append(j)
        done[j] += 1

    result = decode(inst, net, ma, os_seq, conflict_free=True)
    return {
        "name": "rule_spt",
        "makespan": result.makespan,
        "best_chrom": {"ma": ma, "os": os_seq},
        "best_result": result,
        "runtime_sec": round(time.time() - t0, 2),
    }
