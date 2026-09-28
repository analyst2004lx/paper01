"""对比基线。按**消耗的信息**分档，不按论文分组（理由见 README 第四节）。

    R0  匹配告警率的随机指控          无信息，地板
    S1  调度看门狗                    命令账本 + 声明是否到达
    S2  计划一致性残差（通用 FDI 类） 加时长与结果位
    S3  对齐式一致性检验（过程挖掘）  XES + BPMN 的过程模型语言
    W1  全网法定人数投票（PBFT 式）   对声明本身达成一致，不要求物理证据
    W2  全体询证                      见证集 = 全部设备类，本文协议的全询变体
    W3  k 个随机见证者                与本文同规模，但随机提名
    W4  空间邻居见证                  按 BPMN 物料流邻接提名（COLAW/Vouch+ 原则）
    H1  等带宽周期性全量上报          同带宽下的时延对照（接 budget）
    H2  无密码绑定的 GOOSE 式心跳     活性有、归责无
    H3  TESLA 式延迟密钥              认证有、不可否认无
    U1  交接点全传感器先知            天花板：差额 = 覆盖缺口

## 四档的性质完全不同，不可混在一张表里读

**第一档不是赛马，是定理。** 断言 D1 已证 P1 的伪造声明在单观测者可见的 7 个
字段上与良性逐字段一致、时长落在 IQR 内，故整档的检出率是**结构性的 0**，不是
"比较低"。跑它的目的不是比大小，而是把这条可证命题落成可复现的实测确认。

因此第一档的实现必须**尽可能强**，否则会被质疑"你没实现好才检不出"：阈值一律
按良性流标定到刚好不误报的最紧位置（`calibrate`），一致性检验按过程模型的完整
语言判（含同机顺序工序），看门狗与本文用同一套派发排队容差。都做足之后仍是 0，
这个 0 才有分量。

**第二档才是赛马。** 协议、密码学、窗口、预算全部相同，**只换见证集合怎么选**，
故差异只可能来自选取原则本身。这是把第一贡献单独隔离出来的唯一干净办法。

**第三档接带宽—安全裕度定理。** 不比 P1 检出率（那是第一档的事），比的是：等带宽
下时延差多少、无绑定心跳能不能归责、延迟认证能不能不可否认。三条都是解析结论，
由 `budget.py` / `crypto.py` 钉死，不依赖回放噪声。

**第四档是天花板。** 每个交接点都有独立传感器时覆盖率可达 1；与本文 70.05% 的
差额就是覆盖缺口，也是按需主动互证的靶区。

## 三条必须守住的公平性要求

  1. **同一套协议。** 四条基线都走 `corroborate.CorroborationProtocol`，
     只替换 `WitnessPolicy`。任何"基线用另一份实现"的做法都无法排除实现差异。
  2. **同一套窗口与容差。** 特别是派发排队容差 260 s，不给基线设障
     （`detect_diag` 的看门狗基线已按此办）。
  3. **同口径报告。** `W3` 会同时抬高检出率与误报率，只报检出率会得出
     "随机见证者也行"的错误结论。故本模块一律报 **检出率与误报率之差**，
     并在 `compare` 里把两者并列。

## W1 的操作化必须写清楚，否则会被指为稻草人

PBFT 式共识确认的是"多数副本对消息的内容与顺序达成一致"，**不是物理事实**。
一条格式正确、签名有效、按时到达的伪造声明会被法定人数顺利提交——共识给出的是
**一致性**，而任务状态伪造不是一致性问题。故 `W1` 的操作化是
`confirm_on_claim=True`：声明一到达即提交。

**第一版操作化是错的，记下来以免重犯：** 起初写成"任何其它设备的活动都算确认"，
跑出 0.157 的检出率。那个数不是信号，是待确认事项按位置分桶后**结算顺序**的
假象——有些桶恰好在别的设备取件事件到达前就到期了。共识的语义里不存在"等某个
事件来确认"，声明既已提交就是提交了，故正确操作化下检出率恰为 0。

这不是给 BFT 设障，而是它的真实语义，且结论对它并不苛刻：`W1` 的检出能力**恰等
于看门狗 `S1`**（沉默无声明可提交，故 P2 仍能发现），但带宽是本文的 131 倍
（见 `budget.py`）。一句话：**付 131 倍带宽，换一个看门狗。**

Comparison baselines. Tiered by **information consumed**, not by paper (see README section 4).

    R0  random accusation at a matched alarm rate     no information; the floor
    S1  scheduler watchdog                            command ledger + whether the statement arrived
    S2  plan-consistency residual (generic FDI)       plus duration and the result bit
    S3  alignment-style conformance (process mining)  the process-model language of XES + BPMN
    W1  whole-network quorum vote (PBFT-style)        agreement on the statement itself; no physical evidence
    W2  interrogate everyone                          witness set = every device class; the ask-all variant
    W3  k random witnesses                            same size as this paper, but nominated at random
    W4  spatial-neighbor witnesses                    nominated by BPMN material-flow adjacency (COLAW/Vouch+)
    H1  equal-bandwidth periodic full reports         latency contrast at the same bandwidth (feeds budget)
    H2  GOOSE-style heartbeat with no cryptographic binding   liveness yes, attribution no
    H3  TESLA-style delayed keys                      authentication yes, non-repudiation no
    U1  sensor oracle at every handover               ceiling: the difference is the coverage gap

## The four tiers are different in kind and must not be read from one table

**Tier 1 is not a race; it is a theorem.** Assertion D1 already shows that a
P1 forgery matches the benign activity on all 7 single-observer fields and
that its duration lies inside the IQR, so the whole tier's detection rate is
a **structural 0**, not "rather low." Running it is not to compare magnitudes;
it turns a provable claim into a reproducible measurement.

The tier-1 implementation must therefore be **as strong as possible**, or the
objection is "you failed to implement it": thresholds are calibrated on the
benign stream to the tightest point that does not false-alarm (`calibrate`),
conformance judges the full process-model language (including same-machine
sequential steps), and the watchdog uses the same 260 s dispatch-queue
allowance. After all of that the rate is still 0, and that 0 has weight.

**Tier 2 is the race.** Protocol, cryptography, window, and budget are all
the same; **only how the witness set is chosen** changes, so a difference can
come only from the selection principle. That is the only clean way to isolate
the first contribution.

**Tier 3 attaches to the bandwidth–safety margin theorem.** It does not
compare P1 detection rates (that is tier 1). It compares: how much latency
differs at equal bandwidth, whether an unbound heartbeat can attribute, and
whether delayed authentication can be non-repudiable. All three are closed
form, pinned by `budget.py` / `crypto.py`, and do not depend on replay noise.

**Tier 4 is the ceiling.** Coverage can reach 1 when every handover has an
independent sensor; the difference from this paper's 70.05% is the coverage
gap, which is the target of on-demand active corroboration.

## Three fairness requirements

  1. **The same protocol.** All four baselines go through
     `corroborate.CorroborationProtocol` and only replace `WitnessPolicy`.
     A baseline with its own implementation cannot rule out an implementation difference.
  2. **The same window and allowance.** In particular the 260 s dispatch-queue
     allowance; do not handicap a baseline (`detect_diag`'s watchdog already does this).
  3. **The same reporting convention.** `W3` raises both detection rate and
     false-alarm rate; reporting only the detection rate yields the wrong
     conclusion that "random witnesses also work." This module always reports
     **detection rate minus false-alarm rate**, and `compare` puts the two side by side.

## W1's operationalization must be written down, or it will be called a straw man

PBFT-style consensus confirms that "a majority of replicas agree on the
content and order of a message", **not a physical fact**. A forged statement
that is well formed, validly signed, and on time is committed by the quorum —
consensus gives **consistency**, and task-state falsification is not a
consistency problem. So `W1` is operationalized as `confirm_on_claim=True`:
the statement is committed on arrival.

**The first operationalization was wrong; record it so it is not repeated.**
It was first written as "any other device's activity counts as confirmation"
and produced a detection rate of 0.157. That number was not a signal; it was
an artifact of **settlement order** after pending items are bucketed by
position — some buckets happened to expire before another device's pickup
arrived. Consensus has no semantics of "wait for some event to confirm."
Once the statement is committed, it is committed, so the correct
operationalization has detection rate exactly 0.

This does not handicap BFT; it is BFT's real semantics, and the conclusion is
not harsh: `W1`'s detection ability **equals the watchdog `S1`** (silence has
no statement to commit, so P2 is still found), but the bandwidth is 131 times
this paper's (see `budget.py`). In one sentence: **pay 131× bandwidth for a watchdog.**
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from . import coverage, crypto
from .budget import Design
from .corroborate import WitnessPolicy
from .taskgraph import TaskGraph, consumed_at, device_class, produced_at

R0 = "R0_random_accusation"
S1 = "S1_watchdog"
S2 = "S2_plan_residual"
S3 = "S3_conformance"
W1 = "W1_quorum_vote"
W2 = "W2_interrogate_all"
W3 = "W3_random_witness"
W4 = "W4_spatial_neighbor"
H1 = "H1_equal_bandwidth_periodic"
H2 = "H2_unbound_goose"
H3 = "H3_tesla_delayed_auth"
U1 = "U1_sensor_oracle"
OURS = "ours_taskgraph"

#: 第二档（见证选取规则），走 `corroborate` 的同一协议。
#: Tier 2 (witness-selection rules), on the same `corroborate` protocol.
FAMILIES = (OURS, W1, W2, W3, W4)
#: 第一档（单观测者）+ 地板，走下面的 `SingleObserver` 接口。
#: Tier 1 (single observer) plus the floor, via the `SingleObserver` interface below.
TIER1 = (R0, S1, S2, S3)
#: 第三档（心跳/带宽通道），解析对照，不走回放。
#: Tier 3 (heartbeat / bandwidth channel), closed-form contrast, no replay.
TIER3 = (H1, H2, H3)
#: 第四档（天花板）。 / Tier 4 (the ceiling).
TIER4 = (U1,)


@dataclass
class QuorumVotePolicy(WitnessPolicy):
    """`W1`：PBFT 式法定人数对声明本身投票。

    `confirm_on_claim=True` 即"声明一到达即提交"；`corroborates=False` 关掉互证的
    三个入口，理由见 `corroborate.WitnessPolicy` 的文档——共识不制造"B 必须为 A
    的交付作证"这项义务，留着否证通道就是把耦合互证白送给基线（实测那样会给它
    0.136 的检出，全部来自否证）。

    见证集仍取任务图的，以免同时改两个变量——本条基线要单独暴露的是
    **"一致"不等于"真实"**。

    `W1`: a PBFT-style quorum votes on the statement itself.

    `confirm_on_claim=True` means "commit on arrival"; `corroborates=False`
    turns off the three corroboration entries. See `corroborate.WitnessPolicy`:
    consensus does not create a duty that "B must witness A's delivery", and
    leaving the refutation channel on hands coupled corroboration to the
    baseline for free (measured that way it gets a detection rate of 0.136,
    all from refutation).

    The witness set is still the task graph's, so two variables are not
    changed at once — what this baseline isolates is **"agreement" is not "truth"**.
    """
    name: str = W1
    confirm_on_claim: bool = True
    corroborates: bool = False


@dataclass
class InterrogateAllPolicy(WitnessPolicy):
    """`W2`：见证集 = 全部设备类，其余与本文相同。

    对应"既然不知道该问谁，就问所有人"。实测结果分两半，其中一半与预期相反，
    按实测写：

      - **检出与本文逐位相同**（0.997/0.997，误报也同为 0.023）。有本地传感证据的
        只有真正的对手方，问谁都一样——问所有人**不会造出证据**。
      - **也没有造出冤枉**，这一点原先预判错了。以为无对手方的活动会照样开窗并
        全部超时成为假指控；实际上双截止时刻的设计把它们兜住了：对手方从未被派发，
        互证窗口就从不装填，于是归档为 `NOT_DISPATCHED` 而非指控。这反过来是对
        **本文协议自身**的一个发现——双截止时刻是"多问不会多冤枉"的原因。

    于是 `W2` 的代价是纯粹的：见证集规模 4.95 倍（即互证带宽 4.95 倍），检出零
    增益，另加一大批永远悬而未决的待确认事项——那是**覆盖率的假象**，看着监控了
    更多活动，实则一条也结算不了。    这恰好从反面支持 $O(1)$ 见证集的主张。

    `W2`: the witness set is every device class; the rest matches this paper.

    This is "if you do not know whom to ask, ask everyone." The measurement
    splits in two, and one half is the opposite of the expectation, so it is
    written as measured:

      - **Detection matches this paper bit for bit** (0.997/0.997, and the
        false-alarm rate is also 0.023). Only the real counterpart has local
        sensor evidence, so whom you ask does not matter — asking everyone
        **does not create evidence**.
      - **It also does not create false charges**, which the earlier prediction
        got wrong. The fear was that activities with no counterpart would still
        open a window and all time out into false charges. The two-deadline
        design catches them: if the counterpart was never dispatched, the
        corroboration window is never filled, so they are archived as
        `NOT_DISPATCHED` rather than charged. That is a finding about **this
        paper's own protocol** — the two deadlines are why asking more does not accuse more.

    So `W2`'s cost is pure: a witness set 4.95 times larger (corroboration
    bandwidth 4.95 times larger), zero detection gain, plus a large pile of
    pending items that never settle — a **mirage of coverage**. It looks like
    more activities are monitored, but none of them can be settled. That is
    support, from the other side, for an $O(1)$ witness set.
    """
    name: str = W2

    def eligible(self, act) -> frozenset[str]:
        return frozenset(device_class(d) for d in self.graph.resources)


@dataclass
class RandomWitnessPolicy(WitnessPolicy):
    """`W3`：随机提名 $k$ 个设备类作见证者，$k$ 取本文见证集的规模。

    对应随机委员会一类做法。失效机理是结构性的：随机挑中的设备对**这一次**交接
    没有本地传感证据，故它到场不了、也确认不了。

    实测检出率崩到 0.108（本文 0.997），而误报仍低（0.002）——原先预判"检出与
    误报同时趋近 1"是错的，同样因为双截止时刻把无法结算的待确认事项归档为
    `NOT_DISPATCHED`。所以 `W3` 的失败形态是**什么都发现不了**，不是**乱指控**。

    报告口径仍须给出 检出率 - 误报率（判别力），这是方法论要求而非本例所需：
    换一个不含双截止时刻的协议，随机提名就会以乱指控的形态失败。

    **提名必须按活动身份哈希，不可用顺序推进的随机数发生器。** 第一版用了一个
    有状态的 `random.Random`，于是同一条基线在"先算见证集规模再回放"与"先回放
    再算规模"两种调用顺序下给出不同的检出率（0.108 与 0.129）——那不是随机性，
    是不可复现。改为对 (seed, case, event_id) 取哈希后，提名对同一活动恒定，
    与调用次数、调用顺序都无关。

    `W3`: nominate $k$ device classes at random as witnesses, with $k$ equal to this paper's witness-set size.

    This is the random-committee family. The failure is structural: a randomly
    chosen device has no local sensor evidence of **this** handover, so it
    cannot show up and cannot confirm.

    Measured detection collapses to 0.108 (this paper: 0.997), while the
    false-alarm rate stays low (0.002) — the earlier prediction that "detection
    and false alarms both go to 1" was wrong, again because the two deadlines
    archive unsettlable pending items as `NOT_DISPATCHED`. So `W3` fails as
    **it finds nothing**, not as **it accuses at random**.

    The report must still give detection rate minus false-alarm rate
    (discriminability). That is a methodological requirement, not something
    this example needs: on a protocol without the two deadlines, random
    nomination fails in the form of random accusations.

    **Nomination must be a hash of the activity identity, not a sequential
    RNG.** The first version used a stateful `random.Random`, so the same
    baseline gave different detection rates (0.108 and 0.129) under "compute
    witness-set size then replay" versus "replay then compute size" — that is
    not randomness, it is irreproducibility. Hashing (seed, case, event_id)
    makes the nomination constant for an activity, independent of call count
    and call order.
    """
    name: str = W3
    k: int = 1
    seed: int = 42

    def __post_init__(self) -> None:
        self._classes = sorted({device_class(d) for d in self.graph.resources})

    def eligible(self, act) -> frozenset[str]:
        base = super().eligible(act)
        if not base:
            return base            # 无对手方区间对所有规则都一样，不在此制造差异 / the no-counterpart interval is the same for every rule; do not invent a difference here
        k = max(1, min(self.k or len(base), len(self._classes)))
        tag = f"{self.seed}|{act.case}|{act.event_id}|{act.device}|{act.op}"
        rng = random.Random(hashlib.blake2b(tag.encode(),
                                            digest_size=8).digest())
        return frozenset(rng.sample(self._classes, k))

    def admits(self, pending, actor_act) -> bool:
        return device_class(actor_act.device) in pending.expected


@dataclass
class SpatialNeighborPolicy(WitnessPolicy):
    """`W4`：按物料流邻接提名见证者，即 COLAW/Vouch+ 那条"地理邻居作证"原则。

    **移植的是选取原则，不是它们的完整系统。** 二者的实现依赖测距/RSSI，本数据
    没有，硬跑等于自己发明一个方法再冠它的名（见 README 第四节末）。可移植且
    可核对的部分是原则本身：见证者 = 物理上相邻的设备。此处用 BPMN 的物料流边
    `move_graph` 定义邻接，`hops` 控制邻域半径。

    与本文规则的差别正是要测的东西：空间邻接是**静态**的、与当前工件走哪条工艺
    路线无关，故它既会漏掉真正的对手方（该对手方在图上不相邻），也会纳入大量
    与本次交接无关的设备（抬高见证集规模即带宽）。本文规则由**任务图 + 当前
    case** 共同确定，是动态的。

    `W4`: nominate witnesses by material-flow adjacency, the COLAW/Vouch+ principle that "a geographic neighbor witnesses."

    **What is ported is the selection principle, not their full system.** Both
    implementations depend on ranging / RSSI, which this data does not have;
    forcing a run would invent a method and then put their name on it (see the
    end of README section 4). The part that can be ported and checked is the
    principle itself: a witness is a physically adjacent device. Adjacency here
    is the BPMN material-flow edge `move_graph`, and `hops` sets the radius.

    The difference from this paper's rule is what is being measured: spatial
    adjacency is **static** and independent of which process route the current
    part takes, so it both misses the real counterpart (that counterpart is not
    adjacent on the graph) and includes many devices unrelated to this handover
    (which inflates witness-set size, i.e. bandwidth). This paper's rule is
    fixed jointly by the **task graph and the current case**, and it is dynamic.
    """
    name: str = W4
    hops: int = 1

    def __post_init__(self) -> None:
        self._at = {}
        for a, b in self.graph.move_graph:
            self._at.setdefault(a, set())
            self._at.setdefault(b, set())
        self._adj = {}
        for pos in self._at:
            self._adj[pos] = self._neighbors(pos)

    def _neighbors(self, pos: str) -> frozenset[str]:
        seen, frontier = {pos}, {pos}
        for _ in range(self.hops):
            nxt = set()
            for p in frontier:
                for a, b in self.graph.move_graph:
                    if self.graph.same_place(a, p):
                        nxt.add(b)
                    if self.graph.same_place(b, p):
                        nxt.add(a)
            frontier = nxt - seen
            seen |= nxt
        return frozenset(seen)

    def _classes_at(self, positions) -> frozenset[str]:
        out = set()
        for dev in self.graph.resources:
            dc = device_class(dev)
            if any(self.graph.same_place(f"{dev}_pos", p) for p in positions):
                out.add(dc)
            elif any(p.startswith(f"{dev}_") for p in positions):
                out.add(dc)
        return frozenset(out)

    def eligible(self, act) -> frozenset[str]:
        base = super().eligible(act)
        if not base:
            return base
        pos = act.end_pos or f"{act.device}_pos"
        near = self._adj.get(pos) or self._neighbors(pos)
        return self._classes_at(near) - {device_class(act.device)}

    def admits(self, pending, actor_act) -> bool:
        return device_class(actor_act.device) in pending.expected


# ---- 第一档：单观测者检测器 ---------------------------------------------
# ---- Tier 1: single-observer detectors ---------------------------------

class SingleObserver:
    """第一档基线的共同接口：**只看单观测者可见的字段**。

    与第二档不同，这一档不接对手方，故不能复用 `corroborate` 的协议对象，只能
    自成一路。两个方法的分工是硬要求：

      - `calibrate(benign)`：阈值只许由**纯良性流**标定（paper02 规则 30：
        阈值取自含攻击的流会把检出率假性归零）。
      - `accuse(reports)`：返回被指控的声明 id 集合。

    Common interface for tier-1 baselines: **only fields a single observer can see**.

    Unlike tier 2, this tier has no counterpart, so it cannot reuse
    `corroborate`'s protocol object and has to be its own path. The split
    between the two methods is a hard requirement:

      - `calibrate(benign)`: thresholds may be set only on a **pure benign
        stream** (paper02 rule 30: a threshold taken from a stream that
        contains attacks falsely zeros the detection rate).
      - `accuse(reports)`: return the set of accused statement ids.
    """
    name = "abstract"

    def calibrate(self, benign) -> "SingleObserver":
        return self

    def accuse(self, reports) -> set[int]:
        raise NotImplementedError


@dataclass
class RandomAccusation(SingleObserver):
    """`R0`：按匹配的告警率随机指控。地板。

    它的作用不是当对手，而是回答"你那 70% 的覆盖率会不会是撞上的"。在告警预算
    相同时，随机指控的期望检出率恰等于告警率本身，故任何**判别力显著大于 0** 的
    方法才算真的在工作。

    `R0`: random accusation at a matched alarm rate. The floor.

    Its job is not to be an opponent. It answers "could your 70% coverage have
    been a collision." At the same alarm budget, the expected detection rate of
    a random accusation equals the alarm rate itself, so only a method whose
    **discriminability is clearly above 0** is actually working.
    """
    name: str = R0
    #: 告警率，默认取本文在良性流上的误报率 69/3062，做等告警预算对照。
    #: Alarm rate. Default is this paper's benign false-alarm rate 69/3062, for an equal-alarm-budget contrast.
    alarm_rate: float = 69 / 3062
    seed: int = 42

    def accuse(self, reports) -> set[int]:
        rng = random.Random(self.seed)
        return {id(r) for r in reports
                if not r.withheld and rng.random() < self.alarm_rate}


@dataclass
class Watchdog(SingleObserver):
    """`S1`：调度看门狗，只看"该报的没报"。

    工业协议早有先例（IEC 61850 GOOSE 的 MaxTime 心跳与 fail-safe），本文不主张
    这一点。**窗口必须与本文一致地加上派发排队容差**，否则是在给基线设障。

    它对 P2 有效，对 P1/P3/P4 完全无效——一条按时到达、字段正常的伪造声明完全
    满足看门狗。这条与 `detect_diag` 内的同名基线是同一个东西，此处重写只为让
    第一档能在一张表里报齐；两处的数必须一致（断言 H1 对此设了交叉检查）。

    `S1`: the scheduler watchdog. It only looks at "what should have been reported was not."

    Industrial protocols already do this (IEC 61850 GOOSE MaxTime heartbeat and
    fail-safe); this paper does not claim it. **The window must add the same
    dispatch-queue allowance as this paper**, or the baseline is handicapped.

    It works on P2 and is completely useless on P1/P3/P4 — a forged statement
    that arrives on time with ordinary fields fully satisfies the watchdog.
    This is the same object as the same-named baseline inside `detect_diag`;
    it is rewritten here so tier 1 can be reported in one table. The two
    numbers must agree (assertion H1 cross-checks them).
    """
    name: str = S1
    #: 与 `corroborate.CorroborateConfig` 同口径。 / Same convention as `corroborate.CorroborateConfig`.
    margin_factor: float = 0.5
    margin_abs_s: float = 5.0
    fallback_s: float = 60.0
    dispatch_allowance_s: float = 260.0

    def _due(self, act) -> float:
        p = act.planned_s if act.planned_s else self.fallback_s
        return (p * (1.0 + self.margin_factor) + self.margin_abs_s
                + self.dispatch_allowance_s)

    def accuse(self, reports) -> set[int]:
        out = set()
        for r in reports:
            if r.withheld or r.t_report > r.t_cmd + self._due(r.act):
                out.add(id(r))
        return out


@dataclass
class PlanResidual(SingleObserver):
    """`S2`：计划一致性残差。这是"单观测者对照命令账本做残差检验"这一**方法类**
    的通用实现，引 model-based FDI 与 CUSUM 的一般文献，不对应任何特定实现。

    两个通道，都是单观测者能看到的：

      1. **结果位**：`outcome != success` 即异常。
      2. **时长残差** $r = (t_{\\text{end}} - t_{\\text{start}}) - \\text{planned}$，
         按 (设备, 操作) 分组，阈值取良性流上 $|r|$ 的分位数。

    失效是**构造性的**：P1 的伪造声明把结果位置为 success，时长取该 (设备, 操作)
    的中位数——恰好落在残差分布的最中央。攻击者不需要猜，因为**模型就写在命令
    里**：调度器已下发"送到某工位"，它只需如实回答这条命令再把结果位翻真。

    `S2`: plan-consistency residual. A generic implementation of the **method
    class** "a single observer tests residuals against the command ledger",
    citing the general model-based FDI and CUSUM literature, not any particular implementation.

    Two channels, both visible to a single observer:

      1. **Result bit**: `outcome != success` is an anomaly.
      2. **Duration residual** $r = (t_{\\text{end}} - t_{\\text{start}}) - \\text{planned}$,
         grouped by (device, operation), with the threshold at a quantile of $|r|$ on the benign stream.

    The failure is **structural**: a P1 forgery sets the result bit to success
    and the duration to the median of that (device, operation) — exactly the
    center of the residual distribution. The attacker does not need to guess,
    because **the model is written in the command**: the scheduler already
    issued "deliver to some station", and the attacker only answers that
    command and flips the result bit.
    """
    name: str = S2
    #: 分位数。默认 0.995 是**为基线争取的最紧阈值**：再紧就要在良性流上误报。
    #: Quantile. The default 0.995 is the **tightest threshold the baseline is given**: tighter and the benign stream false-alarms.
    quantile: float = 0.995
    _thr: dict = None
    _global: float = 0.0

    def calibrate(self, benign) -> "PlanResidual":
        by: dict[tuple[str, str], list[float]] = {}
        for r in benign:
            v = _residual(r.act)
            if v is not None:
                by.setdefault((r.act.device, r.act.op), []).append(abs(v))
        self._thr = {k: _quantile(v, self.quantile) for k, v in by.items()}
        allv = [x for v in by.values() for x in v]
        self._global = _quantile(allv, self.quantile) if allv else 0.0
        return self

    def accuse(self, reports) -> set[int]:
        out = set()
        for r in reports:
            if r.withheld:
                out.add(id(r))
                continue
            if getattr(r.act, "outcome", "success") != "success":
                out.add(id(r))
                continue
            v = _residual(r.act)
            if v is None:
                continue
            thr = (self._thr or {}).get((r.act.device, r.act.op), self._global)
            if abs(v) > thr:
                out.add(id(r))
        return out


@dataclass
class Conformance(SingleObserver):
    """`S3`：对齐式一致性检验（过程挖掘）。

    本数据集本就是过程挖掘数据集、带 16 个 BPMN，alignment-based conformance
    是此场景下最标准、最好引、工程上真会部署的方法，故它是第一档里最强的一条。

    ## 操作化：只保留对攻击者真正不利的两条规则

    朴素的"case 内相邻活动必须满足模型顺序与位置续接"在本日志上误报率高达 28%，
    那是给基线设障，不能用。根因有三，都必须回避：

      1. case 内并发多条物料链（空料桶 vs 工件）时间交错，相邻活动经常**不是**
         同一条物料流上的前后手；
      2. 可达闭包把 XOR 分支上的可选后继都收进来，真对齐在 Petri 网语义下会
         接受这些交错；
      3. 部分 BPMN 服务任务仍是 `TO_BE_SET`，模型语言本身不完整。

    因此本实现只保留两条**不会误伤良性、却仍对伪造声明最不利**的规则：

      A. `(设备类, 操作)` 不在**任何**工作流的任务集合内（真正的非法活动）；
      B. 两条活动在物理上确为交接（交付位置 = 取件位置），且其顺序是模型顺序
         关系的严格逆序。

    两条在良性流上误报均为 0（见 `tools/tier1_diag`）。对 P1/P3 检出亦为 0——
    因为伪造声明是**合法活动的逐字段拷贝**，落在模型语言里，对齐代价为 0。
    这就是构造性不可能：谎言在于物理事件没发生，一致性检验只看日志。

    `S3`: alignment-style conformance (process mining).

    This dataset is itself a process-mining dataset, with 16 BPMN models, and
    alignment-based conformance is the most standard, most citable, and most
    likely-to-be-deployed method in this setting, so it is the strongest row in tier 1.

    ## Operationalization: keep only the two rules that actually hurt the attacker

    A naive rule "adjacent activities in a case must satisfy model order and
    position continuation" false-alarms at 28% on this log. That handicaps the
    baseline and cannot be used. Three causes, all of which must be avoided:

      1. Several material chains run concurrently inside a case (empty bucket
         vs. workpiece) and interleave in time, so adjacent activities are
         often **not** predecessor and successor on the same material flow;
      2. the reachable closure pulls in optional successors on XOR branches,
         and a real alignment under Petri-net semantics accepts those interleavings;
      3. some BPMN service tasks are still `TO_BE_SET`, so the model language itself is incomplete.

    This implementation therefore keeps only two rules that **do not injure
    the benign stream and are still the most adverse to a forgery**:

      A. `(device class, operation)` is in **no** workflow's task set (a truly illegal activity);
      B. two activities are physically a handover (delivery position = pickup
         position) and their order is the strict reverse of the model order.

    Both have zero false alarms on the benign stream (see `tools/tier1_diag`).
    Detection of P1/P3 is also 0 — the forgery is a **field-by-field copy of a
    legal activity**, it lies in the model language, and the alignment cost is 0.
    That is constructive impossibility: the lie is that the physical event did
    not happen, and conformance only looks at the log.
    """
    name: str = S3
    graph: TaskGraph = None
    _all_tasks: set = None

    def calibrate(self, benign) -> "Conformance":
        self._all_tasks = {k for s in (self.graph.wf_tasks or {}).values()
                           for k in s}
        return self

    def accuse(self, reports) -> set[int]:
        out = set()
        all_tasks = self._all_tasks or {
            k for s in (self.graph.wf_tasks or {}).values() for k in s}
        prev: dict[str, object] = {}
        for r in sorted(reports, key=lambda x: x.t_report):
            if r.withheld:
                out.add(id(r))
                continue
            a = r.act
            order = (self.graph.wf_order or {}).get(
                getattr(a, "workflow", None), set())
            key = (device_class(a.device), a.op)
            bad = bool(all_tasks) and key not in all_tasks
            p = prev.get(a.case)
            if p is not None and not bad:
                pk = (device_class(p.device), p.op)
                linked = self.graph.same_place(
                    produced_at(p.device, p.end_pos),
                    consumed_at(a.device, a.start_pos))
                if linked and (key, pk) in order and (pk, key) not in order:
                    bad = True
            if bad:
                out.add(id(r))
            prev[a.case] = a
        return out


def _residual(act) -> float | None:
    if not (act.t_start and act.t_end and act.planned_s):
        return None
    return (act.t_end - act.t_start).total_seconds() - act.planned_s


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    return ys[min(len(ys) - 1, int(round(q * (len(ys) - 1))))]


def make_tier1(family: str, graph: TaskGraph, **kw) -> SingleObserver:
    """按族名构造第一档检测器。

    Build a tier-1 detector by family name.
    """
    if family == R0:
        return RandomAccusation(**kw)
    if family == S1:
        return Watchdog(**kw)
    if family == S2:
        return PlanResidual(**kw)
    if family == S3:
        return Conformance(graph=graph, **kw)
    raise ValueError(f"未知第一档基线：{family}")


def make(family: str, graph: TaskGraph, **kw) -> WitnessPolicy:
    """按族名构造选取规则。`OURS` 返回默认规则，用于同一入口下的对照。

    Build a selection rule by family name. `OURS` returns the default rule, for a contrast under the same entry point.
    """
    if family == OURS:
        return WitnessPolicy(graph, name=OURS)
    if family == W1:
        return QuorumVotePolicy(graph)
    if family == W2:
        return InterrogateAllPolicy(graph)
    if family == W3:
        return RandomWitnessPolicy(graph, **kw)
    if family == W4:
        return SpatialNeighborPolicy(graph, **kw)
    raise ValueError(f"未知基线族：{family}")


def witness_set_sizes(policy: WitnessPolicy, records) -> list[int]:
    """各活动的见证集规模。带宽与它成正比，故这是 $O(1)$ 主张的直接证据。

    Witness-set size of each activity. Bandwidth is proportional to it, so this is direct evidence for the $O(1)$ claim.
    """
    return [len(policy.eligible(r.act if hasattr(r, "act") else r))
            for r in records]


# ---- 第三档：心跳 / 带宽通道（解析对照，不走回放）----------------------
# ---- Tier 3: heartbeat / bandwidth channel (closed form, no replay) ----

#: 等带宽对照时，"全量状态上报"的报文大小。取 128 B：足够装设备 id、操作、
#: 起终点、时长与结果位，与工业状态帧同量级；也与 `silence.pbft_bandwidth_bps`
#: 的默认 msg_bytes 一致，避免两处对照各用各的数。
#: Message size of a "full state report" in the equal-bandwidth contrast.
#: 128 B is enough for device id, operation, endpoints, duration, and the
#: result bit, the same order as an industrial status frame; it also matches
#: the default msg_bytes of `silence.pbft_bandwidth_bps`, so the two contrasts
#: do not each pick their own number.
FULL_REPORT_BYTES = 128


@dataclass(frozen=True)
class EqualBandwidthPeriodic:
    """`H1`：等带宽周期性全量上报。

    给定可问责沉默的最省配置 `design`（带宽 $B = n L / T_{hb}$），同等带宽下
    周期性全量上报的周期只能是

        T_period = n * report_bytes / B = (report_bytes / L) * T_hb

    于是同样的 $r$ 次连续缺失判决，检测时延放大 `report_bytes / L` 倍。这不是
    仿真噪声，是带宽守恒的直接推论——也是"等带宽对比"第一次做得干净的原因：
    `budget.py` 先把 $B$ 从安全预算解出来，再代入这里。

    本条**不比 P1 检出率**：全量上报仍是单观测者可见字段，对任务状态伪造的
    检出与 `S1`/`S2` 同属结构性 0（第一档已证）。它比的是沉默通道上的时延。

    `H1`: equal-bandwidth periodic full reports.

    Given the cheapest accountable-silence configuration `design` (bandwidth
    $B = n L / T_{hb}$), a periodic full report at the same bandwidth can only have period

        T_period = n * report_bytes / B = (report_bytes / L) * T_hb

    The same verdict of $r$ consecutive misses then has detection latency
    scaled by `report_bytes / L`. That is not simulation noise; it is a direct
    corollary of bandwidth conservation — and the reason an equal-bandwidth
    comparison is clean for the first time: `budget.py` solves $B$ from the
    safety budget, and that $B$ is substituted here.

    This row **does not compare P1 detection rates**: a full report is still
    single-observer fields, and detection of task-state falsification is the
    same structural 0 as `S1`/`S2` (already shown in tier 1). What it compares
    is latency on the silence channel.
    """
    name: str = H1
    silence: Design = None
    report_bytes: int = FULL_REPORT_BYTES
    token_bytes: int = crypto.TOKEN_BYTES
    n_devices: int = 28
    skew_s: float = 0.01

    @property
    def period_s(self) -> float:
        return (self.n_devices * self.report_bytes
                / self.silence.bandwidth_bps)

    @property
    def detect_delay_s(self) -> float:
        return self.silence.r_misses * self.period_s + self.skew_s

    @property
    def latency_ratio(self) -> float:
        """相对可问责沉默的检测时延倍率。

        Detection-latency ratio relative to accountable silence.
        """
        return self.detect_delay_s / self.silence.detect_delay_s

    @property
    def size_ratio(self) -> float:
        return self.report_bytes / self.token_bytes


@dataclass(frozen=True)
class UnboundGoose:
    """`H2`：无密码绑定的 GOOSE 式心跳。

    IEC 61850 GOOSE 的 MaxTime 能发现"该报的没报"（活性），但心跳本身没有
    与设备身份绑定的一次性凭证。任何人都能注入或抑制心跳帧，故：

      - 能检出沉默（与看门狗同能力）；
      - **不能**产出可转移的归责证据；
      - **不能**阻止攻击者替被沉默设备伪造心跳以掩盖 P2。

    这是活性 ≠ 归责的结构化对照，不是检出率赛马。

    `H2`: a GOOSE-style heartbeat with no cryptographic binding.

    IEC 61850 GOOSE MaxTime can find "what should have been reported was not"
    (liveness), but the heartbeat itself has no one-time credential bound to
    device identity. Anyone can inject or suppress a heartbeat frame, so:

      - silence can be detected (the same ability as a watchdog);
      - it **cannot** produce transferable attribution evidence;
      - it **cannot** stop an attacker from forging a heartbeat for a silenced device to cover P2.

    This is a structural contrast of liveness versus attribution, not a detection-rate race.
    """
    name: str = H2
    detects_silence: bool = True
    binds_identity: bool = False
    transferable_evidence: bool = False
    resists_spoofed_heartbeat: bool = False


@dataclass(frozen=True)
class TeslaDelayedAuth:
    """`H3`：TESLA 式延迟密钥认证。

    TESLA / RFC 4082 **明确声明不提供不可否认性**：密钥 $K_i$ 披露之后，
    任何人都能用它重算 MAC，伪造"合法"的历史包。`crypto.py` 的前置条件 1–3
    正是为与此划界——本文把链上原像直接当作一次性凭证，披露后第三方仍能验证
    "只有承诺者能产生该原像"。

    `forge_after_disclosure` 把这条写进可执行的反例：披露后的 MAC 可被第三方
    复现，故归责失败。

    `H3`: TESLA-style delayed-key authentication.

    TESLA / RFC 4082 **explicitly do not provide non-repudiation**: after key
    $K_i$ is disclosed, anyone can recompute the MAC and forge a "valid"
    historical packet. Preconditions 1–3 in `crypto.py` are exactly the line
    drawn against that — this paper treats the chain preimage itself as a
    one-time credential, and after disclosure a third party can still verify
    that "only the committer can produce that preimage."

    `forge_after_disclosure` writes this as an executable counterexample: after
    disclosure the MAC can be reproduced by a third party, so attribution fails.
    """
    name: str = H3
    authenticates: bool = True
    non_repudiation: bool = False

    def forge_after_disclosure(self, key: bytes, msg: bytes
                               ) -> tuple[bytes, bool]:
        """密钥披露后，第三方重算 MAC。返回 (伪造标签, 校验是否通过)。

        After key disclosure, a third party recomputes the MAC. Returns (forged tag, whether the check passes).
        """
        tag = crypto.mac(key, msg)
        return tag, crypto.mac_ok(key, msg, tag)


def equal_bandwidth_periodic(design: Design, *, n_devices: int = 28,
                             report_bytes: int = FULL_REPORT_BYTES,
                             token_bytes: int = crypto.TOKEN_BYTES,
                             skew_s: float = 0.01) -> EqualBandwidthPeriodic:
    """由可问责沉默的可行配置构造等带宽周期上报对照。

    Build the equal-bandwidth periodic-report contrast from a feasible accountable-silence configuration.
    """
    return EqualBandwidthPeriodic(
        silence=design, report_bytes=report_bytes, token_bytes=token_bytes,
        n_devices=n_devices, skew_s=skew_s)


def unbound_goose() -> UnboundGoose:
    return UnboundGoose()


def tesla_delayed_auth() -> TeslaDelayedAuth:
    return TeslaDelayedAuth()


# ---- 第四档：先知天花板 ------------------------------------------------
# ---- Tier 4: the oracle ceiling ----------------------------------------

@dataclass(frozen=True)
class SensorOracle:
    """`U1`：每个交接点均有独立传感器的先知。

    覆盖率可达 1.0（每个交付位置都有与设备无关的传感证据）。本文实测覆盖
    70.05%，差额即覆盖缺口——也是按需主动互证的靶区。先知不提升已覆盖部分的
    检出（本文在已互证区间已是 1.000），它只回答"还差多少"。

    `U1`: an oracle with an independent sensor at every handover.

    Coverage can reach 1.0 (every delivery position has sensor evidence
    independent of the device). This paper's measured coverage is 70.05%; the
    difference is the coverage gap — also the target of on-demand active
    corroboration. The oracle does not raise detection on the already covered
    part (this paper is already 1.000 on the corroborated interval). It only
    answers "how much is still missing."
    """
    name: str = U1
    n_activities: int = 0
    n_ours: int = 0
    n_oracle: int = 0

    @property
    def ours_coverage(self) -> float:
        return self.n_ours / self.n_activities if self.n_activities else 0.0

    @property
    def oracle_coverage(self) -> float:
        return self.n_oracle / self.n_activities if self.n_activities else 0.0

    @property
    def gap(self) -> float:
        return self.oracle_coverage - self.ours_coverage


def sensor_oracle(records) -> SensorOracle:
    """由覆盖记录构造先知天花板。

    先知在每个交付位置都有传感器，故对所有活动都能给出独立证据（含同设备
    接手、无人取件、模型未列）。本文只在存在独立设备对手方时才有证据。

    Build the oracle ceiling from coverage records.

    The oracle has a sensor at every delivery position, so it can give
    independent evidence for every activity (including same-device handovers,
    nobody picking up, and positions absent from the model). This paper has
    evidence only when an independent device counterpart exists.
    """
    n = len(records)
    n_ours = sum(1 for r in records if r.status == coverage.OK)
    return SensorOracle(n_activities=n, n_ours=n_ours, n_oracle=n)


def silence_vs_periodic(design: Design, **kw) -> dict:
    """`H1` 的一页纸摘要：等带宽下时延倍率与是否仍落入检测预算。

    One-page summary of `H1`: the latency ratio at equal bandwidth, and whether it still fits the detection budget.
    """
    h1 = equal_bandwidth_periodic(design, **kw)
    return {
        "silence_T_hb_s": design.t_hb_s,
        "silence_r": design.r_misses,
        "silence_detect_s": design.detect_delay_s,
        "silence_bandwidth_bps": design.bandwidth_bps,
        "periodic_period_s": h1.period_s,
        "periodic_detect_s": h1.detect_delay_s,
        "latency_ratio": h1.latency_ratio,
        "size_ratio": h1.size_ratio,
        "report_bytes": h1.report_bytes,
        "token_bytes": h1.token_bytes,
    }
