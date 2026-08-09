"""补齐基线阶梯没有记录的三样东西:逐臂成本、收敛轨迹、案例分析用的时刻表。

为什么要单独一个工具。tools/baseline_ladder.py 只把每次运行的 makespan 存进 CSV,而
run_ga() 其实还返回了 decodes、runtime_sec 与逐代的 history/history_sec。主结果只需要
makespan,所以那样是对的;但论文第 5.7 小节的代价律、5.3 小节的收敛图与 5.8 小节的甘特图
都需要被丢掉的那部分。改 baseline_ladder.py 再重跑要六个多小时,而这三样东西并不需要
十种子的统计效力:

  - 每次评价的成本是各档的**结构性属性**(开环查常数矩阵 / 闭环全量路由 / 闭环加派车试探),
    档间相差一到两个数量级,少数几个种子就足以把量级定住;
  - 收敛图是**说明性**的,画的是曲线形状与"代理目标下探到不可实现的位置"这件事,不是统计主张;
  - 甘特图是**单个算例的个案**,本来就只用一个种子。

因此本工具在少数代表性算例上跑同样的四档、同样的挂钟预算,只是把该记的都记下来。凡是进入
论文正文的统计主张,一律仍以 baseline_ladder.csv 为准,本工具的产出只供画图与代价说明。

四档与 baseline_ladder.py 严格一致(否则图与表就不是同一件事):
  B0   开环搜索(理想矩阵)-> 真实路由器执行,复现计划中的派车
  B0+  同一次开环搜索的排产,执行时改为查预约表选车
  B1   闭环搜索 + 规则派车
  B2   闭环搜索 + 预约表试探派车(本文方法)
其中 B0 与 B0+ **共用同一次开环搜索**,故二者的成本口径相同,只是执行方式不同——这一点在
成本图上必须体现,不能让读者以为 B0+ 另花了一次搜索。

产出(clbs/output/):
  ladder_cost.csv         case,seed,arm,decodes,runtime_sec,ms_per_eval,makespan,surrogate
  ladder_convergence.csv  case,seed,arm,t_sec,best      (长表,供收敛图)
  case_study/*.json       时刻表(供甘特图与关键链归因)

运行(clbs/ 目录下):
  py -u -m tools.ladder_diag [--budget 90] [--seeds 42,7,2024] [--only 名字,名字]
                             [--case-study "A funnel"] [--no-conv]
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.decoder import critical_chain, decode
from algorithm.ga import GAConfig, run_ga
from algorithm.validator import validate
from tools.abc_matrix import CASES, build
from tools.price_matrix import instance_contention

OUT = os.path.join(os.path.dirname(__file__), "..", "output")


def chain_of(res) -> list:
    """把关键链序列化成图能直接消费的形式。

    归因标签由 decoder.critical_chain 给出:corridor 是让行等待(争用),machine 是等机器
    释放,operation 是加工本身,vehicle/upstream 是车辆不可用或上游未完工。第 5.8 小节的
    论点正是这个构成随机制变化——争用被消掉之后,顶上来的是别的约束,这就是稀释效应的图示。
    """
    out = []
    for it in critical_chain(res):
        out.append({
            "kind": it.kind,
            "job": None if it.op is None else it.op[0],
            "i": None if it.op is None else it.op[1],
            "corridor": it.corridor,
            "agv": it.agv,
            "t_start": round(it.t_start, 4),
            "t_end": round(it.t_end, 4),
            "amount": round(it.amount, 4),
        })
    return out

# 三格代表性算例:最拥堵、中等、车队最紧。第三格是逐格表里唯一"闭环单独用反而有害"的一格,
# 收敛图上它的形状最能说明问题,故必须在内。
DEFAULT_CASES = ["A funnel", "A mid", "B NA/NM 0.5"]


def run_one(inst, net, cfg) -> Dict[str, dict]:
    """在一个算例的一个种子上跑完四档,返回每档的成本、轨迹与时刻表。"""
    out: Dict[str, dict] = {}

    # ---- 开环搜索一次,B0 与 B0+ 共用它 ----
    o0 = run_ga(inst, net, replace(cfg, dispatch="rule"),
                conflict_free=False, use_ls=True)
    ch = o0["best_chrom"]
    # 开环搜索自报的完工时间是**代理目标**(查理想矩阵、无让行),它不可实现;
    # 真实值要把同一份计划放进无冲突路由器执行才能得到。收敛图的关键就在这个落差。
    surrogate = o0["best_result"].makespan
    r_b0 = decode(inst, net, ch["ma"], ch["os"], conflict_free=True,
                  dispatch="rule",
                  forced_dispatch=o0["best_result"].dispatch_order)
    r_b0p = decode(inst, net, ch["ma"], ch["os"], conflict_free=True,
                   dispatch="exact")
    ms = 1000.0 * o0["runtime_sec"] / max(o0["decodes"], 1)
    for arm, res in (("B0", r_b0), ("B0+", r_b0p)):
        out[arm] = {
            "decodes": o0["decodes"], "runtime_sec": o0["runtime_sec"],
            "ms_per_eval": ms, "makespan": res.makespan,
            # 代理目标的轨迹对两档相同(同一次搜索),真实值只有终点一个
            "surrogate": surrogate,
            "history": o0["history"], "history_sec": o0["history_sec"],
            "timetable": res.to_timetable(),
            "chain": chain_of(res),
        }

    # ---- 闭环两档,各自独立搜索,只差派车 ----
    for arm, disp in (("B1", "rule"), ("B2", "exact")):
        o = run_ga(inst, net, replace(cfg, dispatch=disp),
                   conflict_free=True, use_ls=True)
        out[arm] = {
            "decodes": o["decodes"], "runtime_sec": o["runtime_sec"],
            "ms_per_eval": 1000.0 * o["runtime_sec"] / max(o["decodes"], 1),
            "makespan": o["best_result"].makespan,
            # 闭环各档的适应度自始至终就是真实值,故没有代理目标可言
            "surrogate": None,
            "history": o["history"], "history_sec": o["history_sec"],
            "timetable": o["best_result"].to_timetable(),
            "chain": chain_of(o["best_result"]),
        }
    return out


def main() -> int:
    args = sys.argv[1:]

    def opt(flag: str, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    budget = float(opt("--budget", 90.0))
    seeds = [int(x) for x in opt("--seeds", "42,7,2024").split(",")]
    want = set(opt("--only", ",".join(DEFAULT_CASES)).split(","))
    study = opt("--case-study", "A funnel")
    cases = [c for c in CASES if c["name"] in want]
    if not cases:
        print("没有匹配的算例,可选:" + ", ".join(c["name"] for c in CASES))
        return 2

    print(f"阶梯诊断:四档同挂钟 {budget:.0f}s,算例 {len(cases)} 个 x 种子 "
          f"{len(seeds)} 个")
    print("口径:只记成本与轨迹供画图;正文的统计主张仍以 baseline_ladder.csv 为准\n")

    os.makedirs(OUT, exist_ok=True)
    cost_rows: List[str] = []
    conv_rows: List[str] = []
    t0 = time.time()

    for case in cases:
        inst, net, _cc = build(case)
        nm = case["name"]
        cont = instance_contention(inst, net, "exact")
        base = GAConfig(pop=60, max_gen=2000, stall_gen=400,
                        use_conflict_ops=True, theta=0.0,
                        max_entry_options=3, time_budget_sec=budget)
        for s in seeds:
            res = run_one(inst, net, replace(base, seed=s))
            for arm, d in res.items():
                errs = validate(inst, d["timetable"])
                flag = "" if not errs else "  !! 校验失败:%s" % errs[:1]
                # 9 列:case,contention,arm,seed,decodes,runtime,ms/eval,makespan,surrogate
                cost_rows.append("%s,%.4f,%s,%d,%d,%.2f,%.4f,%.4f,%s"
                                 % (nm, cont, arm, s, d["decodes"],
                                    d["runtime_sec"], d["ms_per_eval"],
                                    d["makespan"],
                                    "" if d["surrogate"] is None
                                    else "%.4f" % d["surrogate"]))
                if "--no-conv" not in args:
                    for t, b in zip(d["history_sec"], d["history"]):
                        conv_rows.append("%s,%s,%d,%.3f,%.4f"
                                         % (nm, arm, s, t, b))
                if flag:
                    print("  %s %s seed=%d%s" % (nm, arm, s, flag))

            # 案例分析只留一个种子的时刻表:甘特图是个案,多存只会让人误以为是统计结果。
            if nm == study and s == seeds[0]:
                d = os.path.join(OUT, "case_study")
                os.makedirs(d, exist_ok=True)
                for arm in ("B0", "B2"):
                    p = os.path.join(d, "%s_seed%d_%s.json"
                                     % (arm.replace("+", "plus"), s,
                                        nm.replace(" ", "_").replace("/", "")))
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump({"arm": arm, "case": nm, "seed": s,
                                   "contention": cont,
                                   "surrogate": res[arm]["surrogate"],
                                   "chain": res[arm]["chain"],
                                   **res[arm]["timetable"]}, f,
                                  ensure_ascii=False, indent=1)
                    print("    案例时刻表已写出 %s" % os.path.basename(p))

        n = len(seeds)
        got = {a: [r for r in cost_rows if r.startswith(nm + ",")
                   and ",%s," % a in r] for a in ("B0", "B1", "B2")}
        print("  已完成 %-14s 争用 %5.1f%%  ms/评价 B0 %s  B1 %s  B2 %s  累计 %.0fs"
              % (nm, 100.0 * cont,
                 *["%6.2f" % (sum(float(r.split(",")[6]) for r in got[a]) / n)
                   for a in ("B0", "B1", "B2")],
                 time.time() - t0))

    with open(os.path.join(OUT, "ladder_cost.csv"), "w",
              encoding="utf-8") as f:
        f.write("case,contention,arm,seed,decodes,runtime_sec,ms_per_eval,"
                "makespan,surrogate\n")
        f.write("\n".join(cost_rows) + "\n")
    print("\n逐次运行的成本已写入 output/ladder_cost.csv")

    if conv_rows:
        with open(os.path.join(OUT, "ladder_convergence.csv"), "w",
                  encoding="utf-8") as f:
            f.write("case,arm,seed,t_sec,best\n")
            f.write("\n".join(conv_rows) + "\n")
        print("收敛轨迹已写入 output/ladder_convergence.csv(%d 行)"
              % len(conv_rows))

    print("\n提醒:B0 与 B0+ 共用同一次开环搜索,故两行的 decodes/ms_per_eval 相同,")
    print("  差别只在执行方式。画成本图时不要把它们当成两次独立的搜索。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
