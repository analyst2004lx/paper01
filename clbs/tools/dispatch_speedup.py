"""派车试探的降本改造:等价性验证 + 提速测量。

背景。同代数口径下派车试探比规则派车好约 3%(output/matrix/gen100:拥堵档 +3.39%、
漏斗档 +2.42%,其中一格 p=0.0246),但每次评价贵 4.6 倍(15.9 vs 3.5 毫秒),于是同挂钟
口径下这 3% 被算力吃光(output/matrix/p3:-0.12%,40 胜 39 负,p=0.53)。三个创新点里
只有它真有决策增益,故降本即增效。

两处改造(均在 decoder.dispatch_exact):
  剪枝  无冲突路由只会因让行而更晚,绝不会快过理想最短路,故理想估算是实际送达时刻的
        **可采纳下界**。下界都赢不了现任的车,实测值必然也赢不了,无需试探。原实现按车号
        升序保留首个严格更优者,被剪掉的车原本也当不上最优,故输出逐位相同。
  复用  胜者的两段路径在试探时已在同一预约表状态下算过,回滚后又被重算。缓存直接落表。

本工具做两件事:
  1. 等价性:与"关掉剪枝与复用"的参考实现逐算例逐染色体对比 makespan 与派车序列,
     必须完全一致——这是可证明等价的改造,任何一处不等都说明推理有漏洞。
  2. 提速:统计每次解码的路由调用数与耗时。

运行(clbs/ 目录下):  py -u -m tools.dispatch_speedup [--n 30]
"""
from __future__ import annotations

import os
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm import decoder as D
from algorithm.decoder import decode
from algorithm.ga import GAConfig, init_population
from algorithm.generator import build_instance, make_spec
from algorithm.instance import Instance, parse_instance
from algorithm.network import Network, RoutePlan, Router

CASES = [
    dict(name="中 high",      tag="high",    jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
    dict(name="中 funnel",    tag="funnel",  jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
    dict(name="高 funnel A8", tag="funnel",  jobs=8,  nm=4, na=8,  flex=0.6, tt=3.0),
    dict(name="高 high M8",   tag="high",    jobs=12, nm=8, na=12, flex=0.6, tt=3.0),
    dict(name="低 scatter",   tag="scatter", jobs=8,  nm=4, na=4,  flex=0.6, tt=3.0),
]

_calls = 0


def counting_route(orig):
    def wrapper(self, start, goal, t0, agv, task, commit=True):
        global _calls
        _calls += 1
        return orig(self, start, goal, t0, agv, task, commit)
    return wrapper


def dispatch_exact_naive(router: Router, net: Network,
                         loc: Dict[int, str], avail: Dict[int, float],
                         pickup: str, dest: str, ready: float
                         ) -> Tuple[int, Optional[Tuple[RoutePlan, RoutePlan]]]:
    """参考实现:无剪枝、不复用(即改造前的行为)。返回 plans=None 以强制重算。"""
    best_k, best_est = None, float("inf")
    for k in sorted(loc.keys()):
        token = router.table.checkpoint()
        try:
            empty = router.route(loc[k], pickup, avail[k], k, f"probe{k}-empty", commit=True)
            t_load = max(empty.arrive, ready)
            loaded = router.route(pickup, dest, t_load, k, f"probe{k}-loaded", commit=False)
            est = loaded.arrive
        finally:
            router.table.rollback(token)
        if est < best_est - 1e-12:
            best_k, best_est = k, est
    return best_k, None


def build(case: dict):
    extra = dict(grid_rows=4, grid_cols=4) if case["tag"] in ("low", "scatter") else {}
    spec = make_spec(case["tag"], 0.3, case["flex"], case["jobs"],
                     case["nm"], case["na"], 3, seed=42,
                     tt_tp_target=case["tt"], **extra)
    inst = parse_instance(build_instance(spec))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    return inst, net


def run(inst: Instance, net: Network, pop, use_fast: bool):
    """返回 (makespan 列表, 派车序列列表, 路由调用数, 耗时秒)。"""
    global _calls
    fast = D.dispatch_exact
    if not use_fast:
        D.dispatch_exact = dispatch_exact_naive          # type: ignore
    _calls = 0
    t0 = time.time()
    mks, orders = [], []
    try:
        for ch in pop:
            r = decode(inst, net, ch["ma"], ch["os"],
                       conflict_free=True, dispatch="exact")
            mks.append(r.makespan)
            orders.append(tuple(r.dispatch_order))
    finally:
        D.dispatch_exact = fast                          # type: ignore
    return mks, orders, _calls, time.time() - t0


def main() -> int:
    args = sys.argv[1:]
    n = int(args[args.index("--n") + 1]) if "--n" in args else 30

    orig_route = Router.route
    Router.route = counting_route(orig_route)            # type: ignore

    print(f"每算例 {n} 个随机染色体;派车=exact\n")
    print(f"{'算例':<14s} {'NA':>4s} {'等价':>6s} "
          f"{'路由调用 改造前':>15s} {'改造后':>10s} {'省':>7s} "
          f"{'秒 改造前':>10s} {'改造后':>9s} {'提速':>7s}")
    print("-" * 92)

    tot = [0, 0, 0.0, 0.0]
    all_ok = True
    for case in CASES:
        inst, net = build(case)
        rng = random.Random(42)
        pop = init_population(inst, GAConfig(pop=n, seed=42), rng)

        m0, o0, c0, s0 = run(inst, net, pop, use_fast=False)
        m1, o1, c1, s1 = run(inst, net, pop, use_fast=True)

        ok = (m0 == m1) and (o0 == o1)
        all_ok &= ok
        tot[0] += c0
        tot[1] += c1
        tot[2] += s0
        tot[3] += s1
        print(f"{case['name']:<14s} {case['na']:>4d} {'一致' if ok else '不一致!':>6s} "
              f"{c0:>15d} {c1:>10d} {1 - c1 / max(c0, 1):>6.1%} "
              f"{s0:>10.2f} {s1:>9.2f} {s0 / max(s1, 1e-9):>6.2f}x")
        if not ok:
            bad = [(a, b) for a, b in zip(m0, m1) if abs(a - b) > 1e-9]
            print(f"    makespan 不等 {len(bad)} 处,例:{bad[:3]}")

    print("-" * 92)
    print(f"{'合计':<14s} {'':>4s} {'':>6s} "
          f"{tot[0]:>15d} {tot[1]:>10d} {1 - tot[1] / max(tot[0], 1):>6.1%} "
          f"{tot[2]:>10.2f} {tot[3]:>9.2f} {tot[2] / max(tot[3], 1e-9):>6.2f}x")

    Router.route = orig_route                            # type: ignore
    print()
    if all_ok:
        print("等价性通过:全部算例上 makespan 与派车序列与改造前逐位相同。")
        print("这是可证明等价的改造——剪掉的车其下界已不优于现任,原实现也不会选中它。")
    else:
        print("!! 等价性失败:剪枝或复用的推理有漏洞,不可采用。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
