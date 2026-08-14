"""M6 三通道合成。

**注意:早先"不能用 Fisher"的判断已被实测推翻,见 tools/fusion_diag.py。**
原论证是:M3 落到 case 级后结构与互锁都变成横向通道、共享跨设备时序信息,
故不独立。实测下来三通道证据 (-log p) 的两两相关是 -0.030 / -0.008 /
+0.056,基本为零——独立性前提**成立**。而在 score-level 多通道扰动下
Fisher 的功效 (0.413) 远高于 Simes(0.187)与 minp(0.176)。

**生产路径仍然不跑合成。** 把那次扰动做成红队注入器 A8 之后,E1 口径下
加合成路对 A8 是 Δ=-0.04、对 A1-A6 再 Δ=-0.04(结论五十三)。本模块保留
作诊断:换产线用 dependence() 复测独立性,超过 INDEPENDENCE_TOL 时本就
不该合成;即使独立,合成路也不占 alpha 预算。

三条由实测定下的规矩:

1) **必须先逐通道 conformal,再合成;不能先合成再统一校准。**
   原始参数化 p 值远非均匀:8.1% 的良性活动时序 p 值直接触到 1e-12
   裁剪下界(其中 89.8% 是训练折已见过该路线的**真·模型失配**,只有
   10.2% 是冷启动外推)。这些点在 min 型统计量底部形成原子,末端校准
   无法分辨,Simes/minp 的经验 FPR 卡在 0.074 且对 alpha 不敏感。
   先逐通道校准后,四种合成器在名义水平下都有效(FPR 0.010~0.013)。

2) **逐通道校准之后不需要第二层校准。** "先逐通道校准(名义)"与
   "再合成后校准一次"经验 FPR 相当(0.010 对 0.013),但后者多吃一份
   校准集,与 M8 规则 3 的规模硬约束直接冲突。故取前者。

3) **合成不是免费的,生产路径不留合成路。** 在只触碰时序的抢跑下仅时序
   通道 0.110、任何三通道合成 0.042~0.060。score-level misplace 下
   Fisher 0.413 对仅时序 0.108;红队 A8 上三路并行已达 0.560,再加
   Fisher 降到 0.516。见 tools/a8_fisher.py。

依赖若在别的产线上不成立,退回 simes(任意依赖下保守)或 harmonic
(强依赖下稳健);dependence() 提供了可检查该前提的量,不要凭假设选择。

**弃权约定:**通道无法给出 p 值时(时序遇未见路线、结构遇 case 首活动)
按 1.0 计入而非丢弃。p=1 是最保守的取值,既不破坏合成统计量在 H0 下的
有效性,又不会让"缺证据"被误当成"有反证"。
"""
from __future__ import annotations

import math
from typing import Sequence

METHODS = ("fisher", "simes", "harmonic", "minp")
DEFAULT_METHOD = "fisher"
#: 超过此相关度就不该再用 Fisher,退回 simes / harmonic
INDEPENDENCE_TOL = 0.15
_PMIN = 1e-12


def _clean(pvals: Sequence[float]) -> list[float]:
    return [min(max(float(p) if p is not None else 1.0, _PMIN), 1.0)
            for p in pvals]


def simes(pvals: Sequence[float]) -> float:
    """Simes 合成:min_i k * p_(i) / i。任意依赖下保守,PRDS 下精确。"""
    p = sorted(_clean(pvals))
    k = len(p)
    if k == 0:
        return 1.0
    return min(min(k * pi / (i + 1) for i, pi in enumerate(p)), 1.0)


def harmonic_mean_p(pvals: Sequence[float], weights=None) -> float:
    """调和均值 p 值 sum(w) / sum(w_i / p_i)。

    对强依赖稳健,但只在渐近意义上校准;本文一律再走一层 conformal,
    因此这里不做 Landau 修正——修正与否都会被校准吸收。
    """
    p = _clean(pvals)
    if not p:
        return 1.0
    w = list(weights) if weights is not None else [1.0] * len(p)
    denom = sum(wi / pi for wi, pi in zip(w, p))
    return min(sum(w) / denom, 1.0) if denom > 0 else 1.0


def minp(pvals: Sequence[float]) -> float:
    """Bonferroni 型最小 p 值 min(1, k * min p)。最保守。"""
    p = _clean(pvals)
    return min(1.0, len(p) * min(p)) if p else 1.0


def fisher(pvals: Sequence[float]) -> float:
    """X = -2 sum log p ~ chi2(2k)。累积所有通道的证据,故在多通道攻击下
    功效最高;代价是需要通道近似独立——用 dependence() 检查后再用。"""
    p = _clean(pvals)
    k = len(p)
    if k == 0:
        return 1.0
    x = -2.0 * sum(math.log(pi) for pi in p)
    return chi2_sf(x, 2 * k)


def chi2_sf(x: float, df: int) -> float:
    """偶数自由度下的卡方生存函数,闭式:exp(-x/2) * sum_{i<k} (x/2)^i / i!。"""
    if x <= 0:
        return 1.0
    k = df // 2
    half = x / 2.0
    term, total = 1.0, 1.0
    for i in range(1, k):
        term *= half / i
        total += term
    return min(1.0, math.exp(-half) * total)


def dependence(rows: Sequence[Sequence[float]]) -> dict:
    """量化通道间依赖:证据 -log p 的两两 Pearson 相关。

    返回 {(i, j): r} 并附 'max_abs' 与 'fisher_ok'。Fisher 的前提是
    近似独立,这个前提必须在每个部署现场重新测,不能沿用本文在 Trier
    上的 -0.030 / -0.008 / +0.056。
    """
    if not rows:
        return {"max_abs": 0.0, "fisher_ok": True}
    k = len(rows[0])
    ev = [[-math.log(min(max(float(r[j]), _PMIN), 1.0)) for r in rows]
          for j in range(k)]
    out: dict = {}
    worst = 0.0
    for i in range(k):
        for j in range(i + 1, k):
            r = _pearson(ev[i], ev[j])
            out[(i, j)] = r
            worst = max(worst, abs(r))
    out["max_abs"] = worst
    out["fisher_ok"] = worst <= INDEPENDENCE_TOL
    return out


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return cov / math.sqrt(va * vb)


def combine(pvals: Sequence[float], method: str = DEFAULT_METHOD,
            weights: Sequence[float] | None = None) -> float:
    """把各通道 p 值合成为单一 p 值型统计量(越小越异常)。

    输入必须已是**逐通道 conformal 校准后**的 p 值,否则见模块文档规矩 1:
    原始参数化 p 值的裁剪下界会在 min 型统计量底部形成原子。
    """
    if method == "simes":
        return simes(pvals)
    if method == "harmonic":
        return harmonic_mean_p(pvals, weights)
    if method == "minp":
        return minp(pvals)
    if method == "fisher":
        return fisher(pvals)
    raise ValueError(f"未知合成方法: {method};可选 {METHODS}")


def score(pvals: Sequence[float], method: str = DEFAULT_METHOD,
          weights: Sequence[float] | None = None) -> float:
    """转成"越大越异常"的不符合度分数,供序贯层直接消费。"""
    return -combine(pvals, method=method, weights=weights)
