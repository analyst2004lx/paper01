"""瓶颈归属诊断:makespan 到底被机械臂、AGV 还是走廊顶住?

动机:改派算子的神谕上界只有 3%(tools/probe_diag.py),即"换一个臂"几乎从不改进。
一个自然的怀疑是算例配比不当——若加工负载才是瓶颈,则各臂都已饱和,把工序从
一个臂挪到另一个臂只是把负载搬家,不可能缩短 makespan,反馈机制再精巧也无用武之地。

本脚本对每个算例报告四组量:

1. **下界构成**:job_chain / machine_load / lu_cut 哪一项紧,以及与实解的间隙。
   若 machine_load 紧,说明总加工量除以臂数已经逼近 makespan,瓶颈在加工侧;
2. **资源利用率**:各臂的加工占用 / makespan,各 AGV 的行驶与等待占用 / makespan。
   饱和的一侧就是瓶颈;
3. **关键链构成**:按五类归因统计各占 makespan 的比例。这是最直接的证据——
   若 corridor 类只占几个百分点,那么"走廊争用"在这些算例里根本不是主要矛盾;
4. **让行总量**:全部路径的让行等待 / makespan。

运行(clbs/ 目录下):
    py -m tools.bottleneck_diag                  # 分析 input/ext/ 的四个拥堵档
    py -m tools.bottleneck_diag --sweep          # 扫 臂数 x 车数 网格
    py -m tools.bottleneck_diag --sweep --jobs 12
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import (Instance, load_instance, parse_instance,
                                feature_params, simple_lower_bound)
from algorithm.network import Network
from algorithm.decoder import DecodeResult, critical_chain
from algorithm.ga import GAConfig, run_ga
from algorithm.generator import build_instance, make_spec

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "input", "ext")
KINDS = ("operation", "machine", "upstream", "vehicle", "corridor")


def analyze(inst: Instance, net: Network, result: DecodeResult) -> dict:
    cmax = result.makespan

    # ---- 资源占用 ----
    arm_busy: Dict[int, float] = {m: 0.0 for m in inst.machine_node}
    for rec in result.ops.values():
        if not rec.pseudo and rec.machine is not None:
            arm_busy[rec.machine] += rec.finish - rec.start
    arms = sorted(v / cmax for v in arm_busy.values())

    agv = result.agv_stats()
    travel = [(s["loaded_time"] + s["empty_time"]) / cmax for s in agv.values()]
    waits = [s["wait_time"] / cmax for s in agv.values()]
    # 未被派到任务的车不出现在 agv_stats 里,补 0 以免高估车队利用率
    while len(travel) < inst.num_agvs:
        travel.append(0.0)
        waits.append(0.0)
    travel.sort()
    waits.sort()

    # ---- 关键链构成 ----
    chain = critical_chain(result)
    by_kind = {k: 0.0 for k in KINDS}
    for it in chain:
        if it.kind in by_kind:
            by_kind[it.kind] += it.amount

    # ---- 让行总量 ----
    yield_total = sum(tr.empty_plan.total_wait + tr.loaded_plan.total_wait
                      for tr in result.transports)

    lb = simple_lower_bound(inst, net)
    parts = {k: lb[k] for k in ("job_chain", "machine_load", "lu_cut") if k in lb}
    binding = max(parts, key=lambda k: parts[k]) if parts else "n/a"

    return {
        "cmax": cmax,
        "lb": lb.get("lower_bound", 0.0),
        "lb_parts": parts,
        "binding": binding,
        "gap": (cmax / lb["lower_bound"] - 1.0) if lb.get("lower_bound") else None,
        "arm_min": arms[0], "arm_mean": sum(arms) / len(arms), "arm_max": arms[-1],
        "agv_travel_mean": sum(travel) / len(travel), "agv_travel_max": travel[-1],
        "agv_wait_mean": sum(waits) / len(waits),
        "chain": {k: by_kind[k] / cmax for k in KINDS},
        "chain_sum": sum(by_kind.values()) / cmax,
        "yield_share": yield_total / cmax,
        "n_transports": len(result.transports),
    }


def solve(inst: Instance, net: Network, seed: int, budget_gen: int = 100) -> DecodeResult:
    """用论文的提出方法(规则派车、无局部搜索、闭环评价)求一个像样的解。"""
    cfg = GAConfig(pop=50, max_gen=budget_gen, stall_gen=30, seed=seed,
                   theta=0.0, dispatch="rule")
    out = run_ga(inst, net, cfg, conflict_free=True, use_ls=False)
    return out["best_result"]


def run_one(name: str, inst: Instance, seeds: Sequence[int]) -> dict:
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    rows = [analyze(inst, net, solve(inst, net, s)) for s in seeds]

    def avg(key: str) -> float:
        return sum(r[key] for r in rows) / len(rows)

    out = {k: avg(k) for k in ("cmax", "lb", "gap", "arm_min", "arm_mean", "arm_max",
                               "agv_travel_mean", "agv_travel_max", "agv_wait_mean",
                               "yield_share", "chain_sum", "n_transports")}
    out["chain"] = {k: sum(r["chain"][k] for r in rows) / len(rows) for k in KINDS}
    out["binding"] = rows[0]["binding"]
    out["lb_parts"] = rows[0]["lb_parts"]
    out["name"] = name
    return out


def print_header() -> None:
    print(f"{'算例':<26s} {'C_max':>6s} {'下界':>6s} {'间隙':>6s} {'紧项':>12s} "
          f"{'臂均':>5s} {'臂max':>6s} {'车行':>5s} {'车等':>5s} {'让行':>5s}")
    print("-" * 100)


def print_row(r: dict) -> None:
    print(f"{r['name']:<26s} {r['cmax']:>6.1f} {r['lb']:>6.1f} {r['gap']:>5.0%} "
          f"{r['binding']:>12s} {r['arm_mean']:>5.0%} {r['arm_max']:>6.0%} "
          f"{r['agv_travel_mean']:>5.0%} {r['agv_wait_mean']:>5.0%} {r['yield_share']:>5.0%}")


def print_chains(rows: List[dict]) -> None:
    print()
    print(f"{'算例':<26s} " + " ".join(f"{k:>9s}" for k in KINDS) + f" {'合计':>7s}")
    print("-" * 100)
    for r in rows:
        cells = " ".join(f"{r['chain'][k]:>8.1%}" for k in KINDS)
        print(f"{r['name']:<26s}  {cells} {r['chain_sum']:>7.0%}")
    print("-" * 100)
    print("关键链各类占 C_max 的比例。corridor 是唯一由车辆争用造成的一类;")
    print("若它只占个位数,则本算例族的主要矛盾不在走廊,反馈机制无信号可用。")


def default_paths() -> List[str]:
    names = [("low", "S8x4x4-LG21-H0.3-F0.6-A4-s42.json"),
             ("mid", "S8x4x4-LD22-H0.3-F0.6-A4-s42.json"),
             ("high", "S8x4x4-LD21-H0.3-F0.6-A4-s42.json"),
             ("funnel", "S8x4x4-LD11-H0.3-F0.6-A4-s42.json")]
    return [(t, os.path.join(EXT, n)) for t, n in names
            if os.path.exists(os.path.join(EXT, n))]


def sweep(jobs: int, ops: int, tag: str, het: float, flex: float,
          machines: Sequence[int], agvs: Sequence[int],
          seeds: Sequence[int]) -> List[dict]:
    rows: List[dict] = []
    for nm in machines:
        if flex * nm < 2.0:            # 假设 A3 要求多数工序 |Ω|>=2
            print(f"  (跳过 M{nm}:F={flex} 下 |Ω|={flex*nm:.1f} < 2,与 A3 冲突)")
            continue
        for na in agvs:
            spec = make_spec(tag, het, flex, jobs, nm, na, ops, seed=42)
            data = build_instance(spec)
            inst = parse_instance(data)
            label = f"{tag} J{jobs} M{nm} A{na}"
            r = run_one(label, inst, seeds)
            f = data["_features"]
            r["flex_actual"] = f["flexibility"]
            r["tt_tp"] = f["Tt_over_Tp"]
            rows.append(r)
            print_row(r)
    return rows


def main() -> int:
    args = sys.argv[1:]
    do_sweep = "--sweep" in args
    jobs, ops, tag = 8, 3, "high"
    seeds = [42, 7]
    if "--jobs" in args:
        jobs = int(args[args.index("--jobs") + 1])
    if "--tag" in args:
        tag = args[args.index("--tag") + 1]

    flex = float(args[args.index("--flex") + 1]) if "--flex" in args else 0.6
    if do_sweep:
        machines, agvs = [4, 6, 8], [2, 4, 6, 8]
        print(f"扫描:{tag} 档,工件 {jobs} x 工序 {ops} = {jobs*ops} 道,"
              f"H=0.3 F={flex},种子 {seeds}\n")
        print_header()
        rows = sweep(jobs, ops, tag, 0.3, flex, machines, agvs, seeds)
    else:
        paths = default_paths()
        if not paths:
            print("找不到算例;先运行 tools/gen_instances.py")
            return 1
        print(f"当前算例族(8 工件 x 3 工序 = 24 道,4 臂 4 车),种子 {seeds}\n")
        print_header()
        rows = []
        for label, path in paths:
            inst = load_instance(path)
            r = run_one(f"{label:<8s}{os.path.basename(path)[:16]}", inst, seeds)
            rows.append(r)
            print_row(r)

    print_chains(rows)
    print()
    print("臂均/臂max = 各臂加工占用 / C_max;车行 = AGV 行驶占用;车等 = AGV 让行占用")
    print("让行 = 全部路径的让行等待总和 / C_max(可超过 100%,因为是全车队累加)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
