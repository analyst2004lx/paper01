"""M0/M9 在线检测器:把各通道串成一条每消息 O(1) 的处理流水线。

这是一个**回放驱动**而非生产级在线系统:没有传输层、线程与持久化,但
消息的处理顺序、可见信息范围与状态更新时机都严格按在线语义,因此可以
用它回答三个批处理回答不了的问题:

  1. **时间序下 conformal 保证是否幸存。** 之前所有实验都用随机折划分,
     而 M8 规则 3 恰恰要求随机划分来保交换性——可现场部署没有"随机
     划分"这个选项,只能用过去拟合、对未来判定。这两件事是冲突的,
     必须实测,见 tools/online_diag.py。
  2. **逐消息时延**(E8)。O(1) 是可论证的,常数因子只能实测。
  3. **门控更新的抗投毒作用**(与原专利"无条件在线更新"的实质差别)。

单条消息的处理顺序不可调换:

    1. 硬层互锁 (M5)      物理不可能 -> 立即报警并**丢弃**该消息,
                          不能让它进入任何通道的在线更新,否则攻击者
                          可以用注入数据毒化自己的检测基线。
    2. 时序 p 值 (M4)     Student-t 后验预测,O(1)
    3. 结构 p 值 (M3)     一次行查表,O(1)
    4. 软层互锁 p 值 (M5)
    5. 逐通道 conformal (M8)  必须在合成**之前**,见 fusion 模块规矩 1
    6. 合成       (M6)    Fisher;同时保留逐通道判决,两路并行
    7. 序贯       (M7)    CUSUM / e 过程
    8. 在线更新   (M9)    仅当前 7 步全部通过且隔离窗口内无告警

第 8 步的门控是抗投毒的关键。

**在线与离线的三处必要差异**(不是简化,是在线不可能获得的信息):

  - 互锁软层不再区分 LATE / NEVER / FAILED。这三者靠"该令牌是否由本
    case 稍后产出"来归因,需要向后看,在线只能报"前置令牌缺失"。
  - 令牌状态按 case 常驻,活动开始时消耗、结束时产出,与 interlock
    的 _timeline 语义一致,但由到达事件驱动而非预先排序。
  - 看门狗按每 (设备, 操作) 的生存函数分位触发,覆盖 A6;它是唯一
    "没有消息也会报警"的路径。
"""
from __future__ import annotations

import bisect
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from . import conformal, fusion, interlock, sequential, structural, timing

CHANNELS = ("time", "struct", "inter")


@dataclass
class Alarm:
    t: object
    device: str
    case: str
    level: str                    # 'hard' | 'sequential' | 'watchdog'
    channel: str                  # 触发通道,用于可解释归因
    stat: float
    explanation: str


