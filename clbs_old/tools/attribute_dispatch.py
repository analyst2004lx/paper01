# -*- coding: utf-8 -*-
"""精确派车值多少:与 nofeedback 只差派车方式一项的干净归因。

`opendispatch` 档是在完整方法(含局部搜索)之上改动派车方式,因此它与 `nofeedback`
(精确派车、无局部搜索)之间同时差着两个因素,相减得不出派车方式本身的贡献。
`opendispatch_nols` 把局部搜索也关掉,与 `nofeedback` 只差这一项,故这一对才可归因。

同时报告两档各自拿到的评价次数:规则派车不查预约表,单次解码便宜得多,同挂钟下能
多跑很多代。若它在质量上仍不落后,说明精确派车没能为自己的成本挣回收益。
"""
from __future__ import annotations

import csv
import os
import statistics as st
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from algorithm.stats import stars, wilcoxon_signed_rank  # noqa: E402

REF, ALT = "nofeedback", "opendispatch_nols"
TAGS = ["low", "mid", "high", "funnel"]


def main() -> int:
    path = os.path.join(HERE, "experiments", "runs.csv")
    with open(path, encoding="utf-8") as f:
        runs = list(csv.DictReader(f))

    idx = defaultdict(dict)
    for r in runs:
        idx[(r["instance"], r["seed"])][r["arm"]] = r

    def block(rows_filter, title):
        pairs, ev_ref, ev_alt = [], [], []
        for (inst, _s), v in idx.items():
            if REF not in v or ALT not in v:
                continue
            if not rows_filter(v[REF]):
                continue
            pairs.append((float(v[ALT]["makespan"]), float(v[REF]["makespan"])))
            for arm, acc in ((REF, ev_ref), (ALT, ev_alt)):
                if v[arm].get("evaluations"):
                    acc.append(float(v[arm]["evaluations"]))
        if not pairs:
            print("  %-10s (无数据)" % title)
            return
        # 正数 = 精确派车(nofeedback)更好
        gains = [(a - b) / a for a, b in pairs if a > 0]
        w = wilcoxon_signed_rank([a for a, _ in pairs], [b for _, b in pairs])
        wins = sum(1 for a, b in pairs if b < a)
        loss = sum(1 for a, b in pairs if b > a)
        ratio = (st.mean(ev_alt) / st.mean(ev_ref)) if ev_ref and ev_alt else 0.0
        print("  %-10s %+7.2f%%%-3s n=%-4d %3d胜/%3d负/%3d平  p=%-8.4g "
              "评价次数比 %.1fx"
              % (title, 100 * st.mean(gains), stars(w["p_value"]), len(pairs),
                 wins, loss, len(pairs) - wins - loss, w["p_value"], ratio))

    print("=" * 82)
    print("精确派车的干净归因:%s 相对 %s(两者只差派车方式,均不含局部搜索)"
          % (REF, ALT))
    print("正数 = 精确派车更好;'评价次数比' = 规则派车拿到的评价次数 / 精确派车的")
    print("=" * 82)
    block(lambda r: True, "汇总")
    for tag in TAGS:
        block(lambda r, t=tag: r.get("tag") == t, tag)

    print()
    print("对照(含混淆,不可用于归因):%s 相对 opendispatch —— 两者同时差着"
          "派车方式与局部搜索两项" % REF)
    pairs = [(float(v["opendispatch"]["makespan"]), float(v[REF]["makespan"]))
             for v in idx.values() if "opendispatch" in v and REF in v]
    if pairs:
        g = st.mean([(a - b) / a for a, b in pairs if a > 0])
        w = wilcoxon_signed_rank([a for a, _ in pairs], [b for _, b in pairs])
        print("  汇总       %+7.2f%%%-3s n=%-4d p=%.4g"
              % (100 * g, stars(w["p_value"]), len(pairs), w["p_value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
