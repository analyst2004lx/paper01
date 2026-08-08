# -*- coding: utf-8 -*-
"""论文用的消融表:每一项机制都由"只差这一个因素"的一对档位归因。

七个档位里两两相减大多同时差着两个以上因素,直接相减得出的数会连符号都不对
(精确派车即为一例:混淆的对比给 +0.83%/p=0.046,去混淆后为 -0.93%/p=0.046)。
本脚本只列可归因的配对,并对同一项机制在不同上下文里给出的独立估计做交叉核对——
两个估计一致,该项的结论才算稳。

档位的因素分解(全部在同挂钟预算下,均含无冲突路由与真实 makespan 适应度):
                     派车方式   局部搜索   错峰算子   价格路由
  opendispatch_nols   规则       关         -          关
  opendispatch        规则       开         开         关
  nofeedback          精确       关         -          关
  nostagger           精确       开         关         关
  closed              精确       开         开         关
  priced              精确       开         开         开
"""
from __future__ import annotations

import csv
import os
import statistics as st
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.stats import stars, wilcoxon_signed_rank  # noqa: E402

# (机制, 上下文, 关掉该机制的档, 开着该机制的档)
# 正数 = 开着该机制更好,即该机制在同挂钟下挣回了自己的成本
CONTRASTS = [
    ("真实目标(无冲突路由进评估回路)", "廉价派车", "twostage", "opendispatch_nols"),
    ("真实目标(无冲突路由进评估回路)", "精确派车", "twostage", "nofeedback"),
    ("精确派车(查预约表)", "无局部搜索", "opendispatch_nols", "nofeedback"),
    ("精确派车(查预约表)", "有局部搜索", "opendispatch", "closed"),
    ("争用制导局部搜索", "规则派车", "opendispatch_nols", "opendispatch"),
    ("争用制导局部搜索", "精确派车", "nofeedback", "closed"),
    ("错峰算子(在改派之上)", "精确派车", "nostagger", "closed"),
    ("价格路由", "完整方法之上", "closed", "priced"),
]


def main() -> int:
    path = os.path.join(HERE, "experiments", "runs.csv")
    with open(path, encoding="utf-8") as f:
        runs = list(csv.DictReader(f))

    idx = defaultdict(dict)
    for r in runs:
        idx[(r["instance"], r["seed"])][r["arm"]] = r
    cost = defaultdict(list)
    for r in runs:
        if r.get("ms_per_eval"):
            cost[r["arm"]].append(float(r["ms_per_eval"]))

    print("=" * 96)
    print("消融表:每行只差一个因素。正数 = 该机制在同挂钟预算下挣回了自己的成本")
    print("* p<0.05  ** p<0.01  *** p<0.001;配对 Wilcoxon,16 算例 x 10 种子")
    print("=" * 96)
    print("  %-30s %-12s %9s %-4s %8s %14s %10s"
          % ("机制", "上下文", "收益", "", "p", "胜/负/平", "成本倍数"))

    prev = None
    for mech, ctx, off, on in CONTRASTS:
        pairs = [(float(v[off]["makespan"]), float(v[on]["makespan"]))
                 for v in idx.values() if off in v and on in v]
        if not pairs:
            continue
        g = st.mean([(a - b) / a for a, b in pairs if a > 0])
        w = wilcoxon_signed_rank([a for a, _ in pairs], [b for _, b in pairs])
        wins = sum(1 for a, b in pairs if b < a)
        loss = sum(1 for a, b in pairs if b > a)
        c_off = st.mean(cost[off]) if cost.get(off) else 0.0
        c_on = st.mean(cost[on]) if cost.get(on) else 0.0
        ratio = (c_on / c_off) if c_off > 0 else float("nan")
        if prev is not None and prev != mech:
            print()
        prev = mech
        print("  %-30s %-12s %+8.2f%% %-4s %8.4g %5d/%3d/%3d %9.1fx"
              % (mech, ctx, 100 * g, stars(w["p_value"]), w["p_value"],
                 wins, loss, len(pairs) - wins - loss, ratio))

    print()
    print("交叉核对:同一项机制在两个上下文里的估计若一致,结论才算稳;若符号相反,"
          "说明该项与上下文交互,不能给单一结论。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
