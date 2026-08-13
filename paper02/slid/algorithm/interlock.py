"""M5 互锁通道:带时长的 Petri 网令牌一致性 + 命令-响应因果检查。

分两层,分层依据是实测违反率:

硬层(实测正常数据零违反,可直接报警):
  - F 违反:设备操作转移不在参考模型的可达闭包内(953 次检查 0 违反)
  - 因果缺失:状态上报没有前置 `assigned` 命令事件
  注意"响应时延短于物理下界"**不属于**硬层——派发阶段时长由调度器排队
  竞争主导(p95 达 253.6 s、sigma_log=1.475),不可作时长检验。命令-响应
  通道只做存在性与顺序检查。

软层(转成 p 值参与 M6 合成):
  - 物料流令牌不变量,实测残余 1.70% 良性违反
  - 任务数偏差等守恒量

令牌触发采用**带时长语义**:在 t_consume 消耗 start 位置的令牌,在
t_produce 在 end 位置产出令牌,并按时间戳顺序回放。同时消耗产出会把并发
活动误判为乱序(v3 -> v4 的修正,I 违反率由 1.42% 的口径问题变为可解释的
1.70% 全量口径)。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

CONSUME, PRODUCE = 0, 1


@dataclass
class Violation:
    kind: str            # 'F' | 'causal' | 'token'
    hard: bool
    case: str
    device: str
    op: str
    reason: str          # 人类可读,如"机械臂声称在生产,但无 AGV 投料记录"
    cause: str | None = None   # token 违反的成因:LATE / NEVER / FAILED


@dataclass
class TokenState:
    """(令牌类型, 位置) -> 计数。位置是跨 case 共享的物理地点。"""
    tokens: Counter = field(default_factory=Counter)

    def take(self, ttype: str, pos: str, model) -> bool:
        """消耗一枚令牌,考虑分拣机别名类。"""
        if self.tokens[(ttype, pos)] > 0:
            self.tokens[(ttype, pos)] -= 1
            return True
        for p in model.resolve(pos):
            if p != pos and self.tokens[(ttype, p)] > 0:
                self.tokens[(ttype, p)] -= 1
                return True
        return False

    def put(self, ttype: str, pos: str) -> None:
        self.tokens[(ttype, pos)] += 1


def _timeline(acts):
    """(时刻, 消耗/产出, 稳定序, 活动) 的时间序回放序列。"""
    ev = []
    for a in acts:
        t0, t1 = a.t_consume, a.t_produce
        if t0 is None:
            continue
        ev.append((t0, CONSUME, a.order, a))
        ev.append((t1 or t0, PRODUCE, a.order, a))
    ev.sort(key=lambda x: (x[0], x[1], x[2]))
    return ev


def check_case(acts, model, *, all_acts=None):
    """回放一个 case,返回 (违反列表, 计数器)。

    `all_acts` 含 failure 活动,仅用于诊断残余成因(区分 FAILED 与 NEVER)。
    """
    viols: list[Violation] = []
    cnt = Counter()
    if not acts:
        return viols, cnt

    # 该 case 有能力产出的令牌及其时刻,用于把残余违反归因
    produced_later = defaultdict(list)
    for a in acts:
        for tp in model.token_effects(a)[1]:
            produced_later[tp].append(a.t_produce or datetime.min)
    failed_prod = set()
    for a in (all_acts or ()):
        if a.outcome == "failure":
            failed_prod.update(model.token_effects(a)[1])

    state = TokenState()
    last_op: dict[str, str] = {}

    for t, kind, _, a in _timeline(acts):
        cons, prod = model.token_effects(a)
        if kind == PRODUCE:
            for ttype, pos in prod:
                state.put(ttype, pos)
            continue

        cnt["activities"] += 1

        # --- 硬层 1:可行性掩码 F(同一 case 内的同设备连续操作)---
        d = a.device
        if d in last_op:
            cnt["F_checked"] += 1
            if not model.allows(d, last_op[d], a.op):
                cnt["F_viol"] += 1
                viols.append(Violation(
                    "F", True, a.case, d, a.op,
                    f"设备 {d} 从 {last_op[d]} 直接跳到 {a.op},"
                    f"不在参考模型的可达闭包内"))
        last_op[d] = a.op

        # --- 硬层 2:命令-响应因果配对 ---
        if a.t_cmd is None:
            cnt["causal_viol"] += 1
            viols.append(Violation(
                "causal", True, a.case, d, a.op,
                f"设备 {d} 上报 {a.op},但调度器没有下发过对应命令"))

        # --- 软层:物料流令牌前置条件 ---
        for ttype, pos in cons:
            cnt["I_checked"] += 1
            if state.take(ttype, pos, model):
                continue
            cnt["I_viol"] += 1
            later = [x for x in produced_later.get((ttype, pos), ()) if x > t]
            if later:
                cause = "LATE"
                reason = f"{pos} 上的{_zh(ttype)}要到本 case 稍后才产出(乱序)"
            elif (ttype, pos) in failed_prod:
                cause = "FAILED"
                reason = f"{pos} 上的{_zh(ttype)}本应由一个失败的活动产出"
            else:
                cause = "NEVER"
                reason = f"本 case 内从未有活动在 {pos} 产出{_zh(ttype)}(缺失事件)"
            cnt[f"cause_{cause}"] += 1
            viols.append(Violation("token", False, a.case, d, a.op,
                                   reason, cause=cause))
    return viols, cnt


def _zh(ttype: str) -> str:
    return {"wp": "工件", "bk": "料桶"}.get(ttype, ttype)


def check_all(acts_by_case: dict, model, *, all_by_case: dict | None = None,
              scope: str = "case"):
    """在全部 case 上回放,返回 (违反列表, 汇总计数)。

    `scope='case'` 是逐 case 令牌账（原口径）；`scope='global'` 走跨 case
    全局令牌池 + 守恒，见 check_global 的说明。
    """
    if scope == "global":
        return check_global(acts_by_case, model)
    viols: list[Violation] = []
    total = Counter()
    for case, acts in acts_by_case.items():
        v, c = check_case(acts, model,
                          all_acts=(all_by_case or {}).get(case))
        viols.extend(v)
        total.update(c)
        if c["I_viol"]:
            total["cases_with_I_viol"] += 1
        total["cases"] += 1
    return viols, total


def check_global(acts_by_case: dict, model):
    """跨 case 全局令牌池 + 守恒。是"没有 NFC 时如何近似工件身份"的答案。

    结论八把逐 case 账的 17 次 LATE 残余归因为:**位置是跨 case 共享的物理
    地点,而令牌模型是逐 case 的**——并发 case 在同一位置更早产出过令牌,
    逐 case 账看不见它,于是把合法消耗判成乱序。全局池按时间序回放所有
    case 的事件即可消掉这一类。

    全局池显然比逐 case 账**宽松**,所以必须靠守恒把它箍住:每次产出最多被
    消耗一次(Counter 递减即是),于是"无产出不得消耗"与"不得双花"两条仍然
    成立——攻击者伪造一次消耗,只有在池子恰好非空时才蒙得过去。这个宽松
    代价是要实测的,不能假定它划算:q 变小会解开 min(1, alpha/q) 的功效
    天花板(结论三十),但同时也放走了一部分真攻击。
    """
    viols: list[Violation] = []
    cnt = Counter()
    state = TokenState()
    last_op: dict[tuple[str, str], str] = {}

    ev = []
    for case, acts in acts_by_case.items():
        ev.extend(_timeline(acts))
        cnt["cases"] += 1
    ev.sort(key=lambda x: (x[0], x[1], x[2]))

    bad_cases = set()
    for t, kind, _, a in ev:
        cons, prod = model.token_effects(a)
        if kind == PRODUCE:
            for ttype, pos in prod:
                state.put(ttype, pos)
            continue

        cnt["activities"] += 1
        key = (a.case, a.device)
        if key in last_op:
            cnt["F_checked"] += 1
            if not model.allows(a.device, last_op[key], a.op):
                cnt["F_viol"] += 1
                viols.append(Violation(
                    "F", True, a.case, a.device, a.op,
                    f"设备 {a.device} 从 {last_op[key]} 直接跳到 {a.op},"
                    f"不在参考模型的可达闭包内"))
        last_op[key] = a.op

        if a.t_cmd is None:
            cnt["causal_viol"] += 1
            viols.append(Violation(
                "causal", True, a.case, a.device, a.op,
                f"设备 {a.device} 上报 {a.op},但调度器没有下发过对应命令"))

        for ttype, pos in cons:
            cnt["I_checked"] += 1
            if state.take(ttype, pos, model):
                continue
            cnt["I_viol"] += 1
            cnt["cause_NEVER"] += 1
            bad_cases.add(a.case)
            viols.append(Violation(
                "token", False, a.case, a.device, a.op,
                f"全局池中 {pos} 上没有可用的{_zh(ttype)}"
                f"(此前无任何 case 在此产出,或已被消耗)",
                cause="NEVER"))
    cnt["cases_with_I_viol"] = len(bad_cases)
    return viols, cnt


def summary(cnt: Counter) -> dict:
    """把计数器折算成论文里报告的比率。"""
    def rate(v, c):
        return cnt[v] / cnt[c] if cnt[c] else 0.0
    return {
        "cases": cnt["cases"],
        "activities": cnt["activities"],
        "F_checked": cnt["F_checked"],
        "F_violations": cnt["F_viol"],
        "F_rate": rate("F_viol", "F_checked"),
        "I_checked": cnt["I_checked"],
        "I_violations": cnt["I_viol"],
        "I_rate": rate("I_viol", "I_checked"),
        "causal_violations": cnt["causal_viol"],
        "cause_LATE": cnt["cause_LATE"],
        "cause_NEVER": cnt["cause_NEVER"],
        "cause_FAILED": cnt["cause_FAILED"],
        "cases_with_I_viol": cnt["cases_with_I_viol"],
    }
