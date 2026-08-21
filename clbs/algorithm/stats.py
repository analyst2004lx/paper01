"""实验统计:离散度描述、Wilcoxon 符号秩配对检验、Spearman 秩相关(规格 8.2 协议 2)。

规格 8.2 协议 2 要求"报告均值与标准差并做配对检验",本模块提供其计算。
为什么必须**配对**:同一个种子在两个档位上共享初始种群与随机数流,种子间的方差
(拥堵算例上单档极差可达 11)远大于档位间的差异(1–3),不配对的检验在这个
方差水平上没有任何分辨力(规格 13.2 结论 3)。

纯标准库实现(本机无法安装 scipy,见规格 13.6 第 2 项)。Wilcoxon 在 |d| 无并列、
样本量不大时用**精确零分布**(按秩和的子集计数做动态规划,非枚举),否则退化为
带并列校正的正态近似,方法名随结果一并返回,不隐藏近似。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

EPS = 1e-9
EXACT_MAX_N = 25          # 精确零分布的样本量上限(DP 规模 ~ n^3,足够快)


# ---------------- 描述统计 ----------------

def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def sample_sd(xs: Sequence[float]) -> float:
    """样本标准差(n−1 分母);n < 2 时为 0。"""
    if len(xs) < 2:
        return 0.0
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def describe(xs: Sequence[float]) -> Dict[str, float]:
    """一组重复实验的完整读数。**离散度必须与均值一并报告**(协议 2)。"""
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": round(mean(xs), 3),
        "sd": round(sample_sd(xs), 3),
        "min": round(min(xs), 3),
        "median": round(median(xs), 3),
        "max": round(max(xs), 3),
        "range": round(max(xs) - min(xs), 3),
    }


# ---------------- 秩与 Spearman ----------------

def ranks(vals: Sequence[float]) -> List[float]:
    """升序秩,并列取平均秩(秩从 1 起)。"""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    rk = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(vals[order[j + 1]] - vals[order[i]]) < 1e-12:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            rk[order[t]] = avg
        i = j + 1
    return rk


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Spearman 秩相关;样本 < 3 或任一侧无变异时返回 None。"""
    if len(xs) != len(ys):
        raise ValueError("两组样本长度不等")
    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx < 1e-12 or dy < 1e-12:
        return None
    return num / (dx * dy)


# ---------------- Wilcoxon 符号秩检验 ----------------

def _normal_sf(z: float) -> float:
    """标准正态上尾概率。"""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _exact_two_sided_p(rank_vals: Sequence[float], w_min: float) -> float:
    """精确两侧 p 值:枚举全部 2^n 种符号分配等价于对秩和做子集计数,用 DP 完成。

    零假设下每个差值的符号独立等概率,故 W+ 的分布 = 从秩集合中任取子集的和的分布。
    秩可能是半整数(并列平均秩),故整体乘 2 化为整数索引。
    """
    scaled = [int(round(r * 2)) for r in rank_vals]
    total = sum(scaled)
    counts = [0] * (total + 1)
    counts[0] = 1
    for r in scaled:
        for s in range(total, r - 1, -1):
            if counts[s - r]:
                counts[s] += counts[s - r]
    target = int(round(w_min * 2))
    tail = sum(counts[: target + 1])
    p = 2.0 * tail / float(1 << len(scaled))
    return min(1.0, p)


def wilcoxon_signed_rank(xs: Sequence[float], ys: Sequence[float]) -> Dict[str, object]:
    """配对 Wilcoxon 符号秩检验(两侧)。

    返回字段中 `n_eff` 是**去掉零差值后**的有效对数——它常远小于 n:makespan 取整
    后两档在多数种子上完全打平,这本身就是"分辨不出差异"的直接证据,故必须报告。
    """
    if len(xs) != len(ys):
        raise ValueError("配对检验要求两组样本一一对应")
    diffs = [a - b for a, b in zip(xs, ys) if abs(a - b) > EPS]
    n = len(diffs)
    out: Dict[str, object] = {"n_pairs": len(xs), "n_eff": n,
                              "mean_diff": round(mean([a - b for a, b in zip(xs, ys)]), 3)
                              if xs else None}
    if n == 0:
        out.update({"w_plus": 0.0, "w_minus": 0.0, "statistic": 0.0,
                    "p_value": 1.0, "method": "all-ties"})
        return out

    absr = ranks([abs(d) for d in diffs])
    w_plus = sum(r for d, r in zip(diffs, absr) if d > 0)
    w_minus = sum(r for d, r in zip(diffs, absr) if d < 0)
    w_min = min(w_plus, w_minus)

    tied = len({round(abs(d), 9) for d in diffs}) < n
    if not tied and n <= EXACT_MAX_N:
        p, method = _exact_two_sided_p(absr, w_min), "exact"
    else:
        mu = n * (n + 1) / 4.0
        # 并列校正项:同 |d| 组大小 t 贡献 (t^3 - t)/2
        groups: Dict[float, int] = {}
        for d in diffs:
            k = round(abs(d), 9)
            groups[k] = groups.get(k, 0) + 1
        tie_term = sum(t ** 3 - t for t in groups.values()) / 2.0
        var = (n * (n + 1) * (2 * n + 1) - tie_term) / 24.0
        if var <= 0:
            p, method = 1.0, "degenerate"
        else:
            z = (abs(w_plus - mu) - 0.5) / math.sqrt(var)   # 连续性校正
            p = min(1.0, 2.0 * _normal_sf(max(0.0, z)))
            method = "normal"
    out.update({"w_plus": round(w_plus, 2), "w_minus": round(w_minus, 2),
                "statistic": round(w_min, 2), "p_value": round(p, 5),
                "method": method})
    return out


