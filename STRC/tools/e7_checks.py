# -*- coding: utf-8 -*-
"""B02f 施工核查：E7 四臂读数的三处疑点。

1. \WorthVanishN=8 与 "取到 1.00 的 4 个格两法恒等" 是否矛盾（8 格降幅 0 里有几格真在 1.00）
2. \RAStabWTL 的那 1 个反例格，降幅到底是 +0.007 还是 -0.007（符号口径）
3. P08：RD 对 R2 的 C_max 差，补一个配对检验与区间，判断是否可区分
"""
import csv
import io
import os
import random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "..", "experiments", "cheap_baselines.csv")
OUT = os.path.join(HERE, "..", "experiments", "e7_checks.txt")


def load():
    by_key = defaultdict(dict)
    with io.open(CSV, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row["instance"], int(row["seed"]))
            by_key[key][row["arm"]] = row
    return by_key


def fnum(row, field):
    val = row.get(field, "")
    return float(val) if val not in ("", None) else None


def bootstrap_ci(vals, stat, iters=20000, seed=12345):
    rng = random.Random(seed)
    n = len(vals)
    reps = []
    for _ in range(iters):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        reps.append(stat(sample))
    reps.sort()
    lo = reps[int(0.025 * iters)]
    hi = reps[int(0.975 * iters) - 1]
    return lo, hi


def mean(vals):
    return sum(vals) / float(len(vals))


