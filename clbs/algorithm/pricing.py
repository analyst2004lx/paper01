"""走廊-时段影子价格的估计(规格 5.5)。

注意:本模块驱动的价格协调机制经检验在本问题上系统性有害,`theta` 默认为 0,
故默认执行路径不会调用这里的估计器。保留实现是为了在论文中如实报告负面结果
(规格 13.2 数据、13.3 机制解释)。


价格 pi(c,b) 的定义:把走廊 c 在时间桶 b 的通行容量**松弛一个单位**所能换来的
makespan 改善,再除以桶宽,得到"每单位占用时长的边际代价"(无量纲比率)。

提供两种估计器,精度与代价互补:

1. `finite_difference_prices` —— 定义式估计。固定上层决策(机器指派、工序顺序、
   派车序列),把候选槽位的容量临时 +1 后重解一次,直接量出 makespan 改善。
   它不依赖任何凸性假设、不需要 LP 求解器,是本文报告价格时的**参照版本**;
   代价是每个候选槽位一次重解。

2. `surrogate_prices` —— 廉价代理。用关键链加权的实际让行等待做一阶近似,
   单次解码即可得到,供 GA 每代刷新使用。

两者的关系在实验中可直接检验(`price_agreement`):代理价与定义式价格的秩相关
若足够高,则代理价可安全替代;这是把启发式信号升格为"有理论依据的近似"所需的
证据,也是与"lam * 累计等待"这类无参照启发式的本质区别。

Shadow-price estimates for corridor-time slots (spec 5.5).

Note: the price-coordination mechanism driven by this module was found to be systematically harmful on this problem. `theta` defaults to 0, so the default execution path never calls these estimators. The implementation is kept so the paper can report the negative result faithfully (spec 13.2 data, 13.3 mechanism).

Definition of price pi(c,b): the makespan improvement obtained by relaxing the travel capacity of corridor c in time bucket b by one unit, divided by the bucket width, i.e. the marginal cost per unit of occupation time (a dimensionless ratio).

Two estimators are provided; accuracy and cost complement each other:

1. `finite_difference_prices` — the definitional estimate. Freeze the upper-level decisions (machine assignment, operation sequence, dispatch sequence), temporarily add 1 to a candidate slot's capacity, re-solve once, and measure the makespan improvement directly. It assumes no convexity and needs no LP solver; it is the reference version when this paper reports prices. The cost is one re-solve per candidate slot.

2. `surrogate_prices` — a cheap surrogate. A first-order approximation from critical-chain-weighted actual yield-wait, available from a single decode, refreshed by the GA each generation.

Their relationship can be checked directly in experiments (`price_agreement`): if the rank correlation between the surrogate and the definitional price is high enough, the surrogate may safely stand in. That is the evidence needed to promote a heuristic signal to a "theoretically grounded approximation", and it is the essential difference from an unreferenced heuristic such as "lam * cumulative wait".
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .instance import Instance, OpKey
from .network import BucketKey, Network, PriceTable
from .stats import spearman

# 非关键链上的让行等待在代理价中的折扣系数
# Discount on yield-wait off the critical chain when forming the surrogate price.
OFF_CRITICAL_WEIGHT = 0.25


def default_bucket_width(inst: Instance) -> float:
    """默认桶宽 = 平均加工时间,使时段分辨率与工序时间尺度对齐。

    Default bucket width = mean processing time, so the time resolution matches the operation time scale.
    """
    times = [t for row in inst.proc_time.values() for t in row.values()]
    if not times:
        return 1.0
    return max(1e-6, sum(times) / len(times))


def slot_weights(result, bucket_width: float,
                 critical_slots: Optional[Sequence[BucketKey]] = None
                 ) -> Dict[BucketKey, float]:
    """按走廊-时段汇总"关键性加权的让行等待",作为价格与候选槽位的排序依据。

    Aggregate criticality-weighted yield-wait by corridor-time slot, used to rank prices and candidate slots.
    """
    crit = set(critical_slots or ())
    acc: Dict[BucketKey, float] = {}
    for tr in result.transports:
        for plan in (tr.empty_plan, tr.loaded_plan):
            for cid, w_from, _w_to, amount in plan.wait_events():
                b = int(w_from // bucket_width)
                key = (cid, b)
                weight = 1.0 if key in crit else OFF_CRITICAL_WEIGHT
                acc[key] = acc.get(key, 0.0) + weight * amount
    return acc


def surrogate_prices(inst: Instance, result, bucket_width: float,
                     top_k: int = 24,
                     critical_slots: Optional[Sequence[BucketKey]] = None
                     ) -> PriceTable:
    """代理价格:pi(c,b) = 关键性加权让行等待 / 桶宽,只保留权重最高的 top_k 个槽位。

    截断到 top_k 有两个作用:抑制噪声(大量微小等待不构成瓶颈),以及把多标签
    路由的搜索开销限制在真正拥挤的少数时空槽位上。

    Surrogate price: pi(c,b) = criticality-weighted yield-wait / bucket width, keeping only the top_k highest-weight slots.

    Truncation to top_k does two things: it suppresses noise (many tiny waits are not bottlenecks), and it confines the search cost of multi-label routing to the few space-time slots that are actually congested.
    """
    pt = PriceTable(bucket_width)
    acc = slot_weights(result, bucket_width, critical_slots)
    if not acc:
        return pt
    for (cid, b), w in sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]:
        pt.set(cid, b, w / bucket_width)
    return pt


def finite_difference_prices(inst: Instance, net: Network, ma: Dict[OpKey, int],
                             os_seq: List[int], result, bucket_width: float,
                             decode_fn: Callable, slots: Sequence[BucketKey],
                             prices: Optional[PriceTable] = None,
                             theta: float = 0.0,
                             max_entry_options: int = 3,
                             ) -> Tuple[PriceTable, Dict[BucketKey, float]]:
    """定义式影子价格:逐槽位把容量 1 -> 2,重解一次,量出 makespan 改善。

    两处必须保持"只变一个东西"才使差分可解释:
    - 上层决策(机器指派、工序顺序、派车序列)全部冻结,故改善只能来自该走廊-时段;
    - 探测解码与基准解码使用**同一路由策略**(同一价格表与 theta),否则差分会
      把"容量放宽"与"路由准则改变"两种效应混在一起。

    返回 (价格表, 原始改善量)。

    Definitional shadow price: for each slot, raise capacity from 1 to 2, re-solve once, and measure the makespan improvement.

    Two things must change only one factor, or the difference is not interpretable:
    - upper-level decisions (machine assignment, operation sequence, dispatch sequence) are all frozen, so any improvement can come only from that corridor-time slot;
    - the probe decode and the baseline decode use the same routing policy (the same price table and theta), otherwise the difference mixes "capacity relaxed" with "routing criterion changed".

    Returns (price table, raw improvements).
    """
    pt = PriceTable(bucket_width)
    deltas: Dict[BucketKey, float] = {}
    base = result.makespan
    for cid, b in slots:
        relaxed = decode_fn(
            inst, net, ma, os_seq,
            conflict_free=True,
            forced_dispatch=list(result.dispatch_order),
            prices=prices,
            theta=theta,
            bucket_width=bucket_width,
            capacity_override={(cid, b): 2},
            max_entry_options=max_entry_options,
        )
        gain = base - relaxed.makespan
        deltas[(cid, b)] = gain
        if gain > 1e-9:
            pt.set(cid, b, gain / bucket_width)
    return pt, deltas


def candidate_slots(result, bucket_width: float, top_k: int,
                    critical_slots: Optional[Sequence[BucketKey]] = None
                    ) -> List[BucketKey]:
    """有限差分的候选槽位:按关键性加权等待降序取前 top_k。

    只探测"确实发生过让行"的槽位——从未阻塞过任何车的槽位其边际价值必为 0,
    无需花一次重解去确认。

    Candidate slots for finite differences: the top_k by criticality-weighted wait, descending.

    Probe only slots where a yield actually occurred — a slot that never blocked any vehicle has marginal value 0, and does not need a re-solve to confirm that.
    """
    acc = slot_weights(result, bucket_width, critical_slots)
    return [k for k, _w in sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]]


def price_agreement(surrogate: PriceTable, exact: PriceTable) -> Optional[float]:
    """代理价与定义式价格在共同槽位上的 Spearman 秩相关(样本 < 3 时返回 None)。

    Spearman rank correlation of the surrogate and the definitional price on shared slots (None if the sample size is under 3).
    """
    keys = sorted({k for k, _ in surrogate.items()} | {k for k, _ in exact.items()})
    if len(keys) < 3:
        return None
    rho = spearman([surrogate.get(*k) for k in keys], [exact.get(*k) for k in keys])
    return None if rho is None else round(rho, 4)
