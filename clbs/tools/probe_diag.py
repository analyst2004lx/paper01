"""探询式改派打分的判定实验(是否值得把 t* 打分换成预约表探询)。

背景:规格 6.5 的改派算子按 `t*(前道位置, 候选 RA) + 加工时长` 打分,其中 t* 是
**无争用**最短路。也就是说,这个专为"通往快臂的走廊堵了就换臂"而设的算子,
用的恰是全文批判两阶段基线时所用的那个乐观矩阵——它看不见拥堵。

替代方案是把邻近项从"估计"换成"探询":拿当前解的预约表,对候选 RA 做一次
**不提交**的路由,得到真实到达时刻。代价是一次 Dijkstra,而不是一次完整解码。

本脚本不改动算法,只测三个决定要不要动手的量:

A. 代价比。一次探询 / 一次完整解码。决定"筛选再解码"能省多少。
B. 打分质量。四种打分函数对同一批候选排序,与"解码后真实改进量"比对:
     S0 = t*(前道, 候选) + 加工时长                     ← 现行实现
     S1 = 探询到达 + 加工时长                            ← 只把估计换成探询
     S2 = max(探询到达, 该 RA 空闲时刻) + 加工时长        ← 探询 + 一步绑定式
     S3 = max(理想到达, 该 RA 空闲时刻) + 加工时长        ← 对照:只加机器项,不探询
   S3 是必要的对照。若 S2 优于 S0 而 S3 也同样优,那么收益来自"忘了机器项"
   而非"探询",结论完全不同。
C. 筛选效果。用打分预测"改派是否比现状好",只解码预测为好的候选:
   能省掉多少次解码,又漏掉多少次真实改进。

运行(clbs/ 目录下):  py -m tools.probe_diag [算例路径 ...] [--gens N] [--seeds a,b]
"""
from __future__ import annotations

import os
import sys
import time
import random
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import Instance, OpKey, load_instance
from algorithm.network import Network, Router
from algorithm.decoder import DecodeResult, decode, critical_real_ops
from algorithm.ga import (GAConfig, Chromosome, clone, init_population, mutate,
                          ma_uniform_crossover, pox_crossover)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "input", "ext")
