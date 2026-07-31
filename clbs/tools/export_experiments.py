"""把批跑账本导出为论文绘图用的整洁数据集(CSV)。

职责分离:`output/matrix/<run>/records.jsonl` 是原始运行产物,只追加不修改;
本工具从中派生 `experiments/` 下的若干张宽窄表,供 `paper01_new/fig/*.py` 读取。
图脚本因此不含任何硬编码数字——所有数字都能追溯到某一次具体运行。

运行(clbs/ 目录下):  py -m tools.export_experiments --runs p3
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.stats import describe, mean, wilcoxon_signed_rank  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX_DIR = os.path.join(HERE, "output", "matrix")
EXT_DIR = os.path.join(HERE, "input", "ext")
OUT_DIR = os.path.join(HERE, "experiments")

# 递进链顺序:报告与图例都按这个顺序排,避免不同图里档位次序不一致
ARM_ORDER = ["rule", "twostage", "nofeedback", "opendispatch", "nostagger",
             "closed", "priced"]
TAG_ORDER = {"low": 0, "mid": 1, "high": 2, "funnel": 3}
# closed 相对它们的差值分别对应"集成收益"与三项"机制增益"
BASELINE_ARMS = ["twostage", "nofeedback", "opendispatch", "nostagger"]


def load_ledger(run: str) -> List[dict]:
    path = os.path.join(MATRIX_DIR, run, "records.jsonl")
    if not os.path.exists(path):
        raise SystemExit("账本不存在: %s" % path)
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue          # 断电可能留下半行,跳过而非崩掉
            out.append(rec)
    return out


def load_features() -> Dict[str, dict]:
    feats = {}
    for p in sorted(glob.glob(os.path.join(EXT_DIR, "*.json"))):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if "_features" in data:
            feats[data.get("name") or os.path.basename(p)[:-5]] = data["_features"]
    return feats


def write_csv(path: str, rows: Sequence[dict], fields: Sequence[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("  写出 %-22s %4d 行" % (os.path.basename(path), len(rows)))


def _sort_key(feats: Dict[str, dict], name: str) -> Tuple:
    f = feats.get(name, {})
    return (TAG_ORDER.get(f.get("congestion_tag"), 9),
            f.get("target_heterogeneity") or 0.0, name)


def export(runs: Sequence[str], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    feats = load_features()

    results: List[dict] = []
    budgets: Dict[str, float] = {}
    for run in runs:
        for rec in load_ledger(run):
            if rec.get("kind") == "result":
                rec["run"] = run
                results.append(rec)
            elif rec.get("kind") == "budget":
                budgets[rec["instance"]] = rec["budget_sec"]
    if not results:
        raise SystemExit("账本里没有任何 result 记录")

    names = sorted({r["instance"] for r in results},
                   key=lambda n: _sort_key(feats, n))
    print("导出 %d 条运行,%d 个算例 -> %s" % (len(results), len(names), out_dir))

    # ---------------- 1. 逐次运行(长表) ----------------
    runs_rows = []
    for r in sorted(results, key=lambda x: (_sort_key(feats, x["instance"]),
                                            ARM_ORDER.index(x["arm"])
                                            if x["arm"] in ARM_ORDER else 9,
                                            x["seed"])):
        f = feats.get(r["instance"], {})
        ev, sec = r.get("evaluations"), r.get("runtime_sec")
        runs_rows.append({
            "instance": r["instance"], "tag": r.get("tag") or f.get("congestion_tag"),
            "het": r.get("het"), "arm": r["arm"], "seed": r["seed"],
            "makespan": r["makespan"], "runtime_sec": sec,
            "generations": r.get("generations"), "evaluations": ev,
            "ms_per_eval": (round(1000.0 * sec / ev, 3) if ev and sec else None),
            "stopped_by": r.get("stopped_by"), "valid": int(bool(r.get("valid"))),
            "lower_bound": r.get("lower_bound"), "gap_upper": r.get("gap_upper"),
            "budget_sec": r.get("budget_sec"), "run": r["run"],
        })
    write_csv(os.path.join(out_dir, "runs.csv"), runs_rows,
              ["instance", "tag", "het", "arm", "seed", "makespan", "runtime_sec",
               "generations", "evaluations", "ms_per_eval", "stopped_by", "valid",
               "lower_bound", "gap_upper", "budget_sec", "run"])

    # ---------------- 2. 格子聚合(算例 x 档位) ----------------
    by_cell: Dict[Tuple[str, str], List[dict]] = {}
    for r in results:
        by_cell.setdefault((r["instance"], r["arm"]), []).append(r)

    cell_rows = []
    for n in names:
        for arm in ARM_ORDER:
            rows = by_cell.get((n, arm))
            if not rows:
                continue
            f = feats.get(n, {})
            d = describe([r["makespan"] for r in rows])
            secs = [r["runtime_sec"] for r in rows if r.get("runtime_sec")]
            evs = [r["evaluations"] for r in rows if r.get("evaluations")]
            stops = [r.get("stopped_by") for r in rows if r.get("stopped_by")]
            cell_rows.append({
                "instance": n, "tag": f.get("congestion_tag"),
                "het": f.get("target_heterogeneity"), "arm": arm,
                "n": d["n"], "mean": d["mean"], "sd": d["sd"],
                "median": d["median"], "best": d["min"], "worst": d["max"],
                "mean_sec": round(mean(secs), 2) if secs else None,
                "mean_evals": int(mean(evs)) if evs else None,
                "ms_per_eval": (round(1000.0 * mean(secs) / mean(evs), 3)
                                if evs and secs and mean(evs) > 0 else None),
                "stopped_by": (max(set(stops), key=stops.count) if stops else None),
                "lower_bound": f.get("lower_bound"),
                "gap_upper": (round((d["mean"] - f["lower_bound"]) / d["mean"], 4)
                              if f.get("lower_bound") and d["mean"] else None),
            })
    write_csv(os.path.join(out_dir, "cells.csv"), cell_rows,
              ["instance", "tag", "het", "arm", "n", "mean", "sd", "median",
               "best", "worst", "mean_sec", "mean_evals", "ms_per_eval",
               "stopped_by", "lower_bound", "gap_upper"])

    # ---------------- 3. 配对增益(closed 相对各基线) ----------------
    # 只在两档共有的种子上配对。按列表顺序拼接会静默错位,T14 专门守护这一点。
    by_arm_seed: Dict[Tuple[str, str], Dict[int, float]] = {}
    for r in results:
        by_arm_seed.setdefault((r["instance"], r["arm"]), {})[r["seed"]] = r["makespan"]

    gain_rows = []
    for n in names:
        new = by_arm_seed.get((n, "closed"))
        if not new:
            continue
        f = feats.get(n, {})
        for base_arm in BASELINE_ARMS:
            base = by_arm_seed.get((n, base_arm))
            if not base:
                continue
            common = sorted(set(base) & set(new))
            if not common:
                continue
            xs = [base[s] for s in common]
            ys = [new[s] for s in common]
            per_seed = [(x - y) / x for x, y in zip(xs, ys) if x > 0]
            w = wilcoxon_signed_rank(xs, ys)
            gain_rows.append({
                "instance": n, "tag": f.get("congestion_tag"),
                "het": f.get("target_heterogeneity"),
                "baseline": base_arm,
                "kind": ("integration" if base_arm == "twostage" else "mechanism"),
                "n_pairs": len(common),
                "baseline_mean": round(mean(xs), 3), "closed_mean": round(mean(ys), 3),
                "rel_gain": round(mean(per_seed), 5) if per_seed else None,
                "gain_sd": describe(per_seed)["sd"] if len(per_seed) > 1 else None,
                "n_eff": w["n_eff"], "p_value": w["p_value"], "method": w["method"],
            })
    write_csv(os.path.join(out_dir, "gains.csv"), gain_rows,
              ["instance", "tag", "het", "baseline", "kind", "n_pairs",
               "baseline_mean", "closed_mean", "rel_gain", "gain_sd",
               "n_eff", "p_value", "method"])

    # ---------------- 4. 逐种子增益(供配对检验与散点图) ----------------
    seed_rows = []
    for n in names:
        new = by_arm_seed.get((n, "closed"))
        if not new:
            continue
        f = feats.get(n, {})
        for base_arm in BASELINE_ARMS:
            base = by_arm_seed.get((n, base_arm))
            if not base:
                continue
            for s in sorted(set(base) & set(new)):
                seed_rows.append({
                    "instance": n, "tag": f.get("congestion_tag"),
                    "het": f.get("target_heterogeneity"), "baseline": base_arm,
                    "seed": s, "baseline_makespan": base[s], "closed_makespan": new[s],
                    "rel_gain": (round((base[s] - new[s]) / base[s], 5)
                                 if base[s] > 0 else None),
                })
    write_csv(os.path.join(out_dir, "gains_by_seed.csv"), seed_rows,
              ["instance", "tag", "het", "baseline", "seed",
               "baseline_makespan", "closed_makespan", "rel_gain"])

    # ---------------- 5. 算例特征与下界 ----------------
    inst_rows = []
    for n in names:
        f = feats.get(n)
        if not f:
            continue
        row = {"instance": n, "budget_sec": budgets.get(n)}
        row.update({k: f.get(k) for k in (
            "congestion_tag", "target_heterogeneity", "heterogeneity",
            "target_flexibility", "flexibility", "Tt_over_Tp", "NA_over_NM",
            "num_jobs", "num_machines", "num_agvs", "num_real_ops",
            "num_nodes", "num_corridors", "funnel_share", "lu_min_cut",
            "far_group_cut", "job_chain", "machine_load", "lu_cut",
            "lower_bound")})
        inst_rows.append(row)
    write_csv(os.path.join(out_dir, "instances.csv"), inst_rows,
              ["instance", "congestion_tag", "target_heterogeneity", "heterogeneity",
               "target_flexibility", "flexibility", "Tt_over_Tp", "NA_over_NM",
               "num_jobs", "num_machines", "num_agvs", "num_real_ops", "num_nodes",
               "num_corridors", "funnel_share", "lu_min_cut", "far_group_cut",
               "job_chain", "machine_load", "lu_cut", "lower_bound", "budget_sec"])

    # ---------------- 6. 元信息(图注要引用种子数与预算口径) ----------------
    seeds = sorted({r["seed"] for r in results})
    invalid = [r for r in results if not r.get("valid")]
    meta = {
        "runs": list(runs),
        "num_results": len(results),
        "instances": names,
        "arms": [a for a in ARM_ORDER
                 if any(r["arm"] == a for r in results)],
        "seeds": seeds,
        "num_seeds": len(seeds),
        "budgets_sec": budgets,
        "invalid_count": len(invalid),
        "invalid": [{k: r.get(k) for k in ("instance", "arm", "seed", "errors")}
                    for r in invalid[:20]],
        "complete_cells": sum(1 for k in by_cell if len(by_cell[k]) >= len(seeds)),
        "total_cells": len(by_cell),
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("  写出 %-22s 种子 %s,校验失败 %d"
          % ("meta.json", seeds, len(invalid)))


def main() -> int:
    ap = argparse.ArgumentParser(description="批跑账本 -> 论文绘图数据集")
    ap.add_argument("--runs", nargs="+", default=["p3"], help="账本名(可多个,合并导出)")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()
    export(args.runs, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
