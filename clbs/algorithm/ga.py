"""上层调度层:种群搜索主循环、遗传算子与价格制导局部搜索(规格 6.1、6.4、6.5)。

与价格协调前的差别集中在两处,均为"让上层的决策依据来自下层的真实信息"而非通用算子:
1. 改派评分用下层下发的影子价格计价(量纲一致,无需人工标定的 lam);
2. 新增冲突凭证制导的错峰算子:由下层指认出的"谁挡了谁"直接给出一对操作对象,
   邻域不再是随机变异。
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
    L_ls: int = 5             # 每轮尝试的关键工序数上限
    ls_rounds: int = 3
    seed: int = 42

    # ---- 价格协调参数(规格 5.5) ----
    # theta 默认为 0:诊断实验(tools/sweep_price.py)显示价格加权路由在本问题上
    # 系统性有害——走廊争用引起的延误已经完整体现在该车自身的到达时刻里,再收一次
    # 价格等于重复计价,导致车辆过度绕行/过度等待。详见规格 13.2(数据)与 13.3(机制解释)。
    theta: float = 0.0        # 无量纲协调强度;0 = 关闭价格协调(退化为最早到达)
    price_top_k: int = 24     # 价格表保留的走廊-时段槽位数
    price_refresh: int = 5    # 每多少代用当代最优个体刷新一次价格
    max_entry_options: int = 3  # 多标签路由每条弧考察的进入时刻数;1 = 只考虑最早
    fd_calibrate: bool = False  # 是否用有限差分定义式价格校准(代价高,报告用)
    fd_slots: int = 8         # 有限差分探测的槽位数上限
    use_conflict_ops: bool = True  # 是否启用冲突凭证制导的错峰算子
    dispatch: str = "exact"   # 'rule' = 理想最短路估算(开环);'exact' = 预约表试探(闭环)

    # ---- 同算力预算(规格 8.2 协议 1) ----
    # 各消融档的单次评价代价相差数倍(派车试探约 5 倍),只比同代数会把"多花算力"
    # 误读为"机制更好"(规格 13.2 结论 2)。给定该值后,主循环在每代末检查挂钟时间,
    # 超出即停,使各档在**相同算力**下比较;None = 只由 max_gen / stall_gen 停机。
    time_budget_sec: Optional[float] = None


Chromosome = Dict[str, object]  # {"ma": Dict[OpKey,int], "os": List[int]}


# ---------------- 染色体构造 ----------------

def random_os(inst: Instance, rng: random.Random) -> List[int]:
    seq: List[int] = []
    for j, cnt in inst.os_job_counts().items():
        seq.extend([j] * cnt)
    rng.shuffle(seq)
    return seq


def random_ma(inst: Instance, rng: random.Random) -> Dict[OpKey, int]:
    return {op: rng.choice(inst.eligible(*op)) for op in inst.real_ops()}


def ma_min_time(inst: Instance) -> Dict[OpKey, int]:
    """启发式个体 1:行内最小加工时间指派。"""
    return {op: min(inst.proc_time[op], key=lambda m: (inst.proc_time[op][m], m))
            for op in inst.real_ops()}


def ma_load_balance(inst: Instance) -> Dict[OpKey, int]:
    """启发式个体 2:贪心负载均衡指派。"""
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

def pox_crossover(os1: List[int], os2: List[int], jobs: List[int],
                  rng: random.Random) -> Tuple[List[int], List[int]]:
    """POX:随机工件子集在父代中保位,其余按另一父代顺序回填。"""
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
    """OS 段:随机交换两位;MA 段:随机改派 Omega 内另一 RA。"""
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

def os_index_of(os_seq: List[int], op: OpKey) -> Optional[int]:
    """工序 (j,i) 在 OS 中的位置 = 工件 j 的第 i 次出现。"""
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

def _reassign_neighbors(inst: Instance, net: Network, chrom: Chromosome,
                        result: DecodeResult, cfg: GAConfig,
                        prices: Optional[PriceTable]) -> List[Chromosome]:
    """改派算子:关键链上的工序换到"加工快 + 通行权便宜"的 RA。

    评分三项同为时间量纲:接近程度、加工时长、以及为进出该 RA 要买的通行权价格。
    价格项取代了原先的 lam * 累计让行等待——后者是随算例规模增长的全局量,与前两项
    量纲不符,在大算例上会支配评分。
    """
    out: List[Chromosome] = []
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

        best_m = min(candidates, key=lambda m: (score(m), m))
        nb = clone(chrom)
        nb["ma"][op] = best_m  # type: ignore
        out.append(nb)
    return out


def _stagger_neighbors(inst: Instance, chrom: Chromosome, result: DecodeResult,
                       cfg: GAConfig) -> List[Chromosome]:
    """错峰算子:由下层的冲突凭证指认操作对象,在时间维度上化解走廊争用。

    拥堵有两种缓解方式——换地方(改派)与换时间(错峰),原实现只有前者。
    这里取关键链上让行最久的一次走廊等待,从预约表反查是谁占着该走廊,
    然后给出两个定向邻居:把被堵的工序提前发起,或把对手工序推后。
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
    return out


def local_search(inst: Instance, net: Network, chrom: Chromosome,
                 result: DecodeResult, cfg: GAConfig,
                 conflict_free: bool,
                 prices: Optional[PriceTable] = None) -> Tuple[Chromosome, DecodeResult]:
    bw = prices.bucket_width if prices is not None else 0.0
    for _ in range(cfg.ls_rounds):
        improved = False
        neighbors = (_reassign_neighbors(inst, net, chrom, result, cfg, prices)
                     + _stagger_neighbors(inst, chrom, result, cfg))
        for nb in neighbors:
            res2 = decode(inst, net, nb["ma"], nb["os"],  # type: ignore
                          conflict_free=conflict_free, prices=prices,
                          theta=cfg.theta, bucket_width=bw,
                          max_entry_options=cfg.max_entry_options,
                          dispatch=cfg.dispatch)
            if res2.makespan < result.makespan - 1e-9:
                chrom, result = nb, res2
                improved = True
                break              # 首改进:重新提取关键链
        if not improved:
            break
    return chrom, result


# ---------------- 主循环 ----------------

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
        """用当前最优方案的下层运行信息重估影子价格(层间接口的向下一跳)。"""
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
    history_sec: List[float] = []
    best_idx = min(range(len(results)), key=lambda x: results[x].makespan)
    best_chrom, best_result = clone(population[best_idx]), results[best_idx]
    refresh_prices(best_chrom, best_result)
    stall = 0
    n_eval = len(population)
    stopped_by = "max_gen"

    for gen in range(1, cfg.max_gen + 1):
        order = sorted(range(len(population)), key=lambda x: results[x].makespan)

        # 精英个体做价格制导局部搜索(决策级闭环)
        if use_ls:
            n_ls = max(1, math.ceil(cfg.top_ls * cfg.pop))
            for idx in order[:n_ls]:
                ch2, res2 = local_search(inst, net, population[idx], results[idx],
                                         cfg, conflict_free, prices)
                if res2.makespan < results[idx].makespan - 1e-9:
                    population[idx], results[idx] = ch2, res2
            order = sorted(range(len(population)), key=lambda x: results[x].makespan)

        # 更新全局最优
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
        "stopped_by": stopped_by,
        "runtime_sec": round(time.time() - t_start, 2),
        "config": asdict(cfg),
        "bucket_width": round(bw, 4),
        "price_slots": (len(list(prices.items())) if prices is not None else 0),
        "price_agreement": agreement,
        "price_cost_total": round(best_result.price_cost_total, 4),
    }
