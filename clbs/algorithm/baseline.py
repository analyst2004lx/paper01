"""对比基线(规格文档第八节):两阶段 open-loop、消融(GA 无反馈算子)、派工规则。"""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Dict, List

from .instance import Instance, OpKey
from .network import Network
from .decoder import decode
from .ga import GAConfig, run_ga, ma_min_time

# 递进式消融链的档位顺序(规格 8.1):每一档只比上一档多闭合一个环节;
# priced 是如实报告的负面对照,不属于递进链本身。
ARMS = ("rule", "twostage", "nofeedback", "opendispatch", "nostagger",
        "closed", "priced")

# 不含 GA 搜索的档位:单次解码即完成,故"同算力预算"对其无意义,报告时须单列。
NO_SEARCH_ARMS = ("rule",)


def two_stage_baseline(inst: Instance, net: Network, cfg: GAConfig,
                       log=None) -> dict:
    """规格 8.1 档 2 —— 两阶段 open-loop:
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
        # 第一阶段的停机原因要透传:同算力预算下"被预算掐停"与"自然收敛"是两种
        # 完全不同的处境,批跑脚本的预算体检靠它判断比较是否公平(规格 8.2)
        "stopped_by": stage1.get("stopped_by"),
    }


def ablation_no_feedback(inst: Instance, net: Network, cfg: GAConfig,
                         log=None) -> dict:
    """规格 8.1 档 3 —— 消融:同一闭环框架但关闭决策级反馈(局部搜索)。"""
    out = run_ga(inst, net, cfg, conflict_free=True, use_ls=False, log=log)
    out["name"] = "no_feedback"
    out["makespan"] = out["best_result"].makespan
    return out


def ablation_open_dispatch(inst: Instance, net: Network, cfg: GAConfig,
                           log=None) -> dict:
    """规格 8.1 档 4 —— 消融:派车决策回到开环(用理想最短路矩阵估算送达,不查预约表)。

    与完整版之差 = 补上"框架最后一处开环残余"所带来的增益。注意本档运行时间显著更短,
    因此论文对比必须**同算力预算**复核,不能只比同代数(规格 8.2 协议 1、13.2)。
    """
    out = run_ga(inst, net, replace(cfg, dispatch="rule"), conflict_free=True,
                 use_ls=True, log=log)
    out["name"] = "open_dispatch"
    out["makespan"] = out["best_result"].makespan
    return out


def ablation_no_stagger(inst: Instance, net: Network, cfg: GAConfig,
                        log=None) -> dict:
    """规格 8.1 档 5 —— 消融:关闭冲突凭证制导的错峰算子,只保留改派算子。

    与完整版之差 = "换时间"这一类邻域的贡献;拥堵的两条缓解路径(换地方 / 换时间)
    由此分离。
    """
    out = run_ga(inst, net, replace(cfg, use_conflict_ops=False), conflict_free=True,
                 use_ls=True, log=log)
    out["name"] = "no_stagger"
    out["makespan"] = out["best_result"].makespan
    return out


def ablation_priced(inst: Instance, net: Network, cfg: GAConfig,
                    theta: float = 0.15, log=None) -> dict:
    """规格 8.1 档 7 —— 对照(负面结果):在完整版之上开启价格加权路由。

    诊断实验显示该机制在本问题上系统性有害:走廊争用的延误已完整体现在该车自身的
    到达时刻中,再按占用收一次价格属重复计价,导致过度绕行与过度等待。保留此档是为了
    在论文中如实报告并给出机制解释,而非作为方法贡献(规格 13.2、13.3)。
    """
    out = run_ga(inst, net, replace(cfg, theta=theta), conflict_free=True,
                 use_ls=True, log=log)
    out["name"] = "priced"
    out["makespan"] = out["best_result"].makespan
    return out


def solve_arm(arm: str, inst: Instance, net: Network, cfg: GAConfig,
              theta_priced: float = 0.15, log=None) -> dict:
    """按档位名求解一次(规格 8.1 的七档)。

    七档的配置只在此处定义一次,`main.py` 与批跑脚本共用,避免两处 if/elif 漂移
    导致"同名档位、不同配置"这种最难发现的实验错误。
    """
    if arm == "closed":
        out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True, log=log)
        out["name"] = "closed"
        out["makespan"] = out["best_result"].makespan
        return out
    if arm == "twostage":
        return two_stage_baseline(inst, net, cfg, log=log)
    if arm == "nofeedback":
        return ablation_no_feedback(inst, net, cfg, log=log)
    if arm == "opendispatch":
        return ablation_open_dispatch(inst, net, cfg, log=log)
    if arm == "nostagger":
        return ablation_no_stagger(inst, net, cfg, log=log)
    if arm == "priced":
        return ablation_priced(inst, net, cfg,
                               theta=max(theta_priced, cfg.theta), log=log)
    if arm == "rule":
        return rule_baseline(inst, net)
    raise ValueError(f"未知档位 {arm};可选 {ARMS}")


def rule_baseline(inst: Instance, net: Network) -> dict:
    """规格 8.1 档 1 —— 派工规则基线:机器取最小加工时间,顺序按 SPT 贪心,闭环解码一次。"""
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