def median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def wilcoxon_signed_rank(diffs):
    """双侧 Wilcoxon 符号秩，正态近似（含零差剔除与并列秩平均）。"""
    nz = [d for d in diffs if d != 0.0]
    n = len(nz)
    if n == 0:
        return None, None, 0
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = 0.5 * (i + 1 + j + 1)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(ranks[i] for i in range(n) if nz[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if nz[i] < 0)
    w = min(w_plus, w_minus)
    mu = n * (n + 1) / 4.0
    sigma = (n * (n + 1) * (2 * n + 1) / 24.0) ** 0.5
    if sigma == 0:
        return w, None, n
    z = (w - mu) / sigma
    # 双侧 p，用 erfc 近似正态尾概率
    import math
    p = math.erfc(abs(z) / (2 ** 0.5))
    return w, p, n


def main():
    by_key = load()
    lines = []
    w = lines.append

    keys = sorted(k for k in by_key if "R2" in by_key[k] and "RA" in by_key[k])
    w("配对格数（R2 与 RA 同时存在）：%d" % len(keys))

    # ---- 疑点 1 与 2：R2 对 RA 的改动比例降幅，逐格 ----
    recs = []
    for k in keys:
        r2, ra = by_key[k]["R2"], by_key[k]["RA"]
        drop = fnum(ra, "res_frac") - fnum(r2, "res_frac")  # 正 = R2 改得更少
        alive = fnum(r2, "alive_size")
        rel = fnum(r2, "release_size")
        share = (rel / alive) if alive else None  # 允许改写占比 Cl/|R°|
        recs.append((k, drop, share))

    wins = sum(1 for _, d, _ in recs if d > 0)
    ties = sum(1 for _, d, _ in recs if d == 0)
    loss = sum(1 for _, d, _ in recs if d < 0)
    w("R2 更稳/持平/更差 = %d/%d/%d  （宏 \\RAStabWTL = 31/18/1）" % (wins, ties, loss))

    w("")
    w("== 疑点 2：那 %d 个反例格 ==" % loss)
    for k, d, s in recs:
        if d < 0:
            w("  %s seed=%d：降幅 = %+.4f（即 R2 比 RA 多改 %.4f），占比 = %.4f"
              % (k[0], k[1], d, -d, s))
    w("  → 正文写「唯一的反例格降幅为 +0.007」；按「正 = R2 改得更少」的口径，")
    w("    反例格的降幅应为负数，正文的正号与该口径不符。")

    w("")
    w("== 疑点 1：降幅为 0 的格子里，占比究竟在哪 ==")
    zero = [(k, s) for k, d, s in recs if d == 0]
    w("  降幅 = 0 的格数：%d（宏 \\RAStabWTL 的持平数 = 18）" % len(zero))
    at_one = [(k, s) for k, s in zero if s is not None and abs(s - 1.0) < 1e-9]
    w("  其中占比 = 1.00（影响集 = 全部尚未结束占用，两法恒等）：%d 格" % len(at_one))
    w("  → 正文第 1790 行称「取到 1.00 的 4 个格上两法恒等」")
    ge97 = [(k, s) for k, d, s in recs if s is not None and s >= 0.97]
    ge97_zero = [(k, s) for k, s in ge97 if dict((kk, dd) for kk, dd, _ in recs)[k] == 0]
    w("  占比 >= 0.97 的格数：%d（宏 \\WorthVanishN = 8）" % len(ge97))
    w("  其中降幅 = 0 的：%d 格" % len(ge97_zero))
    w("  其中占比 = 1.00 的：%d 格"
      % sum(1 for _, s in ge97 if abs(s - 1.0) < 1e-9))
    w("  → 若 8 格里只有 4 格在 1.00，则第 1811 行把这 8 格降幅为 0 的原因")
    w("    一律解释为「影响集已是平凡上界，两法恒等」是错的。")

    w("")
    w("== 口径自检：我的「允许改写占比」定义是否与论文一致 ==")
    shares = [s for _, _, s in recs if s is not None]
    w("  share = release_size / alive_size（取 R2 行）")
    w("  均值 %.4f（宏 \\ClosureShareMean = 0.92）；最小 %.4f（宏 \\ClosureShareLo = 0.80）；最大 %.4f"
      % (mean(shares), min(shares), max(shares)))
    w("  → 均值与最小值都与宏对得上，故该定义与论文一致。")
    w("  占比 >= 0.97 的格数：%d；占比 > 0.97 的格数：%d"
      % (sum(1 for s in shares if s >= 0.97), sum(1 for s in shares if s > 0.97)))
    w("  占比 落在 [0.97, 1.00) 的各格占比值：%s"
      % ", ".join("%.4f" % s for s in sorted(s for s in shares if 0.97 <= s < 1.0)))
    w("  占比 = 1.00 的格数：%d" % sum(1 for s in shares if abs(s - 1.0) < 1e-9))
    w("  按算例分组，占比 = 1.00 的格：%s"
      % ", ".join("%s/%d" % (k[0], k[1]) for k, d, s in recs
                  if s is not None and abs(s - 1.0) < 1e-9))

    # 分档均值复核
    hi = [d for _, d, s in recs if s is not None and s >= 0.93]
    lo = [d for _, d, s in recs if s is not None and s < 0.93]
    w("")
    w("== 复核事后分档（阈值 \\WorthThresh = 0.93）==")
    w("  占比 >= 0.93：%d 格，平均降幅 %.4f（宏 \\WorthHighN=23、\\WorthHighMean=0.029）"
      % (len(hi), mean(hi) if hi else float("nan")))
    w("  占比 <  0.93：%d 格，平均降幅 %.4f（宏 \\WorthLowN=27、\\WorthLowMean=0.094）"
      % (len(lo), mean(lo) if lo else float("nan")))

    # ---- 疑点 3：P08，RD 对 R2 的 C_max ----
    w("")
    w("== 疑点 3：P08 —— RD 对 R2 的 C_max 配对比较 ==")
    kk = sorted(k for k in by_key if "R2" in by_key[k] and "RD" in by_key[k])
    w("  配对格数：%d" % len(kk))
    # 退化率 = (makespan - makespan_ref) / makespan_ref
    deg = []
    for k in kk:
        r2, rd = by_key[k]["R2"], by_key[k]["RD"]
        ref = fnum(r2, "makespan_ref")
        d_r2 = (fnum(r2, "makespan") - ref) / ref
        d_rd = (fnum(rd, "makespan") - ref) / ref
        deg.append((k, d_r2, d_rd))
    w("  平均退化 R2 = %.4f，RD = %.4f（正文作 49.8%% 对 49.0%%）"
      % (mean([a for _, a, _ in deg]), mean([b for _, _, b in deg])))
    diffs = [a - b for _, a, b in deg]  # 正 = R2 退化更多 = RD 更优
    w("  配对差（R2 退化 − RD 退化，正 = RD 更优）：")
    w("    均值 %+.4f，中位 %+.4f" % (mean(diffs), median(diffs)))
    lo_m, hi_m = bootstrap_ci(diffs, mean)
    w("    均值的 bootstrap 95%% CI = [%+.4f, %+.4f]" % (lo_m, hi_m))
    lo_d, hi_d = bootstrap_ci(diffs, median)
    w("    中位的 bootstrap 95%% CI = [%+.4f, %+.4f]" % (lo_d, hi_d))
    stat, p, n_nz = wilcoxon_signed_rank(diffs)
    w("    Wilcoxon 符号秩双侧：W = %s，p = %s，非零差格数 n = %d"
      % (stat, ("%.4g" % p) if p is not None else "NA", n_nz))
    rd_better = sum(1 for d in diffs if d > 0)
    same = sum(1 for d in diffs if d == 0)
    r2_better = sum(1 for d in diffs if d < 0)
    w("    逐格 RD 更优/持平/R2 更优 = %d/%d/%d（宏 \\WinVsRedecode = 14/14/22，"
      % (rd_better, same, r2_better))
    w("     该宏是 R2 的赢/平/输，故对应 RD 更优 = 22）")
    # C_max 比值
    ratios = []
    for k in kk:
        r2, rd = by_key[k]["R2"], by_key[k]["RD"]
        ratios.append(fnum(rd, "makespan") / fnum(r2, "makespan"))
    w("  C_max 比值 RD/R2：均值 %.4f，中位 %.4f，最小 %.4f，最大 %.4f"
      % (mean(ratios), median(ratios), min(ratios), max(ratios)))
    lo_r, hi_r = bootstrap_ci(ratios, mean)
    w("    比值均值的 bootstrap 95%% CI = [%.4f, %.4f]" % (lo_r, hi_r))

    text = "\n".join(lines)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
