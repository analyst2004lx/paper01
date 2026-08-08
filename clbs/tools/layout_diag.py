"""布局的"改派杠杆"诊断:换一台机械臂,到底能改变多少条**会被争用**的走廊?

问题来源:哑铃布局把每台 RA 用一条专属支线挂在枢纽上,而任何一趟运输都必经
`v0 -> e_i -> h1`。于是把工序从近端臂 A 改派到近端臂 B,变动的只有那条**只有
它自己会走**的支线——争用路段一条也没换。若如此,则改派算子在原理上就无法缓解
拥堵,它能改变的只有加工时长,与路网无关。

三个量(均按走廊通行时间加权):

  私有段占比    路径中落在"只被一台 RA 使用"的走廊上的时间比例。这部分不可能
                与别的工件争用,改派动它等于没动。
  共用段占比    落在"被两台及以上 RA 共用"的走廊上的时间比例。
  改派杠杆      对每一对 RA,两条路径在**共用段**上的对称差 / 平均路径时长。
                这才是"换一台臂能改变多少争用暴露"。杠杆为 0 意味着无论换到
                哪台臂,你挤的还是同样那几条走廊。

运行(clbs/ 目录下):  py -m tools.layout_diag
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import parse_instance
from algorithm.network import Network
from algorithm.generator import build_instance, make_spec


def route_sets(net: Network, lu: str, arm_nodes: Sequence[str]
               ) -> Dict[str, Dict[str, float]]:
    """每台 RA 的 LU->RA 最短路走廊集合(走廊 -> 通行时间)。"""
    out: Dict[str, Dict[str, float]] = {}
    for node in arm_nodes:
        cids = net.shortest_path_corridors(lu, node)
        out[node] = {c: net.corridor_time[c] for c in cids}
    return out


def analyze_layout(label: str, spec_kwargs: dict) -> dict:
    spec = make_spec(**spec_kwargs)
    data = build_instance(spec)
    inst = parse_instance(data)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()

    arm_nodes = [inst.machine_node[m] for m in sorted(inst.machine_node)]
    routes = route_sets(net, inst.lu_node, arm_nodes)

    # 每条走廊被多少台 RA 的最短路使用
    mult: Dict[str, int] = {}
    for r in routes.values():
        for c in r:
            mult[c] = mult.get(c, 0) + 1
    shared = {c for c, k in mult.items() if k >= 2}

    priv_t = sum(t for r in routes.values() for c, t in r.items() if c not in shared)
    shar_t = sum(t for r in routes.values() for c, t in r.items() if c in shared)
    total_t = priv_t + shar_t

    # 改派杠杆:两两 RA 在共用段上的对称差
    leverages: List[float] = []
    nodes = list(routes)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = routes[nodes[i]], routes[nodes[j]]
            sa = {c for c in a if c in shared}
            sb = {c for c in b if c in shared}
            diff = sum(a.get(c, b.get(c, 0.0)) for c in sa ^ sb)
            base = (sum(a.values()) + sum(b.values())) / 2.0
            leverages.append(diff / base if base > 0 else 0.0)

    return {
        "label": label,
        "nodes": len(inst.nodes), "corridors": len(inst.corridors),
        "arms": len(arm_nodes),
        "priv_share": priv_t / total_t if total_t else 0.0,
        "shared_share": shar_t / total_t if total_t else 0.0,
        "leverage": sum(leverages) / len(leverages) if leverages else 0.0,
        "leverage_zero": (sum(1 for x in leverages if x < 1e-9) / len(leverages)
                          if leverages else 0.0),
        "max_mult": max(mult.values()) if mult else 0,
    }


def main() -> int:
    base = dict(heterogeneity=0.3, flexibility=0.6, ops_per_job=3, seed=42,
                num_jobs=16, tt_tp_target=3.0)
    cases = [
        ("哑铃 high M4", dict(tag="high", num_machines=4, num_agvs=4, **base)),
        ("哑铃 high M8", dict(tag="high", num_machines=8, num_agvs=12, **base)),
        ("哑铃 funnel M8", dict(tag="funnel", num_machines=8, num_agvs=12, **base)),
        ("哑铃 mid M8", dict(tag="mid", num_machines=8, num_agvs=12, **base)),
        ("网格 3x3 M8", dict(tag="low", num_machines=8, num_agvs=12,
                            grid_rows=3, grid_cols=3, **base)),
        ("网格 4x4 M8", dict(tag="low", num_machines=8, num_agvs=12,
                            grid_rows=4, grid_cols=4, **base)),
        ("网格 5x5 M8", dict(tag="low", num_machines=8, num_agvs=12,
                            grid_rows=5, grid_cols=5, **base)),
        ("网格 5x5 M12", dict(tag="low", num_machines=12, num_agvs=16,
                             grid_rows=5, grid_cols=5, **base)),
        ("错落 4x4 M8", dict(tag="scatter", num_machines=8, num_agvs=12, **base)),
        ("错落 5x5 M8", dict(tag="scatter", num_machines=8, num_agvs=12,
                            grid_rows=5, grid_cols=5, **base)),
        ("错落 5x5 M12", dict(tag="scatter", num_machines=12, num_agvs=16,
                             grid_rows=5, grid_cols=5, **base)),
    ]

    print(f"{'布局':<16s} {'点':>3s} {'边':>3s} {'臂':>3s} {'私有段':>7s} {'共用段':>7s} "
          f"{'改派杠杆':>8s} {'零杠杆对':>8s} {'最热走廊':>8s}")
    print("-" * 82)
    for label, kw in cases:
        try:
            r = analyze_layout(label, kw)
        except ValueError as e:
            print(f"{label:<16s} 跳过:{e}")
            continue
        print(f"{r['label']:<16s} {r['nodes']:>3d} {r['corridors']:>3d} {r['arms']:>3d} "
              f"{r['priv_share']:>7.0%} {r['shared_share']:>7.0%} "
              f"{r['leverage']:>8.0%} {r['leverage_zero']:>8.0%} {r['max_mult']:>6d}台")
    print("-" * 82)
    print("私有段 = 只有一台 RA 走的走廊(其上不可能与别的工件争用)占路径时间比例")
    print("改派杠杆 = 两台 RA 的路径在**共用段**上的对称差 / 平均路径时长")
    print("零杠杆对 = 改派后争用暴露完全不变的 RA 对占比;越高说明改派越无从缓解拥堵")
    print("最热走廊 = 被最多 RA 共用的那条走廊的使用台数")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
