"""M3 结构通道:Dirichlet 后验预测的转移似然。

**粒度是 case 级工作流活动序列,不是设备级状态链。**

实测依据:按 (设备, case) 建链后 2,109 条链中 65.1% 长度为 1、28.5% 长度
为 2,3,062 个活动只产出 953 次转移,且全部结构 p 值取值唯一——设备级通道
携带的信息量为零。根因是本产线的设备是无状态服务端点,每个作业只被调用
一到两次;原方法设想的"AGV 空闲/移动/装载"式设备内状态机在这个粒度上
不存在,它位于子日志的 109 个细粒度子活动里。

case 级链:21 个状态、2,780 次转移、282 个 case、140 个变体,样本量与状态
数之比健康(132:1),后验不再被先验主导。

p 值**必须取随机化(平滑)形式**,否则原子化会让 conformal 校准彻底失效
(实测朴素形式在 (设备, case) 链上经验 FPR 达 1.000)。

M3 structural channel: transition likelihood under a Dirichlet posterior predictive.

**The granularity is the case-level workflow activity sequence, not a device-level state chain.**

Measured basis: after chaining by (device, case), 65.1% of 2,109 chains have length 1 and 28.5% have length 2; 3,062 activities yield only 953 transitions, and every structural p-value takes a single value — the device-level channel carries zero information. The cause is that devices on this line are stateless service endpoints, each job calling them once or twice; the device-internal state machine the original method imagined ("AGV idle/move/load") does not exist at this granularity. It lives in the 109 fine-grained sub-activities of the sub-logs.

Case-level chain: 21 states, 2,780 transitions, 282 cases, 140 variants. The sample-to-state ratio is healthy (132:1), and the posterior is no longer dominated by the prior.

The p-value **must be the randomized (smoothed) form**. Otherwise atoms make conformal calibration fail completely (the naive form reaches an empirical FPR of 1.000 on a (device, case) chain).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DIRICHLET_ALPHA0 = 0.5      # Jeffreys 型浓度参数,消除小样本伪零概率
# Jeffreys concentration; removes small-sample pseudo-zeros
_EPS = 1e-15


@dataclass
class TransitionModel:
    states: list[str] = field(default_factory=list)
    counts: np.ndarray | None = None      # (k, k)
    mask: np.ndarray | None = None        # F 强制的真零,与伪零区分 / true zeros forced by F, distinct from pseudo-zeros
    index: dict = field(default_factory=dict)
    alpha0: float = DIRICHLET_ALPHA0

    def predictive(self, prev: str) -> np.ndarray | None:
        """行后验预测分布。掩码强制的真零必须保留,不能被先验抹平。

        伪零(样本没见过)与真零(模型禁止)是两回事:前者该被 Dirichlet
        先验抬成小正数,后者必须严格为 0,否则 F 的硬约束会被 M3 悄悄软化。

        Row posterior predictive. True zeros forced by the mask must be kept; the prior must not smooth them away.

        A pseudo-zero (unseen in the sample) and a true zero (forbidden by the model) are different: the former should be lifted to a small positive by the Dirichlet prior; the latter must stay exactly 0, or M3 would quietly soften the hard constraint F.
        """
        i = self.index.get(prev)
        if i is None or self.counts is None:
            return None
        row = self.counts[i] + self.alpha0
        if self.mask is not None:
            row = np.where(self.mask[i], row, 0.0)
        total = row.sum()
        if total <= 0:
            return None
        return row / total

    @property
    def n_transitions(self) -> int:
        return int(self.counts.sum()) if self.counts is not None else 0


def fit(case_chains, model=None, alpha0: float = DIRICHLET_ALPHA0,
        states=None) -> TransitionModel:
    """在 case 级活动序列上估计转移计数。

    `case_chains` 是 {case: [活动或操作名, ...]}。`model` 给出 F 用于设置
    真零;当前 F 是**设备内**可达关系,在 case 级跨设备转移上不直接适用,
    因此默认不加掩码——要加须先从 BPMN 导出 case 级的活动可达关系,
    那是一项独立的推导,不能拿设备级 F 顶替。

    `states` 可显式给定状态全集,避免不同折推出不同维度的矩阵。

    Estimate transition counts on case-level activity sequences.

    `case_chains` is {case: [activity or operation name, ...]}. `model` supplies F for the true zeros. The current F is **within-device** reachability and does not apply directly to case-level cross-device transitions, so the mask is off by default — adding it requires a case-level activity reachability relation exported from BPMN, a separate derivation that a device-level F cannot stand in for.

    `states` may give the full state set explicitly, so different folds do not produce matrices of different dimension.
    """
    seqs = {k: [_op(x) for x in v] for k, v in case_chains.items()}
    if states is None:
        states = sorted({s for v in seqs.values() for s in v})
    states = list(states)
    index = {s: i for i, s in enumerate(states)}
    k = len(states)
    counts = np.zeros((k, k), dtype=float)
    for v in seqs.values():
        for a, b in zip(v, v[1:]):
            ia, ib = index.get(a), index.get(b)
            if ia is not None and ib is not None:
                counts[ia, ib] += 1.0

    mask = None
    if model is not None:
        mask = np.zeros((k, k), dtype=bool)
        for a, ia in index.items():
            for b, ib in index.items():
                mask[ia, ib] = model.allows_activity(a, b) \
                    if hasattr(model, "allows_activity") else True
    return TransitionModel(states=states, counts=counts, mask=mask,
                           index=index, alpha0=alpha0)


def _op(x):
    return x if isinstance(x, str) else x.op


def struct_pvalue(tm: TransitionModel, prev: str, cur: str,
                  randomised: bool = True, rng=None) -> float | None:
    """随机化结构 p 值:

        p = sum_{j: P_j < P_cur} P_j + U * sum_{j: P_j == P_cur} P_j,  U~Unif(0,1)

    这是"观测到的转移有多不可能"的概率积分变换。`randomised=False` 仅供
    论文中做对照,展示朴素形式如何使 FPR 失控;生产路径一律用随机化形式。

    前驱状态未见过时返回 None(弃权),不能拿一个编造的分布去打分。

    Randomized structural p-value:

        p = sum_{j: P_j < P_cur} P_j + U * sum_{j: P_j == P_cur} P_j,  U~Unif(0,1)

    This is the probability-integral transform of "how unlikely the observed transition is". `randomised=False` is only a paper control, to show how the naive form lets the FPR run away; the production path always randomizes.

    Return None (abstain) when the predecessor state was never seen. Do not score against an invented distribution.
    """
    pred = tm.predictive(prev)
    j = tm.index.get(cur)
    if pred is None or j is None:
        return None
    p_obs = pred[j]
    below = float(pred[pred < p_obs - _EPS].sum())
    at = float(pred[np.abs(pred - p_obs) <= _EPS].sum())
    u = (rng.random() if rng is not None else np.random.random()) \
        if randomised else 1.0
    return below + u * at


def struct_score(tm: TransitionModel, prev: str, cur: str) -> float | None:
    """非 p 值的结构不符合度:直接取预测概率 P(cur|prev),越小越异常。

    **为什么要有这个函数,而 `struct_pvalue` 不够用。**随机化 PIT
    p = below + U*at 对单个转移是精确均匀的,但它把"尾部并列的原子"摊成
    了一段区间:Dirichlet 平滑下几十个从未见过的转移概率完全相等,于是
    at 是一大块尾部质量,一个真正罕见的转移有大约一半机会拿到高于 alpha
    的 p 值。这与结论二十九里时序通道的 p 值撞地板是同一类错误——把有序
    的证据压成了无序。

    交给后面的 conformal 层时,单调分数就够了:分辨率由良性经验分布提供,
    并列由 conformal 自己的随机化在**阈值处**打破一次,而不是在每条消息
    上各摊一次。这与"离散通道一律取随机化 p 值"(结论十四)并不矛盾:那
    条约束针对的是**直接拿去比 alpha** 的 p 值,不是喂给校准器的分数。

    前驱或当前状态未见过时返回 None(弃权)。

    Non-p-value structural nonconformity: the predictive probability P(cur|prev) itself; smaller is more anomalous.

    **Why this function exists, and why `struct_pvalue` is not enough.** The randomized PIT p = below + U*at is exactly uniform for a single transition, but it spreads a "tied atom in the tail" into an interval: under Dirichlet smoothing, dozens of never-seen transitions have exactly equal probability, so `at` is a large tail mass and a truly rare transition has about a half chance of drawing a p-value above alpha. This is the same kind of error as the timing channel's p-value hitting the floor in conclusion 29 — ordered evidence is crushed into unordered evidence.

    When the score is handed to the later conformal layer, a monotone score is enough: resolution comes from the benign empirical distribution, and ties are broken once by conformal's own randomization **at the threshold**, not once per message. That does not contradict "discrete channels always use a randomized p-value" (conclusion 14): that constraint is about p-values **compared directly with alpha**, not about scores fed to a calibrator.

    Return None (abstain) when the predecessor or the current state was never seen.
    """
    pred = tm.predictive(prev)
    j = tm.index.get(cur)
    if pred is None or j is None:
        return None
    return float(pred[j])


def pvalue_stream(tm: TransitionModel, case_chains, keys=None,
                  randomised: bool = True, rng=None) -> list[float]:
    """在若干 case 上批量打分,返回全部转移的结构 p 值。

    Score several cases in batch and return the structural p-value of every transition.
    """
    out = []
    for k in (keys if keys is not None else case_chains):
        seq = [_op(x) for x in case_chains[k]]
        for a, b in zip(seq, seq[1:]):
            p = struct_pvalue(tm, a, b, randomised=randomised, rng=rng)
            if p is not None:
                out.append(p)
    return out


def device_case_chains(acts) -> dict:
    """(设备, case) 链,仅用于复现"设备级通道为空"的反例。

    (device, case) chains, used only to reproduce the counterexample that the device-level channel is empty.
    """
    chains: dict = {}
    for a in acts:
        chains.setdefault((a.device, a.case), []).append(a)
    for v in chains.values():
        v.sort(key=lambda a: (a.t_consume, a.order))
    return chains