@dataclass
class DetectorConfig:
    alpha: float = 0.01
    arl0: int = 1000
    fusion: str = "fisher"
    sequential: str = "cusum"
    one_sided_timing: bool = True
    online_update: bool = True
    quarantine: int = 20          # 告警后暂停在线更新的消息数
    #: False = 复现原专利的**无条件**在线更新(告警也照吃),仅作对照臂。
    #: 实测无门控时攻击者能把 26.4% 的抢跑喂成新常态,门控后 1.4%。
    gated_update: bool = True
    cusum_k: float = 1.5
    watchdog_q: float = 0.999     # 超时判定分位,覆盖 A6
    ewma: float = 0.95            # M9 参数更新的遗忘因子
    #: alpha 预算在"合成"与"逐通道"两路间划分。实测合成在单通道攻击下
    #: 稀释功效约 2.5 倍、在多通道攻击下反超 4 倍,故两路都要留预算。
    budget_fused: float = 0.5
    #: 结构通道 case 级链的状态取 'op'(操作名)还是 'device_op'((设备,操作))。
    #: 'op' 使结构通道**设备盲**——"错误的设备做了正确的操作"看不见,只能靠
    #: 覆盖率仅 31% 的 F 掩码。'device_op' 恢复设备敏感性,代价是状态数上升、
    #: 每个转移的支撑度被稀释。取值由 tools/struct_diag.py 实测决定。
    struct_state: str = "op"
    #: 时序通道的不符合度分数取 'z'(标准化残差)还是 'pvalue'。
    #: **必须取 z。** p 值在 1e-12 处被裁剪,而 8.1% 的良性活动就落在那儿,
    #: 于是尾部完全没有分辨率——conformal 分不开"30% 抢跑"与"良性失配",
    #: A3 的检出率被压到 0.03。z 连续无界,保住了尾部信息。
    timing_score: str = "z"
    #: 结构通道的不符合度分数取 'prob'(预测概率)还是 'pvalue'(随机化 PIT)。
    #: **必须取 prob**,理由与 timing_score 同型:随机化 PIT 的 U*at 项把
    #: Dirichlet 平滑造成的一大片并列尾部原子摊成均匀区间,一个从未见过的
    #: 转移约有一半机会拿到高于 alpha 的 p 值。实测同等满预算下 pvalue 形式
    #: 比一阶马尔可夫基线低 0.10(A4 上低 0.24),换成 prob 后见 T38。
    struct_score: str = "prob"
    #: 互锁令牌账的作用域:'case' 逐 case,'global' 跨 case 全局池 + 守恒。
    #: 位置是**跨 case 共享的物理地点**,而逐 case 账看不见并发 case 在同一
    #: 位置更早的产出,于是把合法消耗判成乱序——实测良性违反率 1.70% 里有
    #: 17/47 是这一类(LATE)。全局池把 q 由 1.70% 压到 0.22%、LATE 精确归零,
    #: 从而解开 min(1, alpha/q) 的功效天花板(alpha=0.01 时原为 0.588)。
    #: 代价是全局池更宽松:攻击者伪造消耗时若池子恰好非空就蒙得过去。
    #: **默认仍取 'case'**:实测两者端到端打平(结论四十六),而全局池把 A4 的
    #: 攻击触发率由 0.69 砍到 0.41,恰好抵消 q 的收益;逐 case 账又与工作流
    #: 实例的 Petri 网语义一致、已记录的全部数字都建立在它上面。
    interlock_scope: str = "case"
    #: 路线获得自己的加性效应所需的最少观测数,传给 timing.fit。
    #: 取一个极大值即**关闭协变量条件化**,是 E2 的 no_covariate 臂;
    #: 实测条件化把 sigma 由 0.355 压到 0.116、rho* 由 56.2% 收到 23.7%。
    min_route_n: int = 8