def stars(p: Optional[float]) -> str:
    """显著性标记;仅作阅读辅助,结论仍以 p 值与效应量为准。"""
    if p is None:
        return "  "
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "* "
    return "  "


# ---------------- 多重比较校正 ----------------
#
# 为什么必须校正:逐格读符号等于在一个算例族上做 10 次检验,而"至少一格显著"在
# 全零假设下的概率远高于名义的 5%(10 次独立检验即 40%)。本文的叙述纪律是"按逐格
# 显著性决定能主张什么",这条纪律若建立在未校正的 p 值上,恰好会在最要紧的地方
# 失效。故凡逐格检验一律按族校正,族的定义(哪 10 个检验算一族)随结果一并报告。
#
# 两种校正都提供,用途不同:Holm 控制族内**至少犯一次**一类错误的概率(FWER),
# 适用于"这一格是否兑现"这种逐格断言;BH 控制被判显著者中的**期望假发现比例**
# (FDR),适用于"这一族里大致有多少格兑现"这种筛选式断言。本文的逐格叙述属于
# 前者,故正文以 Holm 为准,BH 仅作为更宽松的一档一并给出,以免读者误以为
# 校正方式是挑出来的。


def holm(pvals: Sequence[float]) -> List[float]:
    """Holm--Bonferroni 逐步向下校正,返回与输入同序的校正后 p 值。

    校正后 p 值按定义是单调的:排序后第 k 小者乘以 (m-k+1),再对前缀取累计最大值。
    不取累计最大值会得到非单调的序列,于是可能出现"更小的原始 p 反而校正后更大",
    那不是 Holm。
    """
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, (m - k) * pvals[i])
        adj[i] = min(1.0, run)
    return adj


def benjamini_hochberg(pvals: Sequence[float]) -> List[float]:
    """Benjamini--Hochberg 校正(控制 FDR),返回与输入同序的校正后 p 值。"""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i], reverse=True)
    adj = [0.0] * m
    run = 1.0
    for k, i in enumerate(order):
        rank = m - k                      # 该 p 值升序时的位次
        run = min(run, m * pvals[i] / rank)
        adj[i] = min(1.0, run)
    return adj


# ---------------- 效应量:Hodges--Lehmann 点估计与分布无关置信区间 ----------------
#
# 为什么要它:p 值只说"方向可与零区分",不说"差多少、精度如何"。本文报告的点估计
# 是逐对相对增益的均值,它与 Wilcoxon 检验并不同源——检验用的是秩。Hodges--Lehmann
# 伪中位数正是 Wilcoxon 符号秩检验所对应的那个点估计,且它的置信区间可以由同一个
# 零分布直接读出,故"点估计 / 区间 / p 值"三者同源。区间是分布无关的,不假设正态。


def walsh_averages(xs: Sequence[float]) -> List[float]:
    """全部 Walsh 平均 $(x_i+x_j)/2,\\ i\\le j$,升序。共 n(n+1)/2 个。"""
    n = len(xs)
    return sorted((xs[i] + xs[j]) / 2.0
                  for i in range(n) for j in range(i, n))


def hodges_lehmann(xs: Sequence[float]) -> Optional[float]:
    """伪中位数:全部 Walsh 平均的中位数。"""
    if not xs:
        return None
    return median(walsh_averages(xs))


def _signed_rank_counts(n: int) -> List[int]:
    """无并列时 $W^+$ 的零分布计数(下标 = $W^+$ 取值),用子集和 DP 得到。"""
    total = n * (n + 1) // 2
    counts = [0] * (total + 1)
    counts[0] = 1
    for r in range(1, n + 1):
        for s in range(total, r - 1, -1):
            if counts[s - r]:
                counts[s] += counts[s - r]
    return counts


def _normal_ppf(p: float) -> float:
    """标准正态上尾分位点:返回满足 P(Z>z)=p 的 z。二分求解,精度足够且无依赖。"""
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _normal_sf(mid) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def hodges_lehmann_ci(xs: Sequence[float],
                      alpha: float = 0.05) -> Optional[Dict[str, object]]:
    """伪中位数的分布无关置信区间(Hollander--Wolfe 口径)。

    取 $c$ 为满足 $P(W^+\\le c)\\le\\alpha/2$ 的最大整数,则区间端点是升序 Walsh
    平均的第 $c+1$ 与第 $M-c$ 个,$M=n(n+1)/2$。$n\\le$ EXACT_MAX_N 时 $c$ 由精确
    零分布给出,否则用带连续性的正态近似;方法名一并返回,不隐藏近似。

    注意与检验的口径差别:检验按惯例剔除零差值(见 `wilcoxon_signed_rank` 的
    `n_eff`),而单样本 HL 的区间按惯例用**全部** n 个观测,零差值同样参与 Walsh
    平均。两者因此可能在临界处不完全一致,故此处把 n 一并返回供对账。
    """
    n = len(xs)
    if n < 2:
        return None
    w = walsh_averages(xs)
    m = len(w)
    if n <= EXACT_MAX_N:
        counts = _signed_rank_counts(n)
        tot = float(1 << n)
        cum, c = 0, -1
        for val, cnt in enumerate(counts):
            cum += cnt
            if cum / tot <= alpha / 2.0:
                c = val
            else:
                break
        method = "exact"
    else:
        mu = n * (n + 1) / 4.0
        sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
        c = int(math.floor(mu - _normal_ppf(alpha / 2.0) * sd))
        method = "normal"
    c = min(max(c, 0), (m - 1) // 2)
    return {"n": n, "hl": median(w), "lo": w[c], "hi": w[m - c - 1],
            "alpha": alpha, "method": method}
