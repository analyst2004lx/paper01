"""错峰算子的 0% 命中是真结论还是实现缺陷?

现象:tools/regime_curve.py --attrib 里错峰算子在几乎所有格子上命中率为 0%。一整族
算子完全零命中,通常是实现问题而非性质,故须单独验。

被怀疑的机制。解码器按 OS 扫描顺序逐个下预约,`earliest_entry` 只看得见**已经**
落表的预约,故一次让行必定由 OS 序列中**更早**的任务造成;要缓解它,就必须跨过
那个任务。而 ga.os_shift 只与最近的异工件基因交换一次位置——若阻塞者在 OS 中远在
数格之前,这一步换不过去,邻居解码出来与原解完全同一个 makespan。

本工具在同一批情形上比三种走法:

  current    现行:被堵工序前移一格 / 对手后移一格(ga._stagger_neighbors)
  random     随机相邻交换,邻居个数与 current 相同,作为"扰动本身值多少"的基线
  precede    用同一张冲突凭证真正**反转**二者在 OS 中的先后:把被堵工序整体插到
             阻塞者之前,或把阻塞者插到被堵工序之后

同时报告 OS 位置差的分布与"邻居解码后 makespan 未变"的比例——后者直接量化邻域惰性。

运行(clbs/ 目录下):  py -m tools.stagger_fix_diag [--gens N] [--seeds a,b]
"""
from __future__ import annotations

import os
import random
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import Instance, parse_instance
from algorithm.network import Network
from algorithm.decoder import (DecodeResult, decode, critical_chain,
                               blocking_opponents)
from algorithm.ga import (GAConfig, Chromosome, clone, init_population, mutate,
                          ma_uniform_crossover, pox_crossover, os_index_of,
                          _stagger_neighbors)
from algorithm.generator import build_instance, make_spec

# 与 regime_curve --attrib 完全一致的格子,含错峰命中 0% 的那几个
CONFIGS = [
    dict(tag="high", nm=8, na=12, jobs=16),
    dict(tag="low", nm=8, na=12, jobs=16),
    dict(tag="scatter", nm=8, na=12, jobs=16),
    dict(tag="high", nm=12, na=16, jobs=16),
    dict(tag="low", nm=12, na=16, jobs=16),
]
VARIANTS = ("current", "random", "precede")


def os_move(os_seq: List[int], src: int, dst: int) -> None:
    """把 src 处的基因取出、插到 dst 处。仍是同一个多重集,故排列合法。

    同一工件的基因彼此等价(第 k 个出现即第 k 道工序),故跨过同工件基因不改变解码
    结果;真正变化的是该工件与**别的**工件之间的先后。
    """
    g = os_seq.pop(src)
    os_seq.insert(dst, g)


def build_neighbors(inst: Instance, chrom: Chromosome, res: DecodeResult,
                    cfg: GAConfig, rng: random.Random
                    ) -> Tuple[Dict[str, List[Chromosome]], List[int]]:
    """三种走法各自的邻居,以及被堵工序与阻塞者的 OS 位置差。"""
    out: Dict[str, List[Chromosome]] = {v: [] for v in VARIANTS}
    gaps: List[int] = []

    cur = _stagger_neighbors(inst, chrom, res, cfg)
    out["current"] = cur
    if not cur:
        return out, gaps

    items = [it for it in critical_chain(res)
             if it.kind == "corridor" and it.corridor is not None
             and it.amount > 1e-9]
    if not items:
        return out, gaps
    it = max(items, key=lambda x: x.amount)

    os_seq: List[int] = chrom["os"]                       # type: ignore
    i_b = os_index_of(os_seq, it.op) if it.op is not None else None
    opps = [o for o in blocking_opponents(res, it.corridor, it.t_start, it.t_end)
            if o != it.op]

    if i_b is not None:
        for opp in opps:
            i_o = os_index_of(os_seq, opp)
            if i_o is None:
                continue
            gaps.append(i_b - i_o)
            # 反转先后:被堵工序插到阻塞者之前;以及阻塞者插到被堵工序之后
            nb = clone(chrom)
            os_move(nb["os"], i_b, i_o)                   # type: ignore
            out["precede"].append(nb)
            nb2 = clone(chrom)
            os_move(nb2["os"], i_o, i_b)                  # type: ignore
            out["precede"].append(nb2)
            break                                          # 与现行一致,只动一个对手

    # 随机相邻交换,个数与现行对齐,量出"随便扰动"本身值多少
    n = len(os_seq)
    for _ in range(len(cur)):
        nb = clone(chrom)
        seq: List[int] = nb["os"]                          # type: ignore
        for _try in range(20):
            k = rng.randrange(n - 1)
            if seq[k] != seq[k + 1]:
                seq[k], seq[k + 1] = seq[k + 1], seq[k]
                out["random"].append(nb)
                break
    return out, gaps


