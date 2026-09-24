# -*- coding: utf-8 -*-
"""核验 E8(算例规模扫描)「耗时比单调拉大」这条趋势主张是否被离散度支持。

正文两处主张:
  §6.11  「耗时比从 1.5x 升到 3.3x——规模越大,重算一遍越不划算」
  §6.12  「与重解码的耗时比单调拉大到 3.3x」
本脚本按 k 分档,给出逐档耗时比的中位与四分位距,并检查中位是否真的单调。
"""
import csv
import io
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, os.pardir, "experiments")
OUT = os.path.join(EXP, "e8_ratio_check.txt")

buf = io.StringIO()


def w(s=""):
    buf.write(s + "\n")


def quantile(v, q):
    if len(v) == 1:
        return v[0]
    pos = q * (len(v) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def describe(vals):
    v = sorted(float(x) for x in vals)
    q1, q3 = quantile(v, 0.25), quantile(v, 0.75)
    return {"n": len(v), "min": v[0], "max": v[-1], "med": quantile(v, 0.5),
            "q1": q1, "q3": q3, "iqr": q3 - q1, "mean": sum(v) / len(v)}


def fmt(d, nd=2):
    f = "%%.%df" % nd
    return ("n=%d  min=" + f + "  Q1=" + f + "  med=" + f + "  Q3=" + f
            + "  max=" + f + "  IQR=" + f + "  mean=" + f) % (
        d["n"], d["min"], d["q1"], d["med"], d["q3"], d["max"], d["iqr"],
        d["mean"])


with open(os.path.join(EXP, "scale_curve.csv"), encoding="utf-8-sig") as fh:
    rows = list(csv.DictReader(fh))

arms = sorted({r["arm"] for r in rows})
w("scale_curve.csv 行数 = %d;臂 = %s" % (len(rows), ", ".join(arms)))
w("k 档 = %s" % sorted({int(r["k"]) for r in rows}))
w("")

# 按 (k, seed) 配对取各臂耗时,算逐格比值——比值必须逐格配对后再统计,
# 不能用「各档均值之比」,那会把离散度藏起来。
cell = defaultdict(dict)
for r in rows:
    cell[(int(r["k"]), r["seed"])][r["arm"]] = r

pairs = [("RD", "R2"), ("R0+", "R2"), ("R0", "R2")]
for num, den in pairs:
    per_k = defaultdict(list)
    for (k, _seed), d in cell.items():
        if num in d and den in d:
            a, b = d[num], d[den]
            try:
                wa, wb = float(a["wall_ms"]), float(b["wall_ms"])
            except (ValueError, KeyError):
                continue
            if wb > 0:
                per_k[k].append(wa / wb)
    if not per_k:
        continue
    w("=" * 70)
    w("逐格耗时比  %s / %s" % (num, den))
    w("=" * 70)
    meds = []
    for k in sorted(per_k):
        d = describe(per_k[k])
        meds.append((k, d["med"]))
        w("  k=%-3d %s" % (k, fmt(d)))
    w("")
    w("  逐档中位序列: %s" % ", ".join("k=%d:%.2f" % (k, m) for k, m in meds))
    mns = [(k, describe(per_k[k])["mean"]) for k in sorted(per_k)]
    w("  逐档均值序列: %s" % ", ".join("k=%d:%.2f" % (k, m) for k, m in mns))
    for lbl, seq in (("中位", meds), ("均值", mns)):
        vals2 = [m for _k, m in seq]
        ok = all(vals2[i + 1] >= vals2[i] for i in range(len(vals2) - 1))
        w("  %s是否单调不减: %s" % (lbl, ok))
        if not ok:
            bad = [("k=%d->%d" % (seq[i][0], seq[i + 1][0]),
                    round(vals2[i], 2), round(vals2[i + 1], 2))
                   for i in range(len(vals2) - 1) if vals2[i + 1] < vals2[i]]
            w("     下降处: %s" % bad)
    vals = [m for _k, m in meds]
    span = max(vals) - min(vals)
    iqrs = [describe(per_k[k])["iqr"] for k in sorted(per_k)]
    w("  中位跨档跨度 = %.2f;逐档 IQR 在 %.2f--%.2f 之间" %
      (span, min(iqrs), max(iqrs)))
    w("  跨档跨度是否大于最大档内 IQR: %s" % (span > max(iqrs)))
    w("")

open(OUT, "w", encoding="utf-8").write(buf.getvalue())
print("written: " + OUT)
