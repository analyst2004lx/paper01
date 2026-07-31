"""在受控扩展算例矩阵上批跑七档消融(规格 12.3.6 主试验,严格执行 8.2 两条协议)。

用法(clbs/ 目录下):

    py -m tools.run_matrix --preset smoke          # 流程自检:2 算例 x 7 档 x 2 种子
    py -m tools.run_matrix --preset p3             # high/funnel 受控对比(预测 3)
    py -m tools.run_matrix --preset full           # 完整矩阵(4 档拥堵 x 4 个 H)
    py -m tools.run_matrix --preset full --dry-run # 只估算任务数与耗时
    py -m tools.run_matrix --report-only           # 用已有账本重新出报告(不跑)

四条设计约定,均由 13.2 的踩坑经验直接决定:

1. **同算力预算**(协议 1)。默认 `--budget auto`:每个算例先用完整方法(closed)在
   默认停机规则下跑一次,把它的用时定为该算例**全部档位共享的挂钟预算**,同时把
   早停阈值放宽到实质关闭——这就是 13.2 中手工做的 A' 复核档,现在成为默认协议。
   `--budget gen` 保留"同代数"视角,但它已知有偏,仅供对照;
2. **多种子 + 离散度 + 配对检验**(协议 2)。默认 10 个种子;报告一律给出
   均值、标准差、极差,并对每组比较做配对 Wilcoxon(同种子配对,见 stats 模块说明);
3. **可中断续跑**。每完成一个 (算例, 档位, 种子) 立即向 JSONL 账本追加一行并落盘,
   重跑同一 `--run` 时自动跳过已完成项。任务顺序按"算例 → 种子 → 全部档位",
   使中断后留下的也是**完整的配对块**,而非半个种子;
4. **跑与报告分离**。报告全部由账本重算,故 `--report-only` 可在任意时刻(含跑到
   一半时)出当前结论。

每个解都过一遍独立校验器,并与算例自带的复合下界比对;校验失败会在报告顶部单列,
不允许被均值掩盖。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.baseline import ARMS, NO_SEARCH_ARMS, solve_arm
from algorithm.generator import measure
from algorithm.ga import GAConfig
from algorithm.instance import parse_instance
from algorithm.network import Network
from algorithm.stats import (describe, mean, spearman, stars,
                             wilcoxon_signed_rank)
from algorithm.validator import validate

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(HERE, "input", "ext")
OUT_ROOT = os.path.join(HERE, "output", "matrix")

# 固定种子池:前三个沿用 13.2 的种子以便与历史数字对照,其余为固定扩充。
SEED_POOL = [42, 7, 2024, 3, 11, 19, 23, 31, 47, 53, 61, 71, 83, 97, 101]

# 反馈机制的三个消融对照:closed 相对它们的改进即"该机制的增益"。
MECHANISM_ARMS = ("nofeedback", "opendispatch", "nostagger")

PRESETS: Dict[str, dict] = {
    # 流程自检:够快(几分钟),只验证账本、续跑、报告与统计是否正常。
    "smoke": {"tags": ["high", "funnel"], "het": [0.3], "n_seeds": 2,
              "budget": "6", "pop": 40},
    # 预测 3 专用:只跑受控对比的两档拥堵度,全部 H,全部种子。
    "p3": {"tags": ["high", "funnel"], "het": [0.0, 0.15, 0.3, 0.5], "n_seeds": 10,
           "budget": "auto", "pop": 60},
    # 完整主试验(规格 12.3.6)。
    "full": {"tags": ["low", "mid", "high", "funnel"], "het": [0.0, 0.15, 0.3, 0.5],
             "n_seeds": 10, "budget": "auto", "pop": 60},
}


# --------------------------------------------------------------------------
# 参数与算例发现
# --------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="扩展算例矩阵批跑(规格 8.2 / 12.3.6)")
    ap.add_argument("--preset", default="smoke", choices=sorted(PRESETS),
                    help="实验规模预设;其余参数可单独覆盖")
    ap.add_argument("--run", default=None,
                    help="账本名(默认取 preset 名);同名即续跑")
    ap.add_argument("--input-dir", default=EXT_DIR)
    ap.add_argument("--tags", nargs="+", default=None, help="拥堵度档位过滤")
    ap.add_argument("--het", type=float, nargs="+", default=None, help="异构度 H 过滤")
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    ap.add_argument("--seeds", type=int, nargs="+", default=None, help="显式种子列表")
    ap.add_argument("--n-seeds", type=int, default=None,
                    help="从固定种子池取前 N 个(协议 2 要求 >= 10)")
    ap.add_argument("--budget", default=None,
                    help="'auto' = 每算例按 closed 的自然用时标定;数字 = 固定秒数;"
                         "'gen' = 不设时间预算(同代数视角,已知有偏)")
    ap.add_argument("--budget-cap", type=float, default=None,
                    help="auto 标定值的上限(秒)。用于把大矩阵的总耗时压到可接受范围;"
                         "一旦生效,各档都可能欠收敛,报告的预算体检会给出警告")
    ap.add_argument("--pop", type=int, default=None)
    ap.add_argument("--gen", type=int, default=200, help="同代数模式下的最大代数")
    ap.add_argument("--stall", type=int, default=30, help="同代数模式/标定run 的早停代数")
    ap.add_argument("--dry-run", action="store_true", help="只列任务数与预计耗时")
    ap.add_argument("--report-only", action="store_true", help="只按已有账本出报告")
    return ap.parse_args()


def resolve(args: argparse.Namespace) -> argparse.Namespace:
    p = PRESETS[args.preset]
    args.tags = args.tags or p["tags"]
    args.het = args.het if args.het is not None else p["het"]
    args.budget = args.budget or p["budget"]
    args.pop = args.pop or p["pop"]
    if args.seeds is None:
        n = args.n_seeds or p["n_seeds"]
        if n > len(SEED_POOL):
            raise SystemExit(f"种子池只有 {len(SEED_POOL)} 个,请显式给 --seeds")
        args.seeds = SEED_POOL[:n]
    args.run = args.run or args.preset
    return args


def discover(args: argparse.Namespace) -> List[dict]:
    """扫描算例目录,按拥堵度档位与异构度过滤,返回 [{path, name, features, data}]。"""
    found: List[dict] = []
    for path in sorted(glob.glob(os.path.join(args.input_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        feat = data.get("_features") or measure(data)
        tag = feat.get("congestion_tag")
        h = feat.get("target_heterogeneity")
        if tag not in args.tags:
            continue
        if h is None or not any(abs(h - t) < 1e-9 for t in args.het):
            continue
        found.append({"path": path, "name": data.get("name", os.path.basename(path)),
                      "features": feat, "data": data})
    # 排序:先按拥堵度档位(实验矩阵的行序),再按 H,便于中断后按行读结果
    order = {t: i for i, t in enumerate(["low", "mid", "high", "funnel"])}
    found.sort(key=lambda r: (order.get(r["features"]["congestion_tag"], 9),
                              r["features"].get("target_heterogeneity") or 0.0,
                              r["name"]))
    return found


# --------------------------------------------------------------------------
# 账本(JSONL,追加即落盘)
# --------------------------------------------------------------------------

class Ledger:
    def __init__(self, run_dir: str):
        self.dir = run_dir
        os.makedirs(run_dir, exist_ok=True)
        self.path = os.path.join(run_dir, "records.jsonl")
        self.records: List[dict] = []
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.records.append(json.loads(line))

    def append(self, rec: dict) -> None:
        self.records.append(rec)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())      # 断电/强杀也不丢已完成的运行

    def results(self) -> List[dict]:
        return [r for r in self.records if r.get("kind") == "result"]

    def done_keys(self) -> set:
        return {(r["instance"], r["arm"], r["seed"]) for r in self.results()}

    def budgets(self) -> Dict[str, dict]:
        return {r["instance"]: r for r in self.records if r.get("kind") == "budget"}


# --------------------------------------------------------------------------
# 运行
# --------------------------------------------------------------------------

def make_cfg(args: argparse.Namespace, seed: int, budget: Optional[float]) -> GAConfig:
    """构造 GA 配置。给定时间预算时把早停实质关闭,否则各档不会真正用完预算,
    "同算力"就名不副实(13.2 中 A' 档正是靠放宽早停才暴露出机制增益是算力假象)。"""
    if budget is None:
        return GAConfig(pop=args.pop, max_gen=args.gen, stall_gen=args.stall, seed=seed)
    return GAConfig(pop=args.pop, max_gen=10 ** 9, stall_gen=10 ** 9, seed=seed,
                    time_budget_sec=budget)


def calibrate(inst, net, args: argparse.Namespace, seed: int) -> Tuple[float, dict]:
    """用完整方法在默认停机规则下跑一次,其用时即该算例全部档位的共享预算。

    以 closed 为标定基准而非最快档:预算必须够完整方法收敛,否则等于把所有档
    一起限制在欠收敛区间,比较的就不是机制而是"谁在早期更快"。
    """
    cfg = GAConfig(pop=args.pop, max_gen=args.gen, stall_gen=args.stall, seed=seed)
    t0 = time.time()
    out = solve_arm("closed", inst, net, cfg)
    return max(2.0, round(time.time() - t0, 2)), {
        "makespan": out["best_result"].makespan,
        "generations": out.get("generations"),
        "evaluations": out.get("evaluations"),
        "stopped_by": out.get("stopped_by"),
    }


def run(args: argparse.Namespace, instances: List[dict], ledger: Ledger) -> None:
    done = ledger.done_keys()
    budgets = ledger.budgets()
    todo = [(r, seed, arm) for r in instances for seed in args.seeds
            for arm in args.arms
            if (r["name"], arm, seed) not in done]

    print(f"待跑 {len(todo)} 个任务(已完成 {len(done)} 个)"
          f",账本 {os.path.relpath(ledger.path, HERE)}", flush=True)
    if not todo:
        return

    t_start = time.time()
    finished = 0
    try:
        for rec, seed, arm in todo:
            inst = rec.setdefault("_inst", parse_instance(rec["data"]))
            net = rec.get("_net")
            if net is None:
                net = Network(inst.nodes, inst.corridors, inst.lu_node)
                net.check_reachability()
                rec["_net"] = net

            budget: Optional[float] = None
            if args.budget != "gen":
                if args.budget == "auto":
                    b = budgets.get(rec["name"])
                    if b is None:
                        natural, info = calibrate(inst, net, args, args.seeds[0])
                        sec = (min(natural, args.budget_cap) if args.budget_cap
                               else natural)
                        b = {"kind": "budget", "instance": rec["name"],
                             "budget_sec": sec, "natural_sec": natural,
                             "source": "auto-capped" if sec < natural else "auto",
                             "pop": args.pop, "calib": info,
                             "ts": round(time.time(), 3)}
                        ledger.append(b)
                        budgets[rec["name"]] = b
                        print(f"  [标定] {rec['name']}: 预算 {sec}s "
                              f"(closed 自然用时, C_max={info['makespan']})",
                              flush=True)
                    budget = b["budget_sec"]
                else:
                    budget = float(args.budget)

            cfg = make_cfg(args, seed, budget)
            t0 = time.time()
            out = solve_arm(arm, inst, net, cfg)
            elapsed = round(time.time() - t0, 2)
            timetable = out["best_result"].to_timetable()
            errors = validate(inst, timetable)
            lb = rec["features"].get("lower_bound")
            cmax = out["makespan"]

            row = {
                "kind": "result", "instance": rec["name"], "arm": arm, "seed": seed,
                "makespan": cmax, "runtime_sec": elapsed,
                "generations": out.get("generations"), "evaluations": out.get("evaluations"),
                "stopped_by": out.get("stopped_by"),
                "valid": not errors, "errors": errors[:5],
                "budget_sec": budget, "pop": args.pop,
                "tag": rec["features"].get("congestion_tag"),
                "het": rec["features"].get("target_heterogeneity"),
                "lower_bound": lb,
                "gap_upper": (round((cmax - lb) / cmax, 4) if lb and cmax > 0 else None),
                "stage1_makespan": out.get("stage1_makespan"),
                "ts": round(time.time(), 3),
            }
            if lb is not None and cmax < lb - 1e-6:
                row["errors"] = [f"C_max {cmax} 低于下界 {lb}"] + row["errors"]
                row["valid"] = False
            ledger.append(row)

            finished += 1
            per = (time.time() - t_start) / finished
            eta = per * (len(todo) - finished)
            flag = "" if row["valid"] else "  !! 校验失败"
            # 批跑动辄数小时,输出重定向到文件时 Python 会缓冲 stdout,不显式刷新
            # 就看不到任何进度,也无法判断是在跑还是卡住了
            print(f"  [{finished}/{len(todo)}] {rec['name']:<34s} {arm:<13s} "
                  f"seed={seed:<5d} C_max={cmax:>7.1f}  {elapsed:>6.1f}s  "
                  f"gen={row['generations'] or '-':<5} ETA {eta/60:.1f}min{flag}",
                  flush=True)
    except KeyboardInterrupt:
        print(f"\n已中断。完成 {finished} 个任务,结果已全部落盘。"
              f"\n续跑: py -m tools.run_matrix --preset {args.preset} --run {args.run}")


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------

def _by_arm(results: Sequence[dict]) -> Dict[Tuple[str, str], Dict[int, float]]:
    """(算例, 档位) -> {种子: C_max}。"""
    out: Dict[Tuple[str, str], Dict[int, float]] = {}
    for r in results:
        out.setdefault((r["instance"], r["arm"]), {})[r["seed"]] = r["makespan"]
    return out


def _paired(a: Dict[int, float], b: Dict[int, float]) -> Tuple[List[float], List[float]]:
    """取两档共同种子上的配对样本(顺序按种子号,保证可复现)。"""
    common = sorted(set(a) & set(b))
    return [a[s] for s in common], [b[s] for s in common]


def _rel_gain(base: Sequence[float], new: Sequence[float]) -> Optional[float]:
    """new 相对 base 的平均相对改进(正数表示 new 更好)。"""
    vals = [(x - y) / x for x, y in zip(base, new) if x > 0]
    return mean(vals) if vals else None


def build_report(args: argparse.Namespace, instances: List[dict],
                 ledger: Ledger) -> dict:
    results = ledger.results()
    cells = _by_arm(results)
    inst_feat = {r["name"]: r["features"] for r in instances}
    # 账本里可能有本次过滤范围之外的算例(续跑时换过 preset),一并纳入报告
    for r in results:
        inst_feat.setdefault(r["instance"], {"congestion_tag": r.get("tag"),
                                             "target_heterogeneity": r.get("het"),
                                             "lower_bound": r.get("lower_bound")})
    names = sorted(inst_feat, key=lambda n: (
        {"low": 0, "mid": 1, "high": 2, "funnel": 3}.get(
            inst_feat[n].get("congestion_tag"), 9),
        inst_feat[n].get("target_heterogeneity") or 0.0, n))

    rep: dict = {
        "run": args.run,
        "budget_mode": args.budget,
        "budgets": {k: v["budget_sec"] for k, v in ledger.budgets().items()},
        "seeds": args.seeds,
        "pop": args.pop,
        "num_results": len(results),
        "invalid": [{k: r[k] for k in ("instance", "arm", "seed", "errors")}
                    for r in results if not r["valid"]],
        "per_cell": {},
        "integration_gain": {},
        "mechanism_gain": {},
        "predictions": {},
    }

    # ---- 每算例 x 档位:均值/离散度 + 实际算力(用于核对预算是否真的对齐) ----
    for n in names:
        for arm in args.arms:
            vals = cells.get((n, arm))
            if not vals:
                continue
            rows = [r for r in results if r["instance"] == n and r["arm"] == arm]
            d = describe(list(vals.values()))
            d["mean_sec"] = round(mean([r["runtime_sec"] for r in rows]), 1)
            evs = [r["evaluations"] for r in rows if r.get("evaluations")]
            d["mean_evals"] = int(mean(evs)) if evs else None
            # 单次评价成本:同算力下各档评估数的差异**全部**由它解释,
            # 不并列给出就无法判断"评估数多"是机制便宜还是模型被换掉了(见报告注)
            if evs and d["mean_sec"] > 0:
                d["ms_per_eval"] = round(1000.0 * d["mean_sec"] / mean(evs), 2)
            stops = [r.get("stopped_by") for r in rows if r.get("stopped_by")]
            d["stopped"] = (max(set(stops), key=stops.count) if stops else None)
            gaps = [r["gap_upper"] for r in rows if r.get("gap_upper") is not None]
            d["gap_upper"] = round(mean(gaps), 4) if gaps else None
            rep["per_cell"][f"{n}|{arm}"] = d

    # ---- 集成收益:closed vs twostage,按种子配对 ----
    for n in names:
        a, b = cells.get((n, "twostage")), cells.get((n, "closed"))
        if not a or not b:
            continue
        xs, ys = _paired(a, b)
        if not xs:
            continue
        w = wilcoxon_signed_rank(xs, ys)
        rep["integration_gain"][n] = {
            "tag": inst_feat[n].get("congestion_tag"),
            "het": inst_feat[n].get("target_heterogeneity"),
            "twostage_mean": round(mean(xs), 2), "closed_mean": round(mean(ys), 2),
            "rel_gain": round(_rel_gain(xs, ys) or 0.0, 4),
            "n": len(xs), "p_value": w["p_value"], "method": w["method"],
            "n_eff": w["n_eff"],
        }

    # ---- 机制增益:closed 相对三个消融档 ----
    for n in names:
        b = cells.get((n, "closed"))
        if not b:
            continue
        for arm in MECHANISM_ARMS:
            a = cells.get((n, arm))
            if not a:
                continue
            xs, ys = _paired(a, b)
            if not xs:
                continue
            w = wilcoxon_signed_rank(xs, ys)
            rep["mechanism_gain"][f"{n}|{arm}"] = {
                "tag": inst_feat[n].get("congestion_tag"),
                "het": inst_feat[n].get("target_heterogeneity"),
                "ablated_mean": round(mean(xs), 2), "closed_mean": round(mean(ys), 2),
                "rel_gain": round(_rel_gain(xs, ys) or 0.0, 4),
                "n": len(xs), "p_value": w["p_value"], "n_eff": w["n_eff"],
            }

    rep["budget_audit"] = audit_budget(rep, names, args)
    rep["predictions"] = check_predictions(rep, cells, inst_feat, args)
    return rep


def audit_budget(rep: dict, names: Sequence[str], args: argparse.Namespace) -> dict:
    """预算体检:同算力协议自身是否成立。

    两种失效必须显式报出,否则"同算力"这个说法会掩盖比较的真实内容:

    1. **欠收敛**:某档被预算掐停(`stopped_by == "budget"`)而对手是自然收敛
       (`stall`),则该比较测的是"谁在早期涨得快",不是机制优劣;
    2. **代价不对称**:两阶段第一阶段在**理想模型**下评价(路由退化为查表),单次
       评价可比闭环便宜一两个数量级。故等挂钟时间给它的搜索次数会大出数十倍——
       等时间既不等评估数,等评估数又不等时间,两种口径都不中立,必须并列报告。
    """
    audit: dict = {"undertrained": [], "cost_ratio": {}}
    for n in names:
        costs = {}
        stops = {}
        for arm in args.arms:
            d = rep["per_cell"].get(f"{n}|{arm}")
            if not d or arm in NO_SEARCH_ARMS:
                continue
            stops[arm] = d.get("stopped")
            if d.get("ms_per_eval"):
                costs[arm] = d["ms_per_eval"]
        if costs:
            lo = min(costs, key=lambda a: costs[a])
            hi = max(costs, key=lambda a: costs[a])
            audit["cost_ratio"][n] = {
                "cheapest": lo, "cheapest_ms": costs[lo],
                "dearest": hi, "dearest_ms": costs[hi],
                "ratio": round(costs[hi] / costs[lo], 1) if costs[lo] > 0 else None,
            }
        hit = [a for a, s in stops.items() if s == "budget"]
        conv = [a for a, s in stops.items() if s == "stall"]
        if hit and conv:
            audit["undertrained"].append({"instance": n, "budget_bound": hit,
                                          "converged": conv})
    return audit


def check_predictions(rep: dict, cells, inst_feat, args) -> dict:
    """检验 12.3.6 的三条预期。每条都给出判定依据,不能判定时明确写"证据不足"。"""
    gains = rep["integration_gain"]
    out: dict = {}

    # 预测 1:拥堵与异构越高,集成收益越大
    by_tag: Dict[str, List[float]] = {}
    by_het: Dict[float, List[float]] = {}
    for g in gains.values():
        by_tag.setdefault(g["tag"], []).append(g["rel_gain"])
        by_het.setdefault(g["het"], []).append(g["rel_gain"])
    hets = [g["het"] for g in gains.values() if g["het"] is not None]
    rho_h = spearman(hets, [g["rel_gain"] for g in gains.values()
                            if g["het"] is not None]) if len(hets) >= 3 else None
    out["P1_congestion_heterogeneity"] = {
        "by_tag_mean_gain": {k: round(mean(v), 4) for k, v in sorted(by_tag.items())},
        "by_het_mean_gain": {str(k): round(mean(v), 4) for k, v in sorted(by_het.items())},
        "spearman_gain_vs_H": None if rho_h is None else round(rho_h, 4),
        "verdict": _verdict_monotone(by_het),
    }

    # 预测 2:H=0 时改派机制失效,收益应最低
    zero = by_het.get(0.0)
    nonzero = [v for k, vs in by_het.items() if k and k > 0 for v in vs]
    if zero and nonzero:
        out["P2_H0_degenerates"] = {
            "H0_mean_gain": round(mean(zero), 4),
            "H_positive_mean_gain": round(mean(nonzero), 4),
            "verdict": ("支持" if mean(zero) < mean(nonzero) - 1e-9
                        else "不支持(H=0 收益不低于 H>0)"),
        }
    else:
        out["P2_H0_degenerates"] = {"verdict": "证据不足(缺 H=0 或 H>0 的格子)"}

    # 预测 3:high 上的机制增益应大于 funnel 上的(同 H、同种子配对)
    out["P3_high_vs_funnel"] = _check_p3(cells, inst_feat, args)
    return out


def _verdict_monotone(by_het: Dict[float, List[float]]) -> str:
    keys = sorted(k for k in by_het if k is not None)
    if len(keys) < 3:
        return "证据不足(H 取值少于 3 档)"
    ms = [mean(by_het[k]) for k in keys]
    if all(b >= a - 1e-9 for a, b in zip(ms, ms[1:])):
        return "支持(收益随 H 单调不减)"
    return "不支持(收益随 H 非单调)"


def _pair_instances(inst_feat, tag_a: str, tag_b: str) -> List[Tuple[str, str, float]]:
    """把两档拥堵度下同 H 的算例配成对(受控对比:仅 LU 出口容量不同)。"""
    idx: Dict[Tuple[str, float], str] = {}
    for n, f in inst_feat.items():
        t, h = f.get("congestion_tag"), f.get("target_heterogeneity")
        if t and h is not None:
            idx[(t, h)] = n
    pairs = []
    for (t, h), n in sorted(idx.items()):
        if t == tag_a and (tag_b, h) in idx:
            pairs.append((n, idx[(tag_b, h)], h))
    return pairs


def _check_p3(cells, inst_feat, args) -> dict:
    """预测 3:机制增益在 high 上应大于 funnel 上。

    配对方式是这条预测能被判定的关键:high 与 funnel 在同 H、同种子下**只差
    LU 出口容量**(T12 已固化),故 (H, 种子) 就是天然的配对键,两侧增益之差里
    不含任何其他差异。
    """
    pairs = _pair_instances(inst_feat, "high", "funnel")
    if not pairs:
        return {"verdict": "证据不足(缺 high/funnel 配对算例)"}
    detail = {}
    for arm in MECHANISM_ARMS:
        # 按 (H, 种子) 显式建键再取交集:若某格缺失,按列表顺序拼接会让两侧错位,
        # 而错位的配对检验不会报错、只会给出一个看似正常的 p 值
        gains: Dict[str, Dict[Tuple[float, int], float]] = {"high": {}, "funnel": {}}
        for n_high, n_funnel, h in pairs:
            for side, src in (("high", n_high), ("funnel", n_funnel)):
                a, b = cells.get((src, arm)), cells.get((src, "closed"))
                if not a or not b:
                    continue
                for s in sorted(set(a) & set(b)):
                    if a[s] > 0:
                        gains[side][(h, s)] = (a[s] - b[s]) / a[s]
        keys = sorted(set(gains["high"]) & set(gains["funnel"]))
        hi = [gains["high"][k] for k in keys]
        fu = [gains["funnel"][k] for k in keys]
        if len(keys) < 2:
            detail[arm] = {"verdict": "证据不足(可配对的 (H, 种子) 少于 2 组)"}
            continue
        w = wilcoxon_signed_rank(hi, fu)
        detail[arm] = {
            "high_mean_gain": round(mean(hi), 4),
            "funnel_mean_gain": round(mean(fu), 4),
            "n_pairs": len(keys),
            "p_value": w.get("p_value"), "n_eff": w.get("n_eff"),
            "method": w.get("method"),
            "verdict": ("支持" if mean(hi) > mean(fu) + 1e-9 else "不支持"),
        }
    votes = [d.get("verdict") for d in detail.values()]
    return {"by_mechanism": detail,
            "verdict": ("支持" if votes and all(v == "支持" for v in votes)
                        else "部分支持" if "支持" in votes else "不支持/证据不足")}


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

def _md_table(header: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    out = ["| " + " | ".join(str(h) for h in header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def render(rep: dict) -> str:
    L: List[str] = []
    L.append(f"# 矩阵实验报告 `{rep['run']}`\n")
    L.append(f"- 预算模式:`{rep['budget_mode']}`"
             + (f"(各算例预算 {rep['budgets']})" if rep["budgets"] else "")
             + f";种群 {rep['pop']};种子 {rep['seeds']}")
    L.append(f"- 完成运行数:{rep['num_results']};校验失败:{len(rep['invalid'])}")
    if rep["invalid"]:
        L.append("\n> **校验失败项(必须先修,不得只看均值)**\n")
        L.append(_md_table(["算例", "档位", "种子", "错误"],
                           [[r["instance"], r["arm"], r["seed"],
                             "; ".join(r["errors"])[:80]] for r in rep["invalid"]]))

    L.append("\n## 一、各格子结果(均值 ± 样本标准差)\n")
    L.append("> `秒` / `评估数` / `毫秒每评价` / `停机原因` 四列并列,是同算力协议"
             "是否真的成立的证据:秒数应相近,评估数可以差数十倍,而差多少**全部**由"
             "单次评价成本解释。`停机原因 = budget` 意味着该档被预算掐停而非收敛。\n")
    rows = []
    for key, d in rep["per_cell"].items():
        n, arm = key.split("|")
        rows.append([n, arm, d["n"], f"{d['mean']:.1f} ± {d['sd']:.1f}",
                     d["min"], d["max"], d["range"], d["mean_sec"],
                     d["mean_evals"], d.get("ms_per_eval"), d.get("stopped"),
                     d["gap_upper"]])
    L.append(_md_table(["算例", "档位", "n", "均值±sd", "最好", "最差", "极差",
                        "秒/次", "评估数", "毫秒/评价", "停机原因",
                        "下界 gap 上限"], rows))

    aud = rep.get("budget_audit") or {}
    L.append("\n### 1.1 预算体检(同算力协议自身是否成立)\n")
    if aud.get("cost_ratio"):
        rows = [[n, c["cheapest"], c["cheapest_ms"], c["dearest"], c["dearest_ms"],
                 f"{c['ratio']}x"] for n, c in aud["cost_ratio"].items()]
        L.append(_md_table(["算例", "最便宜档", "毫秒/评价", "最贵档", "毫秒/评价",
                            "成本比"], rows))
        L.append("\n**两阶段档的评价成本天然低一两个数量级**——它的第一阶段在理想"
                 "运输模型下搜索(路由退化为查 t\\* 表),故等挂钟时间等于给它数十倍"
                 "的搜索次数。**等时间与等评估数两种口径都不中立**:前者偏向廉价"
                 "代理模型的开环法,后者偏向每次评价都做真实路由的闭环法。结论必须"
                 "同时给出两种口径(`--budget auto` 与 `--budget gen`)才算完整。\n")
    if aud.get("undertrained"):
        L.append("> **欠收敛警告**:以下算例中部分档被预算掐停而另一些已自然收敛,"
                 "该比较测的是收敛速度而非机制优劣,应加大预算后重跑。\n")
        L.append(_md_table(["算例", "被预算掐停", "已收敛"],
                           [[u["instance"], ", ".join(u["budget_bound"]),
                             ", ".join(u["converged"])] for u in aud["undertrained"]]))

    L.append("\n## 二、集成收益(closed vs twostage,同种子配对)\n")
    rows = []
    for n, g in rep["integration_gain"].items():
        rows.append([n, g["tag"], g["het"], g["twostage_mean"], g["closed_mean"],
                     f"{g['rel_gain']*100:.1f}%", g["n"], g["n_eff"],
                     f"{g['p_value']}{stars(g['p_value'])}"])
    L.append(_md_table(["算例", "拥堵档", "H", "两阶段", "闭环", "相对收益",
                        "n", "非平局对数", "p(Wilcoxon)"], rows))

    L.append("\n## 三、机制增益(closed 相对各消融档)\n")
    rows = []
    for key, g in rep["mechanism_gain"].items():
        n, arm = key.split("|")
        rows.append([n, arm, g["tag"], g["het"], g["ablated_mean"], g["closed_mean"],
                     f"{g['rel_gain']*100:.1f}%", g["n_eff"],
                     f"{g['p_value']}{stars(g['p_value'])}"])
    L.append(_md_table(["算例", "消融档", "拥堵档", "H", "消融", "闭环",
                        "机制增益", "非平局对数", "p"], rows))

    L.append("\n## 四、12.3.6 三条预期的判定\n")
    p = rep["predictions"]
    p1 = p["P1_congestion_heterogeneity"]
    L.append(f"**预测 1(拥堵/异构越高收益越大)**:{p1['verdict']};"
             f"Spearman(收益, H) = {p1['spearman_gain_vs_H']}")
    L.append(f"- 按拥堵档:{p1['by_tag_mean_gain']}")
    L.append(f"- 按异构度:{p1['by_het_mean_gain']}\n")
    p2 = p["P2_H0_degenerates"]
    L.append(f"**预测 2(H=0 时机制失效)**:{p2['verdict']}"
             + (f";H=0 收益 {p2.get('H0_mean_gain')} vs H>0 收益 "
                f"{p2.get('H_positive_mean_gain')}" if "H0_mean_gain" in p2 else ""))
    p3 = p["P3_high_vs_funnel"]
    L.append(f"\n**预测 3(high 上机制增益 > funnel 上)**:{p3['verdict']}\n")
    if "by_mechanism" in p3:
        rows = [[arm, d.get("high_mean_gain"), d.get("funnel_mean_gain"),
                 d.get("n_pairs"), d.get("n_eff"), d.get("p_value"), d["verdict"]]
                for arm, d in p3["by_mechanism"].items()]
        L.append(_md_table(["消融档", "high 增益", "funnel 增益", "配对数",
                            "非平局对数", "p", "判定"], rows))
    L.append("\n---\n")
    L.append("> 解读约束(规格 8.2、13.2):引用任何数字必须连同**种子数与预算模式**"
             "一并给出;非平局对数少于种子数一半时,该行差异基本落在取整噪声内。")
    return "\n".join(L)


def main() -> int:
    args = resolve(parse_args())
    instances = discover(args)
    if not instances and not args.report_only:
        print(f"{args.input_dir} 下没有匹配的算例。"
              f"\n先生成:py -m tools.gen_instances")
        return 1

    run_dir = os.path.join(OUT_ROOT, args.run)
    ledger = Ledger(run_dir)
    n_jobs = len(instances) * len(args.seeds) * len(args.arms)
    print(f"矩阵: {len(instances)} 算例 x {len(args.arms)} 档 x "
          f"{len(args.seeds)} 种子 = {n_jobs} 次运行;预算模式 {args.budget}")
    if len(args.seeds) < 10:
        print("  ! 协议 2 要求 >= 10 个种子;当前种子数偏少,结论只能当作流程自检。")

    if args.dry_run:
        known = [v["budget_sec"] for v in ledger.budgets().values()]
        if args.budget not in ("auto", "gen"):
            per, src = float(args.budget), "固定预算"
        elif known:
            per, src = mean(known), "账本中已标定的预算均值"
        else:
            per, src = (args.budget_cap or 40.0), "估计值(auto 实际以标定为准)"
        print(f"  预计耗时 ~{n_jobs * per / 3600:.1f} 小时(按每次 {per:.0f}s,{src})")
        for r in instances:
            f = r["features"]
            print(f"    {r['name']:<36s} tag={f['congestion_tag']:<7s} "
                  f"H={f['target_heterogeneity']} LB={f['lower_bound']}")
        return 0

    if not args.report_only:
        run(args, instances, ledger)

    rep = build_report(args, instances, ledger)
    with open(os.path.join(run_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    text = render(rep)
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n" + text)
    print(f"\n报告已写入 {os.path.relpath(run_dir, HERE)}{os.sep}"
          f"(report.md / summary.json / records.jsonl)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
