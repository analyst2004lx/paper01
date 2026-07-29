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
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .instance import Instance, OpKey
from .network import BucketKey, Network, PriceTable

# 非关键链上的让行等待在代理价中的折扣系数
OFF_CRITICAL_WEIGHT = 0.25


def default_bucket_width(inst: Instance) -> float:
    """默认桶宽 = 平均加工时间,使时段分辨率与工序时间尺度对齐。"""
    times = [t for row in inst.proc_time.values() for t in row.values()]
    if not times:
        return 1.0
    return max(1e-6, sum(times) / len(times))


def slot_weights(result, bucket_width: float,
                 critical_slots: Optional[Sequence[BucketKey]] = None
                 ) -> Dict[BucketKey, float]:
    """按走廊-时段汇总"关键性加权的让行等待",作为价格与候选槽位的排序依据。"""
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
    """
    acc = slot_weights(result, bucket_width, critical_slots)
    return [k for k, _w in sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]]


def price_agreement(surrogate: PriceTable, exact: PriceTable) -> Optional[float]:
    """代理价与定义式价格在共同槽位上的 Spearman 秩相关(样本 < 3 时返回 None)。"""
    keys = sorted({k for k, _ in surrogate.items()} | {k for k, _ in exact.items()})
    if len(keys) < 3:
        return None
    xs = [surrogate.get(*k) for k in keys]
    ys = [exact.get(*k) for k in keys]

    def ranks(vals: List[float]) -> List[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        rk = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and abs(vals[order[j + 1]] - vals[order[i]]) < 1e-12:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for t in range(i, j + 1):
                rk[order[t]] = avg
            i = j + 1
        return rk

    rx, ry = ranks(xs), ranks(ys)
    n = len(keys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx < 1e-12 or dy < 1e-12:
        return None
    return round(num / (dx * dy), 4)
