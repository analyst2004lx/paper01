"""串谋界：一个谎言要永久不被发现，需要多少台设备同时被劫持。

## 形式化

设备 $d_a$ 在活动 $a$ 上谎称"已交付至位置 $p$"。该谎言要不被否证，$p$ 的下一个
消费者必须为它背书；而背书者自己也没收到工件，于是它随后的交付声明同样是假的，
须由**它的**下一个消费者背书。递推下去：

> **命题（串谋闭包）.** 谎言 $a$ 永久不被否证的充要条件是：被劫持设备集合在
> "下一个对手方"关系下**前向封闭**，直到工件离开可互证的链（入库、case 结束、
> 或该活动在模型上无对手方）。

所以串谋界不是最小顶点割，而是一个**前向可达闭包**的规模——README 早先写的
"最小顶点割"是错的表述，虽然直觉相近（要买通的是一组把谎言与诚实观测者隔开的
设备），但对象是闭包，形式化时必须说准。

## 三条必须分清的口径

1. **按设备实例计，不按跳数计。** 链上同一台设备重复出现只需劫持一次。本产线
   的 `vgr`/`wt` 反复承担搬运，故所需设备数可以远小于链长——这是对防御方不利
   的事实，必须如实报，不能用跳数冒充设备数把界说高。

2. **接手方是同一台设备时，链免费延长。** `SELF_ONLY`（原地多工步加工）不引入
   新的作证者，攻击者不需要额外劫持任何设备就能把谎言推进一跳。这把
   `coverage.py` 那 7.45% 的同设备缺口从"覆盖率数字"变成了**具体的安全代价**。

3. **系统的保证是 $\\min_a k(a)$，不是均值。** 攻击者挑最薄弱处下手。均值和中位
   只用来说明分布形状，写进安全论断的必须是最小值与低分位。

## 与调度约束的接口（增补一）

$k(a)$ 依赖调度器把哪台物理设备派给了链上的哪一步：复用同一台设备会压低 $k$。
于是"安全感知任务分配"有了可优化的目标函数——在不违反工艺约束的前提下让链上
相邻步骤落在不同设备上，即可抬高 $\\min_a k(a)$。`assignment_gain` 量化实际派工
与"链内不复用设备"理想派工之间的差距，那是这项设计可获得的收益上限。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import median

from .coverage import NO_MODEL, NO_REALIZED, OK, SELF_ONLY, Corroboration
from .taskgraph import TaskGraph, device_class

#: 链的终止原因。前两者是结构性的（工件离开可互证范围），第三个是保守截断。
END_NO_MODEL = "no_model_witness"
END_NO_REALIZED = "no_realized_witness"
END_CYCLE = "revisited"


@dataclass
class Chain:
    """从一个谎言出发的串谋闭包。"""
    origin: Corroboration
    #: 链上依次经过的活动（含起点）。
    hops: list = field(default_factory=list)
    #: 必须被劫持的设备实例集合。
    devices: set[str] = field(default_factory=set)
    #: 其中因接手方同为原设备而**免费**延长的跳数。
    free_hops: int = 0
    reason: str = END_NO_REALIZED

    @property
    def k(self) -> int:
        """串谋界：需要同时被劫持的设备数。"""
        return len(self.devices)

    @property
    def n_hops(self) -> int:
        return len(self.hops)

    @property
    def k_achievable(self) -> int:
        """改派工能达到的 $k$ 上限：设备序列中**极大连续同设备段**的个数。

        相邻复用（原地多工步加工，工件仍夹在机床夹具里）合并为一段——换机器要先
        卸件再装夹，不是调度器能改的；非相邻复用（同一台设备隔几步又回来）各算
        一段，那是真能换的。

        用 `n_hops` 当理想值会虚报收益：实测 $k_{\\min}$ 会被说成从 1 抬到 2，
        而那 23 条 $k=1$ 的链全是相邻同设备接手，排产根本改不动。
        """
        runs, prev = 0, None
        for a in self.hops:
            if a.device != prev:
                runs += 1
                prev = a.device
        return runs


def _index(records: list[Corroboration]) -> dict[int, Corroboration]:
    """活动 -> 其互证记录。链的推进要从见证活动跳到该活动自己的记录。"""
    return {id(r.act): r for r in records}


def walk(records: list[Corroboration]) -> list[Chain]:
    """对每条交付声明求其串谋闭包。

    只对**模型上存在对手方**的声明求闭包：无对手方的声明本来就没有互证可言，
    它的 $k=1$（只需劫持自己）不是"容易串谋"，而是覆盖率缺口，两件事混在一个
    分布里会把界压低而不自知。这类活动由按需主动互证处理，另行报告。
    """
    by_act = _index(records)
    out: list[Chain] = []
    for r in records:
        if r.status == NO_MODEL:
            continue
        ch = Chain(origin=r, hops=[r.act], devices={r.act.device})
        cur, seen = r, {id(r.act)}
        while True:
            if cur.status == OK and cur.witness is not None:
                nxt = by_act.get(id(cur.witness))
                if nxt is None or id(nxt.act) in seen:
                    ch.reason = END_CYCLE if nxt is not None else END_NO_REALIZED
                    break
                seen.add(id(nxt.act))
                ch.hops.append(nxt.act)
                ch.devices.add(nxt.act.device)
                cur = nxt
            elif cur.status == SELF_ONLY and cur.witness is not None:
                # 接手方是同一台设备：不需要额外劫持，链免费延长
                nxt = by_act.get(id(cur.witness))
                if nxt is None or id(nxt.act) in seen:
                    ch.reason = END_NO_REALIZED
                    break
                seen.add(id(nxt.act))
                ch.hops.append(nxt.act)
                ch.free_hops += 1
                cur = nxt
            else:
                ch.reason = (END_NO_MODEL if cur.status == NO_MODEL
                             else END_NO_REALIZED)
                break
        out.append(ch)
    return out


def _hist(xs: list[int]) -> list[tuple[int, int]]:
    return sorted(Counter(xs).items())


def in_scope(chains: list[Chain]) -> list[Chain]:
    """串谋界的作用域：起点在运行时**存在下游接手方**的链。

    只排除 `NO_REALIZED`（本 case 内根本无人从该位置取件，实测 183 条）：这类
    链长为 1、$k=1$，但那不是"一台设备就够串谋"，而是**运行时没有任何下游**，
    属覆盖率缺口，归按需主动互证处理。混进来会把 $k_{\\min}$ 从 2 压到 1。

    **`SELF_ONLY` 必须留在作用域内**，尽管它在该跳没有独立见证。它是攻击者可以
    真实瞄准的活动，其谎言仍要在下游被截住，$k$ 是有意义的界；排除它等于替机制
    挑掉最不利的样本。这条口径与 `coverage.py` 的覆盖率分母**故意不同**：覆盖率
    问"这一跳有没有独立证据"，串谋界问"永久藏住要买通几台设备"，后者天然跨跳。
    """
    return [c for c in chains if c.origin.status != NO_REALIZED]


def summarize(chains: list[Chain]) -> dict:
    """串谋界的分布。

    **分母必须只含运行时确实被互证的声明。** 起点状态为 `NO_REALIZED` 的链
    长度为 1、$k=1$，但那不是"一台设备就够串谋"，而是**运行时根本没有对手方**
    ——属覆盖率缺口（`coverage.py` 实测 5.98%），归按需主动互证处理。把它们混进
    $k$ 的分布会把界压低而不自知，是本模块最容易出的口径错误，故分开报。

    安全论断只能引用 `k_min` 与低分位：攻击者挑最薄弱处下手，均值无意义。
    """
    real = in_scope(chains)
    gap = [c for c in chains if c.origin.status == NO_REALIZED]
    ks = [c.k for c in real]
    hops = [c.n_hops for c in real]
    ordered = sorted(real, key=lambda c: (c.k, -c.n_hops))
    k1 = [c for c in real if c.k == 1]
    return {
        "n_chains": len(chains),
        "n_in_scope": len(real),
        "n_gap_origin": len(gap),
        "n_self_only_origin": sum(1 for c in real
                                  if c.origin.status == SELF_ONLY),
        "k_min": min(ks) if ks else None,
        "k_median": median(ks) if ks else None,
        "k_max": max(ks) if ks else None,
        "k_hist": _hist(ks),
        "frac_k_le_1": sum(1 for k in ks if k <= 1) / len(ks) if ks else 0.0,
        "frac_k_ge_3": sum(1 for k in ks if k >= 3) / len(ks) if ks else 0.0,
        "hops_median": median(hops) if hops else None,
        "hops_max": max(hops) if hops else None,
        #: k=1 的成因分解:全部应归于同设备接手(免费跳),否则是别的问题
        "n_k1": len(k1),
        "n_k1_free_hop": sum(1 for c in k1 if c.free_hops),
        #: 链长 > 设备数的比例,即"同一台设备在链上重复出现"的普遍程度
        "frac_device_reuse": (sum(1 for c in real if c.n_hops > c.k)
                              / len(real) if real else 0.0),
        "n_free_hop_chains": sum(1 for c in real if c.free_hops),
        "free_hops_total": sum(c.free_hops for c in real),
        "by_reason": dict(Counter(c.reason for c in real)),
        "weakest": [(c.origin.act.device, c.origin.act.op, c.k, c.n_hops)
                    for c in ordered[:10]],
    }


def structural_bound(graph: TaskGraph) -> dict:
    """模型级串谋界：在互证超图上按**设备类**走同一个闭包。

    与实测版的分工要写清：实测版度量的是"这一次排产下攻击者要买通几台机器"，
    随派工而变；模型级版度量的是"这套工艺流程本身能提供几层独立见证"，是过程
    模型的性质，不随排产变化，因此可作为设计期的指标。

    两者不可互相替代，也不该期望数值相等：模型级按类归并，会把 `vgr_1`/`vgr_2`
    算作一个顶点，故给出的是**保守下界**。

    **闭包必须逐工作流算，不能把 16 个模型的邻接混起来。** 混起来会把不同工艺
    路线上的见证关系串成一条更长的链，把界虚高——一个 case 只走一条工艺路线，
    攻击者要买通的也只是那条路线上的设备。
    """
    per_wf_succ: dict[str, dict[tuple[str, str], set[tuple[str, str]]]] = \
        defaultdict(lambda: defaultdict(set))
    for e in graph.witness_edges:
        per_wf_succ[e.workflow][e.producer].add(e.consumer)

    def closure(succ, start) -> set[str]:
        seen, stack, classes = {start}, [start], {start[0]}
        while stack:
            for nxt in succ.get(stack.pop(), ()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                classes.add(nxt[0])
                stack.append(nxt)
        return classes

    per_node: dict[tuple[str, tuple[str, str]], int] = {}
    per_wf: dict[str, int] = {}
    for wf, succ in per_wf_succ.items():
        ks = {p: len(closure(succ, p)) for p in succ}
        per_node.update({(wf, p): k for p, k in ks.items()})
        per_wf[wf] = min(ks.values()) if ks else None
    vals = [v for v in per_wf.values() if v is not None]
    ks = list(per_node.values())
    return {
        "n_nodes": len(per_node),
        "n_workflows": len(per_wf),
        "k_min": min(ks) if ks else None,
        "k_median": median(ks) if ks else None,
        "k_max": max(ks) if ks else None,
        "k_hist": _hist(ks),
        "per_workflow_min": per_wf,
        "worst_workflow_k": min(vals) if vals else None,
        "weakest_nodes": sorted(per_node.items(), key=lambda kv: kv[1])[:10],
    }


def assignment_gain(records: list[Corroboration]) -> dict:
    """安全感知任务分配的收益上限（增补一的定量依据）。

    比较三种派工下的串谋界：

      - **实际派工**：日志中真实发生的设备分配。
      - **可达理想**（`k_achievable`）：只消除**非相邻**复用。相邻复用是原地
        多工步加工，工件仍夹在机床夹具里，换机器要先卸件再装夹，不是调度能改的。
      - **无约束理想**（链长）：假设链上每一步都是不同设备。它不可达，只用来
        说明上界离可达值有多远。

    必须用可达理想报收益。用链长会虚报：$k_{\\min}$ 会被说成从 1 抬到 2，而那
    23 条 $k=1$ 的链全是相邻同设备接手，排产根本改不动。差值仍是**上限**而非
    实测收益——真实调度还要服从产能与交付期约束。
    """
    chains = in_scope(walk(records))
    actual = [c.k for c in chains]
    reach = [c.k_achievable for c in chains]
    ideal = [c.n_hops for c in chains]
    improvable = [c for c in chains if c.k_achievable > c.k]
    dup = Counter()
    for c in improvable:
        for d, n in Counter(a.device for a in c.hops).items():
            if n > 1:
                dup[d] += 1
    n = max(len(chains), 1)
    return {
        "k_min_actual": min(actual) if actual else None,
        "k_min_achievable": min(reach) if reach else None,
        "k_min_unconstrained": min(ideal) if ideal else None,
        "k_median_actual": median(actual) if actual else None,
        "k_median_achievable": median(reach) if reach else None,
        "k_median_unconstrained": median(ideal) if ideal else None,
        "k_mean_actual": sum(actual) / n,
        "k_mean_achievable": sum(reach) / n,
        "n_improvable": len(improvable),
        "frac_improvable": len(improvable) / n,
        #: 增益幅度分布,以及可改善的链原本的 k。后者说明增益集中在何处:
        #: 若集中在高 k 段,则改派工只是"让本来就安全的更安全",对保证无用。
        "gain_hist": _hist([c.k_achievable - c.k for c in chains]),
        "improvable_k_hist": _hist([c.k for c in improvable]),
        "n_improvable_at_k_le_2": sum(1 for c in improvable if c.k <= 2),
        "reuse_by_device": dup.most_common(8),
        "free_hop_cost": sum(c.free_hops for c in chains),
    }


def same_class_reuse(records: list[Corroboration]) -> dict:
    """链上设备复用的成因分解：哪些复用调度器**真的能换**。

    两个必要条件都要查，只查其一会把收益说高：

      1. 该设备类在日志中存在**多个实例**（本产线 6 个类各有 2 台，都满足）。
      2. 复用的两次出现**不相邻**。相邻复用即原地多工步加工（`/mm/mill` 后由
         同一台 `mm_1` 去毛刺），此时工件仍夹在机床夹具里，换机器要先卸件再
         装夹，物理上不是调度器能改的——这类必须从收益里扣掉。

    只统计"不相邻复用"作为可改善量。这也解释了为何同设备免费跳（`SELF_ONLY`）
    不能靠改派工消除，只能靠按需主动互证（增补二）补上：它是工艺决定的。
    """
    instances: dict[str, set[str]] = defaultdict(set)
    for r in records:
        instances[device_class(r.act.device)].add(r.act.device)
    chains = in_scope(walk(records))
    swappable = adjacent_only = single_instance = 0
    for c in chains:
        if c.n_hops <= c.k:
            continue
        devs = [a.device for a in c.hops]
        dup = {d for d, n in Counter(devs).items() if n > 1}
        multi = {d for d in dup if len(instances[device_class(d)]) > 1}
        if not multi:
            single_instance += 1
            continue
        nonadj = {d for d in multi
                  if any(devs[i] == d and d in devs[i + 2:]
                         for i in range(len(devs)))}
        if nonadj:
            swappable += 1
        else:
            adjacent_only += 1
    total = swappable + adjacent_only + single_instance
    return {
        "instances_per_class": {k: sorted(v) for k, v in
                                sorted(instances.items())},
        "n_reuse_chains": total,
        "n_swappable": swappable,
        "n_adjacent_only": adjacent_only,
        "n_single_instance": single_instance,
        "frac_swappable": swappable / total if total else 0.0,
    }
