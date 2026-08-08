"""争用强度 -> 上层算子可用改进量 的关系曲线(方法型论文的关键判据)。

要验证的两个前提:

  前提一  争用代价占比能否被算例参数推高。当前算例族只有百分之几。
  前提二  推高之后,上层算子的**神谕命中率**是否随之上升。若不上升,则争用制导
          反馈即便在高争用下也无改进可捞,决策级闭环这条线可以彻底关闭。

横轴用**争用代价占比**而非关键链走廊份额:

    share = (C_max(无冲突路由) - C_max(理想最短路)) / C_max(无冲突路由)

同一条染色体、同一套派车决策(规则派车只用理想矩阵,故两种路由下派车一致),
唯一差别是下层是否消解冲突。这个量是良定义的,不依赖关键链归因如何划分,
因此可以在归因口径修好之前先用来定位区间。

纵轴是两族算子各自的神谕命中率:把候选全部真解码,看**是否存在**任何一个能缩短
makespan。它是任何打分函数的上限,故若它不随争用上升,再精巧的算子设计也无用。

运行(clbs/ 目录下):  py -m tools.regime_curve [--gens N] [--seeds a,b] [--quick]
"""
from __future__ import annotations

import os
import random
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import Instance, parse_instance
from algorithm.network import Network
from algorithm.decoder import DecodeResult, decode, critical_chain, critical_real_ops
from algorithm.ga import (GAConfig, Chromosome, clone, init_population, mutate,
                          ma_uniform_crossover, pox_crossover, _stagger_neighbors)
from algorithm.generator import build_instance, make_spec
from tools.probe_diag import spearman, loaded_router, os_positions

# 待比较的三种改派打分。三者都是"该工序换到 m 之后何时完工"的近似,只差用了多少
# 现场信息;逐项加信息,便可把打分缺口拆成"缺哪一项"。
#   S0  现行:理想接近时间 + 加工时长。既不知道机器忙不忙,也不知道路上堵不堵。
#   S1  再加机器可用时刻。零成本(解码结果里现成),只补"机器忙不忙"。
#   S2  再把理想接近时间换成对预约表的真实探询。补"路上堵不堵",每次约 0.09 ms。
#   S3  在 S0 之上只加**出向**行程:该工序做完后工件要从这台臂运到下一道工序的臂
#       (末道工序则回 LU)。现行打分只算"进"不算"出",而 Tt/Tp=3 时运输占大头,
#       这个选择所左右的运输成本有一半对打分不可见。一台"好进难出"的臂会被高估,
#       而这正是"加工较慢但连通性好的臂可能更优"所指的那一半。零成本。
SCORERS = ("S0 现行", "S1 +机器", "S2 +机器+探询", "S3 +出向")

# 配置网格:从当前算例出发,沿"车队密度 / 臂数 / 网络容量 / 运输强度"四个方向外推。
# 目的不是做受控对比,而是尽量把争用代价占比拉开,好看出它与神谕命中率的关系。
CONFIGS: List[dict] = [
    # 车队密度(当前算例 = high M4 A4 Tt/Tp=1)
    dict(tag="high",   nm=4, na=2, tt=1.0),
    dict(tag="high",   nm=4, na=4, tt=1.0),
    dict(tag="high",   nm=4, na=6, tt=1.0),
    dict(tag="high",   nm=4, na=8, tt=1.0),
    # 解掉加工侧瓶颈后再加车
    dict(tag="high",   nm=8, na=6, tt=1.0),
    dict(tag="high",   nm=8, na=8, tt=1.0),
    # 收窄网络
    dict(tag="funnel", nm=4, na=6, tt=1.0),
    dict(tag="funnel", nm=8, na=8, tt=1.0),
    # 加大运输强度
    dict(tag="high",   nm=8, na=8, tt=2.0),
    dict(tag="funnel", nm=8, na=8, tt=2.0),
    dict(tag="funnel", nm=8, na=8, tt=3.0),
    dict(tag="funnel", nm=8, na=12, tt=3.0),
    # 更多工件(负载与车队同时放大)
    dict(tag="funnel", nm=8, na=12, tt=3.0, jobs=16),
    dict(tag="funnel", nm=8, na=16, tt=3.0, jobs=16),
    # 决定性的一组:用**可规避**的拥堵结构(2 条 LU 出口)把争用推高。
    # 若只有 funnel 能推高争用,则"争用高"与"争用可规避"不可兼得,
    # 改派算子先天就没有它需要的那种算例。
    dict(tag="high",   nm=8, na=12, tt=3.0, jobs=16),
    dict(tag="high",   nm=8, na=16, tt=3.0, jobs=16),
    dict(tag="mid",    nm=8, na=16, tt=3.0, jobs=16),
    dict(tag="high",   nm=8, na=16, tt=3.0, jobs=24),
]

