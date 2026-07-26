"""算例数据模型与载入(规格文档 3.1 / 建模文档 H 节)。"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

OpKey = Tuple[int, int]  # (job, op_index),op_index 从 1 起


@dataclass
class Instance:
    name: str
    delta_return: int                       # 1=成品回运计入 makespan;0=不回运变体
    job_ids: List[int]
    num_ops: Dict[int, int]                 # job -> 实工序数 n(j)
    machine_node: Dict[int, str]            # machine -> 取放节点
    proc_time: Dict[OpKey, Dict[int, float]]  # (j,i) -> {m: t^P},缺失即不在 Ω 内
    num_agvs: int
    lu_node: str
    nodes: List[str]
    corridors: List[dict]                   # {u, v, time}

    # ---- 派生量 ----
    def eligible(self, j: int, i: int) -> List[int]:
        """工序 O_ji 的可用机器集合 Ω_ji。"""
        return sorted(self.proc_time[(j, i)].keys())

    def real_ops(self) -> List[OpKey]:
        return [(j, i) for j in self.job_ids for i in range(1, self.num_ops[j] + 1)]

    def os_job_counts(self) -> Dict[int, int]:
        """OS 段中每个工件出现的次数(δ_return=1 时含回运伪工序,规格 6.1)。"""
        extra = 1 if self.delta_return else 0
        return {j: self.num_ops[j] + extra for j in self.job_ids}

    def is_pseudo(self, j: int, i: int) -> bool:
        return i == self.num_ops[j] + 1

    @property
    def num_machines(self) -> int:
        return len(self.machine_node)


def load_instance(path: str) -> Instance:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_instance(data)


def parse_instance(data: dict) -> Instance:
    proc: Dict[OpKey, Dict[int, float]] = {}
    for key, row in data["proc_time"].items():
        m = re.match(r"\((\d+)\s*,\s*(\d+)\)", key)
        if not m:
            raise ValueError(f"非法工序键: {key}")
        j, i = int(m.group(1)), int(m.group(2))
        proc[(j, i)] = {int(mm): float(t) for mm, t in row.items()}

    num_ops = {job["id"]: job["num_ops"] for job in data["jobs"]}
    for j, n in num_ops.items():
        for i in range(1, n + 1):
            if (j, i) not in proc:
                raise ValueError(f"缺少工序 ({j},{i}) 的加工时间")
            if not proc[(j, i)]:
                raise ValueError(f"工序 ({j},{i}) 的 Ω 为空")

    net = data["network"]
    return Instance(
        name=data.get("name", "unnamed"),
        delta_return=int(data.get("delta_return", 1)),
        job_ids=sorted(num_ops.keys()),
        num_ops=num_ops,
        machine_node={mac["id"]: mac["node"] for mac in data["machines"]},
        proc_time=proc,
        num_agvs=int(data["num_agvs"]),
        lu_node=net["lu_node"],
        nodes=list(net["nodes"]),
        corridors=list(net["corridors"]),
    )


def feature_params(inst: Instance, ideal_dist: Dict[str, Dict[str, float]]) -> dict:
    """实例特征参数(建模文档 H 五节):T̄t/T̄p、异构度、柔性度、NA/NM。"""
    # 平均加工时间(全部行内非空项)
    all_times = [t for row in inst.proc_time.values() for t in row.values()]
    tp_bar = sum(all_times) / len(all_times)

    # 取放点(机器节点 + LU)两两平均最短路时间
    points = sorted(set(inst.machine_node.values()) | {inst.lu_node})
    dists = [ideal_dist[a][b] for a in points for b in points if a != b]
    tt_bar = sum(dists) / len(dists) if dists else 0.0

    # 异构度:各行(工序)非空项变异系数的平均值
    cvs = []
    for row in inst.proc_time.values():
        vals = list(row.values())
        if len(vals) >= 2:
            mean = sum(vals) / len(vals)
            std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
            cvs.append(std / mean if mean > 0 else 0.0)
        else:
            cvs.append(0.0)
    heterogeneity = sum(cvs) / len(cvs)

    # 柔性度:平均 |Ω| / NM
    flex = sum(len(row) for row in inst.proc_time.values()) / len(inst.proc_time) / inst.num_machines

    return {
        "Tt_over_Tp": round(tt_bar / tp_bar, 4) if tp_bar > 0 else None,
        "heterogeneity": round(heterogeneity, 4),
        "flexibility": round(flex, 4),
        "NA_over_NM": round(inst.num_agvs / inst.num_machines, 4),
        "num_jobs": len(inst.job_ids),
        "num_machines": inst.num_machines,
        "num_agvs": inst.num_agvs,
        "num_real_ops": len(inst.real_ops()),
        "num_nodes": len(inst.nodes),
        "num_corridors": len(inst.corridors),
    }
