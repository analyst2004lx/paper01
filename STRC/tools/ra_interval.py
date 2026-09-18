# -*- coding: utf-8 -*-
"""R2 vs RA 改动比例：配对差的区间估计与离散度（标准库 only）

用现有 experiments/cheap_baselines.csv，不重跑实验。
对应论文 §6.9 的 \\RAStabMean / \\RAStabMed / \\RAStabWTL，
补出决定 D 所需的 bootstrap 置信区间、Hodges--Lehmann 估计与 IQR。

用法：py -m tools.ra_interval      （在 STRC/ 目录内）
      py STRC/tools/ra_interval.py
"""
from __future__ import print_function

import csv
import io
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, os.pardir, "experiments", "cheap_baselines.csv")
B = 10000
SEED = 20260917


def quantile(sorted_xs, q):
    """线性插值分位数（与 numpy 默认 linear 一致）。"""
    if not sorted_xs:
        raise ValueError("empty")
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_xs) - 1)
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


def median(xs):
    return quantile(sorted(xs), 0.5)


def iqr(xs):
    s = sorted(xs)
    return quantile(s, 0.75) - quantile(s, 0.25), quantile(s, 0.25), quantile(s, 0.75)


def hodges_lehmann(xs):
    """配对差的 Walsh 平均之中位数。"""
    walsh = []
    n = len(xs)
    for i in range(n):
        for j in range(i, n):
            walsh.append((xs[i] + xs[j]) / 2.0)
    return median(walsh)


def boot_ci(xs, stat, alpha=0.05):
    rng = random.Random(SEED)
    n = len(xs)
    reps = []
    for _ in range(B):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        reps.append(stat(sample))
    reps.sort()
    return quantile(reps, alpha / 2.0), quantile(reps, 1 - alpha / 2.0)


def main():
    rows = {}
    with io.open(CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[(r["instance"], r["seed"], r["arm"])] = r

    keys = sorted(set((i, s) for (i, s, a) in rows))
    diffs, r2s, ras = [], [], []
    for inst, seed in keys:
        a = rows.get((inst, seed, "R2"))
        b = rows.get((inst, seed, "RA"))
        if not a or not b:
            continue
        x, y = float(a["res_frac"]), float(b["res_frac"])
        r2s.append(x)
        ras.append(y)
        diffs.append(y - x)          # RA - R2 = R2 少改写的幅度

    n = len(diffs)
    win = sum(1 for d in diffs if d > 0)
    tie = sum(1 for d in diffs if d == 0)
    loss = sum(1 for d in diffs if d < 0)

    mean = sum(diffs) / n
    med = median(diffs)
    hl = hodges_lehmann(diffs)
    ci_mean = boot_ci(diffs, lambda s: sum(s) / len(s))
    ci_med = boot_ci(diffs, median)
    # HL 是与 Wilcoxon 配套的点估计，只给点值不给区间等于半份报告
    ci_hl = boot_ci(diffs, hodges_lehmann)

    i_r2, q1_r2, q3_r2 = iqr(r2s)
    i_ra, q1_ra, q3_ra = iqr(ras)
    i_d, q1_d, q3_d = iqr(diffs)

    out = []
    out.append("配对数 n = %d（键 = instance, seed）" % n)
    out.append("逐格胜/平/负（R2 改写更少/持平/更多）= %d/%d/%d" % (win, tie, loss))
    out.append("")
    out.append("配对差 d = res_frac(RA) - res_frac(R2)")
    out.append("  均值          %.4f   bootstrap 95%% CI [%.4f, %.4f]" % (mean, ci_mean[0], ci_mean[1]))
    out.append("  中位          %.4f   bootstrap 95%% CI [%.4f, %.4f]" % (med, ci_med[0], ci_med[1]))
    out.append("  Hodges--Lehmann %.4f   bootstrap 95%% CI [%.4f, %.4f]"
               % (hl, ci_hl[0], ci_hl[1]))
    out.append("  IQR           %.4f   (Q1 %.4f, Q3 %.4f)" % (i_d, q1_d, q3_d))
    out.append("")
    out.append("各臂 res_frac 的离散度")
    out.append("  R2  中位 %.4f  IQR %.4f  (Q1 %.4f, Q3 %.4f)" % (median(r2s), i_r2, q1_r2, q3_r2))
    out.append("  RA  中位 %.4f  IQR %.4f  (Q1 %.4f, Q3 %.4f)" % (median(ras), i_ra, q1_ra, q3_ra))
    out.append("  R2  均值 %.4f   RA 均值 %.4f" % (sum(r2s) / n, sum(ras) / n))
    out.append("")
    out.append("bootstrap: B = %d, 百分位法, 随机种子 %d（固定,可复现）" % (B, SEED))

    text = "\n".join(out)
    with io.open(os.path.join(HERE, os.pardir, "experiments", "ra_interval.txt"),
                 "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    try:
        print(text)
    except UnicodeEncodeError:
        print("written to experiments/ra_interval.txt")


if __name__ == "__main__":
    main()
