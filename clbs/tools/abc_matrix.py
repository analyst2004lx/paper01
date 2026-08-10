"""A/B/C 三参数正交扫描:闭环派车的增益出现在哪个参数区间?

为什么只扫派车。三个创新点里只有预约表探测式派车被证实有净增益(降本改造后,高争用算例
同挂钟 -4.01%,12 胜 2 负,p=0.0372,见 tools/dispatch_ab.py)。定价 + 多标签路由为受控
负结果(+0.47%,p=0.70,见 tools/price_matrix.py);冲突凭证制导的改派虽有真实机会
(收敛期神谕 17.4%),但便宜打分只能捕获随机到神谕之间约 26~29%,真解码全部候选在同挂钟
下反而更差 2.49%。故"参数区间"这个问题只对派车有意义。

扫描设计。每族只动一个因素,其余固定在同一基点(J12 / M8 / tt=4.0 / funnel / A12 / F0.6),
故族内差异可归因:
  A 布局    funnel < high < mid < low < scatter,出口与车道数递增、直至换成网格与错落网格
  B 车臂比  NA/NM = 0.5 / 1.0 / 1.5 / 2.0
  C 柔性    F = 0.3 / 0.6 / 1.0(部分柔性到全柔性)

规模取 J12/M8 而非主基准的 J8/M4:后者的争用强度只有 2~14%,拉不开区间,且 4 臂时每个
改派情形平均仅 1.2 台候选,方法本就无从发挥。

预算陷阱。前一轮 20 秒预算下高争用格的派车档只跑到 8~16 代,pop=60 的 GA 那时还没离开
随机初始化,失利纯属预算假象——放到 90 秒即反超。故本扫描用 90 秒,并**逐格报告代数**,
派车档不足 40 代者标记为预算饥饿,其数据不得用于支撑参数区间的结论。

运行(clbs/ 目录下):
  py -u -m tools.abc_matrix --probe                    # 先看各格争用强度,秒级
  py -u -m tools.abc_matrix [--budget 90] [--seeds a,b,c,d]
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.ga import GAConfig, run_ga
from algorithm.generator import build_instance, make_spec
from algorithm.instance import parse_instance
from algorithm.network import Network
from algorithm.stats import spearman, wilcoxon_signed_rank
from algorithm.validator import validate
from tools.price_matrix import instance_contention

BASE = dict(jobs=12, nm=8, na=12, flex=0.6, tt=4.0, tag="funnel")

# (族, 展示名, 覆盖项)。基点 funnel/A12/F0.6 在三族中共用,只跑一次。
CASES: List[dict] = [
    dict(fam="A 布局", name="A funnel",  tag="funnel"),
    dict(fam="A 布局", name="A high",    tag="high"),
    dict(fam="A 布局", name="A mid",     tag="mid"),
    dict(fam="A 布局", name="A low",     tag="low"),
    dict(fam="A 布局", name="A scatter", tag="scatter"),
    dict(fam="B 车臂比", name="B NA/NM 0.5", na=4),
    dict(fam="B 车臂比", name="B NA/NM 1.0", na=8),
    dict(fam="B 车臂比", name="B NA/NM 2.0", na=16),
    dict(fam="C 柔性", name="C F=0.3", flex=0.3),
    dict(fam="C 柔性", name="C F=1.0", flex=1.0),
]
ARMS = [("规则派车", "rule"), ("试探派车", "exact")]
MIN_GENS = 40          # 派车档低于此代数即视为预算饥饿,数据不可用


def build(case: dict):
    c = dict(BASE)
    c.update({k: v for k, v in case.items() if k not in ("fam", "name")})
    extra = dict(grid_rows=4, grid_cols=4) if c["tag"] in ("low", "scatter") else {}
    spec = make_spec(c["tag"], 0.3, c["flex"], c["jobs"], c["nm"], c["na"], 3,
                     seed=42, tt_tp_target=c["tt"], **extra)
    inst = parse_instance(build_instance(spec))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    return inst, net, c


def probe() -> int:
    print("各格的争用强度(初始随机种群 20 个的均值,派车 exact)\n")
    print(f"{'族':<8s} {'算例':<14s} {'布局':>8s} {'NA/NM':>7s} {'柔性':>6s} {'争用强度':>9s}")
    print("-" * 60)
    for case in CASES:
        inst, net, c = build(case)
        cs = instance_contention(inst, net, "exact")
        print(f"{case['fam']:<8s} {case['name']:<14s} {c['tag']:>8s} "
              f"{c['na'] / c['nm']:>7.2f} {c['flex']:>6.1f} {cs:>9.1%}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--probe" in args:
        return probe()
    budget = float(args[args.index("--budget") + 1]) if "--budget" in args else 90.0
    seeds = ([int(x) for x in args[args.index("--seeds") + 1].split(",")]
             if "--seeds" in args else [42, 7, 2024, 13])

    print(f"基点 J{BASE['jobs']} / M{BASE['nm']} / tt={BASE['tt']} / "
          f"{BASE['tag']} / A{BASE['na']} / F{BASE['flex']};每族只动一个因素")
    print(f"同挂钟预算 {budget:.0f}s/次,种子={seeds},theta=0,错峰算子开\n")

    mk: Dict[str, Dict[str, List[float]]] = {a: {} for a, _ in ARMS}
    gen: Dict[str, Dict[str, List[int]]] = {a: {} for a, _ in ARMS}
    cont: Dict[str, float] = {}
    t0 = time.time()

    for case in CASES:
        inst, net, _c = build(case)
        nm = case["name"]
        cont[nm] = instance_contention(inst, net, "exact")
        base = GAConfig(pop=60, max_gen=2000, stall_gen=400, use_conflict_ops=True,
                        theta=0.0, max_entry_options=3, time_budget_sec=budget)
        for label, disp in ARMS:
            mk[label][nm], gen[label][nm] = [], []
            for s in seeds:
                out = run_ga(inst, net, replace(base, seed=s, dispatch=disp),
                             conflict_free=True, use_ls=True)
                res = out["best_result"]
                errs = validate(inst, res.to_timetable())
                if errs:
                    print(f"  !! 校验失败 {nm} {label} seed={s}: {errs[:1]}")
                mk[label][nm].append(res.makespan)
                gen[label][nm].append(out["generations"])
        print(f"  已完成 {nm:<14s} 争用 {cont[nm]:.1%}  "
              f"代数 规则{sum(gen[ARMS[0][0]][nm]) / len(seeds):.0f}/"
              f"试探{sum(gen[ARMS[1][0]][nm]) / len(seeds):.0f}  "
              f"累计 {time.time() - t0:.0f}s")

    a_rule, a_exact = ARMS[0][0], ARMS[1][0]
    print(f"\n{'族':<8s} {'算例':<14s} {'争用':>7s} {'规则 C':>8s} {'试探 C':>8s} "
          f"{'代数 试探':>9s} {'Δ(负=试探更好)':>16s} {'可用':>5s}")
    print("-" * 82)
    usable: List[str] = []
    gains: Dict[str, float] = {}
    for case in CASES:
        nm = case["name"]
        r, e = mk[a_rule][nm], mk[a_exact][nm]
        rel = sum((x - y) / y for x, y in zip(e, r)) / len(r)
        gains[nm] = rel
        ge = sum(gen[a_exact][nm]) / len(seeds)
        ok = ge >= MIN_GENS
        if ok:
            usable.append(nm)
        print(f"{case['fam']:<8s} {nm:<14s} {cont[nm]:>7.1%} "
              f"{sum(r) / len(r):>8.2f} {sum(e) / len(e):>8.2f} {ge:>9.0f} "
              f"{rel:>15.2%}  {'是' if ok else '饥饿':>4s}")

    print("-" * 82)
    if len(usable) < len(CASES):
        print(f"\n注:{len(CASES) - len(usable)} 格派车档不足 {MIN_GENS} 代,属预算饥饿,"
              f"其 Δ 反映的是搜索没跑完而非机制无效,已排除在下列统计之外。")

    flat_r = [v for nm in usable for v in mk[a_rule][nm]]
    flat_e = [v for nm in usable for v in mk[a_exact][nm]]
    if flat_r:
        rel = sum((x - y) / y for x, y in zip(flat_e, flat_r)) / len(flat_r)
        win = sum(1 for x, y in zip(flat_e, flat_r) if x < y - 1e-9)
        loss = sum(1 for x, y in zip(flat_e, flat_r) if x > y + 1e-9)
        w = wilcoxon_signed_rank(flat_e, flat_r)
        print(f"\n配对检验(可用格 {len(usable)} 个 x {len(seeds)} 种子 = {len(flat_r)} 对):")
        print(f"  试探派车 vs 规则派车:平均 {rel:+.2%}"
              f"({'更好' if rel < 0 else '更差'})  {win} 胜 / {loss} 负 / "
              f"{len(flat_r) - win - loss} 平  n_eff={w['n_eff']}  p={w['p_value']:.4f}")

    print("\n分族看(负值越大越好;族内只有一个因素在动):")
    for fam in ("A 布局", "B 车臂比", "C 柔性"):
        rows = [c["name"] for c in CASES if c["fam"] == fam and c["name"] in usable]
        if not rows:
            print(f"  {fam}:全部预算饥饿,无结论")
            continue
        txt = "  ".join(f"{nm.split(' ', 1)[1]} {gains[nm]:+.2%}" for nm in rows)
        rho = spearman([cont[nm] for nm in rows], [gains[nm] for nm in rows])
        print(f"  {fam}:{txt}"
              + (f"   族内争用-收益秩相关 {rho:+.3f}" if rho is not None else ""))

    if len(usable) >= 4:
        rho = spearman([cont[nm] for nm in usable], [gains[nm] for nm in usable])
        print(f"\n全体可用格的争用强度 vs 收益秩相关:"
              f"{f'{rho:+.3f}' if rho is not None else 'n/a'}"
              f"(负相关 = 争用越强、闭环派车越值)")
        print(f"注:秩相关基于 {len(usable)} 个点,n 小于约 8 时该统计量取值稀疏、"
              f"不宜单独解读,须与逐格 Δ 的符号一致性合看。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
