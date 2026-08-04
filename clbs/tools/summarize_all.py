# -*- coding: utf-8 -*-
"""全部算例的汇总账:16 个算例 x 10 种子,同挂钟口径。

单个格子只有 10 对配对,分辨不出 1~2% 的效应;把全部格子按种子配对汇总,才谈得上
"这个机制到底有没有用"。同时按拥堵档与异构度分层给出,以便看清收益随算例结构
如何变化(而不是只报一个平均数)。
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.stats import spearman, stars, wilcoxon_signed_rank  # noqa: E402

DATA = os.path.join(HERE, "experiments")
TAGS = ["low", "mid", "high", "funnel"]
BASELINES = ["twostage", "nofeedback", "opendispatch", "opendispatch_nols",
             "nostagger", "priced"]
LABEL = {"twostage": "两阶段(集成收益)", "nofeedback": "仅评估回路",
         "opendispatch": "开环派车", "opendispatch_nols": "开环派车+无局搜",
         "nostagger": "去错峰", "priced": "定价档"}


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def paired(rows, base_arm, ref_arm="closed"):
    """按 (算例, 种子) 配对,返回 [(对照档, 参照档), ...]。"""
    idx = defaultdict(dict)
    for r in rows:
        idx[(r["instance"], r["seed"])][r["arm"]] = r
    out = []
    for v in idx.values():
        if base_arm not in v or ref_arm not in v:
            continue
        out.append((float(v[base_arm]["makespan"]), float(v[ref_arm]["makespan"])))
    return out


def report(rows, title, ref_arm="closed"):
    print()
    print("### %s" % title)
    pairs_n = None
    for base in BASELINES:
        if base == ref_arm:
            continue
        pairs = paired(rows, base, ref_arm)
        if not pairs:
            continue
        xs = [a for a, _b in pairs]
        ys = [b for _a, b in pairs]
        gains = [(a - b) / a for a, b in pairs if a > 0]
        w = wilcoxon_signed_rank(xs, ys)
        pairs_n = len(pairs)
        wins = sum(1 for a, b in pairs if b < a)
        loss = sum(1 for a, b in pairs if b > a)
        print("  %-18s %+7.2f%%%-3s  n=%-4d 非平局=%-4d %3d胜/%3d负/%3d平  p=%.4g"
              % (LABEL[base], 100 * st.mean(gains), stars(w["p_value"]),
                 len(pairs), w["n_eff"], wins, loss, len(pairs) - wins - loss,
                 w["p_value"]))
    if pairs_n is None:
        print("  (无数据)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="closed",
                    help="参照档:表中所有收益均为'参照档相对该行'的改进")
    args = ap.parse_args()
    ref = args.ref

    runs = load("runs.csv")
    feats = {r["instance"]: r for r in load("instances.csv")}
    for r in runs:
        f = feats.get(r["instance"], {})
        r["tag"] = r.get("tag") or f.get("congestion_tag")
        r["het"] = r.get("het") or f.get("target_heterogeneity")

    n_inst = len({r["instance"] for r in runs})
    n_seed = len({r["seed"] for r in runs})
    print("=" * 78)
    print("全部算例汇总:%d 个算例 x %d 种子,同挂钟预算(每算例按完整方法自然用时标定)"
          % (n_inst, n_seed))
    print("正数 = 参照档(%s)更好;配对 Wilcoxon;* p<0.05 ** p<0.01 *** p<0.001" % ref)
    print("=" * 78)

    report(runs, "汇总(全部 %d 个算例)" % n_inst, ref)
    for tag in TAGS:
        sub = [r for r in runs if r["tag"] == tag]
        if sub:
            report(sub, "拥堵档 = %s" % tag, ref)

    # 集成收益随结构如何变化
    print()
    print("### 集成收益(相对两阶段)随算例结构的变化")
    print("  %-9s %-7s %8s %6s" % ("拥堵档", "H", "收益", "n"))
    xs_h, ys_g = [], []
    for tag in TAGS:
        for het in ["0.0", "0.15", "0.3", "0.5"]:
            sub = [r for r in runs
                   if r["tag"] == tag and str(float(r["het"] or 0)) == het]
            pairs = paired(sub, "twostage")
            if not pairs:
                continue
            g = st.mean([(a - b) / a for a, b in pairs if a > 0])
            print("  %-9s %-7s %+7.2f%% %6d" % (tag, het, 100 * g, len(pairs)))
            xs_h.append(float(het))
            ys_g.append(g)
    if len(xs_h) > 2:
        print("  Spearman(集成收益, H) = %.3f" % spearman(xs_h, ys_g))

    # 以两阶段为共同基准,看清哪一档才是本方法该主打的配置
    print()
    print("### 各档相对两阶段的收益(正数 = 优于两阶段)")
    idx = defaultdict(dict)
    for r in runs:
        idx[(r["instance"], r["seed"])][r["arm"]] = r
    print("  %-18s %9s %8s %s" % ("档", "收益", "p", "胜/负/平"))
    for arm in ["nofeedback", "closed", "opendispatch", "opendispatch_nols",
                "nostagger", "priced"]:
        pairs = [(float(v["twostage"]["makespan"]), float(v[arm]["makespan"]))
                 for v in idx.values() if "twostage" in v and arm in v]
        if not pairs:
            continue
        g = st.mean([(a - b) / a for a, b in pairs if a > 0])
        w = wilcoxon_signed_rank([a for a, _ in pairs], [b for _, b in pairs])
        wins = sum(1 for a, b in pairs if b < a)
        loss = sum(1 for a, b in pairs if b > a)
        print("  %-18s %+8.2f%%%-3s %7.4g  %3d/%3d/%3d"
              % (arm, 100 * g, stars(w["p_value"]), w["p_value"],
                 wins, loss, len(pairs) - wins - loss))

    print()
    print("### 每次评价的摊销成本(含该档所做的一切局部搜索)")
    cost = defaultdict(list)
    for r in runs:
        if r.get("ms_per_eval"):
            cost[r["arm"]].append(float(r["ms_per_eval"]))
    for arm in sorted(cost, key=lambda a: st.mean(cost[a])):
        print("  %-14s %7.2f 毫秒/评价" % (arm, st.mean(cost[arm])))
    if cost:
        lo = min(st.mean(v) for v in cost.values())
        hi = max(st.mean(v) for v in cost.values())
        print("  最贵/最便宜 = %.0f 倍" % (hi / lo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