@dataclass
class Detector:
    cfg: DetectorConfig
    model: object = None                      # ProcessModel (F / I)
    timing: dict = field(default_factory=dict)
    struct: object = None                     # TransitionModel
    cals: dict = field(default_factory=dict)  # 通道 -> Calibrator
    q_inter: float = 0.017                    # 软层互锁的良性违反率
    h: float = 10.0                           # CUSUM 阈值

    # --- 在线状态 ---
    _tokens: dict = field(default_factory=dict)      # case -> TokenState
    _last_op: dict = field(default_factory=dict)     # (case, device) -> op
    _prev_op: dict = field(default_factory=dict)     # case -> 上一活动
    _seq: dict = field(default_factory=dict)         # device -> 序贯检验器
    _pending: list = field(default_factory=list)     # 待产出令牌(按结束时刻)
    _due: dict = field(default_factory=dict)         # 未完成活动的超时期限
    _quarantine: int = 0
    _n_seen: int = 0
    stats: Counter = field(default_factory=Counter)

    # ------------------------------------------------------------------
    # 离线阶段
    # ------------------------------------------------------------------
    def fit(self, benign, model=None, *, rng=None, temporal: bool = True,
            frac=(0.67, 0.33)) -> "Detector":
        """离线阶段:拟合各通道并定标。

        `temporal=True` 时按 case 首事件时刻切分拟合集与校准集——这是
        部署时唯一可行的划分方式。`temporal=False` 走随机划分,仅用于
        与既有批处理结果对照,不代表可部署配置。
        """
        if model is not None:
            self.model = model
        by_case = _group(benign)
        keys = _order_cases(by_case, temporal=temporal, rng=rng)
        cut = int(len(keys) * frac[0])
        tr_keys, ca_keys = keys[:cut], keys[cut:]
        tr = [a for k in tr_keys for a in by_case[k]]

        self.timing = timing.fit(tr, min_route_n=self.cfg.min_route_n)
        st = self._state
        self.struct = structural.fit(
            {k: [st(a) for a in by_case[k]] for k in tr_keys},
            states=sorted({st(a) for a in benign}))
        self.q_inter = _benign_violation_rate(
            {k: by_case[k] for k in tr_keys}, self.model,
            self.cfg.interlock_scope)

        # 校准折:按在线语义逐消息打分,再冻结每个通道的校准器
        rows = self._score_stream([a for k in ca_keys for a in by_case[k]],
                                  rng=rng)
        self.cals = {}
        for j, ch in enumerate(CHANNELS):
            c = conformal.Calibrator()
            for r in rows:
                c.add(-r[j])
            self.cals[ch] = c.freeze()

        # 序贯阈值:在良性校准流的合成 p 值上反解,达到目标 ARL0
        fused = [fusion.combine(self._recalibrate(r, rng), self.cfg.fusion)
                 for r in rows]
        self.h = sequential.calibrate_h(fused, self.cfg.arl0,
                                        k=self.cfg.cusum_k)
        self._reset_online()
        return self

    # ------------------------------------------------------------------
    # 在线阶段
    # ------------------------------------------------------------------
    def observe(self, act, *, rng=None, now=None) -> list[Alarm]:
        """处理一条消息,返回本条触发的全部告警(可能多条,归因不同)。"""
        self._n_seen += 1
        alarms: list[Alarm] = []
        self._flush_pending(act.t_consume)

        hard = self._hard_layer(act)
        if hard is not None:
            self.stats["hard"] += 1
            self._quarantine = self.cfg.quarantine
            return [hard]                       # 丢弃:不进入任何通道更新

        raw = self._score_one(act, rng=rng)
        p = self._recalibrate(raw, rng)
        for ch, v in zip(CHANNELS, p):
            self.stats[f"p_{ch}"] += 1
            if v <= self._alpha_channel():
                alarms.append(Alarm(
                    act.t_consume, act.device, act.case, "channel", ch, v,
                    f"{_ch_zh(ch)}通道单独判决:p={v:.4g} "
                    f"低于该路预算 {self._alpha_channel():.4g}"))
        pf = fusion.combine(p, self.cfg.fusion)

        det = self._seq.setdefault(
            act.device, sequential.CUSUM(k=self.cfg.cusum_k, h=self.h)
            if self.cfg.sequential == "cusum"
            else sequential.EDetector(alpha=self._alpha_fused()))
        if det.update(pf):
            is_cusum = isinstance(det, sequential.CUSUM)
            stat = det.s if is_cusum else det.wealth
            since = det.n_since_reset if is_cusum else det.n
            alarms.append(Alarm(
                act.t_consume, act.device, act.case, "sequential", "fused",
                stat,
                f"序贯统计量越界(合成 p={pf:.4g},"
                f"自上次重置起 {since} 条消息)"))
            det.reset()

        self._commit(act, alarms, p)
        return alarms

    def replay(self, activities, on_alarm: Callable | None = None, *,
               rng=None) -> list[Alarm]:
        """按时间戳顺序重放一段消息流。看门狗在消息间隙检查。"""
        stream = sorted((a for a in activities if a.t_consume is not None),
                        key=lambda a: (a.t_consume, a.order))
        out: list[Alarm] = []
        for a in stream:
            for al in self._watchdog(a.t_consume):
                out.append(al)
                if on_alarm:
                    on_alarm(al)
            for al in self.observe(a, rng=rng):
                out.append(al)
                if on_alarm:
                    on_alarm(al)
        return out

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _alpha_fused(self) -> float:
        return self.cfg.alpha * self.cfg.budget_fused

    def _alpha_channel(self) -> float:
        """逐通道那一路的预算再按通道数均分(Bonferroni)。"""
        return self.cfg.alpha * (1.0 - self.cfg.budget_fused) / len(CHANNELS)

    def _hard_layer(self, act) -> Alarm | None:
        """F 违反与命令-响应因果缺失。三项在良性数据上实测零违反。

        F 分一元与二元两部分,**一元必须先查**:它不需要前驱,覆盖 100% 的
        消息,而二元的可达闭包只在同 case 同设备有前驱时可查(覆盖 31%)。
        """
        key = (act.case, act.device)
        prev = self._last_op.get(key)
        self._last_op[key] = act.op
        if self.model is not None \
                and not self.model.can_perform(act.device, act.op):
            return Alarm(act.t_consume, act.device, act.case, "hard", "F1",
                         float("inf"),
                         f"设备 {act.device} 上报了 {act.op},"
                         f"但参考模型中该设备从不承担此操作")
        if prev is not None and self.model is not None \
                and not self.model.allows(act.device, prev, act.op):
            return Alarm(act.t_consume, act.device, act.case, "hard", "F",
                         float("inf"),
                         f"设备 {act.device} 从 {prev} 直接跳到 {act.op},"
                         f"不在参考模型的可达闭包内")
        if act.t_cmd is None:
            return Alarm(act.t_consume, act.device, act.case, "hard",
                         "causal", float("inf"),
                         f"设备 {act.device} 上报 {act.op},"
                         f"但调度器没有下发过对应命令")
        return None

    def _state(self, act) -> str:
        """结构通道的状态记号,粒度由 cfg.struct_state 决定。"""
        if self.cfg.struct_state == "device_op":
            return f"{act.device}|{act.op}"
        return act.op

    def _score_one(self, act, *, rng=None) -> tuple:
        """三通道原始 p 值型分数(越小越异常)。弃权按 1.0。

        时序通道在 timing_score='z' 时返回的**不是** p 值,而是把 -z 压回
        (0,1] 的单调变换 —— 保序即可,因为后面还有一层 conformal;关键是
        不能像 p 值那样在 1e-12 处撞到地板而丢掉尾部次序。
        """
        p_t = 1.0
        m = self.timing.get((act.device, act.op))
        if m is not None and m.informative and act.duration_s is not None:
            if self.cfg.timing_score == "z":
                z = m.standardise(act.duration_s, route=act.route,
                                  planned_s=act.planned_s)
                if z is not None:
                    if not self.cfg.one_sided_timing:
                        z = -abs(z)
                    p_t = 1.0 / (1.0 + math.exp(-z))   # z 越负越接近 0
            else:
                v = timing.dwell_pvalue(m, act.duration_s, route=act.route,
                                        planned_s=act.planned_s,
                                        kind=timing.JUMP)
                if v is not None:
                    p_t = v if self.cfg.one_sided_timing \
                        else 2.0 * min(v, 1.0 - v)

        p_s = 1.0
        cur = self._state(act)
        prev = self._prev_op.get(act.case)
        self._prev_op[act.case] = cur
        if prev is not None and self.struct is not None:
            if self.cfg.struct_score == "prob":
                v = structural.struct_score(self.struct, prev, cur)
            else:
                v = structural.struct_pvalue(self.struct, prev, cur,
                                             randomised=True, rng=rng)
            if v is not None:
                p_s = v

        viol = self._token_check(act)
        u = rng.random() if rng is not None else 0.5
        # q 有下界:全局作用域下良性违反率可低至 0.002,训练折上甚至可能取到
        # 0,那会让随机化 p 值退化成恒零而不是"违反时均匀落在 [0,q]"。
        q = max(self.q_inter, 1e-4)
        p_i = u * q if viol else q + u * (1 - q)
        return (p_t, p_s, p_i)

    def _token_check(self, act) -> bool:
        """软层:消耗前置令牌。在线不能归因 LATE/NEVER/FAILED(需向后看)。"""
        if self.model is None:
            return False
        st = self._token_state(act.case)
        cons, prod = self.model.token_effects(act)
        missing = False
        for ttype, pos in cons:
            if not st.take(ttype, pos, self.model):
                missing = True
        t_end = act.t_produce or act.t_consume
        if prod:
            bisect.insort(self._pending, (t_end, act.order, act.case,
                                          tuple(prod)))
        self._arm_watchdog(act)
        return missing

    def path_q(self, benign_ref) -> list[float]:
        """各并行路"离散异常事件"在良性参照流上的发生率 q，顺序同 PATHS。

        只用良性数据，故可合法地用来分配 alpha 预算（结论四十九）。**参照流
        必须是拟合数据之后的一折**：结论四十七实测训练折的 q 比部署折低 9 倍
        （0.0054 对 0.047），用训练折估会把互锁的天花板算成不生效。

        为什么不能从分数分布反推:通用的"最异常处原子质量"在两处同时误判——
        硬层的良性分数全部并列在 0（良性零违反）会读成 q=1.0、把最有用的一路
        剔掉；互锁的 q 那个原子被随机化 p 值摊成 [0,q] 上的连续区间、读不出
        来。天花板是**通道语义**，必须逐通道声明。这与"离散通道一律取随机化
        p 值"（结论十四）之间存在真实张力，论文里要写明。
        """
        self._reset_online()
        n = hard = tok = 0
        for a in benign_ref:
            self._flush_pending(a.t_consume)
            n += 1
            if self._hard_layer(a) is not None:
                hard += 1
                continue
            tok += bool(self._token_check(a))
        self._reset_online()
        n = max(n, 1)
        # 顺序:硬层, 时序, 结构, 互锁(, 合成)。连续路无原子,q 记 0。
        return [hard / n, 0.0, 0.0, tok / n]

    def path_weights(self, benign_ref, *, alpha: float, n_paths: int = 4,
                     min_ceiling: float = 0.5):
        """按天花板判据 min(1, alpha_i/q_i) >= min_ceiling 分配预算。

        天花板要用**该路自己的配额**算，而配额又依赖给谁预算，故迭代到不动点；
        保留集单调递减，最多 n_paths 轮收敛。返回 (权重, q 向量, 保留下标)。
        """
        qs = (self.path_q(benign_ref) + [0.0] * n_paths)[:n_paths]
        keep = list(range(n_paths))
        for _ in range(n_paths):
            a = alpha / max(len(keep), 1)
            nxt = [i for i in keep
                   if qs[i] <= 0 or a / qs[i] >= min_ceiling]
            if nxt == keep or not nxt:
                break
            keep = nxt
        w = [0.0] * n_paths
        for i in keep:
            w[i] = 1.0 / len(keep)
        return w, qs, keep

    def _token_state(self, case: str) -> "interlock.TokenState":
        """全局作用域下所有 case 共用一本账,故键退化为一个常量。"""
        key = "*" if self.cfg.interlock_scope == "global" else case
        return self._tokens.setdefault(key, interlock.TokenState())

    def _arm_watchdog(self, act) -> None:
        """给这条活动的完成事件设一个期限,到点未完成即 A6 告警。

        期限取时长分布的 watchdog_q 分位。用正态分位数而非 Student-t 的
        逆——看门狗只需一个粗的上界,而 t 的逆要迭代求根,会破坏 O(1)。
        """
        m = self.timing.get((act.device, act.op))
        if m is None or not m.informative or act.t_consume is None:
            return
        loc = m.location(act.route, act.planned_s)
        if loc is None or m.sigma <= 0:
            return
        span = math.exp(loc + timing.norm_ppf(self.cfg.watchdog_q) * m.sigma)
        key = (act.case, act.device, act.order)
        self._due[key] = act.t_consume + timedelta(seconds=span)

    def _flush_pending(self, now) -> None:
        """把已到结束时刻的活动的产出令牌放入,复现 _timeline 的先后语义。"""
        while self._pending and now is not None and self._pending[0][0] <= now:
            _, order, case, prod = self._pending.pop(0)
            st = self._token_state(case)
            for ttype, pos in prod:
                st.put(ttype, pos)
            for key in [k for k in self._due if k[0] == case and k[2] == order]:
                del self._due[key]      # 完成事件已到,撤销看门狗

    def _recalibrate(self, raw, rng=None) -> tuple:
        """逐通道 conformal。必须在合成之前——见 fusion 模块规矩 1。"""
        if not self.cals:
            return tuple(raw)
        return tuple(self.cals[ch].pvalue(-v, rng=rng)
                     for ch, v in zip(CHANNELS, raw))

    def _commit(self, act, alarms, p) -> None:
        """M9 门控更新:只有干净消息才允许进入基线。"""
        if not self.cfg.online_update:
            return
        if self.cfg.gated_update:
            if alarms:
                self._quarantine = self.cfg.quarantine
                self.stats["update_blocked"] += 1
                return
            if self._quarantine > 0:
                self._quarantine -= 1
                self.stats["update_blocked"] += 1
                return
        self.stats["update_applied"] += 1
        m = self.timing.get((act.device, act.op))
        if m is None or not m.informative or not act.duration_s \
                or act.duration_s <= 0:
            return
        route = tuple(act.route) if act.route else timing.NO_ROUTE
        if route not in m.route_effect:
            return                      # 未见路线走冷启动先验,不该被在线改写
        lam = self.cfg.ewma
        r = math.log(act.duration_s) - m.route_effect[route]
        m.route_effect[route] += (1.0 - lam) * r
        m.sigma = math.sqrt(max(lam * m.sigma ** 2 + (1.0 - lam) * r * r,
                                1e-9))

    def _watchdog(self, now) -> list[Alarm]:
        """A6:该来的没来。这是唯一"无消息也会告警"的路径。

        **能覆盖的与不能覆盖的必须说清楚:**能抓"活动已开始、完成事件被
        抑制"——期限一过即告警。抓不到"整条活动被完整抹掉",因为那既无
        开始也无完成,看门狗根本没被布防;要抓那一类需要一个活动**间隔**
        模型(上一活动结束后多久应有下一活动),本文的时长模型不提供,
        且 Trier 的主流程层变体率 77%,间隔模型在该数据上学不紧。这也是
        把 A6 从"既有方法结构性无能"的主张里移出去的原因之一。
        """
        out = []
        if now is None:
            return out
        for key, due in list(self._due.items()):
            if due < now:
                case, device, _ = key
                del self._due[key]
                out.append(Alarm(
                    now, device, case, "watchdog", "time", float("inf"),
                    f"设备 {device} 在 {case} 上的活动已开始,但完成事件超过"
                    f"时长分布 {self.cfg.watchdog_q:.1%} 分位仍未到达"))
        return out

    def _score_stream(self, acts, *, rng=None) -> list:
        """按在线语义重放一段良性流并收集原始三元组,供校准使用。"""
        self._reset_online()
        rows = []
        for a in sorted((x for x in acts if x.t_consume is not None),
                        key=lambda x: (x.t_consume, x.order)):
            self._flush_pending(a.t_consume)
            if self._hard_layer(a) is not None:
                continue
            rows.append(self._score_one(a, rng=rng))
        self._reset_online()
        return rows

    def _reset_online(self) -> None:
        self._tokens, self._last_op, self._prev_op = {}, {}, {}
        self._seq, self._pending, self._due = {}, [], {}
        self._quarantine, self._n_seen = 0, 0


def _group(acts) -> dict:
    by = defaultdict(list)
    for a in acts:
        by[a.case].append(a)
    return by


def _order_cases(by_case: dict, *, temporal: bool, rng=None) -> list:
    """时间序按 case 首事件时刻排,随机序用给定 rng 打乱。"""
    keys = list(by_case)
    if temporal:
        return sorted(keys, key=lambda k: min(
            (a.t_consume for a in by_case[k] if a.t_consume is not None),
            default=None) or 0)
    if rng is not None:
        rng.shuffle(keys)
    return keys


def _benign_violation_rate(by_case: dict, model, scope: str = "case") -> float:
    if model is None:
        return 0.0
    _, cnt = interlock.check_all(by_case, model, scope=scope)
    return cnt["I_viol"] / max(cnt["I_checked"], 1)


def _ch_zh(ch: str) -> str:
    return {"time": "时序", "struct": "结构", "inter": "互锁"}.get(ch, ch)
