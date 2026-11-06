"""E1 主表的逐注入配对检验：McNemar 精确检验 + 自助法区间 + Holm 校正。

只读 e1_archive.json（主表口径，注入率 0.2），不重跑检测。配对单位是注入实例：
同一种子下本文与对照方法面对同一条受攻击流，逐条注入记录"延迟预算内是否检出"。
检验的是未扣除偶然告警基线的原始检出；同一流内的注入按相互独立处理（近似）。
族 = 6 类攻击 x 4 个对照 = 24 个比较，Holm 校正。

用法（在 paper02/slid/ 下）：  py -m tools.e1_paired_stats
"""
from __future__ import annotations

import argparse
import math
import os
import random

from algorithm import archive

OUT = os.path.join(archive.OUTPUT, "e1_paired_archive.json")
FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")
CONTROLS = ("butla", "tabor", "hsmm", "markov")


def _comb(n: int, k: int) -> int:
    return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(_comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, prev, m = [0.0] * len(ps), 0.0, len(ps)
    for r, i in enumerate(order):
        prev = min(1.0, max(prev, (m - r) * ps[i]))
        adj[i] = prev
    return adj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=10)
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--archive", default=OUT)
    args = ap.parse_args()

    src = archive.require(archive.E1_PATH)
    runs = {(x["family"], x["seed"], x["method"]): x
            for x in src["runs"] if x["rate"] == args.rate}
    seeds = sorted({s for (_, s, _) in runs})

    def hits(x):
        return [1 if (v is not None and v <= args.budget) else 0
                for v in x["delays"]]

    rng = random.Random(args.seed)
    lo_i = int(0.025 * args.boot)
    hi_i = int(0.975 * args.boot) - 1
    rows = []
    for fam in FAMILIES:
        for ctl in CONTROLS:
            pairs = []
            for s in seeds:
                pairs += list(zip(hits(runs[(fam, s, "ours")]),
                                  hits(runs[(fam, s, ctl)])))
            n = len(pairs)
            diff = sum(o - b for o, b in pairs) / n
            b = sum(1 for o, q in pairs if o == 1 and q == 0)
            c = sum(1 for o, q in pairs if o == 0 and q == 1)
            boots = sorted(
                sum(o - q for o, q in (rng.choice(pairs) for _ in range(n))) / n
                for _ in range(args.boot))
            rows.append({"family": fam, "control": ctl, "n": n,
                         "diff": diff, "ci_lo": boots[lo_i],
                         "ci_hi": boots[hi_i], "ours_only": b,
                         "control_only": c, "p": mcnemar_exact(b, c)})
    for r, a in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = a

    path = archive.dump(args.archive, {
        "source": os.path.basename(archive.E1_PATH), "rate": args.rate,
        "budget": args.budget, "boot": args.boot, "seed": args.seed,
        "seeds": seeds, "test": "McNemar exact, two-sided; Holm over "
        f"{len(rows)} comparisons", "rows": rows})

    print(f"{'攻击':<5}{'对照':<8}{'n':>5}{'差':>8}{'95%区间':>18}"
          f"{'b':>5}{'c':>5}{'p':>10}{'Holm p':>10}")
    for r in rows:
        print(f"{r['family']:<5}{r['control']:<8}{r['n']:>5}{r['diff']:>8.3f}"
              f"   [{r['ci_lo']:>6.3f},{r['ci_hi']:>6.3f}]"
              f"{r['ours_only']:>5}{r['control_only']:>5}"
              f"{r['p']:>10.2g}{r['p_holm']:>10.2g}")
    print(f"存档：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