QUICK = [CONFIGS[i] for i in (1, 3, 7, 10)]

# 网格布局组:哑铃布局把每台 RA 用**专属支线**挂在枢纽上,同侧两臂之间改派动不了
# 任何一条会被争用的走廊(实测 M8 时 43% 的 RA 对改派杠杆恰为零,见 tools.layout_diag)。
# 若改派算子的失效源于此,则换成 RA 分散、路径互不包含的网格布局后,神谕命中率应
# 在同等争用占比下显著抬升;若不抬升,则失效与布局无关。
GRID: List[dict] = [
    dict(tag="low", nm=8,  na=8,  tt=3.0, jobs=16, extra=dict(grid_rows=3, grid_cols=3)),
    dict(tag="low", nm=8,  na=12, tt=3.0, jobs=16, extra=dict(grid_rows=3, grid_cols=3)),
    dict(tag="low", nm=8,  na=16, tt=3.0, jobs=16, extra=dict(grid_rows=3, grid_cols=3)),
    dict(tag="low", nm=8,  na=12, tt=3.0, jobs=16, extra=dict(grid_rows=4, grid_cols=4)),
    dict(tag="low", nm=8,  na=16, tt=3.0, jobs=16, extra=dict(grid_rows=4, grid_cols=4)),
    dict(tag="low", nm=8,  na=16, tt=4.0, jobs=16, extra=dict(grid_rows=4, grid_cols=4)),
    dict(tag="low", nm=12, na=16, tt=3.0, jobs=16, extra=dict(grid_rows=4, grid_cols=4)),
    dict(tag="low", nm=8,  na=16, tt=3.0, jobs=24, extra=dict(grid_rows=4, grid_cols=4)),
    dict(tag="low", nm=12, na=16, tt=3.0, jobs=24, extra=dict(grid_rows=5, grid_cols=5)),
]


# 布局配对组:每两行只差**布局**一个因素,其余(网格规模 / 臂数 / 车数 / 工件数 /
# 运输强度)全部对齐,故两行之差可直接归因给布局。
#   low     网格,但 RA 按到 LU 的距离降序取,实际聚在远端一角
#   scatter 同尺寸网格,RA 用最远点采样铺开,LU 置于边中点
# 参照行给出哑铃布局。若"改派失效源于布局"成立,scatter 行的改派神谕应显著高于
# 同规模的 low 行与哑铃行。
def _pair(rows: int, cols: int, nm: int, na: int, jobs: int, tt: float) -> List[dict]:
    extra = dict(grid_rows=rows, grid_cols=cols)
    return [dict(tag=t, nm=nm, na=na, tt=tt, jobs=jobs, extra=extra)
            for t in ("low", "scatter")]


PAIRS: List[dict] = (
    [dict(tag="high", nm=8, na=12, tt=3.0, jobs=16)]        # 哑铃参照
    + _pair(4, 4, 8, 12, 16, 3.0)
    + _pair(4, 4, 8, 16, 16, 3.0)
    + _pair(4, 4, 12, 16, 16, 3.0)
    + _pair(5, 5, 12, 16, 24, 3.0)
    + _pair(5, 5, 8, 12, 16, 3.0)
)


