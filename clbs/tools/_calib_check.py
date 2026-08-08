"""核对 low 与 scatter 的 makespan 差距是否只是 Tt/Tp 标定的假象。

_calibrate_tt_tp 按平均行程反向缩放加工时间以凑 Tt/Tp 目标。两种布局的平均行程
若不同,加工时间基数随之不同,直接相减 makespan 便无意义。此处打印平均行程、平均
加工时间与零成本下界,供归一化后再比。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.generator import (build_instance, make_spec, _mean_pairwise_travel)

CASES = [(4, 4, 8, 12, 16), (4, 4, 8, 16, 16), (4, 4, 12, 16, 16),
         (5, 5, 12, 16, 24), (5, 5, 8, 12, 16)]

print(f"{'配置':<20s} {'布局':<8s} {'平均行程':>8s} {'平均工时':>8s} "
      f"{'工件链':>7s} {'机器负载':>8s} {'LU割':>7s} {'下界':>7s}")
print("-" * 82)
for r, c, nm, na, j in CASES:
    for tag in ("low", "scatter"):
        spec = make_spec(tag, 0.3, 0.6, j, nm, na, 3, seed=42,
                         tt_tp_target=3.0, grid_rows=r, grid_cols=c)
        data = build_instance(spec)
        f = data["_features"]
        procs = [t for row in data["proc_time"].values() for t in row.values()]
        net = data["network"]
        mt = _mean_pairwise_travel(list(net["nodes"]), net["corridors"],
                                   net["lu_node"],
                                   [m["node"] for m in data["machines"]])
        print(f"{f'{r}x{c} M{nm} A{na} J{j}':<20s} {tag:<8s} {mt:>8.2f} "
              f"{sum(procs) / len(procs):>8.2f} {f['job_chain']:>7.1f} "
              f"{f['machine_load']:>8.1f} {f['lu_cut']:>7.1f} {f['lower_bound']:>7.1f}")
    print()
