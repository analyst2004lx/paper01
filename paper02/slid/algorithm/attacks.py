"""红队注入器:在良性日志上合成攻击流,构成可复用的评测协议。

公开数据集里没有调度层注入攻击的标注,注入器本身就是论文贡献之一——
它把"数据集不可得"这个风险转化为可复现的评测协议。

**编号以 新想法.md 的"攻击类型与检测通道覆盖矩阵"为准。** 本文件早先
用过另一套编号(A2=抢跑、A4=重放),与论文口径完全错位,按那套跑出来的
结果写进论文每个编号都是错的。已统一为下表:

  A1 朴素重放      立即或反复回放捕获的历史消息,时序痕迹明显
  A2 物理不可行注入 违反可行性掩码 F 的状态跳变,硬层直接否决
  A3 抢跑重放      等到接近合法时刻再注入(核心攻击,影响-可检测界针对它)
  A4 状态模仿      注入内容等于预测状态,纵向完全隐形,只有互锁通道能抓
  A5 渐变漂移      多步小幅偏移,单条都在正常区间内,靠序贯层累积
  A6 消息抑制/延迟 该来的没来,靠看门狗定时器(既有方法亦具备,非本文卖点)
  A7 多设备协同伪造 单设备视角自洽的最强攻击者,本方法的能力边界
  A8 跨通道工序伪造 同时改标签与时长:F 允许但非众数的下一步 + 抢跑
                     (结论二十五那个"人工多通道攻击"的红队实现;用来判定
                     Fisher 合成路该留还是该撤)

每种攻击都要标注**攻击者知识等级**:黑盒 / 知模型 / 知模型且知阈值。
最强的对手知道检测器参数并把 rho 压在 rho* 以下——此时防御方的保证不是
"检测到",而是"攻击者能获得的收益被限制在 rho* 以内",这正是论文的
影响-可检测性权衡命题所主张的东西。
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from datetime import timedelta
try:
    from typing import Literal
except ImportError:                                 # Python 3.7
    from typing_extensions import Literal

Family = Literal["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]
Knowledge = Literal["blackbox", "model", "model+threshold"]

#: 与 新想法.md 覆盖矩阵逐行对齐,供报告与断言交叉核对
FAMILY_ZH = {
    "A1": "朴素重放", "A2": "物理不可行注入", "A3": "抢跑重放",
    "A4": "状态模仿", "A5": "渐变漂移", "A6": "消息抑制/延迟",
    "A7": "多设备协同伪造", "A8": "跨通道工序伪造",
}
IMPLEMENTED = ("A1", "A2", "A3", "A4", "A5", "A6", "A8")
#: A7 需要攻击者同时伪造多设备且与命令账本对齐,是本方法声明的能力边界,
#: 不实现即不报告——比实现一个弱版本然后声称"我们也能抓 A7"诚实。
#: A8 已实现:它是判定 Fisher 合成路去留的专用攻击,不是主表的第六族。


@dataclass
class AttackSpec:
    family: Family = "A3"
    rho: float = 0.0              # 抢跑/拖延幅度
    n_messages: int = 1           # 持续注入的消息数
    devices: tuple[str, ...] = ()
    knowledge: Knowledge = "blackbox"
    seed: int = 42
    #: 抢跑后同 case 后续活动是否整体前移。True = 攻击者真的让进度提前
    #: (物理后果真实发生);False = 只伪造上报。两者威胁不同,必须分开跑。
    shift_downstream: bool = False
    #: 受攻击活动占全流的比例
    rate: float = 0.2
    #: A4/A8 用:结构通道的 TransitionModel。给了它,攻击者就会按转移
    #: 概率挑下一步(knowledge='model');不给则退化为复制当前操作,那会
    #: 制造异常重复、被结构通道轻易抓到,**低估了攻击者**。
    struct_model: object = None
    #: A8 用:参考过程模型,用来保证注入仍在一元/二元 F 内。缺了它,A8
    #: 会退化成随机改标签,硬层直接否决,合成路的贡献被硬层吃掉。
    proc_model: object = None


def inject(activities, spec: AttackSpec):
    """返回 (被污染的活动流, 真值标签)。

    标签与污染流一一对应,True 表示该条被篡改过。注入器只改时间戳与
    状态字段,不改 case/device/order,以保证下游按 (t, order) 排序后
    的流结构与良性流可比。
    """
    if spec.family not in IMPLEMENTED:
        raise NotImplementedError(
            f"{spec.family}({FAMILY_ZH.get(spec.family, '?')}) 尚未实现。"
            f"当前仅 {IMPLEMENTED} 可用;其余攻击族请勿在论文中报告结果,"
            f"以免出现'跑了但其实是别的攻击'的错位。")
    return {
        "A1": _naive_replay, "A2": _infeasible, "A3": _advance_replay,
        "A4": _mimicry, "A5": _drift, "A6": _suppress, "A8": _multichannel,
    }[spec.family](activities, spec)


def _victims(activities, spec, rng, need_duration: bool = True):
    """按 rate 抽取受攻击活动,返回 id 集合。"""
    pool = [a for a in activities
            if (a.duration_s or not need_duration)
            and (not spec.devices or a.device in spec.devices)]
    if not pool:
        return set(), pool
    k = max(1, int(len(pool) * spec.rate))
    return {id(a) for a in rng.sample(pool, min(k, len(pool)))}, pool


def _naive_replay(activities, spec: AttackSpec):
    """A1 朴素重放:把该设备上一条历史消息原样再发一遍。

    时间戳照搬历史值会立刻穿帮,故攻击者用当前时刻重发——于是状态序列
    出现异常重复(结构通道),而该状态的停留时长来自另一次执行(时序通道)。
    """
    rng = random.Random(spec.seed)
    chosen, _ = _victims(activities, spec, rng)
    hist: dict[str, object] = {}
    out, labels = [], []
    for a in activities:
        out.append(a)
        labels.append(False)
        prev = hist.get(a.device)
        if id(a) in chosen and prev is not None and a.t_end:
            b = copy.copy(prev)
            b.case = a.case
            # 必须落在 a 之后:同刻注入会因 event_id 较小而排到 a 之前,
            # 变成"重放发生在被重放的消息之前",时间上说不通
            b.t_cmd = a.t_end
            b.t_start = a.t_end + timedelta(seconds=1)
            b.t_end = b.t_start + timedelta(seconds=prev.duration_s or 1.0)
            b.t_done = b.t_end
            out.append(b)
            labels.append(True)
        hist[a.device] = a
    return out, labels


def _infeasible(activities, spec: AttackSpec):
    """A2 物理不可行注入:把操作换成同设备**不可达**的另一个操作。

    需要参考模型来判断可达性;没有 model 时退化为"换成该设备从未做过的
    操作",对掩码而言等价。
    """
    rng = random.Random(spec.seed)
    chosen, _ = _victims(activities, spec, rng, need_duration=False)
    ops_by_dev: dict[str, list] = {}
    for a in activities:
        ops_by_dev.setdefault(a.device, [])
        if a.op not in ops_by_dev[a.device]:
            ops_by_dev[a.device].append(a.op)
    all_ops = sorted({a.op for a in activities})
    out, labels = [], []
    for a in activities:
        if id(a) not in chosen:
            out.append(a)
            labels.append(False)
            continue
        alt = [o for o in all_ops if o not in ops_by_dev[a.device]] \
            or [o for o in ops_by_dev[a.device] if o != a.op]
        b = copy.copy(a)
        b.op = rng.choice(alt) if alt else a.op
        out.append(b)
        labels.append(b.op != a.op)
    return out, labels


def _mimicry(activities, spec: AttackSpec):
    """A4 状态模仿:注入一条**结构上最可能、时序上最普通**的伪造上报。

    这是本文的核心攻击,注入器的强度直接决定头条主张成不成立,所以必须
    按"攻击者知模型"来写:给了 struct_model 时,伪造的操作取该 case 当前
    状态下**转移概率最大的下一个操作**,执行设备取日志中真正做过该操作的
    设备,时长取该 (设备, 操作) 分组的中位数。于是纵向(标签合理、时长
    典型)与结构(转移最常见)都无懈可击。

    唯一露馅处在横向物料:伪造的搬运没有真的搬动工件,它要消耗的令牌不在
    那里。覆盖矩阵声称"A4 只有互锁通道能抓"指的就是这个。
    **未提供 struct_model 时退化为复制当前操作,那会制造异常重复而被结构
    通道轻易抓到——那是在低估攻击者,不可用于论文结论。**
    """
    rng = random.Random(spec.seed)
    chosen, _ = _victims(activities, spec, rng)
    typical: dict[tuple, list] = {}
    dev_of_op: dict[str, list] = {}
    for a in activities:
        if a.duration_s:
            typical.setdefault((a.device, a.op), []).append(a)
        dev_of_op.setdefault(a.op, [])
        if a.device not in dev_of_op[a.op]:
            dev_of_op[a.op].append(a.device)

    tm = spec.struct_model
    out, labels = [], []
    prev_op: dict[str, str] = {}
    for a in activities:
        out.append(a)
        labels.append(False)
        prev_op[a.case] = a.op
        if id(a) not in chosen or not a.t_end:
            continue
        dev, op = _likeliest_next(tm, a.device, a.op) if tm is not None \
            else (a.device, a.op)
        dev = dev or (dev_of_op.get(op) or [a.device])[0]
        pool = typical.get((dev, op)) or typical.get((a.device, a.op)) or [a]
        ref = pool[len(pool) // 2]              # 典型而非极端的一条
        b = copy.copy(ref)
        b.case, b.device, b.op = a.case, dev, op
        b.t_cmd = a.t_end
        b.t_start = a.t_end + timedelta(seconds=1)
        b.t_end = b.t_start + timedelta(seconds=ref.duration_s or 1.0)
        b.t_done = b.t_end
        out.append(b)
        labels.append(True)
    return out, labels


def _likeliest_next(tm, device: str, prev_op: str):
    """攻击者站在结构模型里挑转移概率最大的下一步,返回 (设备, 操作)。

    必须适配模型的状态粒度。结构通道的状态可能是操作名,也可能是
    '设备|操作' 二元组;若用操作名去二元组状态表里查,查不到就会退回复制
    当前操作,**攻击者被悄悄降级成朴素版本**,于是结构通道轻易抓到它、
    "只有互锁能抓 A4"被测成假。这个坑在 M3 粒度实验里真实发生过一次。
    """
    states = getattr(tm, "states", None) or []
    paired = any("|" in s for s in states)
    key = f"{device}|{prev_op}" if paired else prev_op
    try:
        i = states.index(key)
    except ValueError:
        return (device, prev_op)
    row = tm.counts[i]
    j = max(range(len(row)), key=lambda k: row[k])
    if row[j] <= 0:
        return (device, prev_op)
    nxt = states[j]
    if paired:
        d, _, o = nxt.partition("|")
        return (d, o)
    return (None, nxt)


def _ranked_successors(tm, prev_op: str):
    """按 P(next|prev) 降序返回 (概率, 状态名) ,只保留正概率。"""
    pred = tm.predictive(prev_op) if tm is not None else None
    states = getattr(tm, "states", None) or []
    if pred is None or not states:
        return []
    ranked = sorted(zip((float(x) for x in pred), states), reverse=True)
    return [(p, s) for p, s in ranked if p > 0]


def _op_of_state(state: str) -> str:
    return state.partition("|")[2] if "|" in state else state


def _capable_device(op: str, last_op_by_dev: dict, proc, dev_of_op: dict,
                    fallback: str):
    """挑一台能做该操作且不违反二元 F 的设备。找不到就返回 None。

    None 表示这条注入做不成 A8、会退化成 A2,必须跳过而不是硬塞。
    """
    cands = list(dev_of_op.get(op) or [])
    if fallback not in cands:
        cands.append(fallback)
    for d in cands:
        if proc is not None and not proc.can_perform(d, op):
            continue
        prev = last_op_by_dev.get(d)
        if prev is not None and proc is not None \
                and not proc.allows(d, prev, op):
            continue
        return d
    return None


def _multichannel(activities, spec: AttackSpec):
    """A8 跨通道工序伪造:插入一条 F 允许但非众数的下一步,并压缩时长。

    这是 `fusion_diag` 里那个 score-level `misplace` 的红队实现,不是打分
    时随机改前驱。攻击者知模型、知 F,目标是让调度器以为工序跳到了另一
    条仍合法的分支并且提前完成——两个残差都是收益本身带来的,不是攻击者
    变笨。

    与相邻攻击族的边界,必须钉死,否则数字不可读:

      vs A4  A4 插入**众数**下一步 + 典型时长,结构/时序都干净;
             A8 故意跳过众数,取概率次高且 F 仍允许的下一步,并压缩 rho。
      vs A2  A2 故意违反 F,硬层一票否决;A8 的候选在一元/二元 F 内,
             硬层按构造不应触发。找不到 F 允许的非众数后继就跳过该受害者,
             绝不退化为 A2。
      vs A3  A3 只压缩时长、不改标签;A8 两个都改。

    用插入而非原地改写:Trier 上多数设备类只有 1 个操作(vgr 只有搬运),
    原地改写几乎没有 F 允许的替代标签,A8 会退化成空攻击。插入可以换到
    另一台设备上仍合法的下一步,这才是"伪造工序位置"的原意。
    """
    tm = spec.struct_model
    if tm is None:
        raise ValueError(
            "A8 必须提供 struct_model。缺少它就无法按转移概率挑非众数后继,"
            "会退化成随机改标签,硬层直接否决,Fisher 的贡献被硬层吃掉——"
            "那不是在测合成路,是在测 A2。")
    rng = random.Random(spec.seed)
    chosen, _ = _victims(activities, spec, rng)
    typical: dict[tuple, list] = {}
    dev_of_op: dict[str, list] = {}
    for a in activities:
        if a.duration_s:
            typical.setdefault((a.device, a.op), []).append(a)
        dev_of_op.setdefault(a.op, [])
        if a.device not in dev_of_op[a.op]:
            dev_of_op[a.op].append(a.device)

    proc = spec.proc_model
    out, labels = [], []
    last_op_by_dev: dict[tuple, str] = {}      # (case, device) -> op
    n_skip = 0
    for a in activities:
        out.append(a)
        labels.append(False)
        last_op_by_dev[(a.case, a.device)] = a.op
        if id(a) not in chosen or not a.t_end:
            continue
        ranked = _ranked_successors(tm, a.op)
        # 跳过众数(那是 A4);从第二名起找第一个 F 允许的
        placed = False
        for _p, state in ranked[1:]:
            op = _op_of_state(state)
            case_last = {d: o for (c, d), o in last_op_by_dev.items()
                         if c == a.case}
            dev = _capable_device(op, case_last, proc, dev_of_op, a.device)
            if dev is None:
                continue
            pool = typical.get((dev, op)) or typical.get((a.device, a.op)) \
                or [a]
            ref = pool[len(pool) // 2]
            b = copy.copy(ref)
            b.case, b.device, b.op = a.case, dev, op
            b.t_cmd = a.t_end
            b.t_start = a.t_end + timedelta(seconds=1)
            dur = (ref.duration_s or 1.0) * max(1.0 - spec.rho, 1e-3)
            b.t_end = b.t_start + timedelta(seconds=dur)
            b.t_done = b.t_end
            out.append(b)
            labels.append(True)
            last_op_by_dev[(b.case, b.device)] = b.op
            placed = True
            break
        if not placed:
            n_skip += 1
    if not any(labels):
        raise RuntimeError(
            "A8 在本段日志上找不到任何 F 允许的非众数后继。合成路的"
            "存在理由在这个数据上不可测,不得用 score-level misplace 顶替。")
    spec._a8_skipped = n_skip                  # 诊断用,不影响注入
    spec._a8_injected = sum(labels)
    return out, labels


def _drift(activities, spec: AttackSpec):
    """A5 渐变漂移:对一段**连续**活动各施加小幅抢跑,单条都在正常区间内。

    与 A3 的差别是"每条都不显著、靠条数取胜",故 rate 控制的是漂移段
    长度而非零散比例——序贯层的价值只有在连续偏移下才体现得出来。
    """
    rng = random.Random(spec.seed)
    idx = [i for i, a in enumerate(activities) if a.duration_s]
    if not idx:
        return list(activities), [False] * len(activities)
    span = max(1, int(len(idx) * spec.rate))
    start = rng.randrange(max(1, len(idx) - span))
    hit = set(idx[start:start + span])
    out, labels = [], []
    for i, a in enumerate(activities):
        if i not in hit:
            out.append(a)
            labels.append(False)
            continue
        b = copy.copy(a)
        b.t_end = a.t_start + timedelta(seconds=a.duration_s * (1 - spec.rho))
        out.append(b)
        labels.append(True)
    return out, labels


def _suppress(activities, spec: AttackSpec):
    """A6 消息抑制:整条删除。

    注意本数据集把 start/complete 合成了一个活动实例,因此"抑制"只能是
    整条消失。看门狗对这一类**无能为力**——它在活动开始时布防,活动压根
    没出现就没布防。真正会被触发的是下游:被删活动本该产出的物料令牌不
    存在,后继活动的互锁检查落空。标签打在**后继活动**上,因为攻击的可
    观测后果出现在那里。
    """
    rng = random.Random(spec.seed)
    ordered = sorted((a for a in activities if a.t_consume is not None),
                     key=lambda a: (a.t_consume, a.order))
    chosen, _ = _victims(ordered, spec, rng, need_duration=False)
    keep, labels = [], []
    pending: dict[str, bool] = {}       # case -> 该 case 刚被删过一条
    for a in ordered:
        if id(a) in chosen:
            pending[a.case] = True
            continue
        keep.append(a)
        labels.append(pending.pop(a.case, False))
    return keep, labels


def _advance_replay(activities, spec: AttackSpec):
    """A3 抢跑重放:把执行时长压缩 rho,使完成上报提前。

    这是理论界 rho* 直接针对的攻击——攻击者想让调度提前,就必须让某个
    工序看起来比物理规律更快,而快多少受 sigma 约束。
    """
    rng = random.Random(spec.seed)
    out, labels = [], []
    shift: dict[str, timedelta] = {}
    victims = [a for a in activities
               if a.duration_s and (not spec.devices
                                    or a.device in spec.devices)]
    chosen = set()
    if victims:
        k = max(1, int(len(victims) * spec.rate))
        chosen = {id(a) for a in rng.sample(victims, min(k, len(victims)))}

    for a in activities:
        d = shift.get(a.case)
        hit = id(a) in chosen
        if not hit and d is None:
            out.append(a)
            labels.append(False)
            continue
        b = copy.copy(a)
        if d is not None:                       # 上游抢跑导致的整体前移
            for f in ("t_cmd", "t_start", "t_end", "t_done"):
                v = getattr(b, f, None)
                if v is not None:
                    setattr(b, f, v - d)
        if hit:
            cut = a.duration_s * spec.rho
            b.t_end = b.t_start + timedelta(seconds=a.duration_s - cut)
            if b.t_done is not None:
                b.t_done = b.t_done - timedelta(seconds=cut)
            if spec.shift_downstream:
                shift[a.case] = (shift.get(a.case, timedelta())
                                 + timedelta(seconds=cut))
        out.append(b)
        labels.append(hit)
    return out, labels


def sweep_rho(activities, family: Family = "A3",
              rhos=(0.05, 0.10, 0.15, 0.25, 0.50), **kw):
    """扫 rho 生成检出率曲线,与 timing.predicted_dr 的理论曲线对照。"""
    for rho in rhos:
        spec = AttackSpec(family=family, rho=rho, **kw)
        yield rho, inject(activities, spec)
