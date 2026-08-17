"""耦合互证的在线协议：对手方确认、pending 窗口、否证与证据构造。

## 协议

状态迁移声明不因设备自己签名而生效。设备 A 声明"已完成并交付至位置 p"后，
该声明必须由任务图指定的对手方 B 独立签名确认才提交。B 的确认依据是它自己的
本地传感证据（夹爪力矩、到料光电门、视觉），不是 A 的话。

**pending 由命令打开，不由完成声明打开。** 这一点是必须的：若等声明到来才开
pending，设备只要沉默就绕过了整个协议。调度器下发命令时即知道"谁、做什么、
交付到哪、计划多久"，此刻就该把这条待确认事项挂上。

三种终局：

    CONFIRMED   对手方在窗口内取件 -> 提交
    REFUTED     对手方明确否证（工位有到料传感器时）-> 立即判定
    EXPIRED     窗口内既无确认也无否证 -> 判定
    UNWITNESSED 任务图中无对手方，无从互证 -> 不计入通过

## 两个截止时刻，不是一个（这是实现中被数据逼出来的修正）

最初只设一个窗口"上游计划完成时刻 + 余量"，良性流上 EXPIRED 达 67.3%，完全
不可用。根因是互证时延 Δ 的长尾：实测中位 6.7 s 而 p95 达 119.7 s、
max 2237.7 s，长尾来自**调度器自己的排队**——paper02 实测派发阶段时长 p95 为
253.6 s、$\\sigma_{\\log}=1.475$，由调度排队竞争主导，其结论是派发时长
**不可作时长检验**。上游交付完成后，对手方要等多久才被下发取件命令，取决于
调度器的队列，与交接本身无关。把这段队列时间算进互证窗口，要么误报爆炸，
要么窗口大到失去意义。

正确的做法是分成两个截止时刻，各自锚在调度器**自己知道**的量上：

  1. **上报看门狗** = $t_{\\text{cmd}}(A) + \\text{planned}(A) + $ 余量 + 排队容差。
     它只管"该报的没报"，是基线 `S1` 的能力，本文不主张。
  2. **互证窗口** = $t_{\\text{cmd}}(B) + \\text{planned}(B) + $ 余量 + 排队容差，
     即**从对手方被下发取件命令时起算**。上游交付完成到对手方被派发之间的
     等待不计入。

两者都必须加**派发排队容差**。本日志实测派发时延（命令下发到开始动作）
中位仅 4.4 s，但 p95 达 218.3 s、p99 817.4 s、max 1476.4 s（paper02 独立测得
p95 253.6 s，两者吻合）。不容纳这段队列，看门狗在良性流上就要误报四分之一。
容差按良性流的 p95 取 260 s，这符合 paper02 规则 30（阈值只能取自纯良性流）。

代价必须如实写进论文：任务完成类判定的最坏时延**含调度队列的一段**，
$T_{\\text{detect}}$ 只有**条件**确定上界（在对手方被派发之后不超过
$\\text{planned}(B) + $ 余量），无条件上界在这条产线上不存在，因为调度队列
本身没有上界。这恰恰是可问责沉默不可替代的第二个理由：心跳判定的是设备的
状态声明而非任务完成，**与调度队列完全解耦**，故它的 $r\\,T_{\\text{hb}}$ 是
无条件上界。安全裕度定理接的应当是后者。

## 与看门狗的分界（必须写清，否则贡献被 `S1` 吃掉）

"该报的没报"由看门狗即可发现，工业协议早有先例（IEC 61850 GOOSE 的 MaxTime
心跳与 fail-safe），本文不主张这一点，它是基线 `S1`。互证要解决的是**报了但是
假的**：看门狗被一条按时到达、字段完全正常的伪造声明完全满足，而对手方的
本地传感证据不会说谎。两者在消融表里必须分列。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .taskgraph import TaskGraph, consumed_at, device_class, produced_at

CONFIRMED = "confirmed"
REFUTED = "refuted"
EXPIRED = "expired"
UNWITNESSED = "unwitnessed"
#: 声明按时到达、但对手方**从未被派发**。这是覆盖率缺口，不是检测结果，
#: 因此不产生证据。把它算作检出会把 30% 的结构性缺口伪装成误报或检出，
#: 两个方向都是错的。这类声明交由按需主动互证处理。
NOT_DISPATCHED = "counterparty_not_dispatched"


@dataclass
class CorroborateConfig:
    """窗口参数。全部为显式设计量，只允许由**良性流**标定（paper02 规则 30：
    阈值只能取自纯良性流，否则检出率会被假性归零）。"""
    margin_factor: float = 0.5
    margin_abs_s: float = 5.0
    #: 计划时长缺失时的兜底窗口。
    fallback_s: float = 60.0
    #: 派发排队容差：对手方被下发取件命令到它真正开始动作之间的等待。
    #: 这段时间由**调度器自己的队列**决定，与交接无关，必须容纳进互证窗口，
    #: 否则误报爆炸。默认 260 s 取本日志实测派发时延的 p95（见 detect_diag）。
    #: 代价是最坏检测时延加上这一段——这是调度队列的价格，论文必须如实写。
    dispatch_allowance_s: float = 260.0

    def window_s(self, planned_s: float | None) -> float:
        p = planned_s if planned_s else self.fallback_s
        return p * (1.0 + self.margin_factor) + self.margin_abs_s

    def corr_window_s(self, planned_s: float | None) -> float:
        return self.window_s(planned_s) + self.dispatch_allowance_s


@dataclass
class Evidence:
    """可转移证据。构造上不含任何真值标签，只含协议消息与模型事实。"""
    claim_id: int
    device: str
    op: str
    case: str
    pos: str
    outcome: str
    t_open: float
    t_decide: float
    expected_witnesses: tuple[str, ...] = ()
    refuting_witness: str | None = None
    #: 声明是否到达过。False 即"该报没报"，看门狗也能发现（基线 `S1`）。
    claim_seen: bool = False
    #: P3 场景：该设备在此期间披露过的原像槽号，构成"我未偏离"的自认。
    #: 有它则归责强度更高——设备主动签署过一份可证伪的声明。
    revealed_slots: tuple[int, ...] = ()

    @property
    def latency_s(self) -> float:
        return self.t_decide - self.t_open

    @property
    def self_incriminating(self) -> bool:
        return bool(self.revealed_slots)


@dataclass
class _Pending:
    claim_id: int
    device: str
    op: str
    case: str
    pos: str
    t_open: float
    #: 上报看门狗的截止时刻（基线 `S1` 的能力）。
    report_due: float
    expected: frozenset[str]
    claim_seen: bool = False
    #: 互证窗口的截止时刻，对手方被下发取件命令时才装填。
    corr_due: float | None = None

    @property
    def deadline(self) -> float:
        """有效截止时刻。

        声明未到达时看上报看门狗；声明到达后看门狗即被满足，此后只等互证窗口，
        窗口未装填（对手方尚未被派发）则暂不判决。
        """
        if self.corr_due is not None:
            return self.corr_due
        return float("inf") if self.claim_seen else self.report_due


@dataclass
class WitnessPolicy:
    """**见证集合的选取规则**。本文的第一贡献整个落在这个对象上。

    协议的其余部分——双截止时刻、窗口标定、证据构造、归责——对所有基线完全
    相同，故基线之间的差异**只可能**来自这里。这是把"选取原则"单独隔离出来
    做对照的唯一干净办法（见 README 第四节第二档）。

    三个自由度：

      - `eligible`：哪些**设备类**在模型上是本活动的对手方。它决定是否开启
        待确认事项（空集即无对手方区间），也决定 `W2` 那条"问所有人"的基线。
      - `admits`：某个**实际到场**的取件者是否被本规则认可为见证者。本文默认
        全部认可，因为任务图的作用是确定**耦合点在哪**（位置 + case），到场者
        是谁由物理决定；`W3`/`W4` 用它施加各自的提名规则。
      - `confirm_on_claim`：声明一到达即视为确认。只有 `W1` 为真——PBFT 式
        法定人数确认的是"多数副本对消息的内容与顺序达成一致"，声明既已广播、
        签名有效，法定人数就会提交它，**无须任何物理证据**。
      - `corroborates`：是否启用互证的三个入口（装填窗口、取件确认、对手方否证）。
        只有 `W1` 为假。

    ## `W1` 为何不该保留否证通道（这是公平性上最微妙的一处，必须写清）

    留着否证通道时 `W1` 测得 0.136 的检出，全部来自对手方的否证。但**共识协议
    并不提供那个通道**：PBFT 复制消息的内容与顺序，它不制造"B 必须为 A 的交付
    作证"这项协议义务，也不定义"窗口内没有作证即判决"。没有这项义务，B 只会
    上报自己的任务失败，调度器看到的是**B 的任务失败**，而不是**A 说了谎**——
    归责指向了错的设备。本文的证据以 A 的声明为键，故"`W1` 对 A 一无所获"正是
    准确的表述。

    反过来说也成立，而且这才是要点：**若把否证通道交给 PBFT，那就是把耦合互证
    交给了它。** 那不是对基线的让步，那恰好证明了检出来自互证而非共识。

    ## 为什么 `admits` 默认不查设备类

    实现时试过"作证者的设备类必须落在 `eligible` 内"，那会**重新引入断言 B6
    修掉的 bug**。实测 2,373 个已实现对手方中有 392 个不在模型见证集内，而其中
    285 个是**同类跨实例**交接（`vgr_2` 交付、`vgr_1` 取走），88 个是同机顺序
    工序（`mm/mill` → `mm/deburr`）——模型级见证边按**跨类**交接构造，压根无法
    表达"同类的另一台实例"。真正跨类却未建模的只有 6 例。

    按类硬查会把这 392 个真实的独立证据全部丢弃，使本文自己的 P1/P3 检出率从
    1.000 掉到 0.928、良性误报从 69 掉到 64（后者不是改善，是证据变少）。
    覆盖率也会退回 B6 之前的 64.89%。故正确的口径仍是 B6 定下的那条：
    **见证资格看设备类，见证独立性看设备实例。**
    """
    graph: TaskGraph
    name: str = "taskgraph"
    confirm_on_claim: bool = False
    corroborates: bool = True

    def eligible(self, act) -> frozenset[str]:
        return frozenset(dc for dc, _ in
                         self.graph.witnesses_of(act.device, act.op))

    def admits(self, pending, actor_act) -> bool:
        return True


@dataclass
class CorroborationProtocol:
    """在线互证。事件按接收时刻喂入，`sweep` 推进时钟并结算超时。"""
    graph: TaskGraph
    cfg: CorroborateConfig = field(default_factory=CorroborateConfig)
    #: 见证集合的选取规则。默认即本文的任务图规则；换它即得第二档基线。
    policy: WitnessPolicy | None = None
    _pending: dict[int, _Pending] = field(default_factory=dict)
    _by_pos: dict[tuple[str, str], list[int]] = field(
        default_factory=lambda: defaultdict(list))
    _revealed: dict[str, list[int]] = field(
        default_factory=lambda: defaultdict(list))
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    evidence: list[Evidence] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.policy is None:
            self.policy = WitnessPolicy(self.graph)

    # ---- 输入 ----------------------------------------------------------

    def note_reveal(self, device: str, slot: int) -> None:
        """记录一次原像披露。P3 的归责强度来自这条记录。"""
        self._revealed[device].append(slot)

    def on_command(self, claim_id: int, act, t_cmd: float) -> str | None:
        """命令下发。做两件事，缺一不可：

        一是为本活动挂上待确认事项（含上报看门狗）；二是**装填上游的互证窗口**
        ——本活动要从某位置取件，说明调度器此刻正式要求它对上游的交付作证，
        于是上游那条 pending 的互证窗口从现在起算。
        """
        self._arm_upstream(act, t_cmd)
        pos = produced_at(act.device, act.end_pos)
        expected = self.policy.eligible(act)
        if not expected:
            self.counts[UNWITNESSED] += 1
            return UNWITNESSED
        p = _Pending(claim_id=claim_id, device=act.device, op=act.op,
                     case=act.case, pos=pos, t_open=t_cmd,
                     report_due=t_cmd + self.cfg.corr_window_s(act.planned_s),
                     expected=expected)
        self._pending[claim_id] = p
        self._by_pos[(act.case, pos)].append(claim_id)
        return None

    def _arm_upstream(self, act, t_cmd: float) -> None:
        if not self.policy.corroborates:
            return
        for cid in list(self._pending):
            p = self._pending.get(cid)
            if p is None or p.corr_due or not self._attests(p, act):
                continue
            p.corr_due = t_cmd + self.cfg.corr_window_s(act.planned_s)

    def _attests(self, p: _Pending, actor_act) -> bool:
        """`actor_act` 的取件能否为 `p` 的交付作证。

        三个条件，缺一不可，且**基线之间只有第三条不同**：

          1. 作证者是另一台物理设备（见证独立性按实例判定，非按类）。
          2. 它真的在 `p` 的交付位置取到了工件——这是本地传感证据。
          3. 选取规则认可它（`admits`）。本文默认全部认可，理由见 `WitnessPolicy`
             的文档；`W3`/`W4` 在此施加随机提名与空间邻接的限制。
        """
        if p.device == actor_act.device or not self.policy.corroborates:
            return False
        if p.case != actor_act.case:
            return False
        src = consumed_at(actor_act.device, actor_act.start_pos)
        if not self.graph.same_place(p.pos, src):
            return False
        return self.policy.admits(p, actor_act)

    def on_claim(self, claim_id: int, t: float = 0.0) -> None:
        """完成声明到达。只置标记，**不结算**——设备的话不能确认自己。

        唯一的例外是 `W1`：PBFT 式法定人数一旦对消息达成一致就提交它，故声明
        到达即结算为已确认。这条例外正是那个基线要暴露的东西。
        """
        p = self._pending.get(claim_id)
        if p is None:
            return
        p.claim_seen = True
        if self.policy.confirm_on_claim:
            self._settle(claim_id, CONFIRMED, t, None)

    def on_pickup(self, act, t: float) -> list[Evidence]:
        """取件声明。它同时是对上游交付的确认，因为取件方有本地传感证据。

        串谋见证者的确认按协议同样成立——那正是 P4 的边界，由串谋界量化，
        不在此处特判。
        """
        return self._match(act, CONFIRMED, t, None)

    def on_refute(self, act, t: float) -> list[Evidence]:
        """对手方否证：被命令取件但本地传感器未记录工件到达。"""
        return self._match(act, REFUTED, t, act.device)

    def sweep(self, now: float) -> list[Evidence]:
        """结算所有已过窗口的 pending。"""
        out = []
        for cid, p in sorted(self._pending.items(),
                             key=lambda kv: kv[1].deadline):
            if p.deadline < float("inf") and now >= p.deadline:
                ev = self._settle(cid, EXPIRED, p.deadline, None)
                if ev is not None:
                    out.append(ev)
        return out

    def finalize(self) -> list[Evidence]:
        """流结束时结算残余。对手方从未被派发的按 NOT_DISPATCHED 归档。"""
        out = self.sweep(float("inf"))
        for cid, p in list(self._pending.items()):
            self._settle(cid, NOT_DISPATCHED, p.t_open, None)
        return out

    # ---- 内部 ----------------------------------------------------------

    def _match(self, actor_act, outcome, t, witness) -> list[Evidence]:
        """按位置分组，每组最多结算一条——一次取件只能确认一次交付。"""
        out = []
        for key in [k for k in self._by_pos]:
            for cid in list(self._by_pos[key]):
                p = self._pending.get(cid)
                if p is None or not self._attests(p, actor_act):
                    continue
                ev = self._settle(cid, outcome, t, witness)
                if ev is not None:
                    out.append(ev)
                break
        return out

    def _settle(self, cid, outcome, t, witness) -> Evidence | None:
        p = self._pending.pop(cid, None)
        if p is None:
            return None
        self._by_pos[(p.case, p.pos)].remove(cid)
        self.counts[outcome] += 1
        if outcome in (CONFIRMED, NOT_DISPATCHED):
            return None
        ev = Evidence(claim_id=cid, device=p.device, op=p.op, case=p.case,
                      pos=p.pos, outcome=outcome, t_open=p.t_open,
                      t_decide=t, expected_witnesses=tuple(sorted(p.expected)),
                      refuting_witness=witness, claim_seen=p.claim_seen,
                      revealed_slots=tuple(self._revealed.get(p.device, ())))
        self.evidence.append(ev)
        return ev

    @property
    def n_open(self) -> int:
        return len(self._pending)


def replay(reports, graph: TaskGraph, cfg: CorroborateConfig | None = None,
           *, refute: bool = True,
           policy: WitnessPolicy | None = None) -> CorroborationProtocol:
    """回放一条声明流。

    每条 `Report` 生成两个事件：命令下发（$t_{\\text{cmd}}$，来自命令账本，
    **即使设备沉默也存在**）与完成声明（$t_{\\text{report}}$，沉默时不存在）。
    取件声明另兼上游交付的确认。`refute=False` 时对手方是无传感器的褐地设备，
    只能沉默，判定退化为等窗口超时。
    """
    proto = CorroborationProtocol(graph, cfg or CorroborateConfig(),
                                  policy=policy)
    CMD, PICKUP, REFUTE, CLAIM = 0, 1, 2, 3
    events = []
    for rep in reports:
        events.append((rep.t_cmd, CMD, id(rep), rep))
        if rep.refutes:
            if refute and not rep.silent_witness:
                events.append((rep.t_pickup, REFUTE, id(rep), rep))
            continue
        if rep.attests_pickup:
            events.append((rep.t_pickup, PICKUP, id(rep), rep))
        if not rep.withheld:
            events.append((rep.t_report, CLAIM, id(rep), rep))
    for t, kind, cid, rep in sorted(events, key=lambda e: (e[0], e[1])):
        proto.sweep(t)
        a = rep.act
        if kind == CMD:
            proto.on_command(cid, a, t)
        elif kind == PICKUP:
            proto.on_pickup(a, t)
        elif kind == REFUTE:
            proto.on_refute(a, t)
        else:
            proto.on_claim(cid, t)
            if rep.revealed:
                proto.note_reveal(a.device, int(t))
    proto.finalize()
    return proto
