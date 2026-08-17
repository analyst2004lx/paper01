"""互证超图与覆盖度诊断。

第一件必须量化的事:16 个 BPMN 到底给出多少条耦合边、覆盖日志里多少比例的
活动。这是耦合互证机制的**结构性上限**,与 paper02 那个"二元可行性掩码只
覆盖 31% 的消息"是同一类问题。

同时校核解析口径是否与 paper02 一致(同一份日志,数字必须对得上):
    282 个 case / 3,062 个活动(排除 failure)/ 3,157 个含 failure
    BPMN: 16 个模型 / 15 个资源 / 21 个操作 / 23 个位置 / 31 条物料流边

用法(在 paper03/tessera/ 下):  py -m tools.graph_diag
"""
from __future__ import annotations

import argparse
from collections import Counter

from algorithm import coverage, ingest, taskgraph


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=taskgraph.default_bpmn_glob())
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    every = ingest.valid(raw, drop_failure=False)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(args.bpmn, log_positions=log_pos)

    print(f"解析  {len(raw)} 个活动实例, 排除 failure 后 {len(live)} "
          f"(含 failure {len(every)})")
    print(f"      资源 {len({a.device for a in live})}  "
          f"操作 {len({a.op for a in live})}  "
          f"case {len({a.case for a in live})}  "
          f"工作流 {len({a.workflow for a in live if a.workflow})}")
    print()

    print(f"任务图  {g.n_models} 个 BPMN -> 资源 {len(g.resources)}  "
          f"操作 {len(g.operations)}  位置 {len(g.positions)}  "
          f"物料流边 {len(g.move_graph)}")
    print(f"互证超图  边 {len(g.witness_edges)}  "
          f"交接位置 {len(g.handover_positions)}  "
          f"可证的 (设备类, 操作) {len({e.producer for e in g.witness_edges})}")

    fan = Counter(e.producer for e in g.witness_edges)
    dclasses = {p[0] for p in fan}
    print(f"      涉及设备类 {len(dclasses)}: {' '.join(sorted(dclasses))}")
    if fan:
        sizes = sorted(len({e.consumer for e in g.witness_edges
                            if e.producer == p}) for p in fan)
        print(f"      见证集合规模  中位 {sizes[len(sizes)//2]}  "
              f"最大 {sizes[-1]}   <- O(1) 主张的依据")
    print()

    gaps = coverage.no_counterparty_ops(g)
    n_pairs = sum(len(v) for v in g.capable.values())
    print(f"无对手方区间  {len(gaps)}/{n_pairs} 个 (设备类, 操作) 在模型上"
          f"无从互证")
    for dc, op in sorted(gaps):
        print(f"      {dc:8s} {op}")
    print()

    recs = coverage.realized(live, g)
    s = coverage.summarize(recs)
    n = s["n_activities"]
    print(f"覆盖度  回放 {n} 个活动")
    for label, k in (("已互证(有独立对手方)", "n_corroborated"),
                     ("接手方为同一台设备", "n_same_device_only"),
                     ("本 case 内无人接手", "n_no_realized"),
                     ("模型上无对手方", "n_no_model")):
        print(f"      {label:<22s} {s[k]:5d}  {s[k]/n*100:6.2f}%")
    print(f"      未覆盖的 {n - s['n_corroborated']} 个中, "
          f"case 末位 {s['n_gap_terminal']}, "
          f"链中 {s['n_gap_midchain']}")
    print()

    print(f"互证窗口 Δ  样本 {s['delay_n']}  "
          f"负延迟 {s['delay_negative']} (并发乱序, 非互证失败)")
    print(f"      中位 {s['delay_median_s']:.1f}s  "
          f"p90 {s['delay_p90_s']:.1f}s  p95 {s['delay_p95_s']:.1f}s  "
          f"max {s['delay_max_s']:.1f}s")
    print()

    print("按 (设备类, 操作) 分解  [总数 已证 同类 无人接手 模型无]")
    per: dict[tuple[str, str], Counter] = {}
    for r in recs:
        per.setdefault(r.key, Counter())[r.status] += 1
    for key, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(c.values())
        print(f"      {key[0]:5s} {key[1]:<32s} {tot:5d} "
              f"{c[coverage.OK]:5d} {c[coverage.SELF_ONLY]:5d} "
              f"{c[coverage.NO_REALIZED]:5d} {c[coverage.NO_MODEL]:5d}   "
              f"{c[coverage.OK]/tot*100:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
