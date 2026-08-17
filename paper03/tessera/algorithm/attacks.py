"""红队注入器 P1–P4，对应引导例的四条攻击路径。

公开数据集里没有"任务状态伪造"的标注，注入器本身就是评测协议的一部分。
编号与 `../paper03-NewIdea.md` 引导例**必须一致**——paper02 记录过编号错位
的代价：按错位编号跑出来的结果写进论文，每个编号都是错的。

    P1 谎报完成    位置真实、状态位翻真，不维持心跳  -> 互证 + 沉默都能抓
    P2 完全沉默    零消息，令接收方按命令账本推进    -> 只有可问责沉默能判定
    P3 假称合法    谎报完成且**按时披露原像**        -> 只有耦合互证能抓
    P4 串谋        耦合双方同时被劫持                -> 承认的边界，由串谋界量化

## P1 与 P3 的区别（相对 `paper03-NewIdea.md` 引导例的一处细化）

引导例把路 1 与路 3 都写成"谎报完成"，差别只在证据构造。实现时发现这样两族
会跑出完全相同的数字，属于 paper02 设计约束第 8 条警告的"跑了但其实是同一个
攻击"。因此细化为**攻击者是否维持心跳**：

  - P1 是朴素的谎报者，不理会心跳协议。它被互证否证，也被原像缺失确定性判定，
    且后者快两个数量级。这说明可问责沉默的价值不止于 P2。
  - P3 是老练的谎报者，按时披露原像以维持"合法沉默"的外观。沉默机制在它面前
    毫无信号，**只有耦合互证能抓**。这是耦合互证不可被替代的直接证据，也是
    引导例"路 3 自证其罪"的实现：已披露的原像等同于在该槽签署"我未偏离"，
    与对手方的反证一并构成不可否认的作恶证据。

消融的读法由此变得干净：去掉互证，P3 完全逃脱；去掉沉默，P1/P2 的检测时延
从 1.8 s 退化到数十秒。两个机制各自都有对方覆盖不到的攻击。

## 为什么 P1 比 paper02 的 A4 更强

paper02 的 A4（状态模仿）需要攻击者**自己挑一个结构上最可能的下一步**，
注入器强度取决于它对转移模型的掌握，弱版本会制造异常重复而被结构通道抓到
（实测 0.19 对 0.00）。本文的设定里这个负担消失了：调度器已经通过命令账本
下发了"把工件送到 R3 工位"，攻击者只需**如实回答这条命令**、把结果位翻真。
它不需要猜模型，模型就写在命令里。

推论有两个，都要写进论文：其一，本文的攻击者比 paper02 的 A4 **严格更强**，
因为它不承担猜错的风险；其二，残差类检测在此**结构性失效**而非性能不足——
被伪造的量是离散任务状态，所有连续可观测量（位置、时长、转移标签）都保持在
良性值上，没有残差可供检验。断言 D1 把"每个字段都与良性一致"写成可检验的
构造性质，这比重跑一遍 paper02 的检测器更强：它说明失效是构造上的，不是
参数没调好。

## 攻击者知识等级

P1–P4 全部按 **knowledge='ledger'** 实现，即攻击者掌握命令账本（它本来就是
命令的接收方）与参考过程模型。不提供更弱的版本：弱注入器会让本文的头条主张
被测成假的，而那是自己骗自己。
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from statistics import median

from .coverage import OK, Corroboration
from .taskgraph import device_class

P1, P2, P3, P4 = "P1", "P2", "P3", "P4"
FAMILY_ZH = {P1: "谎报完成", P2: "完全沉默", P3: "假称合法", P4: "串谋"}
IMPLEMENTED = (P1, P2, P3, P4)


@dataclass
class Report:
    """设备上报的一条声明，附该活动在命令账本中的三个时刻（秒，相对日志起点）。

    与 `Activity` 的区别在于**它可能是假的**：`physical=False` 表示物理事件
    并未发生，只有声明存在。检测器不得读取 `physical` 与 `forged`，它们是
    真值标签，只供评测使用。

    三个时刻各有用处，不可互相替代：`t_cmd` 是调度器下发命令的时刻，沉默时
    仍然存在；`t_pickup` 是从起点取走工件的时刻，对上游交付的确认发生在此，
    **不是**操作结束时；`t_report` 是完成声明到达的时刻。
    """
    act: object
    t_report: float
    device: str
    t_cmd: float = 0.0
    t_pickup: float = 0.0
    #: 交付事件是否真的发生。False 时对手方不会有本地传感证据。
    physical: bool = True
    #: 是否出具"我已从起点取走工件"的确认。这与 `physical` 是**两件事**：
    #: P1 的受害设备确实取走了工件（故为上游作证成立），只是没有交付到终点；
    #: P2 的设备什么也没做也没说；P4 的串谋方并未取件但仍出具假确认。
    attests_pickup: bool = True
    #: 真值标签：这条声明是否为伪造。
    forged: bool = False
    #: P2 用：设备完全沉默，连声明都不发出。
    withheld: bool = False
    #: P3 用：该槽是否按时披露了哈希链原像。
    revealed: bool = True
    #: P4 用：为该声明背书的串谋见证者。
    colluding_witness: str | None = None
    #: 对手方的否证：被命令取件但本地传感器未记录工件到达。
    refutes: bool = False
    #: 对手方是无传感器的褐地设备，只能沉默，判定退化为等窗口超时。
    silent_witness: bool = False
    #: P4 用：该声明来自串谋的对手方，它为上游的假交接背书。
    accomplice: bool = False


@dataclass
class AttackSpec:
    family: str = P1
    #: 受攻击活动占可攻击池的比例。
    rate: float = 0.2
    devices: tuple[str, ...] = ()
    seed: int = 42
    #: P4 用：串谋规模上限。1 表示只劫持对手方一跳。
    collusion_hops: int = 1
    #: 是否让对手方显式否证（有到料传感器时成立）。False 则只能等超时。
    explicit_refutation: bool = True


def inject(records: list[Corroboration], spec: AttackSpec):
    """在良性互证记录流上注入攻击，返回 (声明流, 真值标签)。

    输入取 `coverage.realized` 的产出而非裸活动流：注入需要知道每条声明的
    对手方是谁，那正是互证记录携带的信息。
    """
    if spec.family not in IMPLEMENTED:
        raise NotImplementedError(f"{spec.family} 未实现")
    fn = {P1: _false_completion, P2: _silence,
          P3: _false_legitimacy, P4: _collusion}[spec.family]
    return fn(records, spec)


def _t0(records) -> object:
    return min(r.act.t_consume for r in records)


def _secs(t, origin) -> float:
    return (t - origin).total_seconds()


def _typical_duration(records) -> dict[tuple[str, str], float]:
    """按 (设备, 操作) 的时长中位数。伪造声明的时长取此值，使纵向检验无残差。"""
    pool: dict[tuple[str, str], list[float]] = {}
    for r in records:
        d = r.act.duration_s
        if d:
            pool.setdefault((r.act.device, r.act.op), []).append(d)
    return {k: median(v) for k, v in pool.items()}


def _victims(records, spec, rng, *, need_witness: bool) -> set[int]:
    """按 rate 抽取受攻击声明。

    `need_witness=True` 时只从**有实测对手方**的声明里抽：P1/P3/P4 的攻击面
    定义在互证关系上，对无对手方的活动谈"互证能否否证"没有意义，把它们混进来
    会把覆盖率缺口算成检测失败。无对手方区间由按需主动互证处理，是另一件事。
    """
    pool = [r for r in records
            if (not need_witness or r.status == OK)
            and (not spec.devices or r.act.device in spec.devices)]
    if not pool:
        return set()
    k = max(1, int(round(len(pool) * spec.rate)))
    return {id(r) for r in rng.sample(pool, min(k, len(pool)))}


def _times(a, origin) -> dict:
    """一个活动的三个时刻。缺 t_cmd 时回落到操作开始时刻。"""
    return {
        "t_cmd": _secs(a.t_cmd or a.t_consume, origin),
        "t_pickup": _secs(a.t_consume, origin),
        "t_report": _secs(a.t_produce, origin),
    }


def benign_stream(records) -> list[Report]:
    """良性声明流，用于误报测量与基线。"""
    origin = _t0(records)
    return [Report(act=r.act, device=r.act.device, **_times(r.act, origin))
            for r in records]


def _false_completion(records, spec: AttackSpec, *, collude: bool = False):
    """P1 谎报完成：位置真实、任务状态位翻真。

    伪造的声明在**一切单观测者可见的字段上都与良性一致**：设备、操作、起点、
    终点由命令账本给定，时长取该 (设备, 操作) 的中位数，结果位为 success，
    上报时刻取计划完成时刻。唯一的破绽在对手方——工件并未到达，故对手方的
    本地传感器没有证据，不会出具确认签名。

    物理后果一并落实：`physical=False`，且对手方的取件**不可能成功**。调度器
    相信 A 已完成，故仍按账本命令对手方 B 取件；B 执行后其到料光电门无信号，
    于是发出否证而非确认（`refutes=True`）。`explicit_refutation=False` 时 B 是
    无传感器的褐地设备，只能沉默，判定退化为等窗口超时——两者检测时延差别很大，
    必须分开报。

    **建模的简化，须如实声明：** 被攻击 case 在 B 之后的活动仍按良性流保留。
    物理上工件卡在上游，后续活动本不该发生，但协议的判决在 B 处（否证）或窗口
    到期（超时）就已产生，晚于判决点的流不影响任何被报告的量。
    """
    rng = random.Random(spec.seed)
    origin = _t0(records)
    chosen = _victims(records, spec, rng, need_witness=True)
    typical = _typical_duration(records)
    witness_of = {id(r.witness): id(r) for r in records
                  if id(r) in chosen and r.witness is not None}

    out: list[Report] = []
    for r in records:
        a = r.act
        t = _times(a, origin)
        if id(a) in witness_of:
            if collude:
                out.append(Report(act=a, device=a.device, physical=False,
                                  forged=True, accomplice=True, **t))
            elif spec.explicit_refutation:
                out.append(Report(act=a, device=a.device, physical=False,
                                  refutes=True, **t))
            else:
                out.append(Report(act=a, device=a.device, physical=False,
                                  refutes=True, silent_witness=True, **t))
            continue
        if id(r) not in chosen:
            out.append(Report(act=a, device=a.device, **t))
            continue
        fake = copy.copy(a)
        fake.outcome = "success"
        d = typical.get((a.device, a.op))
        if d and fake.t_start:
            fake.t_end = fake.t_start + _delta(d)
        out.append(Report(act=fake, device=a.device, physical=False,
                          forged=True, revealed=False,
                          t_cmd=t["t_cmd"], t_pickup=t["t_pickup"],
                          t_report=t["t_cmd"] + (a.planned_s or 0.0)))
    return out, [r.forged for r in out]


def _delta(seconds: float):
    from datetime import timedelta
    return timedelta(seconds=seconds)


def _silence(records, spec: AttackSpec):
    """P2 完全沉默：设备一字不发，令调度器按命令账本推出"应已完成"。

    受攻击声明被整条扣留（`withheld=True`）且不披露原像。物理上什么也没发生，
    故下游同样被抑制。此攻击不需要对手方存在，因此从**全部**声明里抽样——
    沉默对无对手方区间同样有效，这正是可问责沉默不可被互证替代的原因。
    """
    rng = random.Random(spec.seed)
    origin = _t0(records)
    chosen = _victims(records, spec, rng, need_witness=False)
    witness_of = {id(r.witness): id(r) for r in records
                  if id(r) in chosen and r.witness is not None}

    out: list[Report] = []
    for r in records:
        a = r.act
        t = _times(a, origin)
        if id(a) in witness_of:
            # 上游沉默,调度器不会下发取件命令,对手方根本不会被激活
            continue
        if id(r) in chosen:
            out.append(Report(act=a, device=a.device, physical=False,
                              forged=True, withheld=True, revealed=False,
                              attests_pickup=False, **t))
        else:
            out.append(Report(act=a, device=a.device, **t))
    return out, [r.forged for r in out]


def _false_legitimacy(records, spec: AttackSpec):
    """P3 假称合法：按时披露原像，同时谎报完成。

    老练的攻击者不会放弃心跳——放弃即被原像缺失确定性判定。于是它维持"合法
    沉默"的外观，但也因此**主动交出了一份可证伪的声明**：$h_k$ 一旦披露，
    等同于在槽 k 上签署"我未偏离"。此后任一耦合对手方产生矛盾，已披露的
    $h_k$ 加签名承诺根即构成不可否认的作恶证据，可交第三方核验。

    这是本方法唯一能抓、而沉默机制毫无信号的攻击族，因此是"耦合互证不可被
    替代"的直接证据。与 Polygraph 一系的分水岭也在此：无需等到共识出现分歧
    才能归责。
    """
    reports, truth = _false_completion(records, spec)
    for r in reports:
        if r.forged:
            r.revealed = True
    return reports, truth


def _collusion(records, spec: AttackSpec):
    """P4 串谋：耦合双方同时被劫持，对手方代签假交接。

    实现为把伪造声明的对手方也标为串谋者（`colluding_witness`），于是该跳的
    互证通过、攻击在**本跳**成功。谎言能否存活取决于任务链上的下一跳是否也
    被劫持——`collusion_hops` 控制劫持链长。

    这不是"检测失败"，而是**被定理量化的边界**：要让谎言活到工件真正被消耗，
    链上每一跳都需一台被劫持设备。

    **链式传播必须建模，否则会把边界测成比实际更宽。** 串谋方为上游的假交接
    背书，但它自己也没有真的收到工件，因此它随后的交付声明同样是假的，会被
    **它自己的下游**（诚实设备）否证。所以一跳串谋只是把判决推迟一跳，
    并未逃脱。`collusion_hops` 控制劫持链长；链长不足时谎言总在第一个诚实
    对手方处被截住。互证超图上的链长分布由 `collusion.py` 结构性测量。
    """
    rng = random.Random(spec.seed)
    origin = _t0(records)
    chosen = _victims(records, spec, rng, need_witness=True)
    typical = _typical_duration(records)
    by_act = {id(r.act): r for r in records}

    # 沿任务链逐跳展开：受害者 -> 串谋方 -> ... -> 第一个诚实对手方
    liars: dict[int, int] = {}          # act id -> 该设备在链上的跳序
    refuters: set[int] = set()
    for r in records:
        if id(r) not in chosen:
            continue
        liars[id(r.act)] = 0
        cur, hop = r, 0
        while cur.witness is not None and hop < spec.collusion_hops:
            nxt = by_act.get(id(cur.witness))
            if nxt is None:
                break
            hop += 1
            liars[id(nxt.act)] = hop
            cur = nxt
        if cur.witness is not None:
            refuters.add(id(cur.witness))

    out: list[Report] = []
    for r in records:
        a = r.act
        t = _times(a, origin)
        if id(a) in refuters:
            if spec.explicit_refutation:
                out.append(Report(act=a, device=a.device, physical=False,
                                  refutes=True, **t))
            else:
                out.append(Report(act=a, device=a.device, physical=False,
                                  refutes=True, silent_witness=True, **t))
            continue
        hop = liars.get(id(a))
        if hop is None:
            out.append(Report(act=a, device=a.device, **t))
            continue
        fake = copy.copy(a)
        fake.outcome = "success"
        d = typical.get((a.device, a.op))
        if d and fake.t_start:
            fake.t_end = fake.t_start + _delta(d)
        wit = r.witness.device if r.witness is not None else None
        out.append(Report(
            act=fake, device=a.device, physical=False, forged=True,
            # 串谋者同样是老练攻击者，维持心跳，否则被原像缺失直接判定
            revealed=True, accomplice=hop > 0, colluding_witness=wit,
            t_cmd=t["t_cmd"], t_pickup=t["t_pickup"],
            t_report=t["t_cmd"] + (a.planned_s or 0.0)))
    return out, [r.forged for r in out]


def indistinguishability_report(records, spec: AttackSpec) -> dict:
    """P1 的构造性质核验：伪造声明在单观测者可见字段上与良性一致。

    逐字段比对伪造声明与其对应的良性活动，并统计伪造时长落在该 (设备, 操作)
    良性时长四分位距内的比例。这比重跑一遍残差检测器更强的主张：它说明
    残差类方法的失效是**构造上的**，不是参数没调好。
    """
    reports, _ = inject(records, spec)
    by_key = {(r.act.case, r.act.event_id): r.act for r in records}
    forged = [r for r in reports if r.forged and not r.accomplice]
    fields = ("device", "op", "case", "workflow", "start_pos", "end_pos",
              "outcome")
    same = {f: 0 for f in fields}
    dur_in_iqr = n_dur = 0
    pool: dict[tuple[str, str], list[float]] = {}
    for r in records:
        if r.act.duration_s:
            pool.setdefault((r.act.device, r.act.op), []).append(
                r.act.duration_s)
    for r in forged:
        a = r.act
        orig = by_key[(a.case, a.event_id)]
        for f in fields:
            same[f] += getattr(a, f, None) == getattr(orig, f, None)
        xs = sorted(pool.get((a.device, a.op), []))
        d = a.duration_s
        if xs and d:
            n_dur += 1
            lo = xs[max(0, int(0.25 * (len(xs) - 1)))]
            hi = xs[min(len(xs) - 1, int(0.75 * (len(xs) - 1)))]
            dur_in_iqr += lo <= d <= hi
    n = max(len(forged), 1)
    return {"n_forged": len(forged),
            "fields_intact": {f: same[f] / n for f in fields},
            "duration_in_iqr": dur_in_iqr / max(n_dur, 1),
            "n_duration_checked": n_dur}


@dataclass
class Fleet:
    """参与仿真的设备集合，供带宽与心跳核算使用。"""
    devices: tuple[str, ...] = ()
    classes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, records) -> "Fleet":
        devs = sorted({r.act.device for r in records})
        return cls(devices=tuple(devs),
                   classes=tuple(sorted({device_class(d) for d in devs})))
