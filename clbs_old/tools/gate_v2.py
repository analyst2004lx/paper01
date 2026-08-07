# -*- coding: utf-8 -*-
"""邻域改进的准入测试:同代数下与"完全不做局部搜索"配对比较。

判据不是"改得比初版好",而是"终于值得做"。参照系必须是 nofeedback(只闭评估
回路、不做任何局部搜索):初版邻域在同代数、局部搜索免费的条件下相对它是
-0.28%(p=0.68,40 对),即白送算力也换不来收益。改动若不能把这个差距翻正,
再怎么调都只是在装点一个没有信号的邻域。

三项改动分开加,不叠加:先前捆绑测试一致变差,却无从判断是三项都无效,还是
其中一项有害、掩盖了另两项。逐项对照才有归因能力。

同代数(而非同挂钟)是有意为之:它把局部搜索的解码成本记为零,是对改动最宽容
的口径。这一关都过不了,同挂钟只会更差。

用法:
    py tools/gate_v2.py --gen 30 --seeds 42 7 2024 3 11
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics as st
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.generator import measure              # noqa: E402
from algorithm.ga import GAConfig, run_ga            # noqa: E402
from algorithm.instance import parse_instance        # noqa: E402
from algorithm.network import Network                # noqa: E402
from algorithm.stats import wilcoxon_signed_rank     # noqa: E402
from algorithm.validator import validate             # noqa: E402

EXT_DIR = os.path.join(HERE, "input", "ext")

# (档位名, use_ls, 邻域改进开关)
# 三项改动分开测:捆绑版一致变差,但那说明不了是哪一项有害,也说明不了另两项
# 是否其实可用。每项单独对照初版,才谈得上归因。
CONFIGS = [
    ("nofeedback", False, {}),
    ("base", True, {}),
    ("+score", True, {"ls_contention_score": True}),
    ("+stagger", True, {"ls_targeted_stagger": True}),
    ("+plateau", True, {"ls_plateau_accept": True}),
]
LS_ARMS = [c[0] for c in CONFIGS if c[1]]


def discover(tags, het):
    found = []
    for path in sorted(glob.glob(os.path.join(EXT_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        feat = data.get("_features") or measure(data)
        h = feat.get("target_heterogeneity")
        if feat.get("congestion_tag") not in tags:
            continue
        if h is None or not any(abs(h - t) < 1e-9 for t in het):
            continue
        found.append((data.get("name", os.path.basename(path)), data))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, default=30)
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[42, 7, 2024, 3, 11])
    ap.add_argument("--tags", nargs="+", default=["high", "funnel"])
    ap.add_argument("--het", type=float, nargs="+", default=[0.0, 0.3])
    ap.add_argument("--out", default=os.path.join(HERE, "output", "gate_v2.json"))
    args = ap.parse_args()

    found = discover(args.tags, args.het)
    if not found:
        print("没有匹配的算例", flush=True)
        return 1

    total = len(found) * len(args.seeds) * len(CONFIGS)
    print(f"共 {total} 次运行:{len(found)} 算例 x {len(args.seeds)} 种子 "
          f"x {len(CONFIGS)} 档,{args.gen} 代 x {args.pop} 种群", flush=True)

    rows = []
    t0 = time.time()
    done = 0
    for name, data in found:
        inst = parse_instance(data)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        for seed in args.seeds:
            for label, use_ls, flags in CONFIGS:
                cfg = GAConfig(pop=args.pop, max_gen=args.gen,
                               stall_gen=10 ** 9, seed=seed, **flags)
                out = run_ga(inst, net, cfg, conflict_free=True, use_ls=use_ls)
                res = out["best_result"]
                errs = validate(inst, res.to_timetable())
                ok = not errs
                stt = out["ls_stats"]
                rows.append({
                    "instance": name, "seed": seed, "arm": label,
                    "makespan": res.makespan,
                    "evaluations": out["evaluations"],
                    "ls_evaluations": out["ls_evaluations"],
                    "decodes": out["decodes"],
                    "runtime_sec": out["runtime_sec"],
                    "valid": bool(ok), "errors": [] if ok else errs[:3],
                    "ls_stats": stt,
                })
                done += 1
                eta = (time.time() - t0) / done * (total - done) / 60.0
                print(f"  [{done}/{total}] {name:32s} seed={seed:<5d} "
                      f"{label:11s} C_max={res.makespan:6.1f} "
                      f"{out['runtime_sec']:6.1f}s "
                      f"{'' if ok else '校验失败!'} ETA {eta:.1f}min", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    bad = [r for r in rows if not r["valid"]]
    print()
    print("=" * 78)
    print(f"校验失败 {len(bad)} 次")

    by = defaultdict(dict)
    for r in rows:
        by[(r["instance"], r["seed"])][r["arm"]] = r["makespan"]

    def compare(ref: str, label: str) -> None:
        pairs = [(v[ref], v[label]) for v in by.values()
                 if ref in v and label in v]
        if not pairs:
            return
        nz = [1 for a, b in pairs if a != b]
        p = wilcoxon_signed_rank([a for a, b in pairs],
                                 [b for a, b in pairs])["p_value"] if nz else 1.0
        wins = sum(1 for a, b in pairs if b < a)
        loss = sum(1 for a, b in pairs if b > a)
        print(f"  {label:10s} vs {ref:10s} 平均 "
              f"{st.mean([(a - b) / a for a, b in pairs]):+.2%}  "
              f"{wins} 胜 / {loss} 负 / {len(pairs) - wins - loss} 平  "
              f"n={len(pairs)}  p={p:.4f}")

    print()
    print("=== 对照'完全不做局部搜索'(同代数,局部搜索的解码不计入预算) ===")
    for label in LS_ARMS:
        compare("nofeedback", label)
    print()
    print("=== 各项改动相对初版邻域 ===")
    for label in LS_ARMS[1:]:
        compare("base", label)

    print()
    print("=== 算子命中率 ===")
    agg = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for k, v in r["ls_stats"].items():
            agg[r["arm"]][k] += v
    for label in LS_ARMS:
        a = agg[label]
        tried = a["reassign_tried"] + a["stagger_tried"]
        hit = a["reassign_hit"] + a["stagger_hit"]
        print(f"  {label:10s} 改派 {a['reassign_hit']:.0f}/{a['reassign_tried']:.0f}"
              f" = {a['reassign_hit'] / max(1.0, a['reassign_tried']):.1%};"
              f" 错峰 {a['stagger_hit']:.0f}/{a['stagger_tried']:.0f}"
              f" = {a['stagger_hit'] / max(1.0, a['stagger_tried']):.1%};"
              f" 合计 {hit / max(1.0, tried):.1%};"
              f" 平台横移 {a['plateau_hit']:.0f}")

    print()
    print("判读:任一档相对 nofeedback 若仍不显著为正,则决策回路在本问题上确实"
          "不成立——同代数已是对它最宽容的口径,连白送算力都换不来收益。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
