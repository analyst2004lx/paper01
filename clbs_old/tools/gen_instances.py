"""生成规格 12.3 的受控扩展算例(拥堵度 × 异构度双因子矩阵)。

用法(clbs/ 目录下):

    py -m tools.gen_instances                       # 默认矩阵写入 input/ext/
    py -m tools.gen_instances --list                # 只列特征表,不落盘
    py -m tools.gen_instances --seeds 42 7 2024     # 每格多个种子
    py -m tools.gen_instances --jobs 10 --machines 5 --agvs 4 --ops 3

实验矩阵的设计要点(与规格 12.3、13.6 一致):

1. **拥堵度四档**(low / mid / high / funnel)只改路网**容量结构**,T̄t/T̄p 被
   统一标定到同一目标值,故各档之间"运输强度"不变、变的只有网络结构;
2. **`high` 与 `funnel` 是一组受控对比**:两者加工时间、机器位置、T̄t/T̄p 逐字段
   相同,唯一差别是 LU 出口容量(2 条 vs 1 条)。funnel 档多出来的那部分拥堵
   **与机器指派无关**(每个工件的首道送达与成品回运都必经),因此若各反馈机制
   只在 high 上显示增益、在 funnel 上消失,即直接证明"决策无关拥堵稀释机制
   信号"这一诊断;
3. **异构度 H=0 是回归档**:同一工序在各机耗时相同,改派机制应自动失效,可用于
   检验"收益随异构度增长"的使能关系(F2)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.generator import (CONGESTION_PRESETS, build_instance, make_spec,
                                 measure)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "input", "ext")

TAGS = ["low", "mid", "high", "funnel"]
HETEROGENEITIES = [0.0, 0.15, 0.3, 0.5]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="受控扩展算例生成器(规格 12.3)")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--machines", type=int, default=4)
    ap.add_argument("--agvs", type=int, default=4)
    ap.add_argument("--ops", type=int, default=3, help="每工件工序数")
    ap.add_argument("--flex", type=float, default=0.6, help="柔性度 F = 平均|Ω|/NM")
    ap.add_argument("--tt-tp", type=float, default=1.0,
                    help="T̄t/T̄p 标定目标;<=0 表示不标定")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42],
                    help="每个格子的随机种子(多个则每格生成多个算例)")
    ap.add_argument("--tags", nargs="+", default=TAGS,
                    choices=sorted(CONGESTION_PRESETS), help="拥堵度档位")
    ap.add_argument("--het", type=float, nargs="+", default=HETEROGENEITIES,
                    help="异构度 H 取值")
    ap.add_argument("--out", default=OUT_DIR, help="输出目录")
    ap.add_argument("--list", action="store_true", help="只打印特征表,不写文件")
    return ap.parse_args()


_COLS = ("算例", "档位", "H目标", "H实测", "F实测", "Tt/Tp",
         "LU割", "远端割", "漏斗占比", "下界")


def _row(name: str, f: dict) -> tuple:
    return (name, f["congestion_tag"], f["target_heterogeneity"], f["heterogeneity"],
            f["flexibility"], f["Tt_over_Tp"], f["lu_min_cut"], f["far_group_cut"],
            f["funnel_share"], f["lower_bound"])


def main() -> int:
    args = parse_args()
    rows = []
    written = 0
    if not args.list:
        os.makedirs(args.out, exist_ok=True)

    for tag in args.tags:
        for h in args.het:
            for seed in args.seeds:
                spec = make_spec(tag, heterogeneity=h, flexibility=args.flex,
                                 num_jobs=args.jobs, num_machines=args.machines,
                                 num_agvs=args.agvs, ops_per_job=args.ops,
                                 seed=seed,
                                 tt_tp_target=args.tt_tp if args.tt_tp > 0 else None)
                data = build_instance(spec)
                feat = measure(data)
                rows.append(_row(data["name"], feat))
                if not args.list:
                    path = os.path.join(args.out, f"{data['name']}.json")
                    with open(path, "w", encoding="utf-8") as fp:
                        json.dump(data, fp, ensure_ascii=False, indent=2)
                    written += 1

    widths = [max(len(str(r[i])) for r in [_COLS] + rows) for i in range(len(_COLS))]
    line = "  ".join(str(c).ljust(w) for c, w in zip(_COLS, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))

    print(f"\n共 {len(rows)} 个算例"
          + (f",已写入 {os.path.relpath(args.out, HERE)}{os.sep}" if written
             else "(--list 模式,未落盘)"))
    print("\n提示:受控对比请成对取用同种子、同 H 的 high 与 funnel 两档"
          "——两者仅 LU 出口容量不同(规格 3.1 实测修正、13.6 优先级 1)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