def run_cell(inst: Instance, net: Network, seeds: Sequence[int],
             gens: int) -> dict:
    cfg = GAConfig(pop=40, seed=seeds[0], theta=0.0, dispatch="rule",
                   use_conflict_ops=True)
    n_sit = 0
    hit = {v: 0 for v in VARIANTS}
    inert = {v: [0, 0] for v in VARIANTS}      # [makespan 未变数, 邻居总数]
    gaps: List[int] = []

    for seed in seeds:
        rng = random.Random(seed)
        pop = init_population(inst, cfg, rng)
        res = [decode(inst, net, ch["ma"], ch["os"],          # type: ignore
                      conflict_free=True, dispatch=cfg.dispatch) for ch in pop]

        for gen in range(gens):
            order = sorted(range(len(pop)), key=lambda x: res[x].makespan)
            elite, elite_res = pop[order[0]], res[order[0]]

            if gen >= gens - max(1, gens // 3):             # 只看收敛尾段
                nbs, g = build_neighbors(inst, elite, elite_res, cfg, rng)
                gaps += g
                if nbs["current"]:
                    n_sit += 1
                    for v in VARIANTS:
                        for nb in nbs[v]:
                            r2 = decode(inst, net, nb["ma"], nb["os"],  # type: ignore
                                        conflict_free=True,
                                        dispatch=cfg.dispatch)
                            inert[v][1] += 1
                            if abs(r2.makespan - elite_res.makespan) < 1e-9:
                                inert[v][0] += 1
                            if r2.makespan < elite_res.makespan - 1e-9:
                                hit[v] += 1
                                break

            new_pop: List[Chromosome] = [clone(pop[k]) for k in order[: cfg.elite]]
            while len(new_pop) < cfg.pop:
                a1 = pop[min(rng.sample(range(len(pop)), 2),
                             key=lambda x: res[x].makespan)]
                b1 = pop[min(rng.sample(range(len(pop)), 2),
                             key=lambda x: res[x].makespan)]
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

    return {"n": n_sit, "hit": hit, "inert": inert, "gaps": gaps}


def main() -> int:
    args = sys.argv[1:]
    gens = int(args[args.index("--gens") + 1]) if "--gens" in args else 20
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 13, 101])

    print(f"代数={gens} 种子={seeds};只看收敛尾段\n")
    print(f"{'配置':<20s} {'情形':>5s} "
          + "".join(f"{v:>10s}" for v in VARIANTS)
          + f" {'位置差中位':>10s} {'现行惰性':>9s}")
    print("-" * 78)

    tot = {v: 0 for v in VARIANTS}
    tot_n = 0
    all_gaps: List[int] = []
    all_inert = [0, 0]

    for c in CONFIGS:
        spec = make_spec(c["tag"], 0.3, 0.6, c["jobs"], c["nm"], c["na"], 3,
                         seed=42, tt_tp_target=3.0, grid_rows=4, grid_cols=4)
        inst = parse_instance(build_instance(spec))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        r = run_cell(inst, net, seeds, gens)

        n = max(r["n"], 1)
        tot_n += r["n"]
        for v in VARIANTS:
            tot[v] += r["hit"][v]
        all_gaps += r["gaps"]
        all_inert[0] += r["inert"]["current"][0]
        all_inert[1] += r["inert"]["current"][1]
        gs = sorted(r["gaps"])
        med = gs[len(gs) // 2] if gs else 0
        iz = r["inert"]["current"]
        print(f"{c['tag'] + ' M' + str(c['nm']):<20s} {r['n']:>5d} "
              + "".join(f"{r['hit'][v] / n:>10.1%}" for v in VARIANTS)
              + f" {med:>10d} {iz[0] / max(iz[1], 1):>9.1%}")

    print("-" * 78)
    n = max(tot_n, 1)
    print(f"{'合计':<20s} {tot_n:>5d} "
          + "".join(f"{tot[v] / n:>10.1%}" for v in VARIANTS))
    gs = sorted(all_gaps)
    if gs:
        print(f"\n被堵工序与阻塞者的 OS 位置差:样本 {len(gs)},"
              f"中位 {gs[len(gs) // 2]},最大 {gs[-1]},"
              f"为正(阻塞者更早)占 {sum(1 for x in gs if x > 0) / len(gs):.1%},"
              f"相邻(差 1)占 {sum(1 for x in gs if abs(x) == 1) / len(gs):.1%}")
    print(f"现行走法的邻居中 makespan 完全未变的占 "
          f"{all_inert[0] / max(all_inert[1], 1):.1%}")
    print()
    print("位置差为正说明阻塞者在 OS 中更早,必须跨过它才能缓解让行;")
    print("而现行走法一次只挪一格,故只有'相邻'那一小部分情形有可能奏效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
