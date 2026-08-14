"""M4 时序通道:带协变量的半马尔可夫停留时长模型。

半马尔可夫核分解 Q_ij(tau) = P_ij * F_ij(tau),其中 P_ij 正是既有转移矩阵
(严格向后兼容)。停留时长取对数正态,NIG 共轭先验给出闭式 Student-t 后验
预测(小样本时尾部自动变厚,避免误报风暴)。

协变量形态由实测定为**加性 AFT**:
    log tau = mu + a_start + b_end + beta^T x + eps

实测依据:
  - 路线协变量解释 89.3% 的方差,sigma_log 从 0.355 降到 0.116;
    vgr_1 从 0.480 降到 0.149,与 vgr_2 条件后的 0.052 同量级。
  - 加性参数化与逐路线饱和模型残差**完全相等**(差 0.000),因为物料流
    路线图是森林(7 个分组的起点->终点二部图全部无环)。
  - 但森林意味着每条路线都是桥,移除一条即使其端点效应不可辨识,故加性
    模型**无法外推到未见路线**(留一路线残差 0.416,几与不条件化的 0.480
    相同)。未见路线必须回落到 planned_operation_time 冷启动先验,实测
    sigma=0.159,显著优于加性外推的 0.279。

四种观测情形对应四个分支,见 dwell_pvalue。

本模块只依赖 numpy 与标准库:Student-t 的 CDF 由正则化不完全 Beta 函数
自带实现,以免在线检测器为一个分布函数拖进 scipy。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import erf, exp, lgamma, log, log1p, sqrt

import numpy as np

# 只查"太快"的方向性备择。抢跑是有向攻击,双侧白白损失约一半功效
# (rho=0.5 时实测 DR 0.874 对 0.338)。
JUMP, HEARTBEAT, TIMEOUT, INTERVAL = "jump", "heartbeat", "timeout", "interval"

# 人在回路工序在时序通道上不可检测(sigma=1.843 -> rho* 约 98.6%),
# 必须靠互锁通道兜住。这里不是丢弃,而是标记为"时序无信息",
# 让 M6 在合成时不把它当作有效证据。
MANUAL_OPS = frozenset({"/hw/human_review"})
UNINFORMATIVE_SIGMA = 1.0   # sigma 超过此值时 rho* > 90%,时序通道形同虚设

NO_ROUTE = ("-", "-")


# --------------------------------------------------------------------------
# 分布函数(纯标准库实现,避免在线路径依赖 scipy)
# --------------------------------------------------------------------------

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """二分求逆。只在标定时调用几次,精度足够而无需引入 scipy。"""
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _betacf(a: float, b: float, x: float) -> float:
    """不完全 Beta 的连分式(修正 Lentz 法)。"""
    maxit, eps, fpmin = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = fpmin if abs(d) < fpmin else d
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = fpmin if abs(d) < fpmin else d
            c = 1.0 + aa / c
            c = fpmin if abs(c) < fpmin else c
            d = 1.0 / d
            h *= d * c
        if abs(d * c - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (lgamma(a + b) - lgamma(a) - lgamma(b)
          + a * log(x) + b * log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return exp(lb) * _betacf(a, b, x) / a
    return 1.0 - exp(lb) * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, nu: float) -> float:
    """自由度 nu 的标准 Student-t 分布函数。"""
    if nu <= 0:
        return norm_cdf(t)
    if nu > 1e6:
        return norm_cdf(t)
    p = 0.5 * betainc(nu / 2.0, 0.5, nu / (nu + t * t))
    return p if t <= 0 else 1.0 - p


# --------------------------------------------------------------------------
# 观测与模型
# --------------------------------------------------------------------------

@dataclass
class Obs:
    """一次时长观测。log_tau 取自然对数秒。"""
    route: tuple[str, str]
    log_tau: float
    planned_s: float | None = None
    t: datetime | None = None
    outcome: str = "success"


@dataclass
class NIGPrior:
    """Normal-Inverse-Gamma 先验,给出闭式 Student-t 后验预测。

    默认值弱信息且偏保守:sigma 的先验均值约 0.42,略宽于全线无条件尺度
    0.355。宁可先验偏宽——小样本下预测区间自动变宽,避免冷启动误报风暴。
    """
    mu0: float = 0.0
    kappa0: float = 1.0
    alpha0: float = 2.0
    beta0: float = 0.18


@dataclass
class NIGPosterior:
    mu_n: float
    kappa_n: float
    alpha_n: float
    beta_n: float

    @property
    def df(self) -> float:
        return 2.0 * self.alpha_n

    @property
    def scale(self) -> float:
        """后验预测的尺度 sqrt(beta_n (kappa_n + 1) / (alpha_n kappa_n))。"""
        return sqrt(self.beta_n * (self.kappa_n + 1.0)
                    / (self.alpha_n * self.kappa_n))


def nig_update(prior: NIGPrior, residuals) -> NIGPosterior:
    r = np.asarray(residuals, dtype=float)
    n = len(r)
    if n == 0:
        return NIGPosterior(prior.mu0, prior.kappa0, prior.alpha0, prior.beta0)
    rbar = float(r.mean())
    ss = float(((r - rbar) ** 2).sum())
    kappa_n = prior.kappa0 + n
    mu_n = (prior.kappa0 * prior.mu0 + n * rbar) / kappa_n
    alpha_n = prior.alpha0 + n / 2.0
    beta_n = (prior.beta0 + ss / 2.0
              + prior.kappa0 * n * (rbar - prior.mu0) ** 2 / (2.0 * kappa_n))
    return NIGPosterior(mu_n, kappa_n, alpha_n, beta_n)


@dataclass
class DwellModel:
    """单个 (device, op) 分组的时长模型。

    route_effect 存的是**加性 AFT 的拟合位置**而非逐路线均值。在森林结构上
    二者恒等(T4),但存拟合值保证在线查表是 O(1),不必带着设计矩阵。
    """
    device: str
    op: str
    route_effect: dict[tuple[str, str], float] = field(default_factory=dict)
    sigma: float = 0.0
    df: int = 0
    plan_bias: float = 0.0          # \hat c,用于未见路线的冷启动
    stratum: str = "success"        # 必须按 success/failure 分层,见 fit
    posterior: NIGPosterior | None = None
    n: int = 0

    @property
    def informative(self) -> bool:
        """时序通道在本组是否携带有效证据。"""
        return self.op not in MANUAL_OPS and self.sigma < UNINFORMATIVE_SIGMA

    def location(self, route, planned_s: float | None) -> float | None:
        """已见路线取加性 AFT 后验;未见路线回落到 log(plan) + plan_bias。

        两条路都走不通时返回 None——此时时序通道**弃权**,不能拿一个编造的
        位置去算 p 值。弃权由 M6 按"该通道无证据"处理。
        """
        route = tuple(route) if route else NO_ROUTE
        if route in self.route_effect:
            return self.route_effect[route]
        if planned_s and planned_s > 0:
            return log(planned_s) + self.plan_bias
        return None

    def standardise(self, duration_s: float, route=None,
                    planned_s: float | None = None) -> float | None:
        """标准化残差 z。抢跑使 z 变负。"""
        if duration_s is None or duration_s <= 0:
            return None
        loc = self.location(route, planned_s)
        if loc is None or self.sigma <= 0:
            return None
        return (log(duration_s) - loc) / self.sigma


# --------------------------------------------------------------------------
# 拟合
# --------------------------------------------------------------------------

def collect(activities, stratum: str = "success") -> dict:
    """按 (device, op) 收集时长观测。

    只取有正时长的活动。`stratum` 为 None 时不分层(仅供对照实验)。
    """
    out: dict[tuple[str, str], list[Obs]] = {}
    for a in activities:
        d = a.duration_s
        if d is None or d <= 0:
            continue
        if stratum is not None and a.outcome != stratum:
            continue
        route = a.route or NO_ROUTE
        out.setdefault((a.device, a.op), []).append(
            Obs(route=route, log_tau=log(d), planned_s=a.planned_s,
                t=a.t_start, outcome=a.outcome or "success"))
    return out


def _design(routes, s_idx, e_idx):
    X = np.zeros((len(routes), 1 + len(s_idx) + len(e_idx)))
    X[:, 0] = 1.0
    for i, (s, e) in enumerate(routes):
        if s in s_idx:
            X[i, 1 + s_idx[s]] = 1.0
        if e in e_idx:
            X[i, 1 + len(s_idx) + e_idx[e]] = 1.0
    return X


def _fit_additive(routes, y):
    """最小二乘拟合 mu + a_start + b_end。返回 (拟合值, 秩)。"""
    s_idx = {p: i for i, p in enumerate(sorted({s for s, _ in routes}))}
    e_idx = {p: i for i, p in enumerate(sorted({e for _, e in routes}))}
    X = _design(routes, s_idx, e_idx)
    beta, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    return X @ beta, int(rank), (beta, s_idx, e_idx)


def fit_group(device: str, op: str, obs: list[Obs],
              prior: NIGPrior | None = None,
              stratum: str = "success") -> DwellModel | None:
    """拟合单个 (device, op) 分组。

    必须按 `success`/`failure` 分层:hbw_2 /hbw/unload 曾出现 sigma_log=1.798
    而变异系数仅 0.294 的矛盾组合,是重左尾/多峰的典型特征——少量中止执行
    把对数方差抬高而均值稳定。单一对数正态硬拟合会严重高估 sigma。
    """
    if len(obs) < 2:
        return None
    routes = [o.route for o in obs]
    y = np.array([o.log_tau for o in obs], dtype=float)
    fitted, rank, _ = _fit_additive(routes, y)
    resid = y - fitted
    df = max(len(y) - rank, 1)
    sigma = float(sqrt(float((resid ** 2).sum()) / df))

    route_effect = {}
    for r, f in zip(routes, fitted):
        route_effect[r] = float(f)

    # 冷启动偏置:log tau - log(plan) 的均值。planned_operation_time 不是
    # 实际时长的校准估计(实测比值中位数 0.87、跨设备从 0.30 到 1.02),
    # 但作为未见路线的先验位置显著优于加性外推。
    biases = [o.log_tau - log(o.planned_s)
              for o in obs if o.planned_s and o.planned_s > 0]
    plan_bias = float(np.mean(biases)) if biases else 0.0

    post = nig_update(prior or NIGPrior(), resid)
    return DwellModel(device=device, op=op, route_effect=route_effect,
                      sigma=sigma, df=df, plan_bias=plan_bias,
                      stratum=stratum, posterior=post, n=len(obs))


def fit(activities, min_route_n: int = 8, prior: NIGPrior | None = None,
        stratum: str = "success") -> dict[tuple[str, str], DwellModel]:
    """逐 (device, op) 拟合全部分组。

    `min_route_n` 是路线获得自己的效应所需的最少观测数;不足者并入分组的
    共同截距,以免用一两个样本去辨识一个端点效应。
    """
    models = {}
    for (dev, op), obs in collect(activities, stratum=stratum).items():
        counts: dict[tuple[str, str], int] = {}
        for o in obs:
            counts[o.route] = counts.get(o.route, 0) + 1
        kept = [o if counts[o.route] >= min_route_n
                else Obs(NO_ROUTE, o.log_tau, o.planned_s, o.t, o.outcome)
                for o in obs]
        m = fit_group(dev, op, kept, prior=prior, stratum=stratum)
        if m is not None:
            models[(dev, op)] = m
    return models


# --------------------------------------------------------------------------
# 在线打分
# --------------------------------------------------------------------------

def dwell_pvalue(model: DwellModel, duration_s: float, route=None,
                 planned_s: float | None = None, kind: str = JUMP,
                 resolution_s: float = 0.0) -> float | None:
    """按观测情形返回 p 值。无法定位时返回 None(弃权)。

    kind:
      'jump'      状态跳变 -> **左侧** p 值 T_nu(t),只查"太快"(抢跑)。
                  实测单侧对双侧在 rho=0.5 时 DR 为 0.874 对 0.338,
                  方向性备择下双侧白白损失一半功效。
      'heartbeat' 同状态重报 -> 右删失生存函数 1 - T_nu(t),只在"待太久"时报警
      'timeout'   超时无消息 -> 同一生存函数,由定时器在 99.9% 分位触发(覆盖 A6)
      'interval'  周期轮询   -> 区间删失,取区间上端定位(HAI 必需,否则量化
                  误差系统性污染似然;取上端使左侧检验保守,不会因量化误报)
    """
    if duration_s is None or duration_s <= 0:
        return None
    loc = model.location(route, planned_s)
    if loc is None:
        return None
    post = model.posterior
    if post is None or model.sigma <= 0:
        return None
    scale = post.scale * model.sigma
    if scale <= 0:
        return None

    if kind == INTERVAL:
        duration_s = duration_s + max(resolution_s, 0.0)
    t = (log(duration_s) - loc - post.mu_n * model.sigma) / scale
    left = student_t_cdf(t, post.df)
    if kind in (HEARTBEAT, TIMEOUT):
        return max(1.0 - left, 1e-12)
    return max(left, 1e-12)


# --------------------------------------------------------------------------
# 理论界
# --------------------------------------------------------------------------

def rho_star(sigma: float, alpha: float = 0.01, one_sided: bool = True) -> float:
    """理论界:50% 功效对应的抢跑量 rho* = 1 - exp(-z_{1-alpha} * sigma)。

    **z 一律取单侧分位数**(alpha=0.01 -> 2.3263)。抢跑是方向性备择,双侧
    白白损失约一半功效;"滞留/抑制"由 dwell_pvalue 的生存函数分支单独覆盖。
    one_sided=False 仅供论文中做对照。

    **引用 rho* 时必须连同口径一起给**,否则会把两个探针的数字混在一起。
    Trier 上有两套并存且都正确的数字:

      路线条件化、n>=30 的 20 个可建模分组(probe_bound.py,M4 实用口径):
        跨度 1.6%(dm_2 /dm/lower, sigma=0.007)到 98.6%
        (hw_1 /hw/human_review, sigma=1.843);中位分组 sigma=0.155 -> 30.9%;
        13 组 rho* <= 40%;剔除人工工位后最差是 sm_1 /sm/sort 的 51.9%。

      不条件化、n>=5 的 31 个分组(probe_timing.py,改进链条的起点):
        中位 sigma=0.207 -> 38.2%。

    早先的 docstring 把端点取自前者、中位取自后者,是苹果比橘子——
    条件化会把中位从 0.207 压到 0.139(见 group_sigmas 的三档对照),
    正是本通道的收益所在,混用会把这份收益抹掉。

    产线整体可检测性由最易变工序决定,故必须逐组报告而非给全线均值。
    协变量条件化的收益也由本式量化:sigma 0.355 -> 0.116 使 rho*
    从 56.2% 收紧到 23.7%(用未取整的 sigma 算得 23.6%,差异纯属取整)。
    """
    z = norm_ppf(1.0 - alpha) if one_sided else norm_ppf(1.0 - alpha / 2.0)
    return 1.0 - exp(-z * sigma)


def predicted_dr(sigma: float, rho: float, threshold: float,
                 one_sided: bool = True) -> float:
    """理论检出率 Phi(-z - log(1-rho)/sigma)。实测与预测全区间平均绝对
    偏差约 0.03(见 tools/ 的界验证实验)。"""
    if sigma <= 0 or rho <= 0 or rho >= 1:
        return float("nan")
    shift = log(1.0 - rho) / sigma          # 负数
    dr = norm_cdf(-threshold - shift)
    if not one_sided:
        dr += 1.0 - norm_cdf(threshold - shift)
    return dr


# --------------------------------------------------------------------------
# 诊断:支撑 T4 / T5 / T6 的三条断言
# --------------------------------------------------------------------------

def route_graph_is_forest(routes) -> tuple[bool, int, int]:
    """起点->终点二部图是否为森林。返回 (是否森林, 节点数, 边数)。

    森林意味着每条路线都是桥:移除一条,其端点效应即不可辨识。这正是
    "加性与饱和残差完全相等"和"无法外推到未见路线"这两件事的同一根源。
    """
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    acyclic = True
    edges = sorted(set(routes))
    for s, e in edges:
        a, b = find(("s", s)), find(("e", e))
        if a == b:
            acyclic = False
        else:
            parent[a] = b
    nodes = len({("s", s) for s, _ in edges} | {("e", e) for _, e in edges})
    return acyclic, nodes, len(edges)


def _std(v):
    return float(np.std(np.asarray(v, dtype=float), ddof=1)) if len(v) > 2 \
        else float("nan")


def group_sigmas(activities, *, stratum: str | None = None,
                 conditioned: bool = False, min_n: int = 5) -> list[dict]:
    """逐 (device, op) 的 sigma_log,四种口径可自由组合。

    `stratum=None, conditioned=False` 即 probe_timing.py 的基线口径,是本文
    改进链条的起点;`stratum='success', conditioned=True` 是 M4 实际使用的
    口径。把两者并排报告才能说清协变量与分层各自贡献了多少。
    """
    rows = []
    for (dev, op), obs in collect(activities, stratum=stratum).items():
        if len(obs) < min_n:
            continue
        y = np.array([o.log_tau for o in obs], dtype=float)
        if conditioned:
            fitted, rank, _ = _fit_additive([o.route for o in obs], y)
            resid = y - fitted
            df = max(len(y) - rank, 1)
            sigma = float(sqrt(float((resid ** 2).sum()) / df))
        else:
            sigma = float(y.std(ddof=1))
            df = len(y) - 1
        rows.append({"device": dev, "op": op, "n": len(y),
                     "sigma": sigma, "df": df,
                     "routes": len({o.route for o in obs})})
    return sorted(rows, key=lambda r: r["sigma"])


def sigma_summary(rows: list[dict]) -> dict:
    """把逐组表折算成论文里报告的跨度与中位。"""
    if not rows:
        return {"n_groups": 0}
    s = np.array([r["sigma"] for r in rows])
    w = np.array([r["n"] for r in rows], dtype=float)
    return {"n_groups": len(rows), "min": float(s.min()),
            "median": float(np.median(s)), "max": float(s.max()),
            "weighted_mean": float(np.average(s, weights=w))}


def sigma_diagnostics(activities, min_n: int = 15, min_routes: int = 2) -> dict:
    """复现 probe_aft_v2 的四个聚合尺度,用于回归比对。

    返回 pooled / conditioned / loo_additive / loo_planned 四个按样本量
    加权的 sigma_log,以及逐组明细。
    """
    groups = collect(activities, stratum="success")
    per_group, agg = [], {k: [] for k in
                          ("pooled", "conditioned", "loo_additive",
                           "loo_planned")}

    for (dev, op), obs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        obs = [o for o in obs if o.route != NO_ROUTE]
        routes = sorted({o.route for o in obs})
        if len(obs) < min_n or len(routes) < min_routes:
            continue
        y = np.array([o.log_tau for o in obs], dtype=float)
        rs = [o.route for o in obs]

        s_pool = float(y.std(ddof=1))
        fitted, _, _ = _fit_additive(rs, y)
        s_cond = float((y - fitted).std(ddof=1))
        # 逐路线饱和模型:每条路线一个自由均值
        sat = np.array([float(y[[i for i, r in enumerate(rs) if r == o.route]]
                              .mean()) for o in obs])
        s_sat = float((y - sat).std(ddof=1))

        loo_a, loo_p, scorable = [], [], 0
        for r in routes:
            tr = [i for i in range(len(y)) if rs[i] != r]
            te = [i for i in range(len(y)) if rs[i] == r]
            if len(tr) < 5 or not te:
                continue
            b, s2, e2 = _fit_additive([rs[i] for i in tr], y[tr])[2]
            if r[0] in s2 and r[1] in e2:
                scorable += 1
                pred = _design([rs[i] for i in te], s2, e2) @ b
                loo_a.extend(list(y[te] - pred))
            tr_ok = [i for i in tr if obs[i].planned_s]
            te_ok = [i for i in te if obs[i].planned_s]
            if len(tr_ok) >= 5 and te_ok:
                c = float(np.mean([y[i] - log(obs[i].planned_s)
                                   for i in tr_ok]))
                loo_p.extend([y[i] - (log(obs[i].planned_s) + c)
                              for i in te_ok])

        forest, nodes, edges = route_graph_is_forest(routes)
        f_a, f_p = _std(loo_a), _std(loo_p)
        per_group.append({
            "device": dev, "op": op, "n": len(y), "routes": len(routes),
            "forest": forest, "nodes": nodes, "edges": edges,
            "pooled": s_pool, "conditioned": s_cond, "saturated": s_sat,
            "loo_additive": f_a, "loo_planned": f_p,
            "scorable": scorable,
        })
        agg["pooled"].append((s_pool, len(y)))
        agg["conditioned"].append((s_cond, len(y)))
        if not np.isnan(f_a):
            agg["loo_additive"].append((f_a, len(loo_a)))
        if not np.isnan(f_p):
            agg["loo_planned"].append((f_p, len(loo_p)))

    out = {"groups": per_group}
    for k, pairs in agg.items():
        if pairs:
            v = np.array([x[0] for x in pairs])
            w = np.array([x[1] for x in pairs], dtype=float)
            out[k] = float(np.average(v, weights=w))
        else:
            out[k] = float("nan")
    out["additive_saturated_gap"] = max(
        (abs(g["conditioned"] - g["saturated"]) for g in per_group),
        default=0.0)
    out["all_forest"] = all(g["forest"] for g in per_group)
    return out