# 归因拆解:改派算子失效被怀疑有两个独立成因,此处用析因设计把两者分开。
#
#   成因一  候选太少。臂数少时关键工序常常只有一台可换的臂,"选哪台"这个问题
#           根本不存在。沿臂数 M 这一维观察平均候选数与神谕。
#   成因二  换臂换不掉争用走廊。沿布局这一维观察:
#             high    哑铃,每台臂一条专属支线,同侧改派动不了任何争用走廊
#             low     网格,但按到 LU 的距离降序取点,臂聚在远端一角
#             scatter 同尺寸网格,臂用最远点采样铺开
#
# 其余因素(网格尺寸 4x4 / 车数 / 工件数 / 运输强度 / F / H / 种子)全部固定,
# 故行间之差可分别归因给臂数与布局。臂数一维不可避免地同时改变机器负载,这是
# "加臂"这件事的固有后果,不再拆分。
ATTRIB: List[dict] = [
    dict(tag=t, nm=m, na=12, tt=3.0, jobs=16,
         extra=dict(grid_rows=4, grid_cols=4))
    for m in (4, 8, 12) for t in ("high", "low", "scatter")
]

# 去混淆组:臂数固定在 8,改用柔性度 F 单独调候选数(不动机器负载),
# 以判定臂数的作用究竟来自"候选变多"还是"产能变多"。
FLEX: List[dict] = [
    dict(tag=t, nm=8, na=12, tt=3.0, jobs=16, flex=f,
         extra=dict(grid_rows=4, grid_cols=4))
    for f in (0.3, 0.6, 1.0) for t in ("low", "scatter")
]


def contention_share(inst: Instance, net: Network, chrom: Chromosome,
                     res: DecodeResult) -> float:
    """同一染色体在无冲突路由与理想最短路下的 makespan 之差占比。"""
    ideal = decode(inst, net, chrom["ma"], chrom["os"],   # type: ignore
                   conflict_free=False, dispatch="rule")
    if res.makespan <= 1e-9:
        return 0.0
    return max(0.0, (res.makespan - ideal.makespan) / res.makespan)


def chain_corridor_share(res: DecodeResult) -> float:
    """关键链上 corridor 类环节占 C_max 的比例(口径待修,仅作参照)。"""
    if res.makespan <= 1e-9:
        return 0.0
    amt = sum(it.amount for it in critical_chain(res) if it.kind == "corridor")
    return amt / res.makespan


