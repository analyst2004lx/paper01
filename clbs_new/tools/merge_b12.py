# -*- coding: utf-8 -*-
"""把加速后重跑的 B1/B2(CLBS-R/CLBS)并入主批次。

读 output/baseline_ladder_v1.csv(原主批次,保留不动)与 output/ladder_b12_g*.csv
(baseline_ladder --arms B1,B2 写出),用后者替换前者的 B1、B2 行,写回
output/baseline_ladder.csv。其余档(B0、B0宽松、B0+、BL)不经过试算派车,
解码器加速对它们逐位无影响,故沿用原批次。

Merge the post-speedup B1/B2 rerun into the main batch: rows for B1 and B2 in
baseline_ladder_v1.csv are replaced by those in ladder_b12_g*.csv; the other arms
do not use probe dispatch, so the speedup leaves them bit-identical.

  py -3 -m tools.merge_b12
"""
from __future__ import annotations

import csv
import glob
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "output")


def main() -> int:
    new = {}
    for fn in sorted(glob.glob(os.path.join(OUT, "ladder_b12_g*.csv"))):
        with open(fn, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                new[(r["case"], r["arm"], r["seed"])] = r["makespan"]
    rows, replaced = [], 0
    with open(os.path.join(OUT, "baseline_ladder_v1.csv"), encoding="utf-8") as f:
        rd = csv.DictReader(f)
        header = rd.fieldnames
        for r in rd:
            key = (r["case"], r["arm"], r["seed"])
            if r["arm"] in ("B1", "B2"):
                if key not in new:
                    raise SystemExit(f"缺少重跑数据 / missing rerun row: {key}")
                r["makespan"] = new[key]
                replaced += 1
            rows.append(r)
    with open(os.path.join(OUT, "baseline_ladder.csv"), "w", encoding="utf-8",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"替换 {replaced} 行(应为 200),写入 output/baseline_ladder.csv")
    return 0 if replaced == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
