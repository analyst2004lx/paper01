# -*- coding: utf-8 -*-
"""每次评价的成本:第 4.8 小节引用的那三个毫秒数的唯一来源。

存在的理由。第 4.8 小节写着"两阶段 0.39 ms、完整闭环 15.4 ms、加上定价 77.9 ms",
这三个数是手打进正文的,而导言区的宏注释同时从 ladder_cost.csv 算出 B2 均值 14.15 ms
——同一份 CSV,正文与注释差了 1.2 ms。手打的数字来自更早的一个批次,换数据时没人记得
回来改它。本脚本把这三个数从盘上的 CSV 重算出来并打印成宏,和其余数字一样只留一个来源。

口径:
  开环(B0/B0+) 共用同一次搜索,故两档的 ms_per_eval 相同,取其均值作"两阶段"一档。
  闭环规则(B1)、闭环试探(B2)分别取均值。
  定价档不在阶梯批次里,它来自 theta_sweep 那批(降本之前),取 theta>0 各点的均值,
  并与同批 theta=0 的读数一并打印,以便正文引用的是同一批内部的对比而非跨批次对比。

运行(clbs/ 目录下):py -m tools.eval_cost
"""
from __future__ import annotations

import csv
import os
from typing import Dict, List

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")
EXP = os.path.join(HERE, "experiments")


def read(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean(xs) -> float:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def main() -> int:
    rows = read(os.path.join(OUT, "ladder_cost.csv"))
    if not rows:
        raise SystemExit("缺少 output/ladder_cost.csv,先跑 tools.ladder_diag")
    per: Dict[str, List[float]] = {}
    for r in rows:
        per.setdefault(r["arm"], []).append(float(r["ms_per_eval"]))
    n_case = len({r["case"] for r in rows})
    n_seed = len({r["seed"] for r in rows})
    print("ladder_cost.csv:%d 算例 x %d 种子" % (n_case, n_seed))
    for a in ("B0", "B0+", "B1", "B2"):
        if a in per:
            print("  %-4s ms/eval = %6.3f  (n=%d)" % (a, mean(per[a]), len(per[a])))

    open_loop = mean(per.get("B0", []) + per.get("B0+", []))
    b1, b2 = mean(per.get("B1", [])), mean(per.get("B2", []))

    theta = read(os.path.join(EXP, "theta_sweep.csv"))
    priced = base = float("nan")
    if theta:
        key = next((k for k in theta[0]
                    if k in ("ms_per_eval", "ms_per_decode", "msPerEval")), None)
        tk = next((k for k in theta[0] if k.lower() in ("theta", "theta_val")), None)
        if key and tk:
            priced = mean([float(r[key]) for r in theta if float(r[tk]) > 0])
            base = mean([float(r[key]) for r in theta if float(r[tk]) == 0])
            print("theta_sweep.csv:theta=0 为 %.3f ms,theta>0 均值 %.3f ms"
                  % (base, priced))
        else:
            print("!! theta_sweep.csv 无单次评价成本列(有 %s),定价档的毫秒数无源"
                  % ", ".join(theta[0]))

    print("\n把下面这段替换进 paper.tex 导言区:")
    print(r"\newcommand{\MsOpen}{%.2f}" % open_loop)
    print(r"\newcommand{\MsLoopRule}{%.2f}" % b1)
    print(r"\newcommand{\MsLoopProbe}{%.1f}" % b2)
    if priced == priced:
        print(r"\newcommand{\MsPriced}{%.1f}" % priced)
        print("跨档倍数:闭环/开环 = %.0f 倍,定价/开环 = %.0f 倍"
              % (b2 / open_loop, priced / open_loop))
    else:
        print("!! 定价档无盘上来源,正文不得引用其毫秒数。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
