"""用公开数据集的布局拓扑生成算例(布局出处外部化)。

用法(clbs/ 目录下):

    py -m tools.gen_pub_layouts                  # 写入 input/pub/
    py -m tools.gen_pub_layouts --list           # 只列特征表,不落盘
    py -m tools.gen_pub_layouts --keys LyuL4 LyuL6

这批算例与 `tools.gen_instances` 生成的 `S8x4x4` 族**只差布局来源**:工件数、
AGV 数、每工件工序数、H、F 与 T̄t/T̄p 标定目标一律取同值,于是两批之间的差异可以
干净地归因给"拓扑是谁设计的"。

为什么要有这批算例。自建布局族(mid/high/funnel)同属哑铃一族,彼此只差 LU 出口与
中段的并行通道数,即只差容量、不差几何;闭包规模的结构可预测性在这三张上没能测出来,
但那个负结果是**混淆**的——分不清是结构指标太粗,还是同族变体之间的几何差异本就
不足以被任何指标分辨。换一批不由本文设计、几何上真正不同的布局,才能把这两种解释
分开。取数与口径见 `algorithm.generator.PUB_LAYOUTS` 的注释。

**只借拓扑,不借工件数据。** 已实测的公开族其平均运输时长只占平均加工时长的百分之几
(见 `database/README.md`),运输在其上几乎不构成争用;若把工件数据一并搬入,走廊争用
连同以它为研究对象的一整套结论都会退化到观察不到。因此工件与 T̄t/T̄p 标定仍沿用本项目
口径,外部化的只有路网。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.generator import (PUB_LAYOUTS, build_instance, make_pub_spec,
                                 measure)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "input", "pub")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="公开布局算例生成器")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--agvs", type=int, default=4)
    ap.add_argument("--ops", type=int, default=3, help="每工件工序数")
    ap.add_argument("--het", type=float, default=0.3, help="异构度 H")
    ap.add_argument("--flex", type=float, default=0.6, help="柔性度 F = 平均|Ω|/NM")
    ap.add_argument("--tt-tp", type=float, default=1.0,
                    help="T̄t/T̄p 标定目标;<=0 表示不标定")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--keys", nargs="+", default=sorted(PUB_LAYOUTS),
                    choices=sorted(PUB_LAYOUTS), help="外部布局键")
    ap.add_argument("--out", default=OUT_DIR, help="输出目录")
    ap.add_argument("--list", action="store_true", help="只打印特征表,不写文件")
    return ap.parse_args()


_COLS = ("算例", "网格", "机器", "节点", "走廊", "H实测", "F实测", "Tt/Tp",
         "LU割", "远端割", "漏斗占比", "每节点走廊", "下界")


def _row(data: dict, f: dict) -> tuple:
    spec = data["_spec"]
    net = data["network"]
    return (data["name"],
            f"{spec['grid_rows']}x{spec['grid_cols']}",
            spec["num_machines"], len(net["nodes"]), len(net["corridors"]),
            f["heterogeneity"], f["flexibility"], f["Tt_over_Tp"],
            f["lu_min_cut"], f["far_group_cut"], f["funnel_share"],
            f["corridors_per_node"], f["lower_bound"])


def main() -> int:
    args = parse_args()
    rows, skipped = [], []
    written = 0
    if not args.list:
        os.makedirs(args.out, exist_ok=True)

    for key in args.keys:
        for seed in args.seeds:
            try:
                spec = make_pub_spec(
                    key, heterogeneity=args.het, flexibility=args.flex,
                    num_jobs=args.jobs, num_agvs=args.agvs,
                    ops_per_job=args.ops, seed=seed,
                    tt_tp_target=args.tt_tp if args.tt_tp > 0 else None)
            except ValueError as exc:
                # 小布局在固定 F 下可能与 B1(|Ω|>=2)冲突。此处**不**为它单独放宽 F:
                # F 是本批要held住的因子,为一张布局改它就等于多引入一个变量。
                skipped.append((key, str(exc)))
                continue
            data = build_instance(spec)
            feat = measure(data)
            rows.append(_row(data, feat))
            if not args.list:
                path = os.path.join(args.out, f"{data['name']}.json")
                with open(path, "w", encoding="utf-8") as fp:
                    json.dump(data, fp, ensure_ascii=False, indent=2)
                written += 1

    if rows:
        widths = [max(len(str(r[i])) for r in [_COLS] + rows)
                  for i in range(len(_COLS))]
        line = "  ".join(str(c).ljust(w) for c, w in zip(_COLS, widths))
        print(line)
        print("-" * len(line))
        for r in rows:
            print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))

    for key, msg in skipped:
        print(f"\n跳过 {key}:{msg}")

    print(f"\n共 {len(rows)} 个算例"
          + (f",已写入 {os.path.relpath(args.out, HERE)}{os.sep}" if written
             else "(--list 模式,未落盘)"))
    print("口径提醒:边权为本文补齐的等权值,**不可**与 Lyu 或 van Os 的参照值比较;"
          "\n外部化的只有路网拓扑,工件数据仍为本项目生成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
