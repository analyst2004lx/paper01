"""M1/M2/M5 落地后的回归校核:与 database/ 下探针脚本的已验证数字对齐。

目标数字(derive_invariants_v4.py 与 probe_structural_v3.py 的产出):
    282 个 case / 3,062 个活动(排除 failure)
    F   953 次检查, 0 违反      -> 0.00%
    I   2,768 次检查, 47 违反   -> 1.70%   (LATE 17 / NEVER 29 / FAILED 1)
    移动 1,791 次, 47 次未建模  -> 覆盖率 97.38%
    case 级链 21 个状态 / 2,780 次转移 / 140 个变体

用法(在 paper02/slid/ 下):  py -m tools.model_diag
"""
from __future__ import annotations

import argparse

from algorithm import ingest, interlock, procmodel


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    every = ingest.valid(raw, drop_failure=False)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=log_pos)

    print(f"M1  解析: {len(raw)} 个活动实例, 排除 failure 后 {len(live)}")
    print(f"    资源 {len({a.device for a in live})}  "
          f"操作 {len({a.op for a in live})}  "
          f"工作流 {len({a.workflow for a in live if a.workflow})}  "
          f"case {len({a.case for a in live})}")
    print()
    print(f"M2  从 {model.n_models} 个 BPMN 导出: "
          f"资源 {len(model.resources)}  操作 {len(model.operations)}  "
          f"位置 {len(model.positions)}  物料流边 {len(model.move_graph)}  "
          f"设备内操作对 {model.n_feasible_pairs}")
    cov, gaps = procmodel.coverage(model, live)
    n_move = sum(1 for a in live if a.is_move)
    print(f"    参考模型覆盖率 {cov*100:.2f}%  "
          f"({n_move - sum(gaps.values())}/{n_move} 次移动)")
    if gaps:
        print("    未建模的移动(按'未知'处理,不记为违反):")
        for (s, e), n in sorted(gaps.items(), key=lambda kv: -kv[1])[:5]:
            print(f"        {n:4d}  {s} -> {e}")
    print()

    by_case = ingest.case_chains(live)
    all_by_case = ingest.case_chains(every)
    _, cnt = interlock.check_all(by_case, model, all_by_case=all_by_case)
    s = interlock.summary(cnt)
    print(f"M5  回放 {s['cases']} 个 case, {s['activities']} 个活动")
    print(f"    F  {s['F_checked']:5d} 次检查  {s['F_violations']:4d} 违反  "
          f"{s['F_rate']*100:6.2f}%   -> 硬约束")
    print(f"    I  {s['I_checked']:5d} 次检查  {s['I_violations']:4d} 违反  "
          f"{s['I_rate']*100:6.2f}%   -> 软证据")
    print(f"       成因  LATE {s['cause_LATE']}  NEVER {s['cause_NEVER']}  "
          f"FAILED {s['cause_FAILED']}")
    print(f"    因果缺失 {s['causal_violations']} 次")
    print(f"    有 I 违反的 case: {s['cases_with_I_viol']}/{s['cases']}")
    print()

    gran, diag = ingest.chain_granularity(live)
    print(f"M3  结构链粒度自动判别 -> {gran} 级")
    print(f"    (设备, case) 链 {diag['n_chains']} 条  "
          f"平均长度 {diag['mean_len']:.2f}  "
          f"长度为 1 的占 {diag['frac_singleton']*100:.1f}%  "
          f"产出转移 {diag['n_transitions']}")
    seqs = {c: [a.op for a in v] for c, v in by_case.items()}
    states = {s for v in seqs.values() for s in v}
    n_tr = sum(len(v) - 1 for v in seqs.values() if len(v) > 1)
    variants = len({tuple(v) for v in seqs.values()})
    print(f"    case 级链: {len(states)} 个状态  {n_tr} 次转移  "
          f"{len(seqs)} 个 case  {variants} 个变体")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
