"""上层调度层:种群搜索主循环、遗传算子与价格制导局部搜索(规格 6.1、6.4、6.5)。

与价格协调前的差别集中在两处,均为"让上层的决策依据来自下层的真实信息"而非通用算子:
1. 改派评分用下层下发的影子价格计价(量纲一致,无需人工标定的 lam);
2. 新增冲突凭证制导的错峰算子:由下层指认出的"谁挡了谁"直接给出一对操作对象,
   邻域不再是随机变异。

Upper scheduling level: the population-search main loop, genetic operators, and price-guided local search (spec 6.1, 6.4, 6.5).

The differences from the version before price coordination are concentrated in two places, both of which make the upper level's decisions rest on real information from the lower level rather than on a generic operator:
1. reassignment scores are priced with the shadow prices issued by the lower level (same dimension; no hand-tuned lam);
2. a new conflict-certificate-guided stagger operator: the lower level's identification of "who blocked whom" directly supplies a pair of operands, so the neighborhood is no longer a random mutation.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional, Set, Tuple

from .instance import Instance, OpKey
from .network import Network, PriceTable
from .decoder import (DecodeResult, decode, critical_chain, critical_real_ops,
                      critical_corridor_slots, blocking_opponents)
from .pricing import (default_bucket_width, surrogate_prices, candidate_slots,
                      finite_difference_prices, price_agreement)


@dataclass
class GAConfig:
    pop: int = 100
    max_gen: int = 200
    stall_gen: int = 30
    pc: float = 0.8
    pm: float = 0.2
    elite: int = 5
    tournament: int = 2
    top_ls: float = 0.10      # 每代做局部搜索的精英比例
    # Share of elites that receive local search each generation
    L_ls: int = 5             # 每轮尝试的关键工序数上限
    # Cap on the number of critical operations tried each round
    ls_rounds: int = 3
    seed: int = 42

    # ---- 价格协调参数(规格 5.5) ----
    # Price-coordination parameters (spec 5.5)
    # theta 默认为 0:诊断实验(tools/sweep_price.py)显示价格加权路由在本问题上
    # 系统性有害——走廊争用引起的延误已经完整体现在该车自身的到达时刻里,再收一次
    # 价格等于重复计价,导致车辆过度绕行/过度等待。详见规格 13.2(数据)与 13.3(机制解释)。
    # theta defaults to 0: a diagnostic experiment (tools/sweep_price.py) shows that price-weighted routing
    # is systematically harmful on this problem. Delay caused by corridor contention is already fully
    # reflected in that vehicle's own arrival time; charging a price again double-counts it and makes
    # vehicles detour and wait too much. See spec 13.2 (data) and 13.3 (mechanism).
    theta: float = 0.0        # 无量纲协调强度;0 = 关闭价格协调(退化为最早到达)
    # Dimensionless coordination strength; 0 = price coordination off (falls back to earliest arrival)
    price_top_k: int = 24     # 价格表保留的走廊-时段槽位数
    # Number of corridor-time slots kept in the price table
    price_refresh: int = 5    # 每多少代用当代最优个体刷新一次价格
    # How many generations between price refreshes from the current best individual
    max_entry_options: int = 3  # 多标签路由每条弧考察的进入时刻数;1 = 只考虑最早
    # How many entry times multi-label routing considers on each arc; 1 = earliest only
    fd_calibrate: bool = False  # 是否用有限差分定义式价格校准(代价高,报告用)
    # Whether to calibrate with definitional finite-difference prices (costly; for reporting)
    fd_slots: int = 8         # 有限差分探测的槽位数上限
    # Cap on the number of slots probed by finite differences
    use_conflict_ops: bool = True  # 是否启用冲突凭证制导的错峰算子
    # Whether to enable the conflict-certificate-guided stagger operator
    ls_exhaustive: bool = False  # 改派算子是否穷举全部候选(见 _reassign_neighbors)
    # Whether the reassignment operator enumerates every candidate (see _reassign_neighbors)
    dispatch: str = "exact"   # 'rule' = 理想最短路估算(开环);'exact' = 预约表试探(闭环)
    # 'rule' = ideal shortest-path estimate (open-loop); 'exact' = reservation-table probe (closed-loop)

    # ---- 同算力预算(规格 8.2 协议 1) ----
    # Same-compute budget (spec 8.2, protocol 1)
    # 各消融档的单次评价代价相差数倍(派车试探约 5 倍),只比同代数会把"多花算力"
    # 误读为"机制更好"(规格 13.2 结论 2)。给定该值后,主循环在每代末检查挂钟时间,
    # 超出即停,使各档在**相同算力**下比较;None = 只由 max_gen / stall_gen 停机。
    # A single evaluation costs several times more in some ablation arms (a dispatch probe is about 5x).
    # Comparing only at the same generation count reads "spent more compute" as "the mechanism is better"
    # (spec 13.2, conclusion 2). When this value is set, the main loop checks wall-clock time at the end
    # of each generation and stops when it is exceeded, so arms are compared under the same compute.
    # None = stop only by max_gen / stall_gen.
    time_budget_sec: Optional[float] = None


Chromosome = Dict[str, object]  # {"ma": Dict[OpKey,int], "os": List[int]}


# ---------------- 染色体构造 ----------------
# Chromosome construction

def random_os(inst: Instance, rng: random.Random) -> List[int]:
    seq: List[int] = []
    for j, cnt in inst.os_job_counts().items():
        seq.extend([j] * cnt)
    rng.shuffle(seq)
    return seq


def random_ma(inst: Instance, rng: random.Random) -> Dict[OpKey, int]:
    return {op: rng.choice(inst.eligible(*op)) for op in inst.real_ops()}


def ma_min_time(inst: Instance) -> Dict[OpKey, int]:
    """启发式个体 1:行内最小加工时间指派。

    Heuristic individual 1: assign the minimum in-row processing time.
    """
    return {op: min(inst.proc_time[op], key=lambda m: (inst.proc_time[op][m], m))
            for op in inst.real_ops()}


def ma_load_balance(inst: Instance) -> Dict[OpKey, int]:
    """启发式个体 2:贪心负载均衡指派。

    Heuristic individual 2: greedy load-balancing assignment.
    """
    load = {m: 0.0 for m in inst.machine_node}
    ma: Dict[OpKey, int] = {}
    for op in inst.real_ops():
        m = min(inst.eligible(*op), key=lambda mm: (load[mm] + inst.proc_time[op][mm], mm))
        ma[op] = m
        load[m] += inst.proc_time[op][m]
    return ma


def init_population(inst: Instance, cfg: GAConfig, rng: random.Random) -> List[Chromosome]:
    pop: List[Chromosome] = [
        {"ma": ma_min_time(inst), "os": random_os(inst, rng)},
        {"ma": ma_load_balance(inst), "os": random_os(inst, rng)},
    ]
    while len(pop) < cfg.pop:
        pop.append({"ma": random_ma(inst, rng), "os": random_os(inst, rng)})
    return pop[: cfg.pop]


# ---------------- 通用遗传算子 ----------------
# Generic genetic operators

def pox_crossover(os1: List[int], os2: List[int], jobs: List[int],
                  rng: random.Random) -> Tuple[List[int], List[int]]:
    """POX:随机工件子集在父代中保位,其余按另一父代顺序回填。

    POX: a random subset of jobs keeps its positions from one parent; the rest are filled in the other parent's order.
    """
    k = rng.randint(1, max(1, len(jobs) - 1))
    keep = set(rng.sample(jobs, k))

    def make(a: List[int], b: List[int]) -> List[int]:
        child: List[Optional[int]] = [j if j in keep else None for j in a]
        rest = iter([j for j in b if j not in keep])
        return [j if j is not None else next(rest) for j in child]

    return make(os1, os2), make(os2, os1)


def ma_uniform_crossover(ma1: Dict[OpKey, int], ma2: Dict[OpKey, int],
                         rng: random.Random) -> Tuple[Dict[OpKey, int], Dict[OpKey, int]]:
    c1, c2 = {}, {}
    for op in ma1:
        if rng.random() < 0.5:
            c1[op], c2[op] = ma1[op], ma2[op]
        else:
            c1[op], c2[op] = ma2[op], ma1[op]
    return c1, c2


def mutate(inst: Instance, chrom: Chromosome, rng: random.Random) -> None:
    """OS 段:随机交换两位;MA 段:随机改派 Omega 内另一 RA。

    OS segment: swap two random positions. MA segment: reassign at random to another robotic arm inside Omega.
    """
    os_seq: List[int] = chrom["os"]  # type: ignore
    a, b = rng.randrange(len(os_seq)), rng.randrange(len(os_seq))
    os_seq[a], os_seq[b] = os_seq[b], os_seq[a]

    ma: Dict[OpKey, int] = chrom["ma"]  # type: ignore
    flexible = [op for op in ma if len(inst.eligible(*op)) > 1]
    if flexible:
        op = rng.choice(flexible)
        others = [m for m in inst.eligible(*op) if m != ma[op]]
        ma[op] = rng.choice(others)


def clone(chrom: Chromosome) -> Chromosome:
    return {"ma": dict(chrom["ma"]), "os": list(chrom["os"])}  # type: ignore


# ---------------- OS 段的定向移位(错峰算子的底层操作) ----------------
# Directed shift of the OS segment (the stagger operator's underlying move)

def os_index_of(os_seq: List[int], op: OpKey) -> Optional[int]:
    """工序 (j,i) 在 OS 中的位置 = 工件 j 的第 i 次出现。

    Position of operation (j,i) in the OS = the i-th occurrence of job j.
    """
    j, i = op
    cnt = 0
    for idx, jj in enumerate(os_seq):
        if jj == j:
            cnt += 1
            if cnt == i:
                return idx
    return None


def os_shift(os_seq: List[int], idx: int, later: bool) -> bool:
    """把位置 idx 的基因与相邻的**异工件**基因交换,原地生效。

    只交换不同工件的基因,故工件内工序先后序天然保持,交换后仍是合法排列
    (规格 6.1 的可解码性不受影响)。

    Swap the gene at position idx with the neighboring gene of a different job, in place.

    Only genes of different jobs are swapped, so the precedence of operations inside a job is preserved and the result is still a legal permutation (decodability in spec 6.1 is unaffected).
    """
    n = len(os_seq)
    step = 1 if later else -1
    k = idx + step
    while 0 <= k < n:
        if os_seq[k] != os_seq[idx]:
            os_seq[idx], os_seq[k] = os_seq[k], os_seq[idx]
            return True
        k += step
    return False


# ---------------- 价格制导局部搜索(规格 6.5) ----------------
# Price-guided local search (spec 6.5)

def _reassign_neighbors(inst: Instance, net: Network, chrom: Chromosome,
                        result: DecodeResult, cfg: GAConfig,
                        prices: Optional[PriceTable]) -> List[Chromosome]:
    """改派算子:关键链上的工序换到"加工快 + 通行权便宜"的 RA。

    评分三项同为时间量纲:接近程度、加工时长、以及为进出该 RA 要买的通行权价格。
    价格项取代了原先的 lam * 累计让行等待——后者是随算例规模增长的全局量,与前两项
    量纲不符,在大算例上会支配评分。

    cfg.ls_exhaustive 打开后不再只发出评分最优的那台,而是按评分把**全部**候选发出。
    动机见 tools/regime_curve.py --attrib(约 1000 个收敛期情形):随机挑一个候选命中
    7.0%,本函数的评分命中 9.8%,而"存在可改进候选"达 17.4%——评分只捕获了随机到
    上限之间的四分之一,后悔口径给出同一个比例。剩下的四分之三预测不出来,只有真解码
    才拿得到。候选按"每道工序的第 k 优"交错排列,k=0 一轮与现行算子逐个邻居完全一致,
    其后各轮才是穷举多出来的部分——两档搜索顺序严格嵌套,同挂钟下的差异才能归因给
    穷举本身。

    实测结论是这笔钱不值得花:同挂钟 20 秒下穷举反而差 2.49%(3 胜 10 负 2 平,
    tools/exhaustive_ab.py),因为它把代数从 53 压到 27。故默认关闭,保留开关备查。

    Reassignment operator: move an operation on the critical chain to a robotic arm that is "fast to process and cheap in right-of-way".

    The three score terms all have the dimension of time: closeness, processing duration, and the right-of-way price to buy for entering and leaving that robotic arm. The price term replaces the old lam * cumulative yield-wait, which is a global quantity that grows with instance size, is dimensionally inconsistent with the first two terms, and dominates the score on large instances.

    When cfg.ls_exhaustive is on, the operator no longer emits only the best-scoring machine; it emits every candidate in score order. The motive is in tools/regime_curve.py --attrib (about 1000 late-search cases): picking a candidate at random hits 7.0%, this function's score hits 9.8%, and "an improving candidate exists" reaches 17.4%. The score captures only about a quarter of the gap between random and the upper bound; a regret accounting gives the same fraction. The remaining three quarters cannot be predicted and are obtained only by a real decode. Candidates are interleaved as "the k-th best of each operation". The k=0 round matches the current operator neighbor for neighbor, and later rounds are what enumeration adds. The two search orders are strictly nested, so a same-wall-clock difference can be attributed to enumeration itself.

    The measured conclusion is that this spend is not worth it: under the same wall-clock of 20 seconds, enumeration is 2.49% worse (3 wins, 10 losses, 2 ties, tools/exhaustive_ab.py), because it cuts generations from 53 to 27. It is therefore off by default, and the switch is kept for reference.
    """
    out: List[Chromosome] = []
    ranked: List[Tuple[OpKey, List[int]]] = []
    chain = critical_real_ops(result)
    for op in chain[: cfg.L_ls]:
        j, i = op
        cur_m = chrom["ma"][op]  # type: ignore
        candidates = [m for m in inst.eligible(j, i) if m != cur_m]
        if not candidates:
            continue
        pos_prev = inst.lu_node if i == 1 else inst.machine_node[chrom["ma"][(j, i - 1)]]  # type: ignore
        t_query = result.ops[op].start

        def score(m: int) -> float:
            node = inst.machine_node[m]
            approach = net.ideal_dist[pos_prev][node]
            s = approach + inst.proc_time[op][m]
            if prices is not None and cfg.theta > 0.0 and not prices.is_empty():
                s += cfg.theta * prices.node_price(net, node, t_query) * approach
            return s

        order = sorted(candidates, key=lambda m: (score(m), m))
        ranked.append((op, order if cfg.ls_exhaustive else order[:1]))

    for k in range(max((len(o) for _op, o in ranked), default=0)):
        for op, order in ranked:
            if k < len(order):
                nb = clone(chrom)
                nb["ma"][op] = order[k]  # type: ignore
                out.append(nb)
    return out


def _stagger_neighbors(inst: Instance, chrom: Chromosome, result: DecodeResult,
                       cfg: GAConfig) -> List[Chromosome]:
    """错峰算子:由下层的冲突凭证指认操作对象,在时间维度上化解走廊争用。

    拥堵有两种缓解方式——换地方(改派)与换时间(错峰),原实现只有前者。
    这里取关键链上让行最久的一次走廊等待,从预约表反查是谁占着该走廊,
    然后给出两个定向邻居:把被堵的工序提前发起,或把对手工序推后。

    Stagger operator: the lower level's conflict certificate names the operands, and corridor contention is resolved in the time dimension.

    Congestion can be relieved in two ways — change place (reassignment) or change time (stagger). The original implementation had only the first. Here we take the longest corridor yield on the critical chain, look up from the reservation table who occupies that corridor, and emit two directed neighbors: start the blocked operation earlier, or push the opponent operation later.
    """
    if not cfg.use_conflict_ops:
        return []
    items = [it for it in critical_chain(result)
             if it.kind == "corridor" and it.corridor is not None and it.amount > 1e-9]
    if not items:
        return []
    it = max(items, key=lambda x: x.amount)

    out: List[Chromosome] = []
    os_seq: List[int] = chrom["os"]  # type: ignore

    if it.op is not None:
        idx = os_index_of(os_seq, it.op)
        if idx is not None:
            nb = clone(chrom)
            if os_shift(nb["os"], idx, later=False):  # type: ignore
                out.append(nb)

    for opp in blocking_opponents(result, it.corridor, it.t_start, it.t_end):
        if opp == it.op:
            continue
        idx = os_index_of(os_seq, opp)
        if idx is None:
            continue
        nb = clone(chrom)
        if os_shift(nb["os"], idx, later=True):  # type: ignore
            out.append(nb)
        break                      # 一次只动一个对手,保持邻域小而定向
        # Move only one opponent at a time, so the neighborhood stays small and directed.
    return out


def local_search(inst: Instance, net: Network, chrom: Chromosome,
                 result: DecodeResult, cfg: GAConfig,
                 conflict_free: bool,
                 prices: Optional[PriceTable] = None
                 ) -> Tuple[Chromosome, DecodeResult, Dict[str, int]]:
    """返回 (个体, 解码结果, 本次的算子统计)。

    统计不是可有可无的装饰。其一,每个邻居都要走一遍完整的下层路由,代价与一次
    种群评价同量级:不把它计入算力,同挂钟比较就会把"局部搜索偷跑的解码"记成免费,
    从而高估决策级闭环(规格 8.2 协议 1)。其二,两族算子按"生成数/命中数"分开记账,
    才能回答"凭证到底有没有带来信号"——若错峰族极少被触发或极少命中,那么所谓
    冲突制导实际上退化成了普通的关键路径改派。

    Return (individual, decode result, operator statistics for this call).

    The statistics are not optional decoration. First, every neighbor runs a full lower-level route, at the same cost order as one population evaluation. If that is not counted as compute, a same-wall-clock comparison treats "decodes quietly spent by local search" as free and overestimates the decision-level closed loop (spec 8.2, protocol 1). Second, the two operator families are booked separately as "generated / hit", which is what answers "did the certificate actually bring a signal". If the stagger family is rarely triggered or rarely hits, conflict guidance has in practice degenerated into ordinary critical-path reassignment.
    """
    bw = prices.bucket_width if prices is not None else 0.0
    st = {"decodes": 0, "rounds": 0, "chain_corridor": 0,
          "reassign_tried": 0, "reassign_hit": 0,
          "stagger_tried": 0, "stagger_hit": 0}
    for _ in range(cfg.ls_rounds):
        st["rounds"] += 1
        improved = False
        reassign = _reassign_neighbors(inst, net, chrom, result, cfg, prices)
        stagger = _stagger_neighbors(inst, chrom, result, cfg)
        if stagger:
            st["chain_corridor"] += 1
        neighbors = ([("reassign", nb) for nb in reassign]
                     + [("stagger", nb) for nb in stagger])
        for family, nb in neighbors:
            res2 = decode(inst, net, nb["ma"], nb["os"],  # type: ignore
                          conflict_free=conflict_free, prices=prices,
                          theta=cfg.theta, bucket_width=bw,
                          max_entry_options=cfg.max_entry_options,
                          dispatch=cfg.dispatch)
            st["decodes"] += 1
            st[family + "_tried"] += 1
            if res2.makespan < result.makespan - 1e-9:
                chrom, result = nb, res2
                st[family + "_hit"] += 1
                improved = True
                break              # 首改进:重新提取关键链
                # First improvement: re-extract the critical chain.
        if not improved:
            break
    return chrom, result, st


# ---------------- 主循环 ----------------
# Main loop

def run_ga(inst: Instance, net: Network, cfg: GAConfig,
           conflict_free: bool = True, use_ls: bool = True,
           log: Optional[Callable[[str], None]] = None) -> dict:
    rng = random.Random(cfg.seed)
    t_start = time.time()

    bw = default_bucket_width(inst)
    price_on = conflict_free and cfg.theta > 0.0
    prices: Optional[PriceTable] = PriceTable(bw) if price_on else None
    agreement: Optional[float] = None

    def evaluate(ch: Chromosome) -> DecodeResult:
        return decode(inst, net, ch["ma"], ch["os"],  # type: ignore
                      conflict_free=conflict_free, prices=prices,
                      theta=cfg.theta, bucket_width=bw if price_on else 0.0,
                      max_entry_options=cfg.max_entry_options,
                      dispatch=cfg.dispatch)

    def refresh_prices(ch: Chromosome, res: DecodeResult) -> None:
        """用当前最优方案的下层运行信息重估影子价格(层间接口的向下一跳)。

        Re-estimate shadow prices from the lower-level run of the current best solution (the downward hop of the inter-level interface).
        """
        nonlocal prices, agreement
        if not price_on:
            return
        crit = critical_corridor_slots(res, bw)
        new_prices = surrogate_prices(inst, res, bw, cfg.price_top_k, crit)
        if cfg.fd_calibrate:
            slots = candidate_slots(res, bw, cfg.fd_slots, crit)
            if slots:
                exact, _deltas = finite_difference_prices(
                    inst, net, ch["ma"], ch["os"], res, bw, decode, slots,  # type: ignore
                    prices=prices, theta=cfg.theta,
                    max_entry_options=cfg.max_entry_options)
                agreement = price_agreement(new_prices, exact)
                new_prices = exact
        prices = new_prices

    population = init_population(inst, cfg, rng)
    results = [evaluate(ch) for ch in population]
    history: List[float] = []
    # 各档每次评价的成本相差一两个数量级,按代数画收敛曲线会严重误导;
    # 逐代记下挂钟耗时,使收敛图能以"同一时间轴"呈现(规格 8.2 协议 3)
    # Evaluation cost differs by one or two orders of magnitude across arms, so a convergence curve against generation count is badly misleading.
    # Record wall-clock time generation by generation so the convergence plot can share one time axis (spec 8.2, protocol 3).
    history_sec: List[float] = []
    best_idx = min(range(len(results)), key=lambda x: results[x].makespan)
    best_chrom, best_result = clone(population[best_idx]), results[best_idx]
    refresh_prices(best_chrom, best_result)
    stall = 0
    n_eval = len(population)
    n_ls_eval = 0
    ls_stats: Dict[str, int] = {}
    stopped_by = "max_gen"

    for gen in range(1, cfg.max_gen + 1):
        order = sorted(range(len(population)), key=lambda x: results[x].makespan)

        # 精英个体做价格制导局部搜索(决策级闭环)
        # Elite individuals run price-guided local search (decision-level closed loop).
        if use_ls:
            n_ls = max(1, math.ceil(cfg.top_ls * cfg.pop))
            for idx in order[:n_ls]:
                ch2, res2, st = local_search(inst, net, population[idx], results[idx],
                                             cfg, conflict_free, prices)
                n_ls_eval += st["decodes"]
                for k, v in st.items():
                    ls_stats[k] = ls_stats.get(k, 0) + v
                if res2.makespan < results[idx].makespan - 1e-9:
                    population[idx], results[idx] = ch2, res2
            order = sorted(range(len(population)), key=lambda x: results[x].makespan)

        # 更新全局最优
        # Update the global best.
        if results[order[0]].makespan < best_result.makespan - 1e-9:
            best_chrom = clone(population[order[0]])
            best_result = results[order[0]]
            stall = 0
        else:
            stall += 1
        history.append(best_result.makespan)
        history_sec.append(round(time.time() - t_start, 3))
        if log and (gen % 10 == 0 or gen == 1):
            log(f"  gen {gen:4d}  best C_max = {best_result.makespan:.1f}")
        if stall >= cfg.stall_gen:
            stopped_by = "stall"
            break
        if (cfg.time_budget_sec is not None
                and time.time() - t_start >= cfg.time_budget_sec):
            stopped_by = "budget"
            break

        if price_on and cfg.price_refresh > 0 and gen % cfg.price_refresh == 0:
            refresh_prices(best_chrom, best_result)

        # 生成下一代:精英保留 + 锦标赛 + POX/均匀交叉 + 变异
        # Build the next generation: elitism + tournament + POX/uniform crossover + mutation.
        new_pop: List[Chromosome] = [clone(population[i]) for i in order[: cfg.elite]]

        def pick() -> Chromosome:
            cand = rng.sample(range(len(population)), cfg.tournament)
            return population[min(cand, key=lambda x: results[x].makespan)]

        while len(new_pop) < cfg.pop:
            p1, p2 = pick(), pick()
            if rng.random() < cfg.pc:
                os1, os2 = pox_crossover(p1["os"], p2["os"], inst.job_ids, rng)  # type: ignore
                ma1, ma2 = ma_uniform_crossover(p1["ma"], p2["ma"], rng)  # type: ignore
                kids = [{"ma": ma1, "os": os1}, {"ma": ma2, "os": os2}]
            else:
                kids = [clone(p1), clone(p2)]
            for kid in kids:
                if rng.random() < cfg.pm:
                    mutate(inst, kid, rng)
                new_pop.append(kid)
                if len(new_pop) >= cfg.pop:
                    break
        population = new_pop
        results = [evaluate(ch) for ch in population]
        n_eval += len(population)

    return {
        "best_chrom": best_chrom,
        "best_result": best_result,
        "history": history,
        "history_sec": history_sec,
        "generations": len(history),
        "evaluations": n_eval,
        "ls_evaluations": n_ls_eval,
        # 真实算力口径:种群评价 + 局部搜索邻居,两者都是一次完整的下层路由
        # True compute accounting: population evaluations plus local-search neighbors; both are one full lower-level route.
        "decodes": n_eval + n_ls_eval,
        "ls_stats": ls_stats,
        "stopped_by": stopped_by,
        "runtime_sec": round(time.time() - t_start, 2),
        "config": asdict(cfg),
        "bucket_width": round(bw, 4),
        "price_slots": (len(list(prices.items())) if prices is not None else 0),
        "price_agreement": agreement,
        "price_cost_total": round(best_result.price_cost_total, 4),
    }
