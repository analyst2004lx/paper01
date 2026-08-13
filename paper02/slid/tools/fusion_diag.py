"""M6 合成层实测:通道依赖有多强、Fisher 究竟错多少、该在哪一层校准。

三个此前只有论证、没有实测的问题:

  Q1 三通道在良性数据上到底相不相关?"结构与互锁都变成横向通道"是
     推理,不是测量。
  Q2 Fisher 的误报被抬高多少?"会低估 p 值"是定性的,论文需要数字。
  Q3 该按通道分别校准再合成,还是对合成统计量整体校准一次?

用法(在 paper02/slid/ 下):  py -m tools.fusion_diag
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from math import log

import numpy as np

from algorithm import (conformal, fusion, ingest, interlock, procmodel,
                       structural, timing)

ALPHAS = (0.05, 0.01)
CHANNELS = ("time", "struct", "inter")


def channel_pvalues(acts_by_case, keys, models, tm, q_inter, rng,
                    advance: float = 0.0, misplace: float = 0.0):
    """逐活动算三通道 p 值。

    `advance`  A4 抢跑幅度,只作用于时序通道。
    `misplace` 伪造状态上报落在错误的工序位置的概率,作用于结构与互锁通道
               ——模拟同时触碰多个通道的攻击,用来检验合成是否真的换来覆盖面。
    """
    rows = []
    for k in keys:
        seq = acts_by_case[k]
        for i, a in enumerate(seq):
            wrong = misplace > 0 and rng.random() < misplace
            # --- 时序 ---
            p_t = 1.0
            m = models.get((a.device, a.op))
            if m is not None and m.informative:
                d = a.duration_s
                if d is not None and advance:
                    d = d * (1.0 - advance)
                if d is not None:
                    v = timing.dwell_pvalue(m, d, route=a.route,
                                            planned_s=a.planned_s)
                    if v is not None:
                        p_t = v
            # --- 结构 ---
            p_s = 1.0
            if i > 0:
                prev = seq[i - 1].op
                if wrong:
                    prev = tm.states[int(rng.integers(len(tm.states)))]
                v = structural.struct_pvalue(tm, prev, a.op,
                                             randomised=True, rng=rng)
                if v is not None:
                    p_s = v
            # --- 互锁(软层,二值 -> 随机化 p 值) ---
            viol = a.params.get("_viol", False) or wrong
            u = rng.random()
            p_i = u * q_inter if viol else q_inter + u * (1.0 - q_inter)
            rows.append((p_t, p_s, p_i))
    return rows


def mark_violations(by_case, model, all_by_case):
    """把软层互锁违反标注回活动上,供逐活动打分使用。"""
    n_viol = n_tot = 0
    for case, acts in by_case.items():
        for a in acts:
            a.params["_viol"] = False
        viols, cnt = interlock.check_case(acts, model,
                                          all_acts=all_by_case.get(case))
        n_tot += cnt["I_checked"]
        seen = defaultdict(int)
        for v in viols:
            if v.kind != "token":
                continue
            n_viol += 1
            for a in acts:
                if a.device == v.device and a.op == v.op \
                        and not a.params["_viol"] and not seen[id(a)]:
                    a.params["_viol"] = True
                    seen[id(a)] = 1
                    break
    return n_viol / max(n_tot, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--rho", type=float, default=0.20)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    every = ingest.valid(raw, drop_failure=False)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=log_pos)
    by_case = ingest.case_chains(live)
    q_inter = mark_violations(by_case, model, ingest.case_chains(every))
    print(f"软层互锁违反率 q = {q_inter:.4f}(用作二值通道的零分布)")
    print()

    methods = ("simes", "harmonic", "minp", "fisher")
    # 三种校准架构
    arms = ("late", "early", "both")
    fpr = {(m, s): {a: [] for a in ALPHAS} for m in methods for s in arms}
    pw = {(m, s): [] for m in methods for s in arms}
    corr, floor, floor_cause = [], [], []
    solo = {"fpr": [], "power": [], "power_multi": []}
    pw_multi = {(m, s): [] for m in methods for s in arms}
    keys = list(by_case)

    for seed in range(args.seeds):
        rng = np.random.default_rng(seed)
        tr, ca, te = conformal.split(keys, seed=seed)
        # 校准折再对半分:ca1 校准各通道,ca2 校准合成统计量
        half = len(ca) // 2
        ca1, ca2 = ca[:half], ca[half:]
        models = timing.fit([a for k in tr for a in by_case[k]])
        tm = structural.fit({k: [a.op for a in by_case[k]] for k in tr},
                            states=sorted({a.op for a in live}))

        def P(ks, adv=0.0):
            return channel_pvalues(by_case, ks, models, tm, q_inter, rng,
                                   advance=adv)

        P_ca1, P_ca2, P_te = P(ca1), P(ca2), P(te)
        P_atk = P(te, adv=args.rho)
        P_multi = channel_pvalues(by_case, te, models, tm, q_inter, rng,
                                  advance=args.rho, misplace=0.5)

        A = np.array(P_te)
        e = -np.log(np.clip(A, 1e-12, 1.0))
        corr.append([np.corrcoef(e[:, i], e[:, j])[0, 1]
                     for i, j in ((0, 1), (0, 2), (1, 2))])
        floor.append(float((A[:, 0] <= 1e-11).mean()))
        # 下溢成因:训练折见过该路线(真·失配) vs 回落到计划工时(冷启动)
        seen = miss = 0
        for k in te:
            for a in by_case[k]:
                m = models.get((a.device, a.op))
                if m is None or not m.informative or a.duration_s is None:
                    continue
                v = timing.dwell_pvalue(m, a.duration_s, route=a.route,
                                        planned_s=a.planned_s)
                if v is not None and v <= 1e-11:
                    if (a.route or timing.NO_ROUTE) in m.route_effect:
                        seen += 1
                    else:
                        miss += 1
        floor_cause.append((seen, miss))

        # 逐通道 conformal:用 ca1 建校准器,把原始 p 值换成 conformal p 值
        cals = []
        for j in range(3):
            c = conformal.Calibrator(
                scores=[-r[j] for r in P_ca1]).freeze()
            cals.append(c)

        def recal(rows):
            return [tuple(cals[j].pvalue(-r[j], rng=rng) for j in range(3))
                    for r in rows]

        R_ca2, R_te, R_atk = recal(P_ca2), recal(P_te), recal(P_atk)
        R_multi = recal(P_multi)

        # 单通道基线:只用时序,同样过一次逐通道 conformal,同一 alpha
        solo["fpr"].append(float(np.mean([r[0] <= 0.01 for r in R_te])))
        solo["power"].append(float(np.mean([r[0] <= 0.01 for r in R_atk])))
        solo["power_multi"].append(
            float(np.mean([r[0] <= 0.01 for r in R_multi])))

        for m in methods:
            def s(rows):
                return np.array([fusion.combine(r, m) for r in rows])
            raw_ca2, raw_te, raw_at = s(P_ca2), s(P_te), s(P_atk)
            rec_ca2, rec_te, rec_at = s(R_ca2), s(R_te), s(R_atk)
            raw_mu, rec_mu = s(P_multi), s(R_multi)
            for a in ALPHAS:
                # late  先合成原始 p 值,只在末端校准一次
                t = float(np.quantile(raw_ca2, a))
                fpr[(m, "late")][a].append(float((raw_te <= t).mean()))
                # early 先逐通道校准,再合成,用名义零分布判定
                fpr[(m, "early")][a].append(float((rec_te <= a).mean()))
                # both  先逐通道校准,合成后再校准一次
                t = float(np.quantile(rec_ca2, a))
                fpr[(m, "both")][a].append(float((rec_te <= t).mean()))
            t = float(np.quantile(raw_ca2, 0.01))
            pw[(m, "late")].append(float((raw_at <= t).mean()))
            pw_multi[(m, "late")].append(float((raw_mu <= t).mean()))
            pw[(m, "early")].append(float((rec_at <= 0.01).mean()))
            pw_multi[(m, "early")].append(float((rec_mu <= 0.01).mean()))
            t = float(np.quantile(rec_ca2, 0.01))
            pw[(m, "both")].append(float((rec_at <= t).mean()))
            pw_multi[(m, "both")].append(float((rec_mu <= t).mean()))

    c = np.array(corr)
    print("=== Q1 通道依赖(证据 -log p 的 Pearson 相关,越大越不独立) ===")
    for (i, j), v in zip(((0, 1), (0, 2), (1, 2)), c.T):
        print(f"  {CHANNELS[i]:<7} vs {CHANNELS[j]:<7}  "
              f"{v.mean():+.3f} ± {v.std():.3f}")
    print()
    print(f"  时序 p 值触到裁剪下界 1e-12 的良性活动占比: "
          f"{np.mean(floor):.3f} ± {np.std(floor):.3f}")
    fc = np.array(floor_cause, dtype=float)
    tot = fc.sum(axis=0)
    print(f"  其中 训练折已见该路线(真·模型失配) {tot[0]/max(tot.sum(),1):.1%}"
          f"  回落到计划工时(冷启动外推) {tot[1]/max(tot.sum(),1):.1%}")
    print("  -> 这些点让 min 型统计量(Simes/minp)在底部形成原子。")
    print()

    names = {"late": "先合成后校准", "early": "先逐通道校准(名义)",
             "both": "先逐通道校准再合成后校准"}
    print("=== Q3 三种校准架构的经验误报率 ===")
    hdr = (f"  {'合成':<10} {'架构':<26} {'a=0.05':>16} {'a=0.01':>16}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for m in methods:
        for i, s in enumerate(arms):
            cells = "  ".join(
                f"{np.mean(fpr[(m, s)][a]):.3f} ± "
                f"{np.std(fpr[(m, s)][a]):.3f}" for a in ALPHAS)
            print(f"  {m if i == 0 else '':<10} {names[s]:<26} {cells}")
    print()

    for tab, solo_key, title in (
            (pw, "power", f"单通道攻击:A4 抢跑 rho={args.rho}"),
            (pw_multi, "power_multi",
             f"多通道攻击:A4 抢跑 rho={args.rho} + 50% 伪造位置")):
        print(f"=== 功效({title}, alpha=0.01) ===")
        print(f"  {'合成':<10} " + " ".join(f"{names[s]:>26}" for s in arms))
        print("  " + "-" * 90)
        for m in methods:
            print(f"  {m:<10} " + " ".join(
                f"{np.mean(tab[(m, s)]):>26.3f}" for s in arms))
        print(f"  {'仅时序通道':<10} {np.mean(solo[solo_key]):>26.3f}"
              f"   (实际 FPR {np.mean(solo['fpr']):.3f})")
        print()
    print("  功效只能在实际误报率相当的架构之间比较。仅时序通道若显著")
    print("  高于任何三通道合成,说明合成在单通道攻击下稀释了功效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
