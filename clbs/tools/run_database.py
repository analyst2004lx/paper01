"""公开数据集分支的批跑器:退化对标档 + 自动算 gap(规格 12.2)。

用法(在 clbs/ 目录下):

    py -m tools.run_database --smoke                 # 3 种子,先看流程与耗时
    py -m tools.run_database --seeds 10              # 正式跑
    py -m tools.run_database --only sfjs             # 只跑名字含该串的算例
    py -m tools.run_database --report-only           # 用已有账本重出报告

产物:
    output_database/<算例>/summary.json              # 逐算例逐种子明细
    output_database/records.jsonl                    # 可续跑账本(每完成一格追加一行)
    experiments_database/instances.csv               # 算例特征
    experiments_database/runs.csv                    # 逐 (算例, 种子) 记录
    experiments_database/gap_ideal.csv               # 与文献参考值的 gap
    experiments_database/fidelity.csv                # 布局能否还原为走廊图
    experiments_database/meta.json                   # 提交号 / 时间 / 配置

三条硬性判定(报告顶部单列,任一触发都必须先查错再看结论):

1. **低于可证最优**:本方法的解若小于 MILP 已证明的最优值,那不是赢,是口径不一致
   或实现有错。退化档与文献是同一个数学问题,可证最优值是硬地板。
2. **低于零成本复合下界**:同理,违反自算下界即解码器或下界本身有错。
3. **校验失败**:每个解都过 `validator.validate`。注意退化档没有 AGV 分段,故校验项
   (d)(e)(f)(h) 天然为空——这一档的校验强度**低于**争用档,不能用"校验通过"充当
   转换正确的证据;真正的证据是第 1 条(与独立求得的最优值比对)。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import statistics
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.baseline import solve_arm
from algorithm.ga import GAConfig
from algorithm.instance import feature_params, load_instance, simple_lower_bound
from algorithm.network import Network
from algorithm.validator import validate

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "database")
OUT = os.path.join(HERE, "output_database")
EXP = os.path.join(HERE, "experiments_database")

ARM = "ideal"
DEFAULT_TAG = "p100g200s30"      # 规格 7 的默认参数,汇总写在 experiments_database/ 根下


# --------------------------------------------------------------------------
# 参考值
# --------------------------------------------------------------------------

def load_refvalues(key: str) -> Dict[str, List[dict]]:
    path = os.path.join(DB, "refvalues", key + ".csv")
    by_inst: Dict[str, List[dict]] = {}
    if not os.path.exists(path):
        return by_inst
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row["value"] = float(row["value"])
            by_inst.setdefault(row["instance"], []).append(row)
    return by_inst


def pick_reference(rows: List[dict]) -> Optional[dict]:
    """挑一个用于算 gap 的参照,并保留其强度等级。

    优先取 `proven_optimal`(可证最优,是硬地板,gap 有绝对含义);其次取全部行的
    最小值作为 `best_known`(只是当前最好的已知上界,gap 为负不代表求得最优)。
    两者绝不合并成一列——见 database/refvalues/README.md。
    """
    proven = [r for r in rows if r["kind"] == "proven_optimal"]
    if proven:
        best = min(proven, key=lambda r: r["value"])
        return {"kind": "proven_optimal", "value": best["value"],
                "method": best["method"], "citekey": best["citekey"]}
    if not rows:
        return None
    best = min(rows, key=lambda r: r["value"])
    return {"kind": "best_known", "value": best["value"],
            "method": best["method"], "citekey": best["citekey"]}


# --------------------------------------------------------------------------
# 账本
# --------------------------------------------------------------------------

def budget_tag(args: argparse.Namespace) -> str:
    """算力预算的指纹。不同预算的记录**必须分账本**。

    账本键只有 (算例, 种子),不含预算;若同一文件里混进两种预算的记录,续跑会
    静默跳过、报告会把两种算力的数字并进同一列均值,而这种错误在结果里看不出来。
    故预算进文件名,并在载入时逐行核对。
    """
    return "p%dg%ds%d" % (args.pop, args.gen, args.stall)


def ledger_path(args: argparse.Namespace) -> str:
    return os.path.join(OUT, "records_%s.jsonl" % budget_tag(args))


def exp_dir(args: argparse.Namespace) -> str:
    """默认预算的汇总写在 experiments_database/ 根下;其他预算各占一个子目录。"""
    return EXP if budget_tag(args) == DEFAULT_TAG else os.path.join(EXP, budget_tag(args))


def load_ledger(args: argparse.Namespace) -> Dict[Tuple[str, int], dict]:
    done: Dict[Tuple[str, int], dict] = {}
    p = ledger_path(args)
    if not os.path.exists(p):
        return done
    tag = budget_tag(args)
    with open(p, "r", encoding="utf-8-sig") as f:      # 容忍 BOM
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("budget") != tag:
                raise ValueError(
                    "%s 第 %d 行的预算为 %r,与本次 %r 不符;账本已被混用,"
                    "请删除该文件重跑" % (p, n, rec.get("budget"), tag))
            done[(rec["instance"], rec["seed"])] = rec
    return done


def append_ledger(rec: dict, args: argparse.Namespace) -> None:
    os.makedirs(OUT, exist_ok=True)
    with open(ledger_path(args), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------------------------------
# 跑一格
# --------------------------------------------------------------------------

def run_cell(path: str, seed: int, args: argparse.Namespace) -> dict:
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node, ideal_dist=inst.ideal_dist)
    net.check_reachability()
    cfg = GAConfig(pop=args.pop, max_gen=args.gen, stall_gen=args.stall, seed=seed)

    t0 = time.time()
    out = solve_arm(ARM, inst, net, cfg)
    elapsed = time.time() - t0

    timetable = out["best_result"].to_timetable()
    errors = validate(inst, timetable)
    lb = simple_lower_bound(inst, net)

    return {
        "instance": inst.name,
        "seed": seed,
        "arm": ARM,
        "budget": budget_tag(args),
        "pop": args.pop, "max_gen": args.gen, "stall_gen": args.stall,
        "makespan": out["makespan"],
        "runtime_sec": round(elapsed, 3),
        "generations": out.get("generations"),
        "evaluations": out.get("evaluations"),
        "stopped_by": out.get("stopped_by"),
        "valid": not errors,
        "validation_errors": errors,
        "lower_bound": lb["lower_bound"],
        "lb_parts": lb,
        "timetable": timetable,
    }


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------

def write_csv(path: str, fieldnames: List[str], rows: List[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=HERE, stderr=subprocess.DEVNULL
                                       ).decode().strip()
    except Exception:
        return "unknown"


def build_report(paths: List[str], ledger: Dict[Tuple[str, int], dict],
                 refs: Dict[str, List[dict]], args: argparse.Namespace) -> dict:
    inst_rows, run_rows, gap_rows = [], [], []
    flags: List[str] = []

    for path in paths:
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node, ideal_dist=inst.ideal_dist)
        feats = feature_params(inst, net.ideal_dist, net)
        lb = simple_lower_bound(inst, net)
        base = inst.name.rsplit("-", 1)[0]
        spec = {}
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f).get("_spec", {})

        inst_rows.append({
            "instance": inst.name, "base": base,
            "dataset": spec.get("dataset", ""), "layout": spec.get("layout", ""),
            "num_jobs": feats["num_jobs"], "num_machines": feats["num_machines"],
            "num_ops": feats["num_real_ops"], "num_agvs": feats["num_agvs"],
            "delta_return": inst.delta_return,
            "Tt_over_Tp": feats["Tt_over_Tp"],
            "heterogeneity": feats["heterogeneity"],
            "flexibility": feats["flexibility"],
            "lower_bound": lb["lower_bound"],
            "lb_job_chain": lb["job_chain"], "lb_machine_load": lb["machine_load"],
        })

        cells = [r for (nm, _s), r in ledger.items() if nm == inst.name]
        if not cells:
            continue
        for r in sorted(cells, key=lambda x: x["seed"]):
            run_rows.append(r)

        vals = [r["makespan"] for r in cells]
        best, mean = min(vals), statistics.mean(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        ref = pick_reference(refs.get(base, []))

        row = {
            "instance": inst.name, "base": base, "layout": spec.get("layout", ""),
            "seeds": len(vals),
            "best": best, "mean": round(mean, 2), "std": round(std, 2),
            "worst": max(vals),
            "lower_bound": lb["lower_bound"],
            "mean_runtime_sec": round(statistics.mean(
                [r["runtime_sec"] for r in cells]), 2),
            "all_valid": all(r["valid"] for r in cells),
        }
        if ref is not None:
            row.update({
                "ref_kind": ref["kind"], "ref_value": ref["value"],
                "ref_method": ref["method"], "ref_citekey": ref["citekey"],
                "gap_best_pct": round((best - ref["value"]) / ref["value"] * 100, 2),
                "gap_mean_pct": round((mean - ref["value"]) / ref["value"] * 100, 2),
                "matches_ref": abs(best - ref["value"]) < 1e-6,
            })
            if ref["kind"] == "proven_optimal" and best < ref["value"] - 1e-6:
                flags.append(f"[低于可证最优] {inst.name}: 本方法 {best} < 最优 "
                             f"{ref['value']}({ref['method']}, {ref['citekey']})")
        if best < lb["lower_bound"] - 1e-6:
            flags.append(f"[低于自算下界] {inst.name}: {best} < {lb['lower_bound']}")
        for r in cells:
            if not r["valid"]:
                flags.append(f"[校验失败] {inst.name} seed={r['seed']}: "
                             f"{r['validation_errors'][:2]}")
        gap_rows.append(row)

    ed = exp_dir(args)
    write_csv(os.path.join(ed, "instances.csv"),
              ["instance", "base", "dataset", "layout", "num_jobs", "num_machines",
               "num_ops", "num_agvs", "delta_return", "Tt_over_Tp", "heterogeneity",
               "flexibility", "lower_bound", "lb_job_chain", "lb_machine_load"],
              inst_rows)
    write_csv(os.path.join(ed, "runs.csv"),
              ["instance", "seed", "arm", "budget", "pop", "max_gen", "stall_gen",
               "makespan", "runtime_sec", "generations", "evaluations", "stopped_by",
               "valid", "lower_bound"],
              run_rows)
    write_csv(os.path.join(ed, "gap_ideal.csv"),
              ["instance", "base", "layout", "ref_kind", "ref_value", "ref_method",
               "ref_citekey", "seeds", "best", "mean", "std", "worst",
               "gap_best_pct", "gap_mean_pct", "matches_ref", "lower_bound",
               "mean_runtime_sec", "all_valid"],
              gap_rows)

    fid_src = os.path.join(DB, "json", args.dataset, "_fidelity.json")
    if os.path.exists(fid_src):
        with open(fid_src, "r", encoding="utf-8") as f:
            fid = json.load(f)["layouts"]
        write_csv(os.path.join(ed, "fidelity.csv"),
                  ["layout", "size", "symmetric", "closure_violations",
                   "max_excess", "digraph_reconstructible",
                   "corridor_reconstructible"], fid)

    meta = {
        "git_commit": git_commit(),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": args.dataset,
        "arm": ARM,
        "regime": "ideal (conflict_free=False, delta_return=0, 行驶时间取给定矩阵)",
        "budget": budget_tag(args),
        "ga_config": {"pop": args.pop, "max_gen": args.gen, "stall_gen": args.stall},
        "seeds": sorted({s for (_n, s) in ledger}),
        "num_instances": len(gap_rows),
        "ledger": os.path.relpath(ledger_path(args), HERE),
        "flags": flags,
    }
    with open(os.path.join(ed, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"gap_rows": gap_rows, "flags": flags, "meta": meta, "exp_dir": ed}


def compare_budgets(paths: List[str], refs: Dict[str, List[dict]],
                    args: argparse.Namespace, other: str) -> None:
    """把两种算力预算下的结果并排,回答"gap 是搜索上限还是预算不足"。

    这个对比必须做,否则"我们比文献差 x%"这句话没有意义:文献的 MILP 在
    MFJST06 上花了 34796 秒,我们花了 2 秒,两个数字直接相减读者无法解释。
    只有当加大预算**不再显著改善**时,才能说这个 x% 是方法本身的能力边界。
    """
    a_tag = budget_tag(args)
    a = load_ledger(args)
    b_path = os.path.join(OUT, "records_%s.jsonl" % other)
    if not os.path.exists(b_path):
        print(f"找不到对照账本 {b_path}")
        return
    b: Dict[Tuple[str, int], dict] = {}
    with open(b_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                b[(rec["instance"], rec["seed"])] = rec

    rows = []
    for path in paths:
        name = os.path.basename(path)[:-5]
        va = [r["makespan"] for (nm, _s), r in a.items() if nm == name]
        vb = [r["makespan"] for (nm, _s), r in b.items() if nm == name]
        if not va or not vb:
            continue
        ref = pick_reference(refs.get(name.rsplit("-", 1)[0], []))
        ta = statistics.mean([r["runtime_sec"] for (nm, _s), r in a.items() if nm == name])
        tb = statistics.mean([r["runtime_sec"] for (nm, _s), r in b.items() if nm == name])
        row = {
            "instance": name, "seeds_a": len(va), "seeds_b": len(vb),
            "budget_a": a_tag, "budget_b": other,
            "best_a": min(va), "best_b": min(vb),
            "mean_a": round(statistics.mean(va), 1),
            "mean_b": round(statistics.mean(vb), 1),
            "std_a": round(statistics.pstdev(va) if len(va) > 1 else 0.0, 1),
            "std_b": round(statistics.pstdev(vb) if len(vb) > 1 else 0.0, 1),
            "sec_a": round(ta, 1), "sec_b": round(tb, 1),
            "time_ratio": round(ta / tb, 1) if tb > 0 else None,
        }
        if ref:
            row["ref_value"] = ref["value"]
            row["ref_kind"] = ref["kind"]
            row["gap_a_pct"] = round((min(va) - ref["value"]) / ref["value"] * 100, 2)
            row["gap_b_pct"] = round((min(vb) - ref["value"]) / ref["value"] * 100, 2)
            row["gap_closed_pp"] = round(row["gap_b_pct"] - row["gap_a_pct"], 2)
        rows.append(row)

    out = os.path.join(exp_dir(args), "budget_effect.csv")
    write_csv(out, ["instance", "ref_kind", "ref_value", "budget_b", "best_b", "mean_b",
                    "std_b", "sec_b", "gap_b_pct", "budget_a", "best_a", "mean_a",
                    "std_a", "sec_a", "gap_a_pct", "gap_closed_pp", "time_ratio",
                    "seeds_a", "seeds_b"], rows)

    print(f"\n== 算力预算的影响({other} -> {a_tag})==")
    print(f"{'算例':<14}{'参照':>7}{'低预算':>8}{'高预算':>8}{'gap低':>8}{'gap高':>8}"
          f"{'降低pp':>8}{'耗时比':>8}")
    for r in sorted(rows, key=lambda x: x["instance"]):
        print(f"{r['instance']:<14}{r.get('ref_value',0):>7.0f}"
              f"{r['best_b']:>8.0f}{r['best_a']:>8.0f}"
              f"{r.get('gap_b_pct',0):>8.2f}{r.get('gap_a_pct',0):>8.2f}"
              f"{r.get('gap_closed_pp',0):>8.2f}{r.get('time_ratio') or 0:>8.1f}x")
    withref = [r for r in rows if "gap_a_pct" in r]
    if withref:
        print(f"\n  平均 gap: {statistics.mean([r['gap_b_pct'] for r in withref]):+.2f}% "
              f"-> {statistics.mean([r['gap_a_pct'] for r in withref]):+.2f}% "
              f"(耗时增至 {statistics.mean([r['time_ratio'] for r in withref if r['time_ratio']]):.1f} 倍)")
    print(f"  已写入 {os.path.relpath(out, HERE)}")


def print_report(rep: dict) -> None:
    rows = rep["gap_rows"]
    print("\n" + "=" * 78)
    if rep["flags"]:
        print("!! 硬性判定触发,先查错再看结论:")
        for fl in rep["flags"]:
            print("   " + fl)
    else:
        print("硬性判定全部通过:无低于可证最优、无低于自算下界、无校验失败。")
    print("=" * 78)

    print(f"\n{'算例':<14}{'布局':<7}{'参照':<16}{'参照值':>8}{'最优':>8}"
          f"{'均值':>9}{'标差':>7}{'gap%':>8}{'均值gap%':>10}")
    for r in sorted(rows, key=lambda x: x["instance"]):
        print(f"{r['instance']:<14}{r.get('layout',''):<7}"
              f"{r.get('ref_kind','(无)'):<16}{r.get('ref_value',0):>8.0f}"
              f"{r['best']:>8.0f}{r['mean']:>9.1f}{r['std']:>7.1f}"
              f"{r.get('gap_best_pct',0):>8.2f}{r.get('gap_mean_pct',0):>10.2f}")

    withref = [r for r in rows if "gap_best_pct" in r]
    proven = [r for r in withref if r["ref_kind"] == "proven_optimal"]
    matched = [r for r in withref if r.get("matches_ref")]
    print(f"\n有参照的算例 {len(withref)} 个(其中可证最优 {len(proven)} 个);"
          f"最优解命中参照值 {len(matched)} 个")
    if withref:
        gb = [r["gap_best_pct"] for r in withref]
        gm = [r["gap_mean_pct"] for r in withref]
        print(f"  最优解 gap: 均值 {statistics.mean(gb):+.2f}%  "
              f"中位 {statistics.median(gb):+.2f}%  最大 {max(gb):+.2f}%")
        print(f"  各种子均值 gap: 均值 {statistics.mean(gm):+.2f}%  "
              f"最大 {max(gm):+.2f}%")
    print(f"\n预算 {rep['meta']['budget']};CSV 已写入 "
          f"{os.path.relpath(rep['exp_dir'], HERE)}{os.sep}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="公开数据集退化对标批跑器")
    ap.add_argument("--dataset", default="hf")
    ap.add_argument("--seeds", type=int, default=10, help="种子数(1..N)")
    ap.add_argument("--smoke", action="store_true", help="等价于 --seeds 3")
    ap.add_argument("--only", default=None, help="只跑文件名含该子串的算例")
    ap.add_argument("--pop", type=int, default=100)
    ap.add_argument("--gen", type=int, default=200)
    ap.add_argument("--stall", type=int, default=30)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--compare", default=None, metavar="BUDGET_TAG",
                    help="与另一预算的账本并排出 budget_effect.csv,如 p100g200s30")
    args = ap.parse_args(argv)
    if args.smoke:
        args.seeds = 3

    pattern = os.path.join(DB, "json", args.dataset, "*.json")
    paths = sorted(p for p in glob.glob(pattern)
                   if not os.path.basename(p).startswith("_"))
    if args.only:
        paths = [p for p in paths if args.only in os.path.basename(p)]
    if not paths:
        print(f"没有算例匹配 {pattern};先跑 tools.convert_public。")
        return 1

    refs = load_refvalues(args.dataset)
    ledger = load_ledger(args)

    if not args.report_only:
        seeds = list(range(1, args.seeds + 1))
        todo = [(p, s) for p in paths for s in seeds
                if (os.path.basename(p)[:-5], s) not in ledger]
        print(f"{len(paths)} 个算例 x {len(seeds)} 个种子 = {len(paths)*len(seeds)} 格;"
              f"待跑 {len(todo)} 格(账本已有 {len(ledger)} 格)")
        t0 = time.time()
        for n, (path, seed) in enumerate(todo, start=1):
            rec = run_cell(path, seed, args)
            tt = rec.pop("timetable")
            append_ledger(rec, args)
            ledger[(rec["instance"], seed)] = rec

            d = os.path.join(OUT, rec["instance"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "timetable_ideal_%s_seed%d.json"
                                  % (budget_tag(args), seed)), "w",
                      encoding="utf-8") as f:
                json.dump(tt, f, ensure_ascii=False, indent=2)

            print(f"  [{n}/{len(todo)}] {rec['instance']} seed={seed} "
                  f"C_max={rec['makespan']:.0f} ({rec['runtime_sec']}s, "
                  f"{rec['generations']} 代, {rec['stopped_by']})"
                  + ("" if rec["valid"] else "  !! 校验失败"))
        print(f"\n跑完,总耗时 {time.time()-t0:.1f}s")

    # 逐算例 summary.json
    for path in paths:
        name = os.path.basename(path)[:-5]
        cells = [r for (nm, _s), r in ledger.items() if nm == name]
        if not cells:
            continue
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        base = name.rsplit("-", 1)[0]
        with open(os.path.join(d, "summary_%s.json" % budget_tag(args)), "w",
                  encoding="utf-8") as f:
            json.dump({
                "instance": name, "arm": ARM, "budget": budget_tag(args),
                "reference": pick_reference(refs.get(base, [])),
                "cells": sorted(cells, key=lambda x: x["seed"]),
            }, f, ensure_ascii=False, indent=2)

    print_report(build_report(paths, ledger, refs, args))
    if args.compare:
        compare_budgets(paths, refs, args, args.compare)
    return 0


if __name__ == "__main__":
    sys.exit(main())
