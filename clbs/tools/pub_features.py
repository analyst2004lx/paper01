"""公开算例的因子实测:给论文 §5.1.1 的"取值落在公开算例什么位置"供数。

用法(在 clbs/ 目录下):

    py -m tools.pub_features            # 打印逐算例的 F / H / T̄t/T̄p 与分位
    py -m tools.pub_features --csv      # 同时写 experiments_database/pub_features.csv

为什么要单独有这么一个入口。自建算例的 H 与 F 是**旋钮**,取值由我们定;公开算例的同名量是
**实测**结果。要让两边可比,唯一站得住的做法是走同一个函数——本脚本直接调
`algorithm.instance.feature_params`,与 `algorithm/generator.py` 落盘 `_features` 时调的
是同一个,故两边的数可以逐列对照,而不是各算一套再口头声明"口径一致"。

口径上最容易出错的一处:`feature_params` 的 H 是各工序 |Ω| 内工时的总体变异系数在**全部**
工序上的均值,`|Ω|=1` 的工序按 **0** 计入。若改成"跳过单机工序"再取均值,公开算例的 H 中位
会从 0.135 抬到 0.148——因为被跳过的恰是贡献 0 的那些行。抬高的这一版与生成器不同口径,
不能拿去和自建算例比,故本脚本不提供那个选项。
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import statistics
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import feature_params, load_instance
from algorithm.network import Network

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "database")
EXP = os.path.join(HERE, "experiments_database")

FIELDS = ["instance", "num_jobs", "num_machines", "num_real_ops",
          "flexibility", "heterogeneity", "Tt_over_Tp"]


def collect(key: str) -> List[Dict[str, object]]:
    """读 database/json/<key>/ 下的退化档算例,逐个实测特征。

    只取 `-ideal` 那一档:争用档(`-excl`)是我们加了排他约束之后的**派生**算例,其
    F/H 与原文一致但已不是文献发布的那一个,拿它当"公开算例的实测值"会名不副实。
    """
    rows: List[Dict[str, object]] = []
    pat = os.path.join(DB, "json", key, "*-ideal.json")
    for path in sorted(glob.glob(pat)):
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node,
                      ideal_dist=inst.ideal_dist)
        feat = feature_params(inst, net.ideal_dist, net)
        name = os.path.basename(path)[: -len("-ideal.json")]
        rows.append({
            "instance": name,
            "num_jobs": feat["num_jobs"],
            "num_machines": feat["num_machines"],
            "num_real_ops": feat["num_real_ops"],
            "flexibility": feat["flexibility"],
            "heterogeneity": feat["heterogeneity"],
            "Tt_over_Tp": feat["Tt_over_Tp"],
        })
    if not rows:
        raise SystemExit("没找到任何算例:%s\n先跑 tools/convert_public.py 生成 JSON。"
                         % os.path.relpath(pat, HERE))
    return rows


def _summarize(rows: List[Dict[str, object]], col: str) -> Dict[str, float]:
    vals = [float(r[col]) for r in rows]
    return {"min": min(vals), "max": max(vals),
            "median": statistics.median(vals),
            "mean": sum(vals) / len(vals)}


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description="公开算例的因子实测")
    ap.add_argument("--key", default="hf", help="数据集键(默认 hf)")
    ap.add_argument("--csv", action="store_true",
                    help="写 experiments_database/pub_features.csv")
    args = ap.parse_args(argv)

    rows = collect(args.key)
    print("== %s:公开算例的因子实测(feature_params 原样口径)==" % args.key)
    print("%-9s %-5s %-5s %-6s %-9s %-9s %-9s"
          % ("算例", "工件", "机器", "工序", "柔性 F", "异构 H", "T̄t/T̄p"))
    for r in rows:
        print("%-9s %-5s %-5s %-6s %-9.4f %-9.4f %-9.4f"
              % (r["instance"], r["num_jobs"], r["num_machines"],
                 r["num_real_ops"], r["flexibility"], r["heterogeneity"],
                 r["Tt_over_Tp"]))

    print("\n-- 分位(n=%d)--" % len(rows))
    for col, label in (("flexibility", "柔性 F"), ("heterogeneity", "异构 H"),
                       ("Tt_over_Tp", "T̄t/T̄p")):
        s = _summarize(rows, col)
        print("  %-8s min %.4f  max %.4f  中位 %.4f  均值 %.4f"
              % (label, s["min"], s["max"], s["median"], s["mean"]))

    # 论文 §5.1.1 直接引用的三条对照。阈值写在这里而不是正文里,是为了换数据后
    # 这几句话会跟着变,不必靠人记得回去改。
    hs = [float(r["heterogeneity"]) for r in rows]
    n_ge = sum(1 for h in hs if h >= 0.3)
    print("\n-- 与自建算例取值的对照 --")
    print("  H >= 0.3(本章共用取值)的公开算例:%d / %d" % (n_ge, len(rows)))
    print("  H 的中位 %.3f,最大 %.3f;生成器 H=0.15 那一档实测 0.139,故它是"
          % (statistics.median(hs), max(hs)))
    print("  与公开中位最接近的一档 —— 论文用它检验'H 取 0.3 是否抬高了主效应'。")
    tts = [float(r["Tt_over_Tp"]) for r in rows]
    print("  T̄t/T̄p 最大 %.3f,而自建算例标定到 4.0(阶梯批次)/ 约 1.0(矩阵批次):"
          % max(tts))
    print("  公开算例里运输只占加工的百分之几,这正是本文另立算例的理由之一。")

    if args.csv:
        if not os.path.isdir(EXP):
            os.makedirs(EXP)
        out = os.path.join(EXP, "pub_features.csv")
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        print("\n  -> 已写 %s" % os.path.relpath(out, HERE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
