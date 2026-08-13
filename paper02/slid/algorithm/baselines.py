"""基线与消融档位。编号与《新想法.md》"基线(换掉稻草人)"一节一致。

  B1 mbdf        原马尔可夫-贝叶斯双层框架,one-hot + l2 + 边缘概率阈值。
                 用途是实证 T-a 不可能性结果,不只是数值对照。
  B2 markov      一阶马尔可夫似然 -log P,无时长。隔离时序通道的贡献。
  B3 butla       学习型计时自动机(Maier & Niggemann 2011 / BUTLA)。**主基线**
  B4 tabor       计时自动机 + 站内贝叶斯网络(TABOR, AsiaCCS'18)。**主基线**
  B5 hsmm        隐半马尔可夫似然(Tan & Xi, AMC'08)。**主基线**
  B6 lstm_ae     序列自编码器 / Transformer,用于说明算力与可解释性代价
  B7 flow        保留一个流量类(FMM 或 STBAD),历史对照,不作主基线

打不过 B3-B5 方法就不成立;打得过则必须把增益归因到互锁通道,因为单设备
时序那部分它们也有。已核实原文的两个结构性盲区可直接写进结果讨论:

  B3 的并行结构是按**网络拓扑**分解出来的,Def. 1 假设组件顺序执行,检测
     算法在单个自动机上迭代,无跨组件检查 -> A4/A7 结构性无能。它还自陈
     误报问题未解决(人工容差 alpha,无无分布保证),正是 M8 的对照。
  B4 的贝叶斯网络严格限制在同一 stage 内,且显式忽略网络与命令数据
     -> 命令-响应因果配对在其框架内不可表达。

B3/B7 都是逐观测立即判决,无证据累积 -> 弱信号下结构上够不到 CUSUM 的
水平(rho=0.15 时 86.8% 对 19.9%),这是 M7 的对照。

**同一误报预算是本模块的全部要点。** 每个基线自己的原始分数量纲各不相同
(l2 距离、负对数似然、z 值),直接比阈值毫无意义;唯一公平的口径是在**同一
良性校准折**上把各自阈值定到同一经验 FPR,再比检出率。`run_baseline` 只提供
这一种口径,不接受外部传入阈值。

消融(逐档递进,与 clbs 的消融链同构):
  full -> -sequential -> -conformal -> -interlock -> -structural -> -covariate
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

BASELINES = ("mbdf", "markov", "butla", "tabor", "hsmm", "lstm_ae", "flow")

#: 已实现的基线。未实现的一律显式拒绝而不是悄悄退化——理由同 attacks.A7。
IMPLEMENTED = ("mbdf", "markov", "butla", "tabor", "hsmm")

ABLATIONS = ("full", "no_sequential", "no_conformal",
             "no_interlock", "no_structural", "no_covariate")

EPS = 1e-12


# --------------------------------------------------------------------------
# 公共骨架
# --------------------------------------------------------------------------
@dataclass
class _Base:
    """基线的公共接口:拟合、按时间序逐条打分、可重置。

    分数一律**越大越异常**,以便统一用上分位数定阈值。
    """
    name: str = "?"

    def fit(self, train):                       # pragma: no cover - 抽象
        raise NotImplementedError

    def reset(self) -> None:
        pass

    def score(self, act) -> float:              # pragma: no cover - 抽象
        raise NotImplementedError

    def parts(self, act) -> tuple:
        """各子检测器的原始分数。

        分开报是必须的:子分数量纲天差地别(结构违反的哨兵值 vs 时长 z 值),
        直接取 max 会让哨兵值永远压过其它项——实测中 TABOR 因此退化成
        BUTLA、两者检出率逐格相同。正确做法是各子分数先各自转成良性经验
        p 值再取最小(即原文"任一子检测器报警即报警"的语义)。
        """
        return (self.score(act),)

    def score_stream(self, acts) -> list[float]:
        self.reset()
        return [self.score(a) for a in acts]

    def parts_stream(self, acts) -> list[tuple]:
        self.reset()
        return [self.parts(a) for a in acts]


def _quantile(xs, q: float) -> float:
    """经验分位数,不引 numpy——基线要能在只有标准库的环境里跑。"""
    s = sorted(xs)
    if not s:
        return float("inf")
    i = min(len(s) - 1, max(0, int(math.ceil(q * len(s))) - 1))
    return s[i]


def order_stream(acts):
    """时间序,与在线口径一致。"""
    return sorted((a for a in acts if a.t_consume is not None),
                  key=lambda a: (a.t_consume, a.order))


# --------------------------------------------------------------------------
# B1 MBDF:原方法
# --------------------------------------------------------------------------
@dataclass
class MBDF(_Base):
    """B1 原马尔可夫-贝叶斯双层框架。

    偏差 $\\delta = \\lVert \\hat p - e_i \\rVert_2$,自适应阈值
    $\\gamma(1-\\hat p_i)$。**这两者都只依赖 $\\hat p_i$**:
    $\\delta = \\sqrt{\\lVert\\hat p\\rVert^2 - 2\\hat p_i + 1}$ 在给定行内是
    $\\hat p_i$ 的单调减函数,于是判决 $\\delta > \\gamma(1-\\hat p_i)$ 退化成
    对 $\\hat p_i$ 的单阈值——这正是 T-a 不可能性结果的来源:凡预测概率足够
    高的观测标签一律不可标记,与它是否真实无关。

    故本类的分数取 $\\delta/(1-\\hat p_i)$,即原文判决式左右比值;按同一误报
    预算定阈值等价于扫 $\\gamma$。
    """
    states: list = field(default_factory=list)
    idx: dict = field(default_factory=dict)
    counts: list = field(default_factory=list)
    _prev: dict = field(default_factory=dict)

    def fit(self, train):
        self.states = sorted({a.op for a in train})
        self.idx = {s: i for i, s in enumerate(self.states)}
        n = len(self.states)
        self.counts = [[0.0] * n for _ in range(n)]
        prev = {}
        for a in order_stream(train):
            p = prev.get(a.case)
            if p is not None:
                self.counts[self.idx[p]][self.idx[a.op]] += 1.0
            prev[a.case] = a.op
        return self

    def reset(self):
        self._prev = {}

    def score(self, act) -> float:
        prev = self._prev.get(act.case)
        self._prev[act.case] = act.op
        if prev is None or prev not in self.idx or act.op not in self.idx:
            return 0.0                          # 无从判决,按正常
        row = self.counts[self.idx[prev]]
        tot = sum(row)
        if tot <= 0:
            return 0.0
        i = self.idx[act.op]
        phat_i = row[i] / tot
        sq = sum((v / tot) ** 2 for v in row)
        delta = math.sqrt(max(sq - 2.0 * phat_i + 1.0, 0.0))
        return delta / max(1.0 - phat_i, EPS)


# --------------------------------------------------------------------------
# B2 一阶马尔可夫似然
# --------------------------------------------------------------------------
@dataclass
class Markov(_Base):
    """B2 纯结构似然 $-\\log P(o_t \\mid o_{t-1})$,不看时长。

    存在的意义是**隔离时序通道的贡献**:它与本方法的结构通道用同一个转移
    矩阵,差别只在没有时长、没有 conformal、没有序贯累积。
    """
    states: list = field(default_factory=list)
    idx: dict = field(default_factory=dict)
    counts: list = field(default_factory=list)
    alpha: float = 1.0                          # Dirichlet 平滑
    _prev: dict = field(default_factory=dict)

    fit = MBDF.fit
    reset = MBDF.reset

    def score(self, act) -> float:
        prev = self._prev.get(act.case)
        self._prev[act.case] = act.op
        if prev is None or prev not in self.idx:
            return 0.0
        row = self.counts[self.idx[prev]]
        n = len(row)
        tot = sum(row) + self.alpha * n
        c = row[self.idx[act.op]] if act.op in self.idx else 0.0
        return -math.log((c + self.alpha) / tot)


# --------------------------------------------------------------------------
# B3 BUTLA:学习型计时自动机
# --------------------------------------------------------------------------
@dataclass
class BUTLA(_Base):
    """B3 Maier & Niggemann 的学习型计时自动机(主基线)。

    忠实保留原文的三个结构决定,它们同时就是它的三个盲区:

    1. **每个组件一台自动机,组件间无检查。** 原文 Def. 1 假设组件顺序执行,
       检测算法在单台自动机上迭代。故按设备各学一台,状态为该设备的操作,
       跨设备耦合完全不建模 -> A4 结构性无能。
    2. **时长只有区间/正态容差,没有协变量。** 不条件化路线,于是搬运时长的
       方差被路线混合撑大(实测中位 sigma 0.207 -> 条件化后 0.116)。
    3. **逐观测立即判决,无证据累积。** score 只看当条,不跨消息累加。

    分数取"结构不可行"与"时长偏离"的较大者,量纲用 z 值统一。
    """
    trans: dict = field(default_factory=dict)   # 设备 -> {前驱: {后继}}
    dwell: dict = field(default_factory=dict)   # (设备, 操作) -> (mu, sd)
    big: float = 50.0                           # 不可行转移的分数
    _prev: dict = field(default_factory=dict)

    def fit(self, train):
        trans = defaultdict(lambda: defaultdict(set))
        logs = defaultdict(list)
        prev = {}
        for a in order_stream(train):
            key = (a.case, a.device)
            p = prev.get(key)
            if p is not None:
                trans[a.device][p].add(a.op)
            prev[key] = a.op
            if a.duration_s:
                logs[(a.device, a.op)].append(math.log(a.duration_s))
        self.trans = {d: {k: set(v) for k, v in m.items()}
                      for d, m in trans.items()}
        self.dwell = {}
        for k, v in logs.items():
            mu = sum(v) / len(v)
            var = sum((x - mu) ** 2 for x in v) / max(len(v) - 1, 1)
            self.dwell[k] = (mu, max(math.sqrt(var), 1e-3))
        return self

    def reset(self):
        self._prev = {}

    def parts(self, act) -> tuple:
        """(结构不可行, 时长偏离 z)。两台子检测器,任一报警即报警。"""
        key = (act.case, act.device)
        prev = self._prev.get(key)
        self._prev[key] = act.op
        struct = 0.0
        if prev is not None and prev != act.op:
            allowed = self.trans.get(act.device, {}).get(prev)
            if allowed is not None and act.op not in allowed:
                struct = 1.0
        t = 0.0
        d = self.dwell.get((act.device, act.op))
        if d and act.duration_s:
            mu, sd = d
            t = abs(math.log(act.duration_s) - mu) / sd
        return (struct, t)

    def score(self, act) -> float:
        s, t = self.parts(act)
        return max(s * self.big, t)


# --------------------------------------------------------------------------
# B4 TABOR:计时自动机 + 站内贝叶斯网络
# --------------------------------------------------------------------------
@dataclass
class TABOR(_Base):
    """B4 TABOR(AsiaCCS'18,主基线)。

    在 B3 的计时自动机之上,增加一个**严格限制在同一 stage 内**的贝叶斯网络。
    本数据集里 stage 取设备,站内变量取 (操作, 起点, 终点, 结果) —— 原文显式
    忽略网络与命令数据,故 `t_cmd` 一律不可用,命令-响应因果配对在其框架内
    **不可表达**,这是它与本方法 M5 硬层的结构性差别,不是调参能弥补的。

    站内联合概率按朴素分解 $P(op)\\prod P(v \\mid op)$——原文用的是学到的
    站内结构,这里用它的一个上界友好的近似:朴素分解只会**高估**独立性从而
    给 TABOR 更平滑的似然,不会人为压低它的表现。
    """
    auto: BUTLA = field(default_factory=lambda: BUTLA(name="butla"))
    p_op: dict = field(default_factory=dict)        # 设备 -> {操作: 概率}
    p_var: dict = field(default_factory=dict)       # (设备,操作,变量) -> 分布
    alpha: float = 0.5
    _n_var: dict = field(default_factory=dict)

    VARS = ("start_pos", "end_pos", "outcome")

    def fit(self, train):
        self.auto = BUTLA(name="butla").fit(train)
        n_op = defaultdict(lambda: defaultdict(float))
        n_var = defaultdict(lambda: defaultdict(float))
        for a in order_stream(train):
            n_op[a.device][a.op] += 1.0
            for v in self.VARS:
                n_var[(a.device, a.op, v)][getattr(a, v)] += 1.0
        self.p_op = {}
        for d, m in n_op.items():
            tot = sum(m.values())
            self.p_op[d] = {k: v / tot for k, v in m.items()}
        self.p_var = {k: dict(m) for k, m in n_var.items()}
        self._n_var = {k: sum(m.values()) for k, m in n_var.items()}
        return self

    def reset(self):
        self.auto.reset()

    def parts(self, act) -> tuple:
        """(计时自动机的两项, 站内贝叶斯网络负对数似然)。"""
        auto = self.auto.parts(act)
        pm = self.p_op.get(act.device)
        if not pm:
            return auto + (0.0,)
        ll = math.log(max(pm.get(act.op, 0.0), EPS))
        for v in self.VARS:
            key = (act.device, act.op, v)
            dist = self.p_var.get(key)
            if not dist:
                continue
            k = len(dist) + 1
            tot = self._n_var[key] + self.alpha * k
            c = dist.get(getattr(act, v), 0.0)
            ll += math.log((c + self.alpha) / tot)
        return auto + (-ll,)

    def score(self, act) -> float:
        s, t, nll = self.parts(act)
        return max(s * self.auto.big, t, nll)


# --------------------------------------------------------------------------
# B5 HSMM:隐半马尔可夫
# --------------------------------------------------------------------------
@dataclass
class HSMM(_Base):
    """B5 显式时长隐半马尔可夫模型(Tan & Xi, AMC'08 一类,主基线)。

    这是**真正的**隐半马尔可夫,不是把可观测半马尔可夫改个名字——它有隐状态、
    有对隐状态的 EM、有显式时长分布。实现用一个标准等价:**最大时长为 D 的
    显式时长 HSMM 等价于在扩展状态空间 (隐状态 z, 剩余步数 r) 上的 HMM**,
    其转移矩阵由 (A, p) 结构化参数化。于是可以跑标准的带缩放 Baum-Welch,
    M 步再把扩展转移计数映射回 A 与 p:

        A[z,z'] ∝ sum_d xi((z,1) -> (z',d))
        p[z][d] ∝ sum_z0 xi((z0,1) -> (z,d)) + 初始质量

    观测是二元的:操作符号(类别分布)与对数时长(高斯),故它同时用到结构与
    时长信息,是与本方法 M3+M4 对位的基线。隐状态数 K 由**留出集似然**在
    {2,3,4,6} 中选——给基线挑最好的 K 是让利,不是调参作弊。

    与本方法的结构性差别在于它**没有**:参考模型(故不能区分"没见过"与
    "不允许",见结论三十五)、跨设备互锁、无分布的误报保证、跨消息证据累积。
    打得过它才能把增益归因到这四项。
    """
    K: int = 4
    D: int = 6
    iters: int = 40
    k_grid: tuple = (2, 3, 4, 6)
    ops: list = field(default_factory=list)
    oidx: dict = field(default_factory=dict)
    pi0: list = field(default_factory=list)
    A: list = field(default_factory=list)
    pdur: list = field(default_factory=list)
    B: list = field(default_factory=list)
    mu: list = field(default_factory=list)
    sd: list = field(default_factory=list)
    _belief: dict = field(default_factory=dict)

    # -- 序列构造 --------------------------------------------------------
    def _sequences(self, acts):
        by_case = defaultdict(list)
        for a in order_stream(acts):
            by_case[a.case].append(a)
        seqs = []
        for _, v in by_case.items():
            o = [self.oidx.get(a.op, -1) for a in v]
            t = [math.log(a.duration_s) if a.duration_s else None for a in v]
            if o:
                seqs.append((o, t))
        return seqs

    # -- 扩展状态空间 ----------------------------------------------------
    def _expand(self, K, D, A, pdur, pi0):
        S = K * D
        T = [[0.0] * S for _ in range(S)]
        for z in range(K):
            for r in range(1, D + 1):
                s = z * D + (r - 1)
                if r > 1:
                    T[s][z * D + (r - 2)] = 1.0
                else:
                    for z2 in range(K):
                        for d in range(1, D + 1):
                            T[s][z2 * D + (d - 1)] = A[z][z2] * pdur[z2][d - 1]
        pi = [pi0[s // D] * pdur[s // D][s % D] for s in range(S)]
        return T, pi

    def _emit_log(self, K, o, t, B, mu, sd):
        """隐状态的对数发射概率。缺时长的活动只用符号部分。"""
        out = []
        for z in range(K):
            v = math.log(max(B[z][o], EPS)) if o >= 0 else math.log(EPS)
            if t is not None:
                v += (-0.5 * ((t - mu[z]) / sd[z]) ** 2
                      - math.log(sd[z]) - 0.5 * math.log(2 * math.pi))
            out.append(v)
        return out

    # -- EM --------------------------------------------------------------
    def _em(self, seqs, K, D, seed=0):
        import random as _r
        rng = _r.Random(seed)
        O = len(self.ops)
        A = [[1.0 / K] * K for _ in range(K)]
        pdur = [[1.0 / D] * D for _ in range(K)]
        pi0 = [1.0 / K] * K
        B = [[(1.0 + rng.random()) for _ in range(O)] for _ in range(K)]
        B = [[v / sum(r) for v in r] for r in B]
        allt = [t for _, ts in seqs for t in ts if t is not None]
        m0 = sum(allt) / len(allt) if allt else 0.0
        s0 = (math.sqrt(sum((x - m0) ** 2 for x in allt) / len(allt))
              if len(allt) > 1 else 1.0)
        mu = [m0 + (rng.random() - 0.5) * s0 for _ in range(K)]
        sd = [max(s0, 1e-2)] * K

        ll_prev = -float("inf")
        for _ in range(self.iters):
            Texp, piexp = self._expand(K, D, A, pdur, pi0)
            S = K * D
            nA = [[EPS] * K for _ in range(K)]
            nP = [[EPS] * D for _ in range(K)]
            nPi = [EPS] * K
            nB = [[EPS] * O for _ in range(K)]
            wsum = [EPS] * K
            wt = [0.0] * K
            wt2 = [0.0] * K
            ll = 0.0

            for o, ts in seqs:
                n = len(o)
                be = [self._emit_log(K, o[i], ts[i], B, mu, sd)
                      for i in range(n)]
                # 缩放前向
                al = [[0.0] * S for _ in range(n)]
                sc = [0.0] * n
                for s in range(S):
                    al[0][s] = piexp[s] * math.exp(be[0][s // D])
                sc[0] = sum(al[0]) or EPS
                al[0] = [v / sc[0] for v in al[0]]
                for i in range(1, n):
                    for s2 in range(S):
                        acc = 0.0
                        for s1 in range(S):
                            if al[i - 1][s1] and Texp[s1][s2]:
                                acc += al[i - 1][s1] * Texp[s1][s2]
                        al[i][s2] = acc * math.exp(be[i][s2 // D])
                    sc[i] = sum(al[i]) or EPS
                    al[i] = [v / sc[i] for v in al[i]]
                ll += sum(math.log(max(c, EPS)) for c in sc)

                # 缩放后向
                bt = [[0.0] * S for _ in range(n)]
                bt[n - 1] = [1.0] * S
                for i in range(n - 2, -1, -1):
                    for s1 in range(S):
                        acc = 0.0
                        for s2 in range(S):
                            if Texp[s1][s2] and bt[i + 1][s2]:
                                acc += (Texp[s1][s2]
                                        * math.exp(be[i + 1][s2 // D])
                                        * bt[i + 1][s2])
                        bt[i][s1] = acc / sc[i + 1]

                # 累计
                for i in range(n):
                    tot = sum(al[i][s] * bt[i][s] for s in range(S)) or EPS
                    for z in range(K):
                        g = sum(al[i][z * D + r] * bt[i][z * D + r]
                                for r in range(D)) / tot
                        if i == 0:
                            nPi[z] += g
                            for r in range(D):
                                nP[z][r] += (al[0][z * D + r]
                                             * bt[0][z * D + r]) / tot
                        if o[i] >= 0:
                            nB[z][o[i]] += g
                        wsum[z] += g
                        if ts[i] is not None:
                            wt[z] += g * ts[i]
                            wt2[z] += g * ts[i] * ts[i]
                for i in range(n - 1):
                    for z in range(K):
                        s1 = z * D + 0          # 只有 r=1 才会换状态
                        a1 = al[i][s1]
                        if not a1:
                            continue
                        for z2 in range(K):
                            for d in range(1, D + 1):
                                s2 = z2 * D + (d - 1)
                                if not Texp[s1][s2]:
                                    continue
                                x = (a1 * Texp[s1][s2]
                                     * math.exp(be[i + 1][z2])
                                     * bt[i + 1][s2] / sc[i + 1])
                                nA[z][z2] += x
                                nP[z2][d - 1] += x

            # M 步
            pi0 = [v / sum(nPi) for v in nPi]
            A = [[v / sum(r) for v in r] for r in nA]
            pdur = [[v / sum(r) for v in r] for r in nP]
            B = [[v / sum(r) for v in r] for r in nB]
            for z in range(K):
                if wsum[z] > 1e-6:
                    mu[z] = wt[z] / wsum[z]
                    var = wt2[z] / wsum[z] - mu[z] ** 2
                    sd[z] = max(math.sqrt(max(var, 1e-6)), 1e-2)
            if abs(ll - ll_prev) < 1e-4 * max(abs(ll_prev), 1.0):
                break
            ll_prev = ll
        return dict(A=A, pdur=pdur, pi0=pi0, B=B, mu=mu, sd=sd, ll=ll_prev)

    def _loglik(self, seqs, K, D, par) -> float:
        Texp, piexp = self._expand(K, D, par["A"], par["pdur"], par["pi0"])
        S = K * D
        ll = 0.0
        for o, ts in seqs:
            b = list(piexp)
            for i in range(len(o)):
                if i:
                    b = [sum(b[s1] * Texp[s1][s2] for s1 in range(S))
                         for s2 in range(S)]
                e = self._emit_log(K, o[i], ts[i], par["B"], par["mu"],
                                   par["sd"])
                b = [b[s] * math.exp(e[s // D]) for s in range(S)]
                z = sum(b) or EPS
                ll += math.log(z)
                b = [v / z for v in b]
        return ll

    def fit(self, train):
        self.ops = sorted({a.op for a in train})
        self.oidx = {o: i for i, o in enumerate(self.ops)}
        seqs = self._sequences(train)
        cut = max(1, int(len(seqs) * 0.8))
        tr, ho = seqs[:cut], seqs[cut:] or seqs[:1]

        best = None
        for K in self.k_grid:
            par = self._em(tr, K, self.D)
            score = self._loglik(ho, K, self.D, par) / max(
                sum(len(o) for o, _ in ho), 1)
            if best is None or score > best[0]:
                best = (score, K, par)
        _, self.K, par = best
        self.A, self.pdur, self.pi0 = par["A"], par["pdur"], par["pi0"]
        self.B, self.mu, self.sd = par["B"], par["mu"], par["sd"]
        self._Texp, self._piexp = self._expand(self.K, self.D, self.A,
                                               self.pdur, self.pi0)
        return self

    def reset(self):
        self._belief = {}

    def parts(self, act) -> tuple:
        """(结构:符号的预测负对数概率, 时长:条件负对数密度)。

        用**预测**似然而非平滑似然:在线检测只能用过去。分成两项是为了与
        其它基线同口径(各子分数各自转经验 p 值再取最小)。
        """
        S = self.K * self.D
        b = self._belief.get(act.case)
        prior = list(self._piexp) if b is None else \
            [sum(b[s1] * self._Texp[s1][s2] for s1 in range(S))
             for s2 in range(S)]
        pz = [sum(prior[z * self.D + r] for r in range(self.D))
              for z in range(self.K)]
        tot = sum(pz) or EPS
        pz = [v / tot for v in pz]

        o = self.oidx.get(act.op, -1)
        p_sym = sum(pz[z] * self.B[z][o] for z in range(self.K)) \
            if o >= 0 else EPS
        s_sym = -math.log(max(p_sym, EPS))

        s_dur = 0.0
        t = math.log(act.duration_s) if act.duration_s else None
        if t is not None and o >= 0 and p_sym > EPS:
            dens = 0.0
            for z in range(self.K):
                w = pz[z] * self.B[z][o] / p_sym          # P(z | 符号, 历史)
                dens += w * math.exp(
                    -0.5 * ((t - self.mu[z]) / self.sd[z]) ** 2) \
                    / (self.sd[z] * math.sqrt(2 * math.pi))
            s_dur = -math.log(max(dens, EPS))

        e = self._emit_log(self.K, o, t, self.B, self.mu, self.sd)
        post = [prior[s] * math.exp(e[s // self.D]) for s in range(S)]
        z0 = sum(post) or EPS
        self._belief[act.case] = [v / z0 for v in post]
        return (s_sym, s_dur)

    def score(self, act) -> float:
        a, b = self.parts(act)
        return max(a, b)


REGISTRY = {"mbdf": MBDF, "markov": Markov, "butla": BUTLA, "tabor": TABOR,
            "hsmm": HSMM}


# --------------------------------------------------------------------------
# 同一误报预算下的评测
# --------------------------------------------------------------------------
def combine_parts(benign_parts, target_parts) -> list[float]:
    """各子分数先转成良性经验 p 值,再取最小值的相反数作为统一分数。

    这是"任一子检测器报警即报警"的语义,也解决两件事:子分数量纲不可比(哨兵
    值会永远压过 z 值),以及不同基线的子检测器数目不同。经验分布取自**纯良性
    流**,不取自受攻击流——后者的"良性消息"里混着攻击造成的级联效应。
    """
    if not benign_parts:
        return [0.0] * len(target_parts)
    k = len(benign_parts[0])
    cols = [sorted(r[j] for r in benign_parts) for j in range(k)]
    n = len(benign_parts)
    out = []
    for r in target_parts:
        best = 1.0
        for j in range(k):
            # p = 良性中 >= 当前值的比例(离散分数下偏保守,对基线有利)
            lo, hi = 0, n
            col = cols[j]
            while lo < hi:                       # 二分找第一个 >= r[j]
                mid = (lo + hi) // 2
                if col[mid] < r[j]:
                    lo = mid + 1
                else:
                    hi = mid
            best = min(best, (n - lo + 1) / (n + 1))
        out.append(-best)
    return out


def dr_at_alpha(benign_scores, attack_scores, alpha: float):
    """阈值定在**纯良性流**的 1-alpha 分位,再在受攻击消息上算检出率。

    绝不能把阈值定在受攻击流内部的良性消息上:A2 这类原地改写会让后继良性
    消息拿一个伪造的前驱去比对,产生攻击引起的级联触发。把它算成误报会
    (a) 冤枉方法,(b) 在级联率超过 alpha 时使阈值退化为 +inf、检出率假性归零
    ——实测本方法 A2 的 DR 就是这么被测成 0.00 的。
    """
    if not benign_scores or not attack_scores:
        return float("nan"), float("nan")
    thr = _quantile(benign_scores, 1.0 - alpha)
    return (sum(s > thr for s in attack_scores) / len(attack_scores),
            sum(s > thr for s in benign_scores) / len(benign_scores))


def fit_baseline(name: str, train):
    """拟合一个基线。B5 的 EM + K 网格搜索约 20 s,故务必**复用**——每个
    攻击族每个种子重拟合一次会白烧掉六分钟,而训练折是同一份。"""
    if name not in IMPLEMENTED:
        raise NotImplementedError(
            f"基线 {name} 尚未实现。当前仅 {IMPLEMENTED} 可用;"
            f"未实现的基线不得在论文中报告数字。")
    return REGISTRY[name]().fit(train)


def judge(benign_parts, attack_parts, labels, *, alpha: float,
          budget: int = 10, weights=None):
    """所有方法共用的判决口径,返回 (逐消息 DR, FPR, 序贯 DR, 序贯 FPR)。

    `*_parts` 是**每个子检测器一条**分数流(越大越异常)。规则对所有方法
    一视同仁:每个子检测器各自转良性经验 p 值、各自持一个 CUSUM,alpha 预算
    在子检测器间均分,任一触发即算告警。

    为什么不能把子检测器压成一条 min-p 流:那样每条消息的分数都被其它子
    检测器的噪声污染,弱信号在累积时被稀释(结论二十五)。实测把本方法三
    通道压成 min-p 后,A4 的序贯检出率从 0.42 掉到 0.17、反被似然型基线
    超过——那是口径造成的,不是方法造成的。基线同样有 2-3 个子检测器,
    并行是双方都适用的规则,不是给自己开的后门。

    本方法与基线**必须走这同一个函数**。否则一边用检测器自带的 h、另一边
    现场反解,比的就不是通道设计而是两套阈值机器。

    `weights` 给出 alpha 在子检测器间的**非均分**配额(需和为 1,长度与
    `*_parts` 相同,取 0 即完全不给该路预算、该路不参与判决)。默认 None
    即均分。E2 已证明均分不是最优:互锁、Fisher 合成、路线协变量三项的净
    贡献为负(结论四十二至四十四),它们白吃的预算本可以给时序通道。
    **权重只能在校准折上选,在测试折上调即为作弊**,见 tools/alloc.py。
    """
    m = len(benign_parts)
    if weights is None:
        ws = [1.0 / m] * m
    else:
        if len(weights) != m:
            raise ValueError(f"weights 长度 {len(weights)} != 子检测器数 {m}")
        tot = float(sum(weights))
        if tot <= 0:
            raise ValueError("weights 之和必须为正")
        ws = [w / tot for w in weights]
    hit_msg, fp_msg = set(), set()
    fired, fp_seq = set(), set()
    for w, pb_raw, pa_raw in zip(ws, benign_parts, attack_parts):
        if w <= 0:
            continue                    # 不给预算的路不参与判决
        a = alpha * w
        pb = empirical_p(pb_raw, pb_raw)
        pa = empirical_p(pb_raw, pa_raw)
        for i, v in enumerate(pa):
            if v <= a:
                hit_msg.add(i)
        for i, v in enumerate(pb):
            if v <= a:
                fp_msg.add(i)
        f_a, f_b = _cusum_alarms(pb, pa, alpha=a)
        fired |= set(f_a)
        fp_seq |= set(f_b)

    pos = [i for i, v in enumerate(labels) if v]
    neg = [i for i, v in enumerate(labels) if not v]
    n_b = len(benign_parts[0])
    dr = sum(i in hit_msg for i in pos) / len(pos) if pos else float("nan")
    fpr = sum(i in fp_msg for i in neg) / len(neg) if neg else float("nan")
    sdr = (sum(1 for i in pos if any(i <= j <= i + budget for j in fired))
           / len(pos)) if pos else float("nan")
    sfpr = len(fp_seq) / max(n_b, 1)
    return dr, fpr, sdr, sfpr, chance_floor(sfpr, budget)


def chance_floor(fpr: float, budget: int) -> float:
    """延迟预算口径下"纯靠偶然"的检出率地板 1-(1-fpr)^(budget+1)。

    这一项必须与序贯检出率一起报告,否则整张表每个数都虚高一个地板的量。
    判定"第 i 条被篡改消息在 i..i+budget 内出现任一告警即算检出"时,窗口
    里有 budget+1 个机会撞上一次误报;alpha=0.05、预算 10 条时地板高达
    0.43。实测 B1 MBDF 在 alpha=0.05 下六个攻击族全部落在 0.31-0.50,
    而它自己的地板是 0.326——它其实什么都没检出,而**这正是 T-a 不可能性
    结果的预期表现**。不减地板就会把它误读成"原方法也有三成检出率"。
    """
    return 1.0 - (1.0 - fpr) ** (budget + 1)


def _cusum_alarms(benign_p, attack_p, *, alpha: float, k: float = 1.5):
    """在良性流上按 ARL0=1/alpha 反解 h,返回两条流上的告警位置。

    告警后**必须复位**:CUSUM.update 自身不复位,不复位则 S 一旦越过 h 就
    永久停在上方、此后每条消息都告警——基线的序贯误报曾因此虚高到名义值
    的 22 倍,检出率也跟着虚高。calibrate_h 内部的 arl0 是显式复位的,
    两处口径必须一致。
    """
    from algorithm import sequential

    arl0 = max(int(1.0 / alpha), 2)
    if arl0 >= len(benign_p):
        raise ValueError(
            f"良性流只有 {len(benign_p)} 条消息,撑不起 ARL0={arl0} 的反解;"
            f"扩大良性折或放宽 alpha,不要让 h 落到区间下界。")
    h = sequential.calibrate_h(benign_p, arl0, k=k)

    def run(ps):
        c = sequential.CUSUM(k=k, h=h)
        out = []
        for i, p in enumerate(ps):
            if c.update(p):
                out.append(i)
                c.reset()
        return out

    return run(attack_p), run(benign_p)


def run_baseline(name: str, train, calib, benign, attacked, labels, *,
                 alpha: float, spec=None, model=None) -> dict:
    """在同一误报预算下评一个基线,同时给出它的校准漂移。

    `benign` 是与 `attacked` 同一批 case 的**未注入**版本:阈值取它的
    $1-\\alpha$ 分位(oracle,**对基线是让利**,故本方法的优势偏保守),
    DR 在 `attacked` 中被标记的消息上算。

    `fpr_calib` 改用 `calib`(良性、与 train 不重叠)定阈值再在 `benign` 上
    重测,它与名义 alpha 的比值就是该基线在时间序下的校准漂移——基线普遍
    没有无分布保证、阈值靠人工容差,这一项本身是与 M8 的对照结果。
    """
    m = model if model is not None else fit_baseline(name, train)
    pb = m.parts_stream(order_stream(benign))
    pc = m.parts_stream(order_stream(calib))

    st = order_stream(attacked)
    idx = {id(a): i for i, a in enumerate(attacked)}
    lab = [labels[idx[id(a)]] for a in st]
    pa = m.parts_stream(st)

    m = len(pb[0])
    dr, fpr, seq_dr, seq_fpr, floor = judge(
        [[r[j] for r in pb] for j in range(m)],
        [[r[j] for r in pa] for j in range(m)], lab, alpha=alpha)

    s_b = combine_parts(pb, pb)
    thr_c = _quantile(combine_parts(pb, pc), 1.0 - alpha)
    return {
        "name": name,
        "dr": dr,
        "fpr": fpr,
        "seq": seq_dr,
        "seq_fpr": seq_fpr,
        "seq_net": seq_dr - floor,
        "floor": floor,
        "fpr_calib": sum(s > thr_c for s in s_b) / len(s_b),
        "n_pos": sum(lab),
        "n_neg": len(s_b),
    }


def empirical_p(benign_scores, scores) -> list[float]:
    """把任意量纲的分数(越大越异常)转成**良性经验 p 值**。

    所有方法都必经这一步,横向比较才成立:此后每个方法拿到的都是一列
    H0 下近似均匀的 p 值,逐消息阈值与序贯阈值可以用完全相同的机器算。
    """
    col = sorted(benign_scores)
    n = len(col)
    if not n:
        return [1.0] * len(scores)
    out = []
    for s in scores:
        lo, hi = 0, n
        while lo < hi:                       # 第一个 >= s 的位置
            mid = (lo + hi) // 2
            if col[mid] < s:
                lo = mid + 1
            else:
                hi = mid
        out.append((n - lo + 1) / (n + 1))
    return out


def dr_with_sequential(benign_p, attack_p, labels, *, alpha: float,
                       k: float = 1.5, budget: int = 10):
    """给基线**套上同一套序贯累积**,再按同一延迟预算算检出率。

    这一臂是必须做的:否则"本方法序贯 vs 基线逐消息"会被质疑不公平。
    B3/B7 逐观测判决确实是它们的设计属性(也正是 M7 的对照),但 B2/B5 这类
    似然型基线完全可以外挂 CUSUM。加上这一臂,才能把增益**归因**到通道设计
    而不是归因到累积机制。

    ARL0 目标取 1/alpha 而**不能**取更大的值:良性流只有几百条消息,目标
    ARL0 一旦超过流长,零误报会让 ARL0 记作无穷,二分搜索于是返回区间下界
    ——h 被定得过低、序贯检出率虚高。实测中基线曾因此拿到 0.66 的假成绩。
    达成的序贯误报率一并返回,必须核对。
    """
    from algorithm import sequential

    arl0 = max(int(1.0 / alpha), 2)
    if arl0 >= len(benign_p):
        raise ValueError(
            f"良性流只有 {len(benign_p)} 条消息,撑不起 ARL0={arl0} 的反解;"
            f"扩大良性折或放宽 alpha,不要让 h 落到区间下界。")
    h = sequential.calibrate_h(benign_p, arl0, k=k)

    def run(ps):
        """告警后**必须复位**。CUSUM.update 自身不复位,不复位则 S 一旦越过
        h 就永久停在上方、此后每条消息都告警——基线的序贯误报曾因此虚高到
        名义值的 22 倍,检出率也跟着虚高。calibrate_h 内部的 arl0 就是显式
        复位的,两处口径必须一致。"""
        c = sequential.CUSUM(k=k, h=h)
        out = []
        for i, p in enumerate(ps):
            if c.update(p):
                out.append(i)
                c.reset()
        return out

    fired = run(attack_p)
    pos = [i for i, v in enumerate(labels) if v]
    hit = sum(1 for i in pos
              if any(i <= j <= i + budget for j in fired))
    return (hit / len(pos) if pos else float("nan"),
            len(run(benign_p)) / max(len(benign_p), 1))


def run_ablation(arm: str, train, test, spec=None) -> dict:
    raise NotImplementedError


def undetectable_set(transition_matrix, threshold) -> list[tuple[int, int]]:
    """B1 的构造性反例:枚举 (前驱, 观测标签) 中恒落在阈值内的对。

    已实现于 tools/mbdf_undetectable.py,本函数供 run_baseline 复用。
    Trier 实测:6 个前驱状态的 delta 精确为 0(确定性转移),零误报可标记集
    恰为掩码已拒绝集 357/420,全 gamma 网格上 A4 得手率 >= 20.5%。
    """
    raise NotImplementedError