SCORERS = ("S0", "S1", "S2", "S3")
SCORER_DESC = {
    "S0": "t* + 加工        (现行)",
    "S1": "探询 + 加工",
    "S2": "探询 + 机器 + 加工",
    "S3": "t* + 机器 + 加工  (对照)",
}


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """秩相关;并列取平均秩。样本不足或某一列为常数时返回 None。"""
    n = len(xs)
    if n < 2:
        return None

    def ranks(v: Sequence[float]) -> List[float]:
        order = sorted(range(n), key=lambda i: v[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and abs(v[order[j + 1]] - v[order[i]]) < 1e-12:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx < 1e-12 or dy < 1e-12:
        return None
    return num / (dx * dy)


def os_positions(os_seq: Sequence[int]) -> Dict[OpKey, int]:
    """工序 -> 它在 OS 序列中的下标(含伪工序)。"""
    cnt: Dict[int, int] = {}
    pos: Dict[OpKey, int] = {}
    for idx, j in enumerate(os_seq):
        cnt[j] = cnt.get(j, 0) + 1
        pos[(j, cnt[j])] = idx
    return pos


def loaded_router(net: Network, result: DecodeResult) -> Router:
    """从一个已解码方案重建预约表,得到"当前车间实际交通状况"下的路由器。

    与解码途中的活预约表不同:这里含全部任务(包括时间上更晚的),因此探询回答的是
    "把一趟行程插进这份完整交通里会几点到",这正是局部搜索所处的语境。
    """
    router = Router(net, conflict_free=True)
    for tr in result.transports:
        for kind, plan in (("empty", tr.empty_plan), ("loaded", tr.loaded_plan)):
            task = f"J{tr.job}-{tr.i}-{kind}"
            for s in plan.segments:
                router.table.reserve(s.corridor, s.enter, s.exit, tr.agv, task)
    return router


# --------------------------------------------------------------------------
# A. 代价比
# --------------------------------------------------------------------------

def measure_cost(inst: Instance, net: Network, chrom: Chromosome,
                 result: DecodeResult, reps: int = 30) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for mode in ("rule", "exact"):
        t0 = time.perf_counter()
        for _ in range(reps):
            decode(inst, net, chrom["ma"], chrom["os"],  # type: ignore
                   conflict_free=True, dispatch=mode)
        out[f"decode_{mode}_ms"] = (time.perf_counter() - t0) * 1000.0 / reps

    router = loaded_router(net, result)
    nodes = [inst.machine_node[m] for m in sorted(inst.machine_node)]
    pairs = [(inst.lu_node, d) for d in nodes] + [(a, b) for a in nodes for b in nodes if a != b]
    horizon = result.makespan
    n = 0
    t0 = time.perf_counter()
    for _ in range(reps):
        for k, (a, b) in enumerate(pairs):
            router.route(a, b, horizon * (k % 5) / 5.0, -1, "probe", commit=False)
            n += 1
    out["probe_ms"] = (time.perf_counter() - t0) * 1000.0 / max(n, 1)
    return out


# --------------------------------------------------------------------------
# B/C. 打分质量与筛选效果
# --------------------------------------------------------------------------

def eval_situation(inst: Instance, net: Network, chrom: Chromosome,
                   result: DecodeResult, op: OpKey, dispatch: str,
                   gen: int = 0) -> Optional[dict]:
    """对关键链上的一个工序,给出全部候选 RA 的四种打分与真实改进量。"""
    j, i = op
    cur_m: int = chrom["ma"][op]            # type: ignore
    cands = sorted(inst.eligible(j, i))
    if len(cands) < 2:                      # 无可换之处,打分无从谈起
        return None

    pos_prev = inst.lu_node if i == 1 else inst.machine_node[chrom["ma"][(j, i - 1)]]  # type: ignore
    ready = 0.0 if i == 1 else result.ops[(j, i - 1)].finish
    positions = os_positions(chrom["os"])   # type: ignore
    my_pos = positions[op]

    def free_time(m: int) -> float:
        """该 RA 上排在本工序之前的作业完工时刻(一步近似,不重排同机序)。"""
        f = 0.0
        for o, rec in result.ops.items():
            if rec.machine == m and o != op and positions.get(o, -1) < my_pos:
                f = max(f, rec.finish)
        return f

    router = loaded_router(net, result)
    # 本工序原有的两段行程会被改派替换掉,探询时不应把它们算作占用
    router.table.release_all(f"J{j}-{i}-empty")
    router.table.release_all(f"J{j}-{i}-loaded")

    rows: List[dict] = []
    for m in cands:
        node = inst.machine_node[m]
        proc = inst.proc_time[op][m]
        ideal_arr = ready + net.ideal_dist[pos_prev][node]
        probe_arr = router.route(pos_prev, node, ready, -1, "probe", commit=False).arrive
        fm = free_time(m)
        rows.append({
            "m": m,
            "S0": net.ideal_dist[pos_prev][node] + proc,
            "S1": probe_arr + proc,
            "S2": max(probe_arr, fm) + proc,
            "S3": max(ideal_arr, fm) + proc,
            "detour": probe_arr - ideal_arr,     # 探询相对理想的额外耗时
        })

    for r in rows:
        if r["m"] == cur_m:
            r["delta"] = 0.0                     # 现状,按定义无改进
            continue
        nb = clone(chrom)
        nb["ma"][op] = r["m"]                    # type: ignore
        res2 = decode(inst, net, nb["ma"], nb["os"],  # type: ignore
                      conflict_free=True, dispatch=dispatch)
        r["delta"] = result.makespan - res2.makespan

    return {"op": op, "cur_m": cur_m, "rows": rows, "gen": gen}


def collect_situations(path: str, seeds: Sequence[int], gens: int,
                       dispatch: str, log=print) -> Tuple[dict, List[dict], Instance]:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    cfg = GAConfig(pop=40, seed=seeds[0])

    sits: List[dict] = []
    cost: Dict[str, float] = {}
    for si, seed in enumerate(seeds):
        rng = random.Random(seed)
        pop = init_population(inst, cfg, rng)
        res = [decode(inst, net, ch["ma"], ch["os"],  # type: ignore
                      conflict_free=True, dispatch=dispatch) for ch in pop]

        for gen in range(gens):
            order = sorted(range(len(pop)), key=lambda x: res[x].makespan)
            elite, elite_res = pop[order[0]], res[order[0]]

            if si == 0 and gen == 0:
                cost = measure_cost(inst, net, elite, elite_res)

            # 局部搜索只作用于精英,故情形样本取自精英的关键链
            for op in critical_real_ops(elite_res)[: cfg.L_ls]:
                s = eval_situation(inst, net, elite, elite_res, op, dispatch, gen)
                if s is not None:
                    s["gen_frac"] = gen / max(gens - 1, 1)
                    sits.append(s)

            new_pop: List[Chromosome] = [clone(pop[k]) for k in order[: cfg.elite]]
            while len(new_pop) < cfg.pop:
                a = pop[min(rng.sample(range(len(pop)), 2), key=lambda x: res[x].makespan)]
                b = pop[min(rng.sample(range(len(pop)), 2), key=lambda x: res[x].makespan)]
                if rng.random() < cfg.pc:
                    os1, os2 = pox_crossover(a["os"], b["os"], inst.job_ids, rng)  # type: ignore
                    ma1, ma2 = ma_uniform_crossover(a["ma"], b["ma"], rng)         # type: ignore
                    kids = [{"ma": ma1, "os": os1}, {"ma": ma2, "os": os2}]
                else:
                    kids = [clone(a), clone(b)]
                for kid in kids:
                    if rng.random() < cfg.pm:
                        mutate(inst, kid, rng)
                    new_pop.append(kid)
                    if len(new_pop) >= cfg.pop:
                        break
            pop = new_pop
            res = [decode(inst, net, ch["ma"], ch["os"],  # type: ignore
                          conflict_free=True, dispatch=dispatch) for ch in pop]
        log(f"    seed {seed}: 累计 {len(sits)} 个情形")
    return cost, sits, inst


def summarize(sits: List[dict]) -> dict:
    """把情形样本折算成决策相关的指标。"""
    n = len(sits)
    n_alt = [len(s["rows"]) - 1 for s in sits]
    oracle_hit = 0
    detours = []
    sel = {k: {"hit": 0, "regret": 0.0, "rho": [], "n_sel": 0} for k in SCORERS}
    scr = {k: {"go": 0, "go_and_improve": 0} for k in SCORERS}

    for s in sits:
        rows = s["rows"]
        cur = next(r for r in rows if r["m"] == s["cur_m"])
        alts = [r for r in rows if r["m"] != s["cur_m"]]
        detours.extend(r["detour"] for r in rows)
        best = max(r["delta"] for r in alts)
        if best > 1e-9:
            oracle_hit += 1

        for k in SCORERS:
            pick = min(alts, key=lambda r: (r[k], r["m"]))
            sel[k]["n_sel"] += 1
            if pick["delta"] > 1e-9:
                sel[k]["hit"] += 1
            sel[k]["regret"] += best - pick["delta"]
            if len(alts) >= 2:
                rho = spearman([-r[k] for r in alts], [r["delta"] for r in alts])
                if rho is not None:
                    sel[k]["rho"].append(rho)
            # 筛选:打分认为比现状好才值得解码
            if pick[k] < cur[k] - 1e-9:
                scr[k]["go"] += 1
                if best > 1e-9:
                    scr[k]["go_and_improve"] += 1

    out = {
        "n_situations": n,
        "mean_alternatives": sum(n_alt) / max(n, 1),
        "frac_single_alt": sum(1 for a in n_alt if a == 1) / max(n, 1),
        "oracle_improve_rate": oracle_hit / max(n, 1),
        "mean_detour": sum(detours) / max(len(detours), 1),
        "frac_detour_positive": sum(1 for d in detours if d > 1e-9) / max(len(detours), 1),
        "scorers": {},
    }
    for k in SCORERS:
        rhos = sel[k]["rho"]
        out["scorers"][k] = {
            "hit_rate": sel[k]["hit"] / max(sel[k]["n_sel"], 1),
            "mean_regret": sel[k]["regret"] / max(sel[k]["n_sel"], 1),
            "spearman": (sum(rhos) / len(rhos)) if rhos else None,
            "n_rho": len(rhos),
            "screen_go_rate": scr[k]["go"] / max(n, 1),
            "screen_recall": (scr[k]["go_and_improve"] / oracle_hit) if oracle_hit else None,
        }
    return out


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def default_paths() -> List[str]:
    names = ["S8x4x4-LG21-H0.3-F0.6-A4-s42.json",   # low
             "S8x4x4-LD22-H0.3-F0.6-A4-s42.json",   # mid
             "S8x4x4-LD21-H0.3-F0.6-A4-s42.json",   # high
             "S8x4x4-LD11-H0.3-F0.6-A4-s42.json"]   # funnel
    return [os.path.join(EXT, n) for n in names if os.path.exists(os.path.join(EXT, n))]


def main() -> int:
    args = [a for a in sys.argv[1:]]
    gens, seeds, dispatch = 12, [42, 7], "rule"
    paths: List[str] = []
    k = 0
    while k < len(args):
        if args[k] == "--gens":
            gens = int(args[k + 1]); k += 2
        elif args[k] == "--seeds":
            seeds = [int(x) for x in args[k + 1].split(",")]; k += 2
        elif args[k] == "--dispatch":
            dispatch = args[k + 1]; k += 2
        else:
            paths.append(args[k]); k += 1
    if not paths:
        paths = default_paths()
    if not paths:
        print("找不到算例;先运行 tools/gen_instances.py 生成 input/ext/")
        return 1

    all_sits: List[dict] = []
    print(f"派车模式={dispatch}  代数={gens}  种子={seeds}\n")
    for path in paths:
        tag = os.path.basename(path)
        print(f"[{tag}]")
        cost, sits, _inst = collect_situations(path, seeds, gens, dispatch)
        print(f"    代价: 完整解码 rule={cost['decode_rule_ms']:.2f} ms / "
              f"exact={cost['decode_exact_ms']:.2f} ms;"
              f" 单次探询={cost['probe_ms']:.4f} ms")
        print(f"    比值: 一次解码 = {cost['decode_rule_ms']/cost['probe_ms']:.0f} 次探询(rule)"
              f" / {cost['decode_exact_ms']/cost['probe_ms']:.0f} 次(exact)")
        s = summarize(sits)
        print(f"    情形 {s['n_situations']}  平均候选 {s['mean_alternatives']:.2f}"
              f"  仅一个候选占比 {s['frac_single_alt']:.0%}"
              f"  存在可改进候选 {s['oracle_improve_rate']:.1%}")
        all_sits.extend(sits)
        print()

    report("全部情形", all_sits)
    # 局部搜索真正起作用的是收敛后期;早期任何扰动都容易改进,会高估机制价值
    report("搜索前半程", [s for s in all_sits if s.get("gen_frac", 0.0) < 0.5])
    report("搜索后半程", [s for s in all_sits if s.get("gen_frac", 0.0) >= 0.5])
    print("命中率 = 该打分选中的候选确实缩短了 makespan 的情形占比(上限为神谕)")
    print("后悔   = 最优候选的改进量 - 所选候选的改进量,越小越好")
    print("筛选   = 打分判定「值得一试」的情形占比,越低越省算力;")
    print("查全   = 真实可改进的情形中,被筛选放行的比例,应接近 100%")
    return 0


def report(title: str, sits: List[dict]) -> None:
    if not sits:
        return
    s = summarize(sits)
    print("=" * 78)
    print(f"【{title}】情形 {s['n_situations']};平均候选 {s['mean_alternatives']:.2f};"
          f" 仅一个候选 {s['frac_single_alt']:.0%}")
    print(f"  探询与理想最短路的差距:均值 {s['mean_detour']:.2f},"
          f" 有正差距的候选占 {s['frac_detour_positive']:.0%}"
          "  <- 若接近 0 则探询无信息可给")
    print(f"  神谕上界(存在某候选能改进 makespan): {s['oracle_improve_rate']:.1%}"
          "  <- 任何打分的命中率都不可能超过它")
    print(f"  {'打分':<22s} {'命中率':>7s} {'平均后悔':>9s} {'秩相关':>7s} "
          f"{'筛选放行':>8s} {'查全':>7s}")
    print("  " + "-" * 74)
    for k in SCORERS:
        d = s["scorers"][k]
        rho = f"{d['spearman']:+.3f}" if d["spearman"] is not None else "    n/a"
        rec = f"{d['screen_recall']:.0%}" if d["screen_recall"] is not None else "  n/a"
        print(f"  {SCORER_DESC[k]:<22s} {d['hit_rate']:>6.1%} {d['mean_regret']:>9.3f} "
              f"{rho:>7s} {d['screen_go_rate']:>7.0%} {rec:>7s}")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
