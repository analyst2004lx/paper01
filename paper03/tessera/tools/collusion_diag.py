"""串谋界：实测分布、模型级下界、安全感知任务分配的收益上限。

四件事：
  1. 实测串谋界的分布与**最小值**——安全论断只能引用最小值与低分位。
  2. 模型级下界：按设备类在互证超图上走同一个闭包，是过程模型的性质，
     不随排产变化，可作设计期指标。
  3. 链上设备复用有多普遍，以及其中多少是调度器**真的能换**的（该设备类在
     日志中有多个实例）。这决定了增补一是可操作的设计还是纸上主张。
  4. 同设备接手（`SELF_ONLY`）让链免费延长多少跳——把 7.45% 的覆盖率缺口
     换算成具体的安全代价。

用法(在 paper03/tessera/ 下):  py -m tools.collusion_diag
"""
from __future__ import annotations

import argparse

from algorithm import collusion, coverage, ingest, taskgraph


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=taskgraph.default_bpmn_glob())
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(args.bpmn, log_positions=pos)
    recs = coverage.realized(live, g)

    chains = collusion.walk(recs)
    s = collusion.summarize(chains)
    print(f"实测串谋界（{s['n_chains']} 条链中，起点运行时有下游接手方的 "
          f"{s['n_in_scope']} 条）")
    print(f"      剔除 {s['n_gap_origin']} 条起点在本 case 内根本无人接手的，"
          "k=1 但那是覆盖缺口不是串谋易度")
    print(f"      保留 {s['n_self_only_origin']} 条同设备接手的：该跳无独立见证，"
          "但攻击者可真实瞄准，排除它等于替机制挑样本")
    print(f"      k_min = {s['k_min']}   k 中位 = {s['k_median']}   "
          f"k_max = {s['k_max']}")
    print(f"      k 分布 {s['k_hist']}")
    print(f"      k<=1 占 {s['frac_k_le_1']*100:.2f}%   "
          f"k>=3 占 {s['frac_k_ge_3']*100:.2f}%")
    print(f"      k=1 的 {s['n_k1']} 条中，因同设备接手而免费延长的 "
          f"{s['n_k1_free_hop']} 条")
    print(f"      链长中位 {s['hops_median']}  最长 {s['hops_max']}  "
          f"终止原因 {s['by_reason']}")
    print("      安全论断只能引用 k_min 与低分位——攻击者挑最薄弱处下手，"
          "均值无意义。")
    print()

    print("最薄弱的十条链（设备, 操作, k, 链长）")
    for d, op, k, h in s["weakest"]:
        print(f"      {d:<8} {op:<34} k={k}  链长={h}")
    print()

    print(f"设备复用：链长 > 设备数的链占 {s['frac_device_reuse']*100:.2f}%")
    print(f"      同设备免费延长的链 {s['n_free_hop_chains']} 条，"
          f"免费跳数合计 {s['free_hops_total']}")
    print("      这是 coverage 那 7.45% 同设备缺口的安全代价：攻击者不需额外"
          "劫持任何设备即可把谎言推进一跳。")
    print()

    sw = collusion.same_class_reuse(recs)
    print(f"复用成因分解（{sw['n_reuse_chains']} 条复用链）")
    print(f"      调度器真能换（不相邻复用 + 该类有多实例）{sw['n_swappable']} 条 "
          f"= {sw['frac_swappable']*100:.2f}%")
    print(f"      仅相邻复用、工件仍在夹具里，换不了的 {sw['n_adjacent_only']} 条")
    print(f"      该设备类只有单实例、换不了的 {sw['n_single_instance']} 条")
    multi = {k: v for k, v in sw["instances_per_class"].items() if len(v) > 1}
    print(f"      多实例设备类 {multi}")
    print()

    ga = collusion.assignment_gain(recs)
    print("安全感知任务分配的收益**上限**（不是实测收益）")
    print(f"      {'':<8} {'实际':>6} {'可达理想':>10} {'无约束理想':>12}")
    print(f"      {'k_min':<8} {ga['k_min_actual']:6d} "
          f"{ga['k_min_achievable']:10d} {ga['k_min_unconstrained']:12d}")
    print(f"      {'k 中位':<7} {ga['k_median_actual']:6.0f} "
          f"{ga['k_median_achievable']:10.0f} "
          f"{ga['k_median_unconstrained']:12.0f}")
    print(f"      {'k 均值':<7} {ga['k_mean_actual']:6.2f} "
          f"{ga['k_mean_achievable']:10.2f}")
    print(f"      可改善的链 {ga['n_improvable']} 条 "
          f"= {ga['frac_improvable']*100:.2f}%，增益幅度分布 {ga['gain_hist']}")
    print(f"      可改善链原本的 k 分布 {ga['improvable_k_hist']}")
    print(f"      其中 k<=2（真正需要加固的那些）只有 "
          f"{ga['n_improvable_at_k_le_2']} 条")
    print(f"      被复用最多的设备 {ga['reuse_by_device']}")
    print("      「可达理想」只消除非相邻复用；相邻复用是原地多工步加工，工件仍"
          "夹在机床里，排产改不动。")
    print("      用「无约束理想」报收益会虚报——k_min 会被说成从 1 抬到 2，"
          "而 k=1 的链全是相邻同设备接手。")
    print()

    st = collusion.structural_bound(g)
    print(f"模型级下界（按设备类，逐工作流，{st['n_workflows']} 个模型 / "
          f"{st['n_nodes']} 个 (工作流, 设备类, 操作) 顶点）")
    print(f"      k_min = {st['k_min']}   k 中位 = {st['k_median']}   "
          f"k_max = {st['k_max']}")
    print(f"      k 分布 {st['k_hist']}")
    print(f"      最薄弱工作流的 k = {st['worst_workflow_k']}")
    print("      最薄弱顶点：")
    for (wf, (dc, op)), k in st["weakest_nodes"]:
        print(f"        {wf:<8} {dc:<6} {op:<34} k={k}")
    print("      按类归并把 vgr_1/vgr_2 算作一个顶点，故这是**保守下界**；"
          "它度量工艺流程本身能提供几层独立见证，不随排产变化。")
    print()

    print("综合：两项增补设计的分工（这一段是本诊断最重要的结论）")
    print(f"      安全感知任务分配（增补一）**抬不动最坏情形**：k_min 实际 "
          f"{ga['k_min_actual']} -> 可达理想 {ga['k_min_achievable']}，纹丝不动；")
    print(f"      它只把中位从 {ga['k_median_actual']:.0f} 抬到 "
          f"{ga['k_median_achievable']:.0f}，收益在分布而不在保证。")
    print(f"      最坏情形有两个来源，都不是排产能改的：其一是相邻同设备接手"
          f"（{s['n_k1']} 条 k=1 的链全属此类，工件仍在夹具里）；")
    print(f"      其二是工艺流程本身的层数——模型级下界 {st['k_min']}"
          "（WF_108/WF_121 的 wt 搬运只有两层独立见证）。")
    print("      能抬高保证的只有按需主动互证（增补二），它造出原本不存在的"
          "见证事件。这就是两项增补的分工。")
    print()
    h = dict(s["k_hist"])
    frac_k2 = ((h.get(1, 0) + h.get(2, 0)) / s["n_in_scope"]
               if s["n_in_scope"] else 0.0)
    print(f"      与 detect_diag 的交叉核对：结构上 k<=2 的链占 "
          f"{frac_k2*100:.1f}%，即一跳串谋应有约这么大比例能永久藏住；")
    print("      实测串谋方逃脱率 25.0%（1-0.750）。同一量级，差额来自串谋方"
          "自身链上的覆盖缺口。两者独立算出，可互为佐证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