def oracle_at(inst: Instance, net: Network, chrom: Chromosome, res: DecodeResult,
              cfg: GAConfig) -> Dict[str, int]:
    """一遍同时量出改派算子的三件事,归因缺一不可:

      候选数    该情形有几台可换的臂。若普遍只有一台,则"打分选哪台"这个问题
                根本不存在,任何打分的命中率都只能等于神谕。
      神谕      存在某个候选能缩短 makespan 的情形占比,任何打分的上限。
      现行打分  按 ga._reassign_neighbors 的 (理想接近时间 + 加工时长) 取最优的
                那一台,真解码后确实缩短了 makespan 的情形占比。

    神谕与现行打分之差 = 打分函数留在桌上的改进;候选数则决定这个差有没有意义。
    """
    acc: Dict[str, float] = dict(n_re=0, hit_re=0, cand=0, n_st=0, hit_st=0,
                                 decodes=0, rand=0.0, reg_rand=0.0, n_pos=0)
    for s in SCORERS:
        acc[f"hit_{s}"] = 0
        acc[f"reg_{s}"] = 0.0

    positions = os_positions(chrom["os"])                     # type: ignore

    for op in critical_real_ops(res)[: cfg.L_ls]:
        j, i = op
        cur_m = chrom["ma"][op]                               # type: ignore
        cands = [m for m in inst.eligible(j, i) if m != cur_m]
        if not cands:
            continue
        acc["n_re"] += 1
        acc["cand"] += len(cands)

        pos_prev = (inst.lu_node if i == 1
                    else inst.machine_node[chrom["ma"][(j, i - 1)]])  # type: ignore
        ready = 0.0 if i == 1 else res.ops[(j, i - 1)].finish
        my_pos = positions[op]

        # 出向落点:下一道工序所在的臂;末道工序则视 delta_return 决定是否回 LU
        if i < inst.num_ops[j]:
            pos_next: Optional[str] = inst.machine_node[chrom["ma"][(j, i + 1)]]  # type: ignore
        elif inst.delta_return:
            pos_next = inst.lu_node
        else:
            pos_next = None

        # 该工序原有的两段行程会被改派替换掉,探询时不应把它们算作占用
        router = loaded_router(net, res)
        router.table.release_all(f"J{j}-{i}-empty")
        router.table.release_all(f"J{j}-{i}-loaded")

        def free_time(m: int) -> float:
            """该 RA 上排在本工序之前的作业完工时刻(一步近似,不重排同机序)。"""
            return max((rec.finish for o, rec in res.ops.items()
                        if rec.machine == m and o != op
                        and positions.get(o, -1) < my_pos), default=0.0)

        # 三种打分各自的最优候选,以及每个候选的真实改进量
        score: Dict[str, Dict[int, float]] = {s: {} for s in SCORERS}
        delta: Dict[int, float] = {}
        for m in cands:
            node = inst.machine_node[m]
            proc = inst.proc_time[op][m]
            fm = free_time(m)
            ideal_arr = ready + net.ideal_dist[pos_prev][node]
            probe_arr = router.route(pos_prev, node, ready, -1, "probe",
                                     commit=False).arrive
            score["S0 现行"][m] = net.ideal_dist[pos_prev][node] + proc
            score["S1 +机器"][m] = max(ideal_arr, fm) + proc
            score["S2 +机器+探询"][m] = max(probe_arr, fm) + proc
            score["S3 +出向"][m] = (net.ideal_dist[pos_prev][node] + proc
                                   + (net.ideal_dist[node][pos_next]
                                      if pos_next is not None else 0.0))

            nb = clone(chrom)
            nb["ma"][op] = m                                  # type: ignore
            r2 = decode(inst, net, nb["ma"], nb["os"],        # type: ignore
                        conflict_free=True, dispatch=cfg.dispatch)
            acc["decodes"] += 1
            delta[m] = res.makespan - r2.makespan

        best = max(delta.values())
        if best > 1e-9:
            acc["hit_re"] += 1

        # 随机基线。神谕允许在全部候选里挑,打分只能选一个,二者试的次数不同,
        # 故神谕天然占着"多试几次"的便宜——这部分与打分好坏无关。随机挑一个的
        # 命中概率恰为「可改进候选数 / 候选数」,取期望即得基线,无需再解码。
        # 打分的真实本领应看它在随机与神谕之间走了多远。
        n_pos = sum(1 for v in delta.values() if v > 1e-9)
        acc["rand"] += n_pos / len(cands)
        acc["reg_rand"] += sum(max(0.0, best - v) for v in delta.values()) / len(cands)
        acc["n_pos"] += n_pos

        for s in SCORERS:
            pick = min(cands, key=lambda m: (score[s][m], m))
            if delta[pick] > 1e-9:
                acc[f"hit_{s}"] += 1
            acc[f"reg_{s}"] += max(0.0, best - delta[pick])

    st_nbs = _stagger_neighbors(inst, chrom, res, cfg)
    if st_nbs:
        acc["n_st"] += 1
        for nb in st_nbs:
            r2 = decode(inst, net, nb["ma"], nb["os"],        # type: ignore
                        conflict_free=True, dispatch=cfg.dispatch)
            acc["decodes"] += 1
            if r2.makespan < res.makespan - 1e-9:
                acc["hit_st"] += 1
                break
    return acc


