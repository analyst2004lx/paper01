# -*- coding: utf-8 -*-
"""离线探针:汇总 sens_c*.csv 上 CLBS 相对 OL/TS/AE 的显著性拐点(不写论文)。

读 output/sens_c{1,2,3,...,10,inf}.csv;逐格 Wilcoxon(配对种子);
Holm 族可选:按「同对比 × 全部已有 c 格」校正,或仅看未校正 p。

  py -3 -m tools.sens_c_probe
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.stats import holm, mean, wilcoxon_signed_rank

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
PAIRS = (("B0", "OL"), ("B0+", "TS"), ("BL", "AE"))
LAYOUT = {"A funnel": "S11", "A high": "S21"}
# 扫描顺序:有限容量升序,再 ∞
CAP_ORDER = [str(i) for i in range(1, 11)] + ["inf"]


def load(fn: str):
    by = defaultdict(lambda: defaultdict(dict))
    meta = {}
    path = os.path.join(OUT, fn)
    if not os.path.isfile(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by[r["case"]][r["arm"]][int(r["seed"])] = float(r["makespan"])
            meta[r["case"]] = (r["cap"], r["het"], float(r["contention"]))
    return by, meta


def cell(by, case, a, b):
    # a=baseline, b=CLBS(B2); 与 sens_summary 同: wilcoxon(CLBS, base), rel=(CLBS-base)/base
    seeds = sorted(set(by[case][a]) & set(by[case][b]))
    if len(seeds) < 3:
        return None
    xa = [by[case][a][s] for s in seeds]
    xb = [by[case][b][s] for s in seeds]
    st = wilcoxon_signed_rank(xb, xa)
    return {
        "n": len(seeds),
        "m_a": mean(xa),
        "m_b": mean(xb),
        "gain": mean([(y - x) / x for x, y in zip(xa, xb)]),
        "p": float(st["p_value"]),
        "w": sum(y < x - 1e-9 for x, y in zip(xa, xb)),
        "l": sum(y > x + 1e-9 for x, y in zip(xa, xb)),
    }


def main() -> int:
    rows = []  # (cap, case, pair_name, result, raw_p)
    available = []
    for cap in CAP_ORDER:
        fn = f"sens_c{cap}.csv"
        by, meta = load(fn)
        if by is None:
            continue
        available.append(cap)
        for case in ("A funnel", "A high"):
            if case not in by:
                continue
            for arm, name in PAIRS:
                if arm not in by[case] or "B2" not in by[case]:
                    continue
                r = cell(by, case, arm, "B2")
                if r is None:
                    continue
                rows.append((cap, case, name, r))

    if not rows:
        print("尚无可用 sens_c*.csv")
        return 1

    # Holm: 每个对比方法单独一族,族内含全部 (layout × available c)
    for name in ("OL", "TS", "AE"):
        idxs = [i for i, row in enumerate(rows) if row[2] == name]
        ps = [rows[i][3]["p"] for i in idxs]
        adj = holm(ps)
        for j, i in enumerate(idxs):
            rows[i][3]["p_holm"] = adj[j]

    print(f"已加载 c ∈ {{{', '.join(available)}}}")
    print(f"{'c':>4} {'lay':>4} {'vs':>3}  {'base':>7} {'CLBS':>7}  {'Δ%':>7}  "
          f"{'W/L':>5}  {'p':>8}  {'p_holm':>8}  mark")
    print("-" * 78)
    # 找「开始不再更显著」:对每个 (layout, vs), 按 c 升序找首个 p_holm>=0.05
    first_ns = {}
    for cap, case, name, r in rows:
        lay = LAYOUT[case]
        mark = ("**" if r["p_holm"] < 0.01 else
                "*" if r["p_holm"] < 0.05 else
                "†" if r["p"] < 0.05 else "-")
        print(f"{cap:>4} {lay:>4} {name:>3}  {r['m_a']:7.2f} {r['m_b']:7.2f}  "
              f"{100*r['gain']:+6.1f}%  {r['w']}/{r['l']:>2}  {r['p']:8.4g}  "
              f"{r['p_holm']:8.4g}  {mark}")
        key = (lay, name)
        if key not in first_ns and r["p_holm"] >= 0.05:
            first_ns[key] = (cap, r["p"], r["p_holm"], mark)

    print("\n--- 拐点摘要(未校正 p;有限 c 升序;看优势从 c≥2 显著段之后何时褪去) ---")
    for lay in ("S11", "S21"):
        for name in ("OL", "TS", "AE"):
            series = [(cap, r) for cap, case, n, r in rows
                      if LAYOUT[case] == lay and n == name]
            if not series:
                print(f"  {lay} vs {name}: 无数据")
                continue
            last_sig, first_fade, seen_sig_ge2 = None, None, False
            for cap, r in series:
                if cap == "inf":
                    continue
                ci = int(cap)
                if r["p"] < 0.05:
                    if first_fade is None:
                        last_sig = (cap, r["p"], r["gain"])
                    if ci >= 2:
                        seen_sig_ge2 = True
                elif ci >= 2 and seen_sig_ge2 and first_fade is None:
                    first_fade = (cap, r["p"], r["gain"])
            if first_fade:
                print(f"  {lay} vs {name}: 自 c={first_fade[0]} 起未校正不再显著 "
                      f"(p={first_fade[1]:.4g}, Δ={100*first_fade[2]:+.1f}%)"
                      + (f"; 此前末显著档 c={last_sig[0]}" if last_sig else ""))
            elif last_sig:
                print(f"  {lay} vs {name}: 已测有限 c 上未校正均显著 "
                      f"(末档 c={last_sig[0]}, p={last_sig[1]:.4g}, Δ={100*last_sig[2]:+.1f}%)")
            else:
                print(f"  {lay} vs {name}: c≥2 已测档均未达未校正显著")

    print("\n--- 参考:Holm 族=同对比×全部已加载格(格越多越严,探针用) ---")
    for lay in ("S11", "S21"):
        for name in ("OL", "TS", "AE"):
            key = (lay, name)
            if key in first_ns:
                cap, p, ph, mark = first_ns[key]
                print(f"  {lay} vs {name}: 自 c={cap} 起 Holm 不再显著 "
                      f"(p={p:.4g}, p_holm={ph:.4g})")
            else:
                caps_here = [cap for cap, case, n, _ in rows
                             if LAYOUT[case] == lay and n == name]
                if caps_here:
                    print(f"  {lay} vs {name}: 已测 c 上 Holm 均显著")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
