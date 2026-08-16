"""复合下界与最优已知解的间隙:在当前(新)算例族上重算 \\LBGapLo/Hi/Med。

为什么需要这个工具。论文导言区的 \\LBGapLo/Hi/Med 三个宏原先取自旧算例族(J8/M4 那一批),
而第 5 章的全部结果都已换到 abc_matrix.CASES 这十格(J12/M8/tt=4.0)。两者不同源,宏注释
里也标注了"待新算例族的结果落盘后一并更新"。本工具就做这一步。

口径。
  下界     algorithm.instance.simple_lower_bound 的 max(job_chain, machine_load, lu_cut),
           零成本、三个分量各自都是合法松弛,不含任何排队与换机运输。
  最优已知解 baseline_ladder.csv 中该格**全部档位 × 全部种子**的最小完工时间。这些解都经过
           无冲突路由执行并过校验器,故是可实现的;取全档最小是为了不让"最优已知"依赖于
           挑哪一档。
  间隙     gap = (best_known - LB) / best_known,即下界距可实现解还差最优值的百分之几。
           另报 (best_known - LB) / LB 作对照,以免读者误解分母。

运行(clbs/ 目录下):
  py -u -m tools.lb_gap [--csv output/baseline_ladder.csv]
"""
from __future__ import annotations

import csv
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import simple_lower_bound
from tools.abc_matrix import CASES, build

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def best_known(csv_path: str) -> dict:
    """每格在全部档位、全部种子上的最小完工时间。"""
    best: dict = defaultdict(lambda: float("inf"))
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            nm, mk = row["case"], float(row["makespan"])
            if mk < best[nm]:
                best[nm] = mk
    return dict(best)


def main() -> int:
    args = sys.argv[1:]
    rel = (args[args.index("--csv") + 1] if "--csv" in args
           else os.path.join("output", "baseline_ladder.csv"))
    csv_path = rel if os.path.isabs(rel) else os.path.join(HERE, rel)

    best = best_known(csv_path)
    print(f"最优已知解取自 {os.path.relpath(csv_path, HERE)}(全档位 × 全种子的最小值)\n")
    print(f"{'算例':<14s} {'job_chain':>10s} {'mach_load':>10s} {'lu_cut':>8s} "
          f"{'下界':>8s} {'最优已知':>9s} {'gap/best':>9s} {'gap/LB':>8s}")
    print("-" * 84)

    gaps = []
    rows = []
    for case in CASES:
        nm = case["name"]
        if nm not in best:
            print(f"{nm:<14s}  !! baseline_ladder.csv 中没有这一格,跳过")
            continue
        inst, net, _c = build(case)
        lb = simple_lower_bound(inst, net)
        b = best[nm]
        g_best = (b - lb["lower_bound"]) / b
        g_lb = (b - lb["lower_bound"]) / lb["lower_bound"]
        gaps.append(g_best)
        rows.append((nm, lb, b, g_best, g_lb))
        print(f"{nm:<14s} {lb['job_chain']:>10.2f} {lb['machine_load']:>10.2f} "
              f"{lb['lu_cut']:>8.2f} {lb['lower_bound']:>8.2f} {b:>9.2f} "
              f"{g_best:>8.1%} {g_lb:>7.1%}")

    if not gaps:
        print("\n没有可用的格,检查 CSV 与 CASES 是否同源。")
        return 1

    lo, hi = min(gaps), max(gaps)
    med = statistics.median(gaps)
    print("-" * 84)
    print(f"{'':<14s} {'':>10s} {'':>10s} {'':>8s} {'':>8s} {'区间':>9s} "
          f"{lo:>8.1%} ~ {hi:.1%}")
    print(f"{'':<14s} {'':>10s} {'':>10s} {'':>8s} {'':>8s} {'中位':>9s} {med:>8.1%}")

    # 哪个分量在起作用:三个松弛互不支配,报一下各自当选的次数
    who = defaultdict(int)
    for _nm, lb, _b, _gb, _gl in rows:
        key = max(("job_chain", "machine_load", "lu_cut"), key=lambda k: lb[k])
        who[key] += 1
    print("\n下界由哪个分量决定:" +
          "、".join(f"{k} {v} 格" for k, v in sorted(who.items(), key=lambda x: -x[1])))

    print("\n宏更新(粘贴进 paper01/paper.tex 导言区):")
    print(f"\\newcommand{{\\LBGapLo}}{{{lo * 100:.0f}\\%}}")
    print(f"\\newcommand{{\\LBGapHi}}{{{hi * 100:.0f}\\%}}")
    print(f"\\newcommand{{\\LBGapMed}}{{{med * 100:.0f}\\%}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
