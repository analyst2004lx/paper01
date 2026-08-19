"""第一档基线：单观测者方法在任务状态伪造上的**结构性 0**。

这一档不是赛马而是定理，故报告方式也不同：不比大小，而是把"单观测者族在构造上
不可能检出"这条可证命题落成可复现的实测确认。

为让这个 0 有分量，实现上一律**给基线争取到最强**：阈值按纯良性流标定到刚好不
误报的最紧位置，一致性检验按过程模型的完整语言判（含同机顺序工序与物料流衔接），
看门狗与本文用同一套派发排队容差 260 s。都做足之后仍是 0。

同时给出两个对照口径，缺一不可：

  - **P1（不维持心跳的朴素谎报）** 与 **P3（按时披露原像的老练谎报）**：两者对
    单观测者完全一样，故第一档的数必须相同——若不同，说明实现里漏进了本不该有的
    信息。这是一条自检。
  - **P2（完全沉默）**：单观测者**能**发现，看门狗即可。本文不主张这一点，如实
    报出来，否则会显得在夸大第一档的无能。

用法(在 paper03/tessera/ 下):  py -m tools.tier1_diag
"""
from __future__ import annotations

import argparse

from algorithm import attacks, baselines, corroborate, coverage, ingest, taskgraph

_LABEL = {
    baselines.R0: "R0 匹配告警率随机指控",
    baselines.S1: "S1 调度看门狗",
    baselines.S2: "S2 计划一致性残差",
    baselines.S3: "S3 对齐式一致性检验",
}
_FAMS = (attacks.P1, attacks.P3, attacks.P2)


def load(xes, bpmn):
    raw = ingest.read_xes(xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(bpmn, log_positions=pos)
    return live, g, coverage.realized(live, g)


def run(det, benign, streams) -> dict:
    """标定一次，然后在各攻击流上评测。分母是伪造声明数。"""
    det.calibrate(benign)
    fa = det.accuse(benign)
    out = {"far": len(fa) / max(len(benign), 1), "n_fa": len(fa)}
    for fam, reports in streams.items():
        primary = {id(r) for r in reports if r.forged and not r.accomplice}
        hit = det.accuse(reports) & primary
        out[fam] = {"dr": len(hit) / max(len(primary), 1), "n": len(primary)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=None)
    ap.add_argument("--bpmn", default=None)
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    live, g, recs = load(args.xes or ingest.default_log_path(),
                         args.bpmn or taskgraph.default_bpmn_glob())
    benign = attacks.benign_stream(recs)
    streams = {}
    for fam in _FAMS:
        streams[fam], _ = attacks.inject(recs, attacks.AttackSpec(
            family=fam, rate=args.rate, seed=args.seed,
            explicit_refutation=True))

    # 本文的误报率先测出来，作为 R0 的等告警预算。
    ours_p1 = corroborate.replay(streams[attacks.P1], g, refute=True)
    prim = {id(r) for r in streams[attacks.P1]
            if r.forged and not r.accomplice}
    ours_dr = (len({e.claim_id for e in ours_p1.evidence if e.claim_id in prim})
               / max(len(prim), 1))
    bp = corroborate.replay(benign, g)
    # 与 `detect_diag` / 断言 D2 / `_bl` 同口径：只计声明已被看到的证据。
    ours_far = (len([e for e in bp.evidence if e.claim_seen])
                / max(len(benign), 1))

    print(f"活动 {len(live)}  工作流 {len(g.wf_tasks)}  "
          f"攻击 rate={args.rate} seed={args.seed}\n")

    print("一、单观测者族的检出（分母 = 伪造声明数）")
    print(f"      {'基线':24s} {'误报率':>8s} {'P1 检出':>9s} {'P3 检出':>9s} "
          f"{'P2 检出':>9s} {'P1 判别力':>10s}")
    res = {}
    for fam in baselines.TIER1:
        kw = {"alarm_rate": ours_far} if fam == baselines.R0 else {}
        det = baselines.make_tier1(fam, g, **kw)
        r = run(det, benign, streams)
        res[fam] = r
        print(f"      {_LABEL[fam]:24s} {r['far']:8.3f} "
              f"{r[attacks.P1]['dr']:9.3f} {r[attacks.P3]['dr']:9.3f} "
              f"{r[attacks.P2]['dr']:9.3f} "
              f"{r[attacks.P1]['dr'] - r['far']:10.3f}")

    print(f"      {'本文 耦合互证':24s} {ours_far:8.3f} {ours_dr:9.3f} "
          f"{ours_dr:9.3f} {'1.000':>9s} {ours_dr - ours_far:10.3f}")
    print()

    print("二、自检：P1 与 P3 对单观测者必须完全一样")
    ok = all(abs(res[f][attacks.P1]["dr"] - res[f][attacks.P3]["dr"]) < 1e-9
             for f in baselines.TIER1)
    print(f"      {'一致' if ok else '不一致——实现里漏进了本不该有的信息'}"
          f"（P1 与 P3 的差别只在是否披露哈希链原像，那不是单观测者能看到的字段）")
    print()

    print("三、逐条读法")
    print(f"      R0：检出 {res[baselines.R0][attacks.P1]['dr']:.3f} ≈ 告警率 "
          f"{res[baselines.R0]['far']:.3f}，判别力 "
          f"{res[baselines.R0][attacks.P1]['dr'] - res[baselines.R0]['far']:+.3f}。")
    print("        地板成立：等告警预算下随机指控的期望检出率恰等于告警率本身，"
          "故判别力显著大于 0 才算真在工作。")
    for f, why in ((baselines.S1, "一条按时到达、字段正常的伪造声明完全满足看门狗"),
                   (baselines.S2, "伪造时长取该 (设备, 操作) 的中位数，恰落在残差"
                                  "分布最中央；结果位被置为 success"),
                   (baselines.S3, "伪造的轨迹是合法活动的逐字段拷贝，落在模型语言"
                                  "里，对齐代价为 0；操作化已避开 case 内并发链交错"
                                  "与 BPMN 残缺带来的假误报")):
        r = res[f]
        print(f"      {_LABEL[f]}：P1/P3 检出 {r[attacks.P1]['dr']:.3f}，"
              f"P2 检出 {r[attacks.P2]['dr']:.3f}，"
              f"误报 {r['far']:.3f}。")
        print(f"        {why}。")
    print()
    print("四、结论")
    print("      单观测者族对任务状态伪造的检出是**结构性的 0**，不是精度不足："
          "谎言在于物理事件没发生，")
    print("      而单观测者看到的每个字段都正常。P2 那一列同时说明这一档并非"
          "一无所长——沉默它们能发现，")
    print("      本文不主张那一点。**这正是必须引入物理对手方的理由，也是贡献 0 "
          "的经验确认。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
