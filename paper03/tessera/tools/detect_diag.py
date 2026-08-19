"""P1–P4 的检出率与检测时延，以及组合必要性的消融。

四件事：
  1. **P1 的构造性质核验**：伪造声明在单观测者可见的每个字段上都与良性一致。
     这比重跑残差检测器更强的主张——它说明残差类方法的失效是构造上的。
  2. 良性流上的误报，验证协议在无攻击时不产生证据。
  3. P1–P4 逐族的检出率与时延，分"对手方有到料传感器（可否证）"与"无传感器
     （只能等超时）"两个口径。
  4. **消融**：看门狗（基线 `S1`）/ 只用耦合互证 / 只用可问责沉默 / 两者合用。
     这是回应"为何必须是组合方法"的直接材料。

用法(在 paper03/tessera/ 下):  py -m tools.detect_diag
"""
from __future__ import annotations

import argparse
from statistics import median

from algorithm import (attacks, corroborate, coverage, ingest, silence,
                       taskgraph)


def _pct(xs, q):
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def _fmt(xs, q=None):
    if not xs:
        return "      -"
    return f"{(median(xs) if q is None else _pct(xs, q)):6.1f}s"


def load(xes, bpmn):
    raw = ingest.read_xes(xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(bpmn, log_positions=pos)
    return live, g, coverage.realized(live, g)


def evaluate(recs, g, family, *, refute: bool, rate: float, seed: int) -> dict:
    """跑一族攻击，按声明身份对齐真值与证据。

    检出率的分母是**伪造声明数**，不含对手方的否证消息（那是诚实设备发的）。
    """
    spec = attacks.AttackSpec(family=family, rate=rate, seed=seed,
                              explicit_refutation=refute)
    reports, _ = attacks.inject(recs, spec)
    primary = {id(r) for r in reports if r.forged and not r.accomplice}
    accomp = {id(r) for r in reports if r.accomplice}
    proto = corroborate.replay(reports, g, refute=refute)

    hit = [e for e in proto.evidence if e.claim_id in primary]
    hit_acc = [e for e in proto.evidence if e.claim_id in accomp]
    fp = [e for e in proto.evidence
          if e.claim_id not in primary and e.claim_id not in accomp
          and e.claim_seen]
    return {
        "n_forged": len(primary),
        "n_accomplice": len(accomp),
        "n_hit": len({e.claim_id for e in hit}),
        "n_hit_accomplice": len({e.claim_id for e in hit_acc}),
        "n_fp": len(fp),
        "dr": len({e.claim_id for e in hit}) / max(len(primary), 1),
        "dr_accomplice": (len({e.claim_id for e in hit_acc})
                          / max(len(accomp), 1)),
        "lat": [e.latency_s for e in hit],
        "by_outcome": {o: sum(1 for e in hit if e.outcome == o)
                       for o in (corroborate.REFUTED, corroborate.EXPIRED)},
        "n_self_incrim": sum(1 for e in hit if e.self_incriminating),
        "counts": dict(proto.counts),
        "reports": reports,
        "forged": primary,
    }


def watchdog_dr(res, cfg: corroborate.CorroborateConfig
                ) -> tuple[float, list[float]]:
    """基线 `S1`：GOOSE 式看门狗，只看"该报的没报"。

    工业协议早有先例（IEC 61850 的 MaxTime 与 fail-safe），本文不主张这一点。
    它对 P2 有效，对 P1/P3/P4 完全无效——一条按时到达、字段正常的伪造声明
    完全满足看门狗。

    **窗口必须与本文一致地加上派发排队容差**，否则是在给基线设障：不加容差时
    看门狗在良性流上要误报约四分之一（派发时延 p95 218.3 s 远超 planned 窗口）。
    """
    caught = [r for r in res["reports"]
              if id(r) in res["forged"] and r.withheld]
    return (len(caught) / max(res["n_forged"], 1),
            [cfg.corr_window_s(r.act.planned_s) for r in caught])


def silence_dr(res, cfg: silence.SilenceConfig) -> tuple[float, list[float]]:
    """可问责沉默：只看原像是否按槽披露。

    对 P2 有效（未披露即确定性判定），对 P1/P3/P4 无效——攻击者按时披露原像的
    同时谎报完成，声明本身无从检验。这正是"仅可问责沉默"留下的逃脱口。
    """
    caught = [r for r in res["reports"]
              if id(r) in res["forged"] and not r.revealed]
    return (len(caught) / max(res["n_forged"], 1),
            [cfg.detect_delay_s] * len(caught))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=taskgraph.default_bpmn_glob())
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t-hb", type=float, default=0.2)
    ap.add_argument("--r-misses", type=int, default=9,
                    help="突发丢包口径下的连续缺失数，见 silence_diag")
    args = ap.parse_args()

    live, g, recs = load(args.xes, args.bpmn)
    scfg = silence.SilenceConfig(t_hb_s=args.t_hb, r_misses=args.r_misses)

    disp = [(a.t_start - a.t_cmd).total_seconds()
            for a in live if a.t_cmd and a.t_start]
    print(f"调度器派发时延（命令下发 -> 开始动作，{len(disp)} 个活动）")
    print(f"      中位 {median(disp):.1f}s  p90 {_pct(disp, 0.9):.1f}s  "
          f"p95 {_pct(disp, 0.95):.1f}s  p99 {_pct(disp, 0.99):.1f}s  "
          f"max {max(disp):.1f}s")
    print("      这段等待由调度器自己的队列决定，与交接无关，必须容纳进互证窗口。")
    print(f"      当前 dispatch_allowance_s = "
          f"{corroborate.CorroborateConfig().dispatch_allowance_s:.0f}s")
    print()

    bs = attacks.benign_stream(recs)
    print("排队容差扫参（良性流，纯误报口径；容差是必须付的代价，不是可调的旋钮）")
    print(f"      {'容差':>6} {'总告警':>10} {'其中声明已到':>14} "
          f"{'已确认':>8} {'最坏时延':>9}")
    for al in (0.0, 60.0, 130.0, 260.0, 400.0, 600.0):
        cfg = corroborate.CorroborateConfig(dispatch_allowance_s=al)
        p = corroborate.replay(bs, g, cfg)
        armed = [e for e in p.evidence if e.claim_seen]
        print(f"      {al:5.0f}s {len(p.evidence):6d} "
              f"({len(p.evidence)/len(recs)*100:5.2f}%) "
              f"{len(armed):6d} ({len(armed)/len(recs)*100:5.2f}%) "
              f"{p.counts[corroborate.CONFIRMED]:8d} "
              f"{cfg.corr_window_s(median([r.act.planned_s for r in recs if r.act.planned_s])):8.1f}s")
    print("      读法：容差换的是误报，付的是最坏检测时延。260 s 处总告警已降到"
          "平台，再加只增时延。")
    print()

    print("P1 的构造性质核验（伪造声明与良性活动逐字段一致）")
    rep = attacks.indistinguishability_report(
        recs, attacks.AttackSpec(family=attacks.P1, rate=args.rate,
                                 seed=args.seed))
    print(f"      伪造声明 {rep['n_forged']} 条")
    print("      " + "  ".join(f"{f}={v*100:.0f}%"
                               for f, v in rep["fields_intact"].items()))
    print(f"      时长落在该 (设备,操作) 良性四分位距内 "
          f"{rep['duration_in_iqr']*100:.1f}%")
    print("      -> 单观测者可见字段无任何残差，残差类检测结构性失效。")
    print()

    benign = attacks.benign_stream(recs)
    bp = corroborate.replay(benign, g, refute=True)
    armed = [e for e in bp.evidence if e.claim_seen]
    print(f"良性流误报  声明 {len(benign)} 条，证据 {len(bp.evidence)} 条 "
          f"= {len(bp.evidence)/len(benign)*100:.2f}%")
    print(f"      终局分布 {dict(bp.counts)}")
    print(f"      其中声明确实到达过的 {len(armed)} 条 "
          f"= {len(armed)/len(benign)*100:.2f}%  <- 这才是互证的误报")
    print("      注：EXPIRED 含 case 末位（282 条，无下游可作证）与对手方从未被"
          "派发两类结构缺口。")
    print()

    for refute in (True, False):
        tag = "对手方可否证" if refute else "对手方无传感器"
        print(f"检出率与时延  [{tag}]  注入率 {args.rate}")
        print(f"      {'族':<3} {'伪造':>5} {'检出':>5} {'DR':>6} "
              f"{'时延中位':>8} {'p95':>8} {'否证':>5} {'超时':>5} "
              f"{'自证':>5} {'次生':>5}")
        for fam in attacks.IMPLEMENTED:
            r = evaluate(recs, g, fam, refute=refute, rate=args.rate,
                         seed=args.seed)
            print(f"      {fam:<3} {r['n_forged']:5d} {r['n_hit']:5d} "
                  f"{r['dr']:6.3f} {_fmt(r['lat'])} {_fmt(r['lat'], 0.95)} "
                  f"{r['by_outcome'][corroborate.REFUTED]:5d} "
                  f"{r['by_outcome'][corroborate.EXPIRED]:5d} "
                  f"{r['n_self_incrim']:5d} {r['n_fp']:5d}")
            if fam == attacks.P4:
                print(f"           串谋方自身的下游声明: "
                      f"{r['n_hit_accomplice']}/{r['n_accomplice']} = "
                      f"{r['dr_accomplice']:.3f}  <- 谎言沿任务链传播时被截住")
        print("      「次生」不是误报：沉默/伪造的设备同时**拒绝为其上游作证**，"
              "上游的诚实声明因此超时。")
        print("      这是对无辜邻居的连带指控，也是必须与可问责沉默合用的第二个"
              "理由——沉默机制直接指认")
        print("      沉默者，上游的未确认声明才能被正确归因而非被冤枉。")
        print()

    print(f"消融：为何必须是组合方法  (T_hb={args.t_hb}s, r={args.r_misses}, "
          f"注入率 {args.rate})")
    print(f"      {'族':<3} | {'看门狗B5':>16} | {'仅耦合互证':>16} "
          f"| {'仅可问责沉默':>16} | {'合用':>16}")
    ccfg = corroborate.CorroborateConfig()
    for fam in attacks.IMPLEMENTED:
        r = evaluate(recs, g, fam, refute=True, rate=args.rate, seed=args.seed)
        wd, wl = watchdog_dr(r, ccfg)
        sd, sl = silence_dr(r, scfg)
        both_dr = max(r["dr"], sd)
        both_lat = sl if (sd >= r["dr"] and sl) else r["lat"]
        print(f"      {fam:<3} | {wd:6.3f} {_fmt(wl):>9} "
              f"| {r['dr']:6.3f} {_fmt(r['lat']):>9} "
              f"| {sd:6.3f} {_fmt(sl):>9} "
              f"| {both_dr:6.3f} {_fmt(both_lat):>9}")
    print()
    print("      读法：")
    print("        P1 朴素谎报者不维持心跳，两个机制都能抓，沉默快两个数量级。")
    print("        P2 沉默：看门狗与互证都要等调度队列（>300 s），沉默 1.8 s。")
    print("        P3 老练谎报者按时披露原像 —— **沉默机制毫无信号，只有互证能抓**。")
    print("           这是耦合互证不可被替代的直接证据，也是消融表最关键的一行。")
    print("        P4 串谋：两个机制同时失效，是承认的边界，由串谋界量化。")
    print("           但串谋方自身的下游声明仍会被下一跳诚实设备截住，")
    print("           故谎言要存活必须沿任务链每一跳都有被劫持设备。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
