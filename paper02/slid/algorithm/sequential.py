"""M7 序贯检验:把逐条消息的弱证据累积成可判定的告警。

单条消息的功效在小幅攻击下很低,但序贯累积把它救回来:实测 rho=0.15 时
单条 DR 仅 19.9%,允许 10 条消息延迟的 CUSUM 达到 86.8%;rho=0.10 时
从 10.4% 升到 51.6%。这条对比是论文里"为什么必须要序贯层"的核心证据,
也说明报告口径必须是**给定检测延迟预算下的检出率**,而不是单条检出率。

两种实现:
  cusum  经典 CUSUM,对已知漂移方向最优,阈值由 ARL0 定标。
  eproc  e 过程 / 检验鞅,任意停时下有效,给 anytime-valid 保证,
         不需要为每个 ARL0 重新定标——攻击者不能靠"等到阈值刚好被
         重置"来规避。

两者都消费 M6 输出的合成 p 值,取 -log p 作为增量证据:H0 下 p ~ U(0,1),
故 -log p ~ Exp(1),均值为 1。因此 CUSUM 的松弛量 k 必须 **> 1**,否则
H0 下漂移非负,统计量会无界增长导致必然误报。

M7 sequential testing: accumulate the weak evidence of single messages into a decidable alarm.

Per-message power is low under a small attack, but sequential accumulation recovers it: at rho=0.15 the per-message DR is only 19.9%, while a CUSUM allowed a 10-message delay reaches 86.8%; at rho=0.10 it rises from 10.4% to 51.6%. That comparison is the paper's core evidence for "why a sequential layer is required", and it means the reporting rule must be **detection rate under a given detection-delay budget**, not a per-message detection rate.

Two implementations:
  cusum  classical CUSUM, optimal for a known drift direction; the threshold is set from ARL0.
  eproc  e-process / test martingale, valid at any stopping time, with an anytime-valid guarantee. It does not need a new calibration for each ARL0 — an attacker cannot evade it by waiting until the threshold has just been reset.

Both consume the fused p-value from M6 and take -log p as incremental evidence: under H0, p ~ U(0,1), so -log p ~ Exp(1) with mean 1. The CUSUM slack k must therefore be **> 1**. Otherwise the drift under H0 is non-negative, the statistic grows without bound, and false alarms are inevitable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_PMIN = 1e-12


def evidence(p: float) -> float:
    """单条消息的证据量 -log p。H0 下服从 Exp(1)。

    Evidence of one message, -log p. Under H0 it is Exp(1).
    """
    return -math.log(max(min(p, 1.0), _PMIN))


@dataclass
class CUSUM:
    """S_t = max(0, S_{t-1} + (-log p_t) - k)。

    k 是每条消息的"入场费",必须大于 1(H0 下证据的期望),否则无界增长。
    h 由 calibrate_h 在良性流上按目标 ARL0 反解。

    S_t = max(0, S_{t-1} + (-log p_t) - k).

    k is the per-message "admission fee" and must exceed 1 (the expected evidence under H0), or the statistic grows without bound. h is inverted by calibrate_h on a benign stream for the target ARL0.
    """
    k: float = 1.5
    h: float = 10.0
    s: float = 0.0
    n_since_reset: int = 0

    def __post_init__(self):
        if self.k <= 1.0:
            raise ValueError(
                f"k={self.k} <= 1:H0 下 E[-log p]=1,松弛量不足会必然误报")

    def update(self, p: float) -> bool:
        """吃一条消息,返回是否越过阈值。

        Consume one message and return whether the threshold was crossed.
        """
        self.s = max(0.0, self.s + evidence(p) - self.k)
        self.n_since_reset += 1
        return self.s > self.h

    def reset(self) -> None:
        self.s, self.n_since_reset = 0.0, 0


@dataclass
class EDetector:
    """乘积型检验鞅,阈值 1/alpha 由 Ville 不等式给出 anytime-valid 保证。

    下注函数取 e(p) = kappa * p^(kappa-1),kappa in (0,1)。H0 下
    E[e(p)] = kappa * \\int_0^1 p^(kappa-1) dp = 1,故财富是非负鞅,
    Ville 不等式保证 P(sup_t W_t >= 1/alpha) <= alpha —— **在任意停时下**
    成立,不需要预先固定观测条数。这正是 CUSUM 所缺的性质:CUSUM 的
    ARL0 是平均意义的,攻击者若能观测检测器状态,可以挑刚重置的时刻下手。

    Product test martingale. The threshold 1/alpha gives an anytime-valid guarantee by Ville's inequality.

    The betting function is e(p) = kappa * p^(kappa-1), kappa in (0,1). Under H0, E[e(p)] = kappa * \\int_0^1 p^(kappa-1) dp = 1, so wealth is a non-negative martingale. Ville's inequality guarantees P(sup_t W_t >= 1/alpha) <= alpha — **at any stopping time**, with no need to fix the number of observations in advance. That is the property CUSUM lacks: CUSUM's ARL0 is an average, and an attacker who can see the detector state can strike just after a reset.
    """
    alpha: float = 0.01
    kappa: float = 0.5
    wealth: float = 1.0
    n: int = 0

    def update(self, p: float) -> bool:
        p = max(min(p, 1.0), _PMIN)
        self.wealth *= self.kappa * p ** (self.kappa - 1.0)
        self.n += 1
        return self.wealth >= 1.0 / self.alpha

    def reset(self) -> None:
        self.wealth, self.n = 1.0, 0


def calibrate_h(pvals, target_arl0: int, k: float = 1.5,
                lo: float = 0.5, hi: float = 60.0, iters: int = 50) -> float:
    """在良性校准流上反解 CUSUM 阈值 h 使平均误报间隔达到 target_arl0。

    单调性:h 越大 ARL0 越大,故可二分。返回满足 ARL0 >= target 的最小 h。

    Invert the CUSUM threshold h on a benign calibration stream so the mean false-alarm gap reaches target_arl0.

    Monotone: larger h gives larger ARL0, so binary search works. Returns the smallest h with ARL0 >= target.
    """
    pv = list(pvals)
    if not pv:
        return hi

    def arl0(h: float) -> float:
        c = CUSUM(k=k, h=h)
        runs, since = [], 0
        for p in pv:
            since += 1
            if c.update(p):
                runs.append(since)
                c.reset()
                since = 0
        return float(np.mean(runs)) if runs else float(len(pv) * 2)

    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if arl0(mid) < target_arl0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def run_to_detection(pvals, detector, budget: int | None = None):
    """回放一段流,返回首次告警所需的消息数;未告警返回 None。

    `budget` 是检测延迟预算,超过即算漏报——论文的报告口径就是
    "给定延迟预算下的检出率",不是无限等待下的检出率。

    Replay one stream and return the number of messages until the first alarm; return None if none fires.

    `budget` is the detection-delay budget; exceeding it counts as a miss. The paper reports "detection rate under a given delay budget", not detection rate under unlimited waiting.
    """
    for i, p in enumerate(pvals, start=1):
        if detector.update(p):
            return i
        if budget is not None and i >= budget:
            return None
    return None


def detection_profile(streams, make_detector, budget: int) -> dict:
    """在多段流上统计检出率与延迟分位。

    Detection rate and delay quantiles over many streams.
    """
    delays = []
    n = 0
    for s in streams:
        n += 1
        d = run_to_detection(s, make_detector(), budget=budget)
        if d is not None:
            delays.append(d)
    if n == 0:
        return {"n": 0, "dr": float("nan"), "delays": []}
    out = {"n": n, "dr": len(delays) / n, "delays": [int(d) for d in delays]}
    if delays:
        out["median_delay"] = float(np.median(delays))
        out["p90_delay"] = float(np.percentile(delays, 90))
    return out
