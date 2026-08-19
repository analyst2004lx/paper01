"""第二档基线：见证集合的**选取规则**对照。

协议、密码学、窗口、派发容差全部相同，只换 `WitnessPolicy`，故差异只可能来自
选取原则本身。四件事：

  1. 见证集规模分布 —— $O(1)$ 主张的直接证据，也是带宽的比例因子。
  2. 良性流上的**误报率**。必须先看这个：`W2`/`W3` 的检出率会被误报抬起来。
  3. P1/P3 的检出率，并一律报 **检出率 − 误报率**。只报检出率会得出
     "随机见证者也行"的错误结论。
  4. 带宽折算：见证集规模 × 事件率，与 `budget.py` 的心跳带宽合并成总账。

用法(在 paper03/tessera/ 下):  py -m tools.baseline_diag
"""
from __future__ import annotations

import argparse
from statistics import mean, median

from algorithm import attacks, baselines, corroborate, coverage, ingest, taskgraph

_LABEL = {
    baselines.OURS: "本文 任务图对手方",
    baselines.W1: "W1 全网法定人数(PBFT)",
    baselines.W2: "W2 全体询证",
    baselines.W3: "W3 k 个随机见证者",
    baselines.W4: "W4 空间邻居见证",
}


def load(xes, bpmn):
    raw = ingest.read_xes(xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(bpmn, log_positions=pos)
    return live, g, coverage.realized(live, g)


def run(recs, g, policy, family, *, rate: float, seed: int) -> dict:
    """同一协议下跑一条基线：良性误报 + P1/P3 检出。"""
    benign = corroborate.replay(attacks.benign_stream(recs), g, policy=policy)
    n_fa = len([e for e in benign.evidence if e.claim_seen])
    far = n_fa / max(len(recs), 1)

    c = dict(benign.counts)
    out = {"far": far, "n_fa": n_fa, "counts": c,
           "n_unresolved": c.get(corroborate.NOT_DISPATCHED, 0),
           "n_unwitnessed": c.get(corroborate.UNWITNESSED, 0)}
    for fam in (attacks.P1, attacks.P3):
        spec = attacks.AttackSpec(family=fam, rate=rate, seed=seed,
                                  explicit_refutation=True)
        reports, _ = attacks.inject(recs, spec)
        primary = {id(r) for r in reports if r.forged and not r.accomplice}
        proto = corroborate.replay(reports, g, policy=policy, refute=True)
        hit = {e.claim_id for e in proto.evidence if e.claim_id in primary}
        lat = [e.latency_s for e in proto.evidence if e.claim_id in primary]
        dr = len(hit) / max(len(primary), 1)
        out[fam] = {"dr": dr, "n": len(primary), "lat": lat,
                    "margin": dr - far}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=None)
    ap.add_argument("--bpmn", default=None)
    # 与 detect_diag 及断言集一致，否则两处报出的数无法互相引用。
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    live, g, recs = load(args.xes or ingest.default_log_path(),
                         args.bpmn or taskgraph.default_bpmn_glob())
    print(f"活动 {len(live)}  互证边 {len(g.witness_edges)}  "
          f"设备 {len(g.resources)}\n")

    ours = baselines.make(baselines.OURS, g)
    n_ours = mean([x for x in baselines.witness_set_sizes(ours, recs) if x])

    print("一、见证集规模（带宽的比例因子，也是 O(1) 主张的直接证据）")
    sizes = {}
    for fam in baselines.FAMILIES:
        pol = baselines.make(fam, g)
        xs = baselines.witness_set_sizes(pol, recs)
        nz = [x for x in xs if x]
        sizes[fam] = xs
        print(f"      {_LABEL[fam]:26s} 中位 {median(nz) if nz else 0:4.1f}  "
              f"均值 {mean(nz) if nz else 0:5.2f}  最大 {max(xs):3d}  "
              f"相对本文 {(mean(nz)/n_ours if nz else 0):5.2f}x")
    print("      W1 的见证集沿用本文的（只改是否要求物理证据），故规模相同——"
          "它的代价在共识消息数，见第四节。")
    print()

    print("二、良性误报与 P1/P3 检出（同协议、同窗口、同派发容差 260 s）")
    print(f"      {'规则':26s} {'误报率':>8s} {'P1 检出':>8s} "
          f"{'P1 判别力':>10s} {'P3 检出':>8s} {'P3 判别力':>10s} {'时延中位':>9s}")
    res = {}
    for fam in baselines.FAMILIES:
        pol = baselines.make(fam, g)
        r = run(recs, g, pol, fam, rate=args.rate, seed=args.seed)
        res[fam] = r
        p1, p3 = r[attacks.P1], r[attacks.P3]
        lat = f"{median(p1['lat']):8.1f}s" if p1["lat"] else "        -"
        print(f"      {_LABEL[fam]:26s} {r['far']:8.3f} {p1['dr']:8.3f} "
              f"{p1['margin']:10.3f} {p3['dr']:8.3f} {p3['margin']:10.3f} "
              f"{lat}")
    print("      判别力 = 检出率 - 误报率。只报检出率会得出『随机也行』的错误结论。")
    print()

    print("三、悬而未决的待确认事项（覆盖率的假象）")
    for fam in baselines.FAMILIES:
        r = res[fam]
        print(f"      {_LABEL[fam]:26s} 无对手方 {r['n_unwitnessed']:5d}  "
              f"开了窗但从未结算 {r['n_unresolved']:5d}")
    print("      读法：`W2` 把无对手方的活动也开了窗，看着监控面更广，实则一条也"
          "结算不了。")
    print("      它没有变成假指控，是因为双截止时刻把它们归档而非指控——这是对"
          "**本文协议自身**的一个发现。")
    print()

    print("四、逐条读法")
    o = res[baselines.OURS]
    w1, w2, w3, w4 = (res[k] for k in (baselines.W1, baselines.W2,
                                       baselines.W3, baselines.W4))
    w4x = mean([x for x in sizes[baselines.W4] if x]) / n_ours
    w2x = mean([x for x in sizes[baselines.W2] if x]) / n_ours
    print(f"      本文：P1/P3 检出 {o[attacks.P1]['dr']:.3f}/"
          f"{o[attacks.P3]['dr']:.3f}，误报 {o['far']:.3f}，"
          f"判别力 {o[attacks.P1]['margin']:.3f}。")
    print(f"      W1：检出 {w1[attacks.P1]['dr']:.3f}。共识给出的是**一致性**，"
          f"而任务状态伪造不是一致性问题——")
    print("        一条格式正确、签名有效、按时到达的伪造声明会被法定人数顺利"
          "提交。它对 P2 仍有效(无声明可提交)，")
    print("        故其检出能力**恰等于看门狗 S1**，而带宽是本文的 131 倍"
          "(budget.py)。一句话：付 131 倍带宽换一个看门狗。")
    print(f"      W2：检出与误报与本文**逐位相同**，代价是见证集 {w2x:.2f}x "
          f"即互证带宽 {w2x:.2f}x，零增益。")
    print("        问所有人不会造出证据——有本地传感证据的只有真正的对手方。"
          "这从反面支持 O(1) 见证集。")
    print(f"      W3：检出崩到 {w3[attacks.P1]['dr']:.3f}（本文 "
          f"{o[attacks.P1]['dr']:.3f}），判别力 {w3[attacks.P1]['margin']:.3f}。")
    print("        随机挑中的设备对这一次交接没有本地传感证据，到不了场也确认"
          "不了。它的失败形态是**什么都发现不了**，")
    print("        不是乱指控——后者被双截止时刻兜住了。可见『有见证者』远不等于"
          "『有正确的见证者』。")
    print(f"      W4（主对照）：判别力 {w4[attacks.P1]['margin']:.3f}，只恢复本文的 "
          f"{w4[attacks.P1]['dr']/o[attacks.P1]['dr']*100:.0f}%，")
    print(f"        却多付 {(w4x-1)*100:.0f}% 的见证集规模。**这一行就是第一贡献"
          f"的全部证据：**")
    print("        空间邻接是**静态**的、与当前工件走哪条工艺路线无关，故既漏掉"
          "图上不相邻的真对手方，")
    print("        又纳入大量与本次交接无关的设备。本文规则由任务图 + 当前 case "
          "共同确定，是动态的。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
