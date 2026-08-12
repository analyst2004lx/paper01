"""降本对照:量"可采纳下界剪枝 + 胜者路径复用"在同挂钟预算下值多少。

为什么需要这个实验。矩阵批次(output/matrix/p3、lowmid,08-03/08-05 跑的,当时代码里
还没有剪枝与复用)测得预约表试探派车在同挂钟下为 -0.74%、16 格中 0 格显著,即"不划算";
基线阶梯(降本之后跑的)测得同一机制在闭环内值 -5.8% 且显著。两者相差三项:降本、基线口径
(两阶段 vs B0)、算例集。只凭这两个批次并列,无法把符号翻转归因于降本——那是三个变量同时
动了。本工具把另外两项固定住,只动降本这一项。

方法上这个对照特别干净,原因是两项优化**不改变输出**:
  - 剪枝:理想最短路是实测送达时刻的可采纳下界,故下界已不优于现任的车,实测值必然也不优;
    原实现按车号升序保留首个严格更优者,被剪掉的车本来也不会当选。
  - 复用:胜者的两段路径是在回滚后同一张表状态下算出的,直接落表与重算后落表逐位相同。
所以关掉它们唯一的作用就是**变慢**,同挂钟下的 makespan 差值就是"省下的算力买到了多少解
质量",不掺任何其他机制。开跑前先做一次逐位等价性自检,把上面这段论证兑现成可观测的事实。

两档:
  开   dispatch="exact"        剪枝与复用都开(论文的默认实现)
  关   dispatch="exact_noopt"  两项都关,退回未优化的全量试探

同种子 → 同初始种群、同算子序列,故两档唯一的差别是每秒能做多少次评价。

默认算例集只取 6 个而非全部 10 个:争用(A funnel/high/low)与车队规模(B 三档)是决定
试探开销的两个因素,剪枝的效力恰随二者变化,取这 6 格既够又省一半机时。

运行(clbs/ 目录下):
  py -u -m tools.prune_ablation [--budget 90] [--seeds a,b,c] [--only 名字,名字] [--check-only]
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.decoder import decode
from algorithm.ga import GAConfig, random_ma, random_os, run_ga
from algorithm.network import Router
from algorithm.stats import wilcoxon_signed_rank
from algorithm.validator import validate
from tools.abc_matrix import CASES, build
from tools.price_matrix import instance_contention

DEFAULT_CASES = ["A funnel", "A high", "A low",
                 "B NA/NM 0.5", "B NA/NM 1.0", "B NA/NM 2.0"]
ARMS = [("开", "exact"), ("关", "exact_noopt")]


def equivalence_check(cases: List[dict], n_chrom: int = 6) -> bool:
    """逐位等价性自检:同一染色体在两档下必须得到同一张时间表。

    这是论文命题(降本不改变输出)的实证。同时报告两档的路由调用数,给出降本的直接口径。
    """
    import random

    print("等价性自检:同一染色体,两档必须给出逐位相同的结果")
    print(f"{'算例':<14s} {'染色体':>6s} {'makespan':>18s} {'派车序列':>10s} "
          f"{'路由调用(开/关)':>20s} {'减少':>7s}")
    print("-" * 88)
    ok = True
    for case in cases:
        inst, net, _c = build(case)
        rng = random.Random(20260808)
        calls = {"exact": 0, "exact_noopt": 0}
        same_mk = same_disp = 0
        for _ in range(n_chrom):
            ma, os_seq = random_ma(inst, rng), random_os(inst, rng)
            res = {}
            for _label, disp in ARMS:
                Router.total_route_calls = 0
                res[disp] = decode(inst, net, ma, os_seq,
                                   conflict_free=True, dispatch=disp)
                calls[disp] += Router.total_route_calls
            a, b = res["exact"], res["exact_noopt"]
            if abs(a.makespan - b.makespan) < 1e-9:
                same_mk += 1
            else:
                ok = False
            if list(a.dispatch_order) == list(b.dispatch_order):
                same_disp += 1
            else:
                ok = False
        cut = 1.0 - calls["exact"] / max(calls["exact_noopt"], 1)
        print(f"{case['name']:<14s} {n_chrom:>6d} {same_mk:>10d}/{n_chrom} 一致 "
              f"{same_disp:>6d}/{n_chrom} "
              f"{calls['exact']:>10d}/{calls['exact_noopt']:<9d} {cut:>6.1%}")
    print("-" * 88)
    print("  结论:" + ("两档输出逐位相同,命题成立;差别仅在路由调用数。" if ok
                       else "!! 存在不一致,降本改变了输出,必须先修好再谈同挂钟比较。"))
    return ok


def main() -> int:
    args = sys.argv[1:]
    budget = float(args[args.index("--budget") + 1]) if "--budget" in args else 90.0
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args
             else [42, 7, 2024, 13, 1, 99, 123, 777, 31415, 8])
    want = set(args[args.index("--only") + 1].split(",")) if "--only" in args \
        else set(DEFAULT_CASES)
    cases = [c for c in CASES if c["name"] in want]
    if not cases:
        print("没有匹配的算例,可选:" + ", ".join(c["name"] for c in CASES))
        return 2

    if not equivalence_check(cases):
        return 1
    if "--check-only" in args:
        return 0

    print(f"\n降本对照:B2(闭环+试探派车)在剪枝与复用「开 / 关」两档下同挂钟 {budget:.0f}s")
    print(f"算例 {len(cases)} 个 x 种子 {len(seeds)} 个;两档同种子同初始种群,唯一差别是速度\n")

    mk: Dict[str, Dict[str, List[float]]] = {a: {} for a, _ in ARMS}
    ev: Dict[str, Dict[str, List[int]]] = {a: {} for a, _ in ARMS}
    ms: Dict[str, Dict[str, List[float]]] = {a: {} for a, _ in ARMS}
    cont: Dict[str, float] = {}
    t0 = time.time()

    for case in cases:
        inst, net, _c = build(case)
        nm = case["name"]
        cont[nm] = instance_contention(inst, net, "exact")
        base = GAConfig(pop=60, max_gen=2000, stall_gen=400, use_conflict_ops=True,
                        theta=0.0, max_entry_options=3, time_budget_sec=budget)
        for a, _ in ARMS:
            mk[a][nm], ev[a][nm], ms[a][nm] = [], [], []

        for s in seeds:
            for label, disp in ARMS:
                out = run_ga(inst, net, replace(base, seed=s, dispatch=disp),
                             conflict_free=True, use_ls=True)
                mk[label][nm].append(out["best_result"].makespan)
                ev[label][nm].append(out["decodes"])
                ms[label][nm].append(1000.0 * out["runtime_sec"]
                                     / max(out["decodes"], 1))
                errs = validate(inst, out["best_result"].to_timetable())
                if errs:
                    print(f"  !! 校验失败 {nm} {label} seed={s}: {errs[:1]}")

        n = len(seeds)
        print(f"  已完成 {nm:<14s} 争用 {cont[nm]:>6.1%}  "
              f"makespan 开 {sum(mk['开'][nm]) / n:>6.2f} / 关 {sum(mk['关'][nm]) / n:>6.2f}  "
              f"评价数 开 {sum(ev['开'][nm]) / n:>7.0f} / 关 {sum(ev['关'][nm]) / n:>7.0f}  "
              f"累计 {time.time() - t0:.0f}s")

    n = len(seeds)
    print(f"\n{'算例':<14s} {'争用':>7s} {'开':>8s} {'关':>8s} {'降本增益':>9s} "
          f"{'评价数比':>9s} {'ms/评价 开':>11s} {'关':>8s} {'加速比':>7s}")
    print("-" * 100)
    for case in cases:
        nm = case["name"]
        a = sum(mk["开"][nm]) / n
        b = sum(mk["关"][nm]) / n
        ea = sum(ev["开"][nm]) / n
        eb = sum(ev["关"][nm]) / n
        ma = sum(ms["开"][nm]) / n
        mb = sum(ms["关"][nm]) / n
        print(f"{nm:<14s} {cont[nm]:>7.1%} {a:>8.2f} {b:>8.2f} {(a - b) / b:>8.2%} "
              f"{ea / max(eb, 1):>8.2f}x {ma:>11.2f} {mb:>8.2f} {mb / max(ma, 1e-9):>6.2f}x")
    print("-" * 100)

    xa = [v for c in cases for v in mk["关"][c["name"]]]     # 基准档 = 关
    xb = [v for c in cases for v in mk["开"][c["name"]]]     # 处理档 = 开
    rel = sum((x - y) / y for x, y in zip(xb, xa)) / len(xa)
    w = wilcoxon_signed_rank(xb, xa)
    win = sum(1 for x, y in zip(xb, xa) if x < y - 1e-9)
    lose = sum(1 for x, y in zip(xb, xa) if x > y + 1e-9)
    ea = sum(v for c in cases for v in ev["开"][c["name"]])
    eb = sum(v for c in cases for v in ev["关"][c["name"]])
    ma = sum(v for c in cases for v in ms["开"][c["name"]]) / len(xa)
    mb = sum(v for c in cases for v in ms["关"][c["name"]]) / len(xa)

    print(f"\n配对合计({len(cases)} 算例 x {len(seeds)} 种子 = {len(xa)} 配对):")
    print(f"  降本的价值(关 → 开)  {rel:>+8.2%}  {win} 胜 / {lose} 负  "
          f"n_eff={w['n_eff']}  p={w['p_value']:.4f}")
    print(f"  同预算内评价次数       {eb} → {ea}  ({ea / max(eb, 1):.2f}x)")
    print(f"  单次评价耗时           {mb:.2f} → {ma:.2f} ms  (加速 {mb / max(ma, 1e-9):.2f}x)")
    print("\n口径提醒:两档输出逐位相同(已过自检),故上面这个增益**只**来自省下的算力,")
    print("  不含任何机制变化。这正是把矩阵批次的负结果与阶梯批次的正结果连起来的那一环。")

    out_csv = os.path.join(os.path.dirname(__file__), "..", "output",
                           "prune_ablation.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", encoding="utf-8") as f:
        f.write("case,contention,arm,seed,makespan,decodes,ms_per_eval\n")
        for case in cases:
            nm = case["name"]
            for label, _ in ARMS:
                for s, v, e, m in zip(seeds, mk[label][nm], ev[label][nm],
                                      ms[label][nm]):
                    f.write(f"{nm},{cont[nm]:.4f},{label},{s},{v:.4f},{e},{m:.4f}\n")
    print(f"\n逐种子原始数据已写入 {os.path.normpath(out_csv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
