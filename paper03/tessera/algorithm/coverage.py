"""互证覆盖度与无对手方区间。

回答两个必须先量化的问题:
  1. 日志里的活动有多少比例存在对手方见证者(结构性覆盖上限)。这是耦合互证
     机制能触及的活动比例,和 paper02 那个"二元可行性掩码只覆盖 31% 的消息"
     是同一类问题——机制再好也管不到覆盖不到的部分,越早知道越好。
  2. 覆盖不到的那部分是什么。它们即**无对手方区间**,须由按需主动互证补足
     (`../paper03-NewIdea.md` 增补二)。这个清单同时是探测开销的输入。

覆盖分三层,不可混为一谈:
  - **模型可证**:任务图中 (设备类, 操作) 存在对手方见证者。这是设计上限。
  - **实测已证**:该 case 内确实有另一设备类从其交付位置取走了工件,
    即对手方本地传感证据在现实中真的产生了。
  - **未建模**:活动的位置对不在任何 BPMN 里(paper02 实测 2.62% 的物料移动
    如此)。这类按"未知"处理,不能算作违反,也不能算作互证失败。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median

from .ingest import Activity, case_chains
from .taskgraph import TaskGraph, consumed_at, device_class, produced_at

#: 覆盖判定的结果,顺序即降级顺序。
#: SELF_ONLY 与 NO_REALIZED 必须分开:前者交接确实发生了但接手方是**同一台
#: 设备**,故不存在独立的第二方传感证据(原地多工步加工即如此);后者是本 case
#: 内根本无人从该位置取件。二者对按需主动互证的含义不同——前者要换一个
#: 见证者,后者要造一个事件。
OK = "corroborated"
SELF_ONLY = "same_device_only"
NO_REALIZED = "no_realized_witness"
NO_MODEL = "no_model_witness"


@dataclass
class Corroboration:
    """一次交付声明的互证结果。"""
    act: Activity
    pos: str
    status: str
    witness: Activity | None = None
    delay_s: float | None = None
    terminal: bool = False   # 是否为该 case 的末位活动

    @property
    def key(self) -> tuple[str, str]:
        return (device_class(self.act.device), self.act.op)


def realized(acts, graph: TaskGraph) -> list[Corroboration]:
    """对每个活动求其在日志中真实出现的对手方见证者。

    作用域是 case:位置是跨 case 共享的物理地点,跨 case 取对手方会把并发
    工件混为一谈(paper02 互锁通道 LATE 类违反的成因)。

    **见证资格按设备类判定,见证独立性按设备实例判定。** 两者粒度不同,不是
    疏漏:前者是"这类设备的传感器能不能观测到这件事",只能从 BPMN 得知,而
    16 个模型只实例化了部分设备,按实例读会把未实例化的设备判为无资格
    (paper02 规则 13 同因);后者是"作证者是否为另一台物理机器",必须按实例,
    因为 vgr_1 与 vgr_2 是两台独立的机械手,各有自己的夹爪与光电传感器。
    按类判独立性会误杀本数据集中最有价值的一类互证事件——两条产线之间的
    工件交换正是 vgr_2 交付至 dm_2_sink_pos、vgr_1 从该位置取走。
    """
    out: list[Corroboration] = []
    for chain in case_chains(acts).values():
        for i, a in enumerate(chain):
            pos = produced_at(a.device, a.end_pos)
            last = i == len(chain) - 1
            if not graph.corroborable(a.device, a.op):
                out.append(Corroboration(a, pos, NO_MODEL, terminal=last))
                continue
            hit, self_hit = None, None
            for b in chain[i + 1:]:
                if not graph.same_place(pos,
                                        consumed_at(b.device, b.start_pos)):
                    continue
                if b.device == a.device:
                    self_hit = self_hit or b
                    continue
                hit = b
                break
            if hit is None:
                st = SELF_ONLY if self_hit is not None else NO_REALIZED
                out.append(Corroboration(a, pos, st, witness=self_hit,
                                         terminal=last))
            else:
                d = None
                if a.t_produce and hit.t_consume:
                    d = (hit.t_consume - a.t_produce).total_seconds()
                out.append(Corroboration(a, pos, OK, witness=hit,
                                         delay_s=d, terminal=last))
    return out


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def summarize(records: list[Corroboration], *, top: int = 12) -> dict:
    """覆盖度与互证窗口的诊断量。

    `delay_s` 的分位数直接给出耦合互证的 pending 窗口 Δ 该取多大——它是路 1
    检测时延的上界,并经安全裕度定理接入 FHI 时间预算(budget.py)。负延迟是
    并发导致的乱序(paper02 在互锁通道上实测 17 次),不是互证失败。
    """
    n = len(records)
    by_status = Counter(r.status for r in records)
    delays = [r.delay_s for r in records if r.delay_s is not None]
    uncovered = Counter(r.key for r in records if r.status != OK)
    gap = [r for r in records if r.status != OK]
    return {
        "n_activities": n,
        "n_corroborated": by_status[OK],
        "n_same_device_only": by_status[SELF_ONLY],
        "n_no_realized": by_status[NO_REALIZED],
        "n_no_model": by_status[NO_MODEL],
        "frac_corroborated": by_status[OK] / n if n else 0.0,
        "n_gap_terminal": sum(1 for r in gap if r.terminal),
        "n_gap_midchain": sum(1 for r in gap if not r.terminal),
        "delay_n": len(delays),
        "delay_negative": sum(1 for d in delays if d < 0),
        "delay_median_s": median(delays) if delays else None,
        "delay_p90_s": _pct(delays, 0.90),
        "delay_p95_s": _pct(delays, 0.95),
        "delay_max_s": max(delays) if delays else None,
        "uncovered_top": uncovered.most_common(top),
    }


def no_counterparty_ops(graph: TaskGraph) -> set[tuple[str, str]]:
    """任务图中不存在对手方见证者的 (设备类, 操作)。

    按需主动互证的作用对象。返回的是**模型级**清单,与日志无关,因此可在
    任务下发时预先判定,不必等运行时才发现无从互证。
    """
    return {(dc, op) for dc, ops in graph.capable.items() for op in ops
            if not graph.corroborable(dc, op)}
