"""A8 红队攻击:Fisher 合成路该不该留。

结论二十五用 score-level 的 `misplace`(打分时随机改前驱)测出 Fisher 0.413
对仅时序 0.108,于是留下"要么补 A8 要么撤合成路"的分叉。本工具把那次
人工扰动换成真正的注入器,再按 E1 主表口径(序贯@10、减偶然地板、总
alpha 固定)问三件事:

  Q1  A8 在 Trier 上是否可实现?找不到 F 允许的非众数后继就不能拿它
      为合成路背书,更不能用 score-level misplace 顶替。
  Q2  A8 是不是真的跨通道?硬层 DR 应近零(否则是 A2),时序与结构都应
      有可见残差(否则是 A3 或"弱 A4")。
  Q3  在生产配置(硬层+时序+结构)上再加 Fisher,A8 的增益是否大过它
      在 A1–A6 上的预算摊薄代价?

判定规则写在 verdict() 里,不在跑完后再解释。

用法(在 paper02/slid/ 下):  py -m tools.a8_fisher
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from algorithm import attacks, baselines, fusion, ingest, procmodel  # noqa: E402
from algorithm.detector import CHANNELS, Detector, DetectorConfig  # noqa: E402
from tools.baseline_diag import attack_stream, split  # noqa: E402

PATHS = ("硬层", "时序", "结构", "互锁", "合成")
COST_FAMS = ("A1", "A2", "A3", "A4", "A5", "A6")
#: 生产配置三路 vs 三路+Fisher。互锁权重恒 0:天花板判据已剔除它。
WEIGHTS = {
    "三路(现行)":     (1 / 3, 1 / 3, 1 / 3, 0.0, 0.0),
    "三路+Fisher":    (1 / 4, 1 / 4, 1 / 4, 0.0, 1 / 4),
    "仅时序":         (0.0, 1.0, 0.0, 0.0, 0.0),
    "仅结构":         (0.0, 0.0, 1.0, 0.0, 0.0),
    "仅Fisher":       (0.0, 0.0, 0.0, 0.0, 1.0),
}


def score_parts(det, stream, rng):
    """五路原始分数(越大越异常)。E1 口径:不做冻结 conformal,交给 judge。"""
    det._reset_online()
    rows = []
    for a in stream:
        hard = 1.0 if det._hard_layer(a) is not None else 0.0
        raw = det._score_one(a, rng=rng)
        fused = fusion.combine(raw, "fisher")
        rows.append((hard, -raw[0], -raw[1], -raw[2], -fused))
    det._reset_online()
    return [[r[j] for r in rows] for j in range(5)]


def net(det, benign, stream, lab, alpha, rng, weights):
    pb = score_parts(det, benign, np.random.default_rng(rng.integers(1 << 30)))
    pa = score_parts(det, stream, rng)
    _, _, sdr, sfpr, floor = baselines.judge(
        pb, pa, lab, alpha=alpha, weights=list(weights))
    return sdr - floor, sfpr


def coverage(det, stream, lab, alpha, rng):
    """逐通道单消息 DR/FPR,问的是看得见与否,不是端到端。"""
    det._reset_online()
    hard, pvals = [], []
    for a in stream:
        det._flush_pending(a.t_consume)
        hard.append(det._hard_layer(a) is not None)
        raw = det._score_one(a, rng=rng)
        pvals.append(det._recalibrate(raw, rng))
    det._reset_online()
    pos = [i for i, v in enumerate(lab) if v]
    neg = [i for i, v in enumerate(lab) if not v]
    out = {}
    out["hard"] = (float(np.mean([hard[i] for i in pos])),
                   float(np.mean([hard[i] for i in neg])))
    for j, ch in enumerate(CHANNELS):
        dr = float(np.mean([pvals[i][j] <= alpha for i in pos]))
        fp = float(np.mean([pvals[i][j] <= alpha for i in neg]))
        out[ch] = (dr, fp)
    fused = [fusion.combine(p, "fisher") for p in pvals]
    out["fused"] = (float(np.mean([fused[i] <= alpha for i in pos])),
                    float(np.mean([fused[i] <= alpha for i in neg])))
    return out


def injector_stats(test, spec):
    """A8 有多少受害者能真正落下,落下去的是不是非众数。"""
    tm = spec.struct_model
    bad, lab = attacks.inject(test, spec)
    n_hit = sum(lab)
    n_try = max(1, int(len([a for a in test if a.duration_s]) * spec.rate))
    modes = 0
    for a, hit in zip(bad, lab):
        if not hit:
            continue
        # 插入条的前驱是它在同 case 里、时刻更早的那条
        prev = None
        for b in bad:
            if b.case == a.case and b.t_consume is not None \
                    and a.t_consume is not None \
                    and b.t_consume < a.t_consume:
                if prev is None or b.t_consume > prev.t_consume:
                    prev = b
        if prev is None or tm is None:
            continue
        ranked = attacks._ranked_successors(tm, prev.op)
        if ranked and attacks._op_of_state(ranked[0][1]) == a.op:
            modes += 1
    skipped = getattr(spec, "_a8_skipped", 0)
    return {
        "injected": n_hit, "attempted": n_try, "skipped": skipped,
        "modal_hits": modes, "n_stream": len(bad),
    }


def verdict(stats, cov, a8, cost):
    """三条必须同时成立才留 Fisher,缺一条就撤。"""
    realizable = stats["injected"] >= 0.3 * stats["attempted"]
    not_a2 = cov["hard"][0] < 0.10
    multi = (cov["time"][0] - cov["time"][1] >= 0.05
             and cov["struct"][0] - cov["struct"][1] >= 0.05)
    gain = a8["三路+Fisher"] - a8["三路(现行)"]
    tax = cost["三路(现行)"] - cost["三路+Fisher"]   # >0 表示加 Fisher 在 A1-A6 上亏
    unique = gain >= 0.08
    worth = gain >= tax                           # A8 增益盖得住 A1-A6 的税
    stay = realizable and not_a2 and multi and unique and worth
    reasons = []
    if not realizable:
        reasons.append(
            f"A8 不可实现:注入 {stats['injected']}/{stats['attempted']} "
            f"(跳过 {stats['skipped']}),低于 30% 门槛")
    if not not_a2:
        reasons.append(f"A8 退化成 A2:硬层 DR={cov['hard'][0]:.2f} ≥ 0.10")
    if not multi:
        reasons.append(
            f"A8 不是跨通道:时序提升 {cov['time'][0]-cov['time'][1]:+.2f},"
            f"结构提升 {cov['struct'][0]-cov['struct'][1]:+.2f}(需两边 ≥0.05)")
    if not unique:
        reasons.append(
            f"Fisher 无独特贡献:三路+Fisher 相对现行三路仅 {gain:+.2f}(<0.08)")
    if not worth:
        reasons.append(
            f"A8 增益 {gain:+.2f} 盖不住 A1–A6 上的摊薄 {tax:+.2f}")
    if stay:
        reasons.append(
            f"A8 增益 {gain:+.2f} ≥ A1–A6 摊薄 {tax:+.2f},且硬层/跨通道/可实现均过")
    return stay, reasons, gain, tax


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--rate", type=float, default=0.20)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)
    benign = baselines.order_stream(test)

    det = Detector(DetectorConfig(alpha=args.alpha,
                                  online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)

    spec0 = attacks.AttackSpec(family="A8", rho=args.rho, rate=args.rate,
                               seed=0, knowledge="model",
                               struct_model=det.struct, proc_model=model)
    st = injector_stats(test, spec0)
    print(f"=== A8 × Fisher 去留(alpha={args.alpha}, rho={args.rho}, "
          f"注入率 {args.rate}, {args.seeds} 个种子,时间序) ===")
    print(f"  训练 {len(train)} / 校准 {len(calib)} / 测试 {len(test)}")
    print(f"  Q1 注入器:尝试 {st['attempted']} ,落下 {st['injected']} ,"
          f"跳过 {st['skipped']} ,众数误伤 {st['modal_hits']}")
    print(f"      流长 {st['n_stream']}(原 {len(test)})")
    print()

    # --- Q2 覆盖 ---
    covs = []
    a8_net = {k: [] for k in WEIGHTS}
    a8_fpr = {k: [] for k in WEIGHTS}
    for s in range(args.seeds):
        stream, lab = attack_stream(test, "A8", s, args.rate, args.rho,
                                    det.struct, model)
        rng = np.random.default_rng(300 + s)
        covs.append(coverage(det, stream, lab, args.alpha, rng))
        for name, w in WEIGHTS.items():
            n, f = net(det, benign, stream, lab, args.alpha,
                       np.random.default_rng(400 + s), w)
            a8_net[name].append(n)
            a8_fpr[name].append(f)
    cov = {k: (float(np.mean([c[k][0] for c in covs])),
               float(np.mean([c[k][1] for c in covs])))
           for k in covs[0]}
    print("  Q2 覆盖(单消息 DR(FPR),alpha 对齐):")
    for k, zh in (("hard", "硬层"), ("time", "时序"), ("struct", "结构"),
                  ("inter", "互锁"), ("fused", "Fisher")):
        dr, fp = cov[k]
        print(f"    {zh:<8} {dr:.3f}({fp:.3f})  提升 {dr - fp:+.3f}")
    print()
    print("  Q2 端到端(序贯@10 减地板):")
    a8_mean = {k: float(np.mean(v)) for k, v in a8_net.items()}
    for name, v in a8_mean.items():
        print(f"    {name:<12} {v:+.3f}  (序贯FPR "
              f"{float(np.mean(a8_fpr[name])):.3f})")
    print()

    # --- Q3 代价:A1-A6 上三路 vs 三路+Fisher ---
    cost = {"三路(现行)": [], "三路+Fisher": []}
    per = {f: {"三路(现行)": [], "三路+Fisher": []} for f in COST_FAMS}
    for fam in COST_FAMS:
        for s in range(args.seeds):
            stream, lab = attack_stream(test, fam, s, args.rate, args.rho,
                                        det.struct, model)
            for name in cost:
                n, _ = net(det, benign, stream, lab, args.alpha,
                           np.random.default_rng(500 + s), WEIGHTS[name])
                cost[name].append(n)
                per[fam][name].append(n)
    cost_mean = {k: float(np.mean(v)) for k, v in cost.items()}
    print("  Q3 A1–A6 上加 Fisher 的摊薄(序贯@10 减地板):")
    print(f"    {'攻击':<8}{'三路':>8}{'+Fisher':>10}{'Δ':>8}")
    for fam in COST_FAMS:
        a = float(np.mean(per[fam]["三路(现行)"]))
        b = float(np.mean(per[fam]["三路+Fisher"]))
        print(f"    {fam:<8}{a:>8.3f}{b:>10.3f}{b - a:>+8.3f}")
    print(f"    {'均值':<8}{cost_mean['三路(现行)']:>8.3f}"
          f"{cost_mean['三路+Fisher']:>10.3f}"
          f"{cost_mean['三路+Fisher'] - cost_mean['三路(现行)']:>+8.3f}")
    print()

    stay, reasons, gain, tax = verdict(st, cov, a8_mean, cost_mean)
    print("  === 判定 ===")
    print(f"  Fisher 合成路: {'保留' if stay else '撤掉'}")
    for r in reasons:
        print(f"    - {r}")
    print()
    print("  口径:E1 主表(原始分数 → judge 经验 p,总 alpha 固定,减地板)。")
    print("  互锁不参与任何配额。A8 不进主表六族,只用来决定合成路去留。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