def run_cell(inst: Instance, net: Network, seeds: Sequence[int], gens: int) -> dict:
    cfg = GAConfig(pop=40, seed=seeds[0], theta=0.0, dispatch="rule",
                   use_conflict_ops=True)
    # 分阶段累计:打分函数的优势可能只存在于种群尚未收敛的前半程,而局部搜索真正
    # 要啃的是收敛尾段。两段合并统计会把这个区别抹掉,故分开记。
    def _blank() -> Dict[str, float]:
        d: Dict[str, float] = dict(n_re=0, hit_re=0, cand=0, n_st=0, hit_st=0,
                                   decodes=0, rand=0.0, reg_rand=0.0, n_pos=0)
        for s in SCORERS:
            d[f"hit_{s}"] = 0
            d[f"reg_{s}"] = 0.0
        return d

    phases = {"前半程": _blank(), "后半程": _blank()}
    shares: List[float] = []
    chain_shares: List[float] = []
    cmaxes: List[float] = []

    for seed in seeds:
        rng = random.Random(seed)
        pop = init_population(inst, cfg, rng)
        res = [decode(inst, net, ch["ma"], ch["os"],          # type: ignore
                      conflict_free=True, dispatch=cfg.dispatch) for ch in pop]

        for gen in range(gens):
            order = sorted(range(len(pop)), key=lambda x: res[x].makespan)
            elite, elite_res = pop[order[0]], res[order[0]]

            # 全程取样但分两段记账。前期任何扰动都容易改进,合并统计会高估算子价值;
            # 而只看尾段又会漏掉"优势只在前期"这种情况,那正是待检验的假设。
            late = gen >= gens - max(1, gens // 3)
            if late:
                shares.append(contention_share(inst, net, elite, elite_res))
                chain_shares.append(chain_corridor_share(elite_res))
                cmaxes.append(elite_res.makespan)
            if late or gen < max(1, gens // 3):
                bucket = phases["后半程" if late else "前半程"]
                for k, v in oracle_at(inst, net, elite, elite_res, cfg).items():
                    bucket[k] += v

            new_pop: List[Chromosome] = [clone(pop[k]) for k in order[: cfg.elite]]
            while len(new_pop) < cfg.pop:
                a1 = pop[min(rng.sample(range(len(pop)), 2), key=lambda x: res[x].makespan)]
                b1 = pop[min(rng.sample(range(len(pop)), 2), key=lambda x: res[x].makespan)]
                if rng.random() < cfg.pc:
                    os1, os2 = pox_crossover(a1["os"], b1["os"], inst.job_ids, rng)  # type: ignore
                    ma1, ma2 = ma_uniform_crossover(a1["ma"], b1["ma"], rng)         # type: ignore
                    kids = [{"ma": ma1, "os": os1}, {"ma": ma2, "os": os2}]
                else:
                    kids = [clone(a1), clone(b1)]
                for kid in kids:
                    if rng.random() < cfg.pm:
                        mutate(inst, kid, rng)
                    new_pop.append(kid)
                    if len(new_pop) >= cfg.pop:
                        break
            pop = new_pop
            res = [decode(inst, net, ch["ma"], ch["os"],      # type: ignore
                          conflict_free=True, dispatch=cfg.dispatch) for ch in pop]

    n = max(len(shares), 1)
    out = {
        "share": sum(shares) / n,
        "chain_share": sum(chain_shares) / n,
        "cmax": sum(cmaxes) / n,
    }
    for tag, acc in phases.items():
        nre = max(acc["n_re"], 1)
        out[tag] = {
            "oracle_re": acc["hit_re"] / nre,
            "cands": acc["cand"] / nre,
            "hit_rand": acc["rand"] / nre,
            "reg_rand": acc["reg_rand"] / nre,
            "n_pos": acc["n_pos"] / nre,
            "oracle_st": acc["hit_st"] / max(acc["n_st"], 1),
            "n_re": acc["n_re"],
            **{f"hit_{s}": acc[f"hit_{s}"] / nre for s in SCORERS},
            **{f"reg_{s}": acc[f"reg_{s}"] / nre for s in SCORERS},
        }
    return out


def main() -> int:
    args = sys.argv[1:]
    gens = int(args[args.index("--gens") + 1]) if "--gens" in args else 24
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7])
    if "--attrib" in args:
        grid = ATTRIB
    elif "--flex" in args:
        grid = FLEX
    elif "--pairs" in args:
        grid = PAIRS
    elif "--grid" in args:
        grid = GRID
    elif "--quick" in args:
        grid = QUICK
    else:
        grid = CONFIGS
    if "--last" in args:                    # 只跑网格末尾若干格,便于增量补测
        grid = grid[-int(args[args.index("--last") + 1]):]

    print(f"代数={gens} 种子={seeds};前 1/3 代与后 1/3 代分别记账\n")
    rows: List[dict] = []
    for c in grid:
        jobs = c.get("jobs", 8)
        extra = c.get("extra", {})
        flex = c.get("flex", 0.6)
        spec = make_spec(c["tag"], 0.3, flex, jobs, c["nm"], c["na"], 3,
                         seed=42, tt_tp_target=c["tt"], **extra)
        inst = parse_instance(build_instance(spec))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        if "--attrib" in args:
            label = f"{c['tag']:<8s} M{c['nm']}"
        elif "--flex" in args:
            label = f"{c['tag']:<8s} F{flex:g}"
        else:
            shape = (f" {extra['grid_rows']}x{extra['grid_cols']}"
                     if "grid_rows" in extra else "")
            label = f"{c['tag']}{shape} J{jobs} M{c['nm']} A{c['na']} Tt/Tp={c['tt']:g}"
        r = run_cell(inst, net, seeds, gens)
        r["label"] = label
        rows.append(r)
        print(f"  已完成 {label}", flush=True)

    for phase in ("前半程", "后半程"):
        print(f"\n【{phase}】")
        print(f"{'配置':<22s} {'候选':>5s} {'可改进':>6s} {'随机':>6s} {'神谕':>6s} "
              + "".join(f"{s:>8s}" for s in SCORERS) + f" {'情形':>6s}")
        print("-" * 92)
        for r in rows:
            p = r[phase]
            print(f"{r['label']:<22s} {p['cands']:>5.1f} {p['n_pos']:>6.2f} "
                  f"{p['hit_rand']:>6.1%} {p['oracle_re']:>6.1%} "
                  + "".join(f"{p[f'hit_{s}']:>8.1%}" for s in SCORERS)
                  + f" {p['n_re']:>6d}")
        print("-" * 92)
        tot = max(sum(r[phase]["n_re"] for r in rows), 1)

        def wavg(key: str) -> float:
            return sum(r[phase][key] * r[phase]["n_re"] for r in rows) / tot

        rnd, orc = wavg("hit_rand"), wavg("oracle_re")
        span = orc - rnd
        print(f"  {'随机基线':<16s} 命中 {rnd:>6.1%}   后悔 {wavg('reg_rand'):>5.2f}")
        for s in SCORERS:
            h = wavg(f"hit_{s}")
            cap = (h - rnd) / span if span > 1e-9 else float("nan")
            print(f"  {s:<16s} 命中 {h:>6.1%}   后悔 {wavg(f'reg_{s}'):>5.2f}   "
                  f"捕获 {cap:>6.1%}")
        print(f"  {'神谕上界':<16s} 命中 {orc:>6.1%}   后悔  0.00   捕获 100.0%")

    print()
    xs = [r["share"] for r in rows]
    for key, name in (("oracle_re", "改派神谕"), ("oracle_st", "错峰神谕")):
        rho = spearman(xs, [r["后半程"][key] for r in rows])
        txt = f"{rho:+.3f}" if rho is not None else "n/a"
        print(f"争用占比 vs {name}(后半程)的秩相关: {txt}")
    print()
    print("争用占比 = (无冲突路由 C_max - 理想最短路 C_max) / 无冲突路由 C_max,同一染色体")
    print("候选     = 每个改派情形平均有几台可换的臂;接近 1 则打分无从发挥")
    print("可改进   = 这些候选里平均有几台真能缩短 makespan")
    print("随机     = 随机挑一个候选的命中概率(= 可改进/候选 的期望),打分的下界")
    print("神谕     = 存在某个候选能缩短 makespan 的情形占比,打分的上界")
    print("捕获     = (打分命中 - 随机) / (神谕 - 随机),即打分在可争取的区间里走了多远。")
    print("           神谕允许在全部候选里挑而打分只能选一个,直接看两者之差会把")
    print("           '多试几次'的便宜误记成打分的失分,故须以随机基线为原点。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
