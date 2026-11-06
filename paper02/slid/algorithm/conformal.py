"""M8 conformal 校准:无分布假设的误报率控制,且不需要攻击标签。

这是全篇最关键的工程细节,三条必须遵守的规则都是被实测打出来的:

1) **随机化(平滑) p 值是离散通道的必要条件,不是可选项。**
   朴素 conformal 在 (设备, case) 链上经验 FPR 直接到 1.000(名义 0.05
   与 0.01 皆然),因为该通道的 p 值只有 1 个取值,校准分位数恰好落在那个
   原子上,于是全部测试点被判异常。改随机化后取值数从 1 升到 99,
   FPR 变为 0.051 / 0.010,几乎精确。

2) **校准集划分必须随机,不能按 case id 字典序切。**
   case id 形如 `WF_101_0`,字典序切会把不同工作流整块分到不同折;
   工作流之间转移集合的 Jaccard 重叠中位仅 0.324,交换性因此被破坏。

3) **校准集规模是硬约束。** 有限样本下可达的最小名义水平是
   1/(n_calib+1)。alpha=0.01 需要 n_calib >= 99,alpha=0.001 需要 999。
   逐设备逐操作分组校准很容易跌破这条线——此时"经验 FPR 0.000"
   不是模型好,是根本无法产生那么小的 p 值。
   论文中每个 alpha 都必须同时报告有效校准集规模。

对照组保留高斯阈值,用以量化分布假设的代价:实测名义 0.01 下,
高斯阈值给出双侧 0.0196、单侧 0.0140,而 conformal 给出 0.0028 / 0.0084。

**约定:score 越大越异常。**通道给出的 p 值(越小越异常)须以 -p 传入。

M8 conformal calibration: distribution-free false-alarm control, with no attack labels required.

This is the most important engineering detail in the paper. The three rules below were all forced by measurement:

1) **A randomized (smoothed) p-value is required on discrete channels, not optional.**
   Naive conformal on a (device, case) chain reaches an empirical FPR of 1.000 (at both nominal 0.05 and 0.01), because that channel's p-value takes only one value, the calibration quantile lands on that atom, and every test point is declared anomalous. After randomization the value count rises from 1 to 99, and the FPR becomes 0.051 / 0.010, nearly exact.

2) **The calibration split must be random, not a lexicographic cut on case id.**
   Case ids look like `WF_101_0`. A lexicographic cut puts whole workflows into different folds; the median Jaccard overlap of transition sets across workflows is only 0.324, so exchangeability breaks.

3) **Calibration-set size is a hard constraint.** With a finite sample the smallest reachable nominal level is 1/(n_calib+1). alpha=0.01 needs n_calib >= 99; alpha=0.001 needs 999. Per-device, per-operation group calibration easily falls below that line — an "empirical FPR of 0.000" then means the sample cannot produce so small a p-value, not that the model is good. Every alpha in the paper must also report the effective calibration-set size.

The control arm keeps a Gaussian threshold to quantify the cost of the distributional assumption: at nominal 0.01 the Gaussian threshold gives 0.0196 two-sided and 0.0140 one-sided, while conformal gives 0.0028 / 0.0084.

**Convention: a larger score is more anomalous.** A channel p-value (smaller is more anomalous) must be passed in as -p.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Calibrator:
    """一个分组的 conformal 校准器。scores 越大越异常。

    One group's conformal calibrator. Larger scores are more anomalous.
    """
    group: tuple = ()
    scores: list[float] = field(default_factory=list)
    _sorted: np.ndarray | None = field(default=None, repr=False)

    def add(self, score: float) -> None:
        self.scores.append(float(score))
        self._sorted = None

    def freeze(self) -> "Calibrator":
        """排序一次,之后 pvalue 走二分,单条消息 O(log n)。

        Sort once; pvalue then binary-searches, O(log n) per message.
        """
        self._sorted = np.sort(np.asarray(self.scores, dtype=float))
        return self

    @property
    def n(self) -> int:
        return len(self.scores)

    @property
    def min_alpha(self) -> float:
        """有限样本可达的最小名义水平。

        Smallest nominal level reachable with a finite sample.
        """
        return 1.0 / (self.n + 1)

    def reachable(self, alpha: float) -> bool:
        """alpha 是否可达。不可达时任何"零误报"都是假象,必须在报告中标注。

        Whether alpha is reachable. If it is not, any "zero false-alarm" figure is illusory and must be marked in the report.
        """
        return alpha >= self.min_alpha

    def pvalue(self, score: float, rng=None, randomised: bool = True) -> float:
        """随机化 conformal p 值:

            p = (#{s_i > s} + U * (1 + #{s_i == s})) / (n + 1)

        交换性成立时 p 在 (0,1] 上精确均匀。`randomised=False` 取 U=1,
        即朴素形式,仅供论文中做对照——它在离散通道上会使 FPR 失控。

        Randomized conformal p-value:

            p = (#{s_i > s} + U * (1 + #{s_i == s})) / (n + 1)

        Under exchangeability, p is exactly uniform on (0,1]. `randomised=False` sets U=1, the naive form, kept only as a paper control — on discrete channels it lets the FPR run away.
        """
        if self._sorted is None:
            self.freeze()
        s = self._sorted
        n = len(s)
        if n == 0:
            return 1.0
        lo = int(np.searchsorted(s, score, side="left"))
        hi = int(np.searchsorted(s, score, side="right"))
        gt, eq = n - hi, hi - lo
        u = (rng.random() if rng is not None else np.random.random()) \
            if randomised else 1.0
        return (gt + u * (1.0 + eq)) / (n + 1.0)

    def threshold(self, alpha: float) -> float:
        """分位数形式的等价阈值,便于与非 conformal 基线并排比较。

        Equivalent threshold in quantile form, for side-by-side comparison with non-conformal baselines.
        """
        if self._sorted is None:
            self.freeze()
        return float(np.quantile(self._sorted, 1.0 - alpha))


@dataclass
class ConformalBank:
    """按 Mondrian 键分组的校准器集合,组内样本不足时回落到全局组。

    回落次数必须报告:它直接反映规则 3 与分组粒度之间的张力。

    Calibrators grouped by Mondrian key, falling back to the global group when a group is too small.

    The fallback count must be reported: it is the tension between rule 3 and group granularity.
    """
    min_size: int = 30
    groups: dict = field(default_factory=dict)
    pooled: Calibrator = field(default_factory=Calibrator)
    n_fallback: int = 0

    def add(self, key, score: float) -> None:
        self.groups.setdefault(key, Calibrator(group=key)).add(score)
        self.pooled.add(score)

    def freeze(self) -> "ConformalBank":
        for c in self.groups.values():
            c.freeze()
        self.pooled.freeze()
        return self

    def _pick(self, key) -> Calibrator:
        c = self.groups.get(key)
        if c is None or c.n < self.min_size:
            self.n_fallback += 1
            return self.pooled
        return c

    def pvalue(self, key, score: float, rng=None,
               randomised: bool = True) -> float:
        return self._pick(key).pvalue(score, rng=rng, randomised=randomised)

    def size_report(self) -> dict:
        """每个 alpha 下有效校准集规模的分布,论文里必须给。

        Distribution of the effective calibration-set size at each alpha; the paper must report it.
        """
        sizes = sorted(c.n for c in self.groups.values())
        if not sizes:
            return {"n_groups": 0, "pooled": self.pooled.n}
        return {"n_groups": len(sizes), "min": sizes[0],
                "median": sizes[len(sizes) // 2], "max": sizes[-1],
                "pooled": self.pooled.n,
                "min_alpha_worst": 1.0 / (sizes[0] + 1),
                "min_alpha_pooled": self.pooled.min_alpha}


def split(items, frac=(0.5, 0.25, 0.25), seed: int = 42):
    """train / calib / test 随机划分。**不要**按 id 排序后顺序切。

    返回三个列表。`items` 通常是 case 键,以保证同一 case 的活动不跨折——
    否则同案内的强相关会让校准集乐观。

    Random train / calib / test split. **Do not** sort by id and then cut in order.

    Returns three lists. `items` is usually the case key, so one case's activities do not cross folds — otherwise strong within-case correlation would make the calibration set optimistic.
    """
    items = list(items)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(items))
    n = len(items)
    a = int(n * frac[0])
    b = int(n * (frac[0] + frac[1]))
    return ([items[i] for i in idx[:a]],
            [items[i] for i in idx[a:b]],
            [items[i] for i in idx[b:]])


def split_lexicographic(items, frac=(0.5, 0.25, 0.25)):
    """反例对照:按 id 字典序切。case id 形如 `WF_101_0`,这会把不同
    工作流整块分开,破坏交换性。仅用于论文中展示后果,不可用于生产。

    Counterexample control: cut by lexicographic id. Case ids look like `WF_101_0`, which separates workflows in blocks and breaks exchangeability. For showing the consequence in the paper only; not for production.
    """
    items = sorted(items)
    n = len(items)
    a = int(n * frac[0])
    b = int(n * (frac[0] + frac[1]))
    return items[:a], items[a:b], items[b:]


def mondrian_groups(act) -> tuple:
    """Mondrian 分组键。按 (device, op, outcome) 分组可保证条件覆盖率,
    但会稀释每组样本量,与规则 3 直接冲突——分组粒度须与目标 alpha
    联合选择,并在论文中报告每组规模分布(见 ConformalBank.size_report)。

    Mondrian grouping key. Grouping by (device, op, outcome) gives conditional coverage, but it thins each group's sample and conflicts directly with rule 3 — granularity must be chosen jointly with the target alpha, and the per-group size distribution must be reported (see ConformalBank.size_report).
    """
    return (act.device, act.op, act.outcome or "success")


def gaussian_threshold(scores, alpha: float) -> float:
    """对照用参数化阈值 mu + z_{1-alpha} * sigma。

    论文中用于量化分布假设带来的误报代价:真实残差的尾部不是高斯的,
    实测名义 0.01 下高斯阈值给出 0.0196(双侧),接近名义值的两倍。

    Parametric control threshold mu + z_{1-alpha} * sigma.

    Used in the paper to quantify the false-alarm cost of a distributional assumption: the real residual tail is not Gaussian. At nominal 0.01 the Gaussian threshold gives 0.0196 (two-sided), nearly twice the nominal level.
    """
    s = np.asarray(scores, dtype=float)
    if s.size == 0:
        return float("inf")
    z = _norm_ppf(1.0 - alpha)
    return float(s.mean() + z * s.std(ddof=1))


def _norm_ppf(p: float) -> float:
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if 0.5 * (1.0 + math.erf(mid / math.sqrt(2.0))) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def empirical_fpr(p_calib, p_test, alpha: float) -> float:
    """用校准折的 alpha 分位数作阈值,量测测试折上的经验误报率。

    这是探针脚本使用的口径,与"conformal p 值 <= alpha"等价,
    保留它是为了让实现与 database/ 下的结果可逐位比对。

    Use the alpha quantile of the calibration fold as the threshold and measure the empirical false-alarm rate on the test fold.

    This is the probe scripts' reporting rule. It matches "conformal p-value <= alpha", and it is kept so the implementation can be checked digit by digit against the results under database/.
    """
    if len(p_calib) == 0 or len(p_test) == 0:
        return float("nan")
    thr = float(np.quantile(np.asarray(p_calib, dtype=float), alpha))
    return float((np.asarray(p_test, dtype=float) <= thr).mean())
