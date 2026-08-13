"""构造性验证原方法(MBDF)的不可检测集合 —— T-a 的实证形式(实验 E3)。

原方法的判决规则(录自 paper02_old/Latex/paper02.tex 的 Eq.(prediction)、
Eq.(threshold) 与 Algorithm 2):

    预测   p = P^T e_i                 (概率分布,不是 one-hot)
    观测   e_j                          (one-hot)
    偏差   delta = || e_j - p ||_2
    阈值   eps_i = gamma / h(c)         c = argmax p,  h = -ln P_BN(c)   [论文版]
           eps_i = k * P_BN(c)                                          [专利版]
    判决   delta >= eps_i  -> 报警

本脚本要证明三件事,强度递增:

T-a.1 (数值版,文档原有):存在状态使 eps_i 超过 delta 的理论上界 sqrt(2),
      此时该行**任何观测都不会报警**。这一条依赖具体系数取值。

T-a.2 (结构版):把 delta 展开,
          delta_j^2 = || e_j - p ||^2 = 1 - 2 p_j + ||p||^2
      所以 delta 只是 p_j 的单调减函数——**几何距离退化为对预测概率的
      一元变换**,所谓"l2 范数偏差"里那个 ||p||^2 对同一行的所有 j 是常数,
      纯属冗余。由此立即得到:攻击者的最优规避目标 j = argmax_j p_j,
      **恰好也是最有攻击价值的目标**(调度器正等着这个状态,伪造它就能
      推进调度)。规避与收益在原方法下是对齐的,而本文方法(M-a)让二者冲突。

T-a.3 (不可能性,与系数取值无关):delta 是 (i, j) 的确定性函数,与该消息
      是良性还是注入**无关**。因此在行 i 上,
          能检出"注入 j"  <=>  每一次良性的 j 都报警
      故  DR(注入 j) = 1  蕴含  FPR_i >= p_j。
      推论:能在行 i 上零误报地标记的 j 恰好是 { j : p_j = 0 },
      **即可行性掩码本已零成本拒绝的那些转移**。也就是说,马尔可夫层与
      贝叶斯阈值层对"标签自洽的注入"贡献恒为零。

T-a.3 不依赖 gamma / k / 阈值函数形式,任何"只看 (预测分布, 观测标签)"
的检测器都逃不掉。这是本文换掉判据的根本理由,也是 M-c 的出发点。

用法(在 paper02/slid/ 下):
    py -m tools.mbdf_undetectable
    py -m tools.mbdf_undetectable --xes <path> --csv
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import numpy as np

XES_NS = "{http://www.xes-standard.org/}"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_XES = os.path.normpath(os.path.join(
    ROOT, "..", "database", "ft_trier_iot_log", "MainProcess_cleaned.xes"))

# 论文/专利自报的系数
GAMMA_STAR = 0.73          # 论文 Scenario A 网格搜索最优 (kappa*)
GAMMA_GRID = np.arange(0.10, 2.001, 0.05)
K_STAR = 10.25             # 专利线性版系数
K_GRID = np.arange(0.5, 20.001, 0.25)

SQRT2 = math.sqrt(2.0)


def load_case_sequences(path: str):
    """case 级工作流活动序列(结论十三确定的唯一可行粒度)+ 逐活动执行时长。

    时长按活动名池化(跨资源),这对本文是**保守**的:池化把资源异质性算进
    sigma,高估了 sigma、低估了时序通道的检出能力。真实建模按
    (resource, activity) 分组会更紧。
    """
    acts: dict[tuple, dict] = defaultdict(dict)
    for trace in ET.parse(path).getroot().findall(XES_NS + "trace"):
        for ev in trace.findall(XES_NS + "event"):
            a = {c.get("key"): c.get("value") for c in ev if c.get("key")}
            rec = acts[(a.get("case"), a.get("event_id"))]
            rec.setdefault("case", a.get("case"))
            rec.setdefault("op", a.get("concept:name"))
            st = a.get("lifecycle:state")
            if st == "inProgress" and a.get("time:timestamp"):
                rec["t"] = datetime.fromisoformat(a["time:timestamp"])
                if a.get("operation_end_time"):
                    rec["t_end"] = datetime.fromisoformat(a["operation_end_time"])
            if st in ("success", "failure"):
                rec["outcome"] = st
    seqs: dict[str, list[str]] = defaultdict(list)
    durs: dict[str, list[float]] = defaultdict(list)
    for r in sorted((r for r in acts.values()
                     if r.get("outcome") == "success" and r.get("t")),
                    key=lambda r: r["t"]):
        seqs[r["case"]].append(r["op"])
        if r.get("t_end"):
            d = (r["t_end"] - r["t"]).total_seconds()
            if d > 0:
                durs[r["op"]].append(d)
    sigma = {op: float(np.log(np.array(v)).std(ddof=1))
             for op, v in durs.items() if len(v) >= 5}
    return dict(seqs), sigma


def build_markov(seqs):
    """MBDF 的一阶转移矩阵与边缘分布(按其自身设定用极大似然,不加先验)。"""
    states = sorted({s for v in seqs.values() for s in v})
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    counts = np.zeros((n, n))
    occ = np.zeros(n)
    for seq in seqs.values():
        for s in seq:
            occ[idx[s]] += 1
        for a, b in zip(seq, seq[1:]):
            counts[idx[a], idx[b]] += 1
    row = counts.sum(axis=1)
    P = np.divide(counts, row[:, None], out=np.zeros_like(counts),
                  where=row[:, None] > 0)
    p_bn = occ / occ.sum()                     # P_BN(s_i),贝叶斯层的边缘概率
    return states, counts, P, row, p_bn


def deviations(P):
    """delta[i, j] = ||e_j - P[i]||_2 = sqrt(1 - 2 P[i,j] + ||P[i]||^2)。"""
    sq = (P ** 2).sum(axis=1, keepdims=True)
    d2 = 1.0 - 2.0 * P + sq
    return np.sqrt(np.maximum(d2, 0.0))


def thresholds(P, p_bn, *, gamma=None, k=None):
    """eps 只依赖预测主状态 c = argmax_j P[i,j]。"""
    c = P.argmax(axis=1)
    pc = np.clip(p_bn[c], 1e-12, 1.0)
    if gamma is not None:
        return gamma / (-np.log(pc)), c
    return k * pc, c


def analyse(states, P, row, p_bn, delta, eps, cmode):
    """返回单一系数取值下的诊断量。"""
    live = row > 0
    n = len(states)
    # 预测分布的先验权重:用前驱状态被观测到的频次
    w = row / row.sum()

    undetectable = delta < eps[:, None]            # (i, j) 注入后不会报警
    modal = P.argmax(axis=1)
    modal_safe = undetectable[np.arange(n), modal]  # A4 状态模仿是否成功

    # 整行盲:该行任何观测都不报警
    row_max_delta = np.where(live, delta.max(axis=1), 0.0)
    fully_blind = live & (eps > row_max_delta)

    # 良性误报率:delta 是 (i,j) 的函数,良性 j 以 P[i,j] 出现
    fpr_row = (undetectable == False) * P
    fpr = float((w * fpr_row.sum(axis=1))[live].sum())

    # 攻击者可自由伪造的转移质量:落在 U_i 内的良性转移占比
    mimic_mass = float((w * (undetectable * P).sum(axis=1))[live].sum())

    return {
        "eps_min": float(eps[live].min()),
        "eps_max": float(eps[live].max()),
        "n_live_rows": int(live.sum()),
        "n_fully_blind": int(fully_blind.sum()),
        "fully_blind_rows": [states[i] for i in np.where(fully_blind)[0]],
        "modal_safe_rows": int((modal_safe & live).sum()),
        "modal_safe_weighted": float(w[live & modal_safe].sum()),
        "mean_undetectable_labels": float(undetectable[live].sum(axis=1).mean()),
        "mimic_mass": mimic_mass,
        "fpr": fpr,
        "undetectable": undetectable,
        "live": live,
        "w": w,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=DEFAULT_XES)
    ap.add_argument("--csv", action="store_true", help="导出到 experiments/")
    args = ap.parse_args()

    if not os.path.exists(args.xes):
        print(f"找不到日志: {args.xes}")
        return 1

    seqs, sigma = load_case_sequences(args.xes)
    states, counts, P, row, p_bn = build_markov(seqs)
    delta = deviations(P)
    live = row > 0
    n = len(states)
    n_trans = int(counts.sum())

    print(f"case 级链: {len(seqs)} 个 case, {n} 个状态, {n_trans} 次转移, "
          f"{int(live.sum())} 个有出边的前驱状态")
    print()

    # ---- T-a.2 结构版:delta 的取值范围与冗余项 ----
    print("=" * 78)
    print("T-a.2  几何距离退化:delta_j^2 = 1 - 2 p_j + ||p||^2")
    print("=" * 78)
    modal = P.argmax(axis=1)
    pmax = P[np.arange(n), modal]
    d_modal = delta[np.arange(n), modal]
    dmax = np.where(live, delta.max(axis=1), np.nan)
    print(f"  理论上界 delta <= sqrt(2) = {SQRT2:.4f}"
          f"   实测行内最大 delta: {np.nanmax(dmax):.4f}")
    print(f"  注入最可能后继时的 delta:  中位 {np.median(d_modal[live]):.4f}"
          f"   最小 {d_modal[live].min():.4f}   最大 {d_modal[live].max():.4f}")
    det = int(((pmax >= 0.999) & live).sum())
    print(f"  确定性转移行(p_max >= 0.999): {det}/{int(live.sum())}"
          f"  —— 这些行 delta_modal = 0,任何正阈值都抓不到状态模仿")
    print()
    print("  最易被模仿的 8 个前驱状态(delta 越小越无法检出):")
    print(f"  {'前驱状态':<34} {'p_max':>6} {'d_modal':>8} {'n':>5}")
    print("  " + "-" * 58)
    for i in sorted(np.where(live)[0], key=lambda i: d_modal[i])[:8]:
        print(f"  {states[i][:34]:<34} {pmax[i]:>6.3f} "
              f"{d_modal[i]:>8.4f} {int(row[i]):>5}")
    print()

    # ---- T-a.1 数值版:两种阈值形式下的盲区 ----
    print("=" * 78)
    print("T-a.1  两种阈值形式在各自自报系数下的不可检测集合")
    print("=" * 78)
    variants = [
        ("专利线性版  eps = k * P_BN(c),  k = 10.25",
         thresholds(P, p_bn, k=K_STAR)),
        ("论文惊异版  eps = gamma / h(c), gamma = 0.73",
         thresholds(P, p_bn, gamma=GAMMA_STAR)),
    ]
    results = {}
    for name, (eps, c) in variants:
        r = analyse(states, P, row, p_bn, delta, eps, c)
        results[name] = r
        print(f"\n  {name}")
        print(f"    eps 取值范围            {r['eps_min']:.4f} – {r['eps_max']:.4f}"
              f"   (delta 上界 {SQRT2:.4f})")
        print(f"    整行全盲的前驱状态数    {r['n_fully_blind']}/{r['n_live_rows']}"
              f"   —— 这些行任何观测都不报警")
        if r["fully_blind_rows"]:
            for s in r["fully_blind_rows"][:6]:
                print(f"        {s}")
            if len(r["fully_blind_rows"]) > 6:
                print(f"        ... 另有 {len(r['fully_blind_rows'])-6} 个")
        print(f"    状态模仿(A4)得手的行   {r['modal_safe_rows']}/{r['n_live_rows']}"
              f"   按转移频次加权 {r['modal_safe_weighted']*100:.1f}%")
        print(f"    每行平均不可检测标签数  {r['mean_undetectable_labels']:.1f}/{n}")
        print(f"    可自由伪造的转移质量    {r['mimic_mass']*100:.1f}%")
        print(f"    良性数据上的误报率      {r['fpr']*100:.1f}%")

    # ---- T-a.3 不可能性:扫系数,证明无论怎么调都逃不掉 ----
    print()
    print("=" * 78)
    print("T-a.3  不可能性:DR(状态模仿) 与 FPR 在任何系数取值下都同步移动")
    print("=" * 78)
    print("  delta 是 (前驱, 观测标签) 的确定性函数,与消息是良性还是注入无关。")
    print("  故'能检出注入 j' 等价于 '每次良性的 j 都报警'。扫系数验证:")
    print()
    print(f"  {'gamma':>6} {'eps 中位':>9} {'A4 得手(加权)':>14} "
          f"{'良性 FPR':>10} {'可伪造质量':>11}")
    print("  " + "-" * 56)
    sweep = []
    for g in GAMMA_GRID:
        eps, c = thresholds(P, p_bn, gamma=float(g))
        r = analyse(states, P, row, p_bn, delta, eps, c)
        sweep.append((float(g), float(np.median(eps[r["live"]])),
                      r["modal_safe_weighted"], r["fpr"], r["mimic_mass"]))
    for g, em, ms, fp, mm in sweep[::4]:
        print(f"  {g:>6.2f} {em:>9.4f} {ms*100:>13.1f}% "
              f"{fp*100:>9.1f}% {mm*100:>10.1f}%")

    # 找出能把 A4 压到 50% 以下所需的 FPR
    feasible = [(fp, ms, g) for g, _, ms, fp, _ in sweep if ms <= 0.5]
    print()
    if feasible:
        fp, ms, g = min(feasible)
        print(f"  要把状态模仿得手率压到 50% 以下,最省的取值是 gamma={g:.2f},")
        print(f"  代价是良性误报率 {fp*100:.1f}%。")
    else:
        print("  在整个 gamma 网格 [0.10, 2.00] 上,状态模仿得手率**从未**低于 50%。")
    zero_fp = [(ms, g) for g, _, ms, fp, _ in sweep if fp <= 1e-9]
    if zero_fp:
        ms, g = min(zero_fp)
        print(f"  反之,要做到零误报(gamma={g:.2f}),状态模仿得手率为 {ms*100:.1f}%。")

    # 零误报可标记集 == 掩码已拒绝集
    print()
    zero_fp_flaggable = int(((P == 0) & live[:, None]).sum())
    total_pairs = int(live.sum()) * n
    print(f"  零误报前提下可标记的 (前驱, 标签) 对 = {{ j : p_j = 0 }} "
          f"共 {zero_fp_flaggable}/{total_pairs} 对,")
    print(f"  这恰好是可行性掩码 F 已经零成本拒绝的集合。**马尔可夫层与贝叶斯")
    print(f"  阈值层对标签自洽的注入贡献恒为零。**")

    # ---- 互补性:MBDF 恰好全盲的地方,正是时序通道最锐利的地方 ----
    print()
    print("=" * 78)
    print("互补性  MBDF 精确全盲的转移 vs 本文时序通道的 rho*")
    print("=" * 78)
    print("  delta_modal = 0 意味着注入最可能后继产生的偏差**精确为零**:")
    print("  预测与观测完全一致,任何阈值、任何系数都不可能报警。")
    print("  这类转移之所以确定,正因为工序是刚性的——而刚性工序的时长方差也小,")
    print("  所以本文时序通道在同一批转移上最锐利。攻击者仍需抢跑才能获益(A3),")
    print("  抢跑就落进时序通道。")
    print()
    z = 2.3263          # 单侧 alpha=0.01,与 timing.rho_star 口径一致
    exact = [i for i in np.where(live)[0] if d_modal[i] < 1e-12]
    print(f"  {'前驱状态(MBDF delta=0)':<32} {'n':>4} {'sigma_log':>10} "
          f"{'rho*':>7}  时序通道")
    print("  " + "-" * 70)
    covered = 0
    for i in sorted(exact, key=lambda i: -row[i]):
        s = sigma.get(states[i])
        if s is None:
            print(f"  {states[i][:32]:<32} {int(row[i]):>4} {'样本不足':>10} "
                  f"{'—':>7}  n<5,无法建模")
            continue
        rs = 1.0 - math.exp(-z * s)
        covered += int(row[i])
        verdict = "可检出" if rs < 0.5 else "弱"
        print(f"  {states[i][:32]:<32} {int(row[i]):>4} {s:>10.3f} "
              f"{rs*100:>6.1f}%  {verdict}")
    tot_exact = sum(int(row[i]) for i in exact)
    print()
    print(f"  MBDF 精确全盲的转移共 {tot_exact} 次 "
          f"({tot_exact/n_trans*100:.1f}% 的全部转移),")
    print(f"  其中 {covered} 次落在时序通道可建模的分组内。")
    print("  结论:两种方法的盲区互补,而不是本文只是'数值上更好'。")

    if args.csv:
        out_dir = os.path.join(ROOT, "experiments")
        os.makedirs(out_dir, exist_ok=True)
        p1 = os.path.join(out_dir, "mbdf_undetectable_rows.csv")
        with open(p1, "w", newline="", encoding="utf-8") as f:
            wtr = csv.writer(f)
            wtr.writerow(["predecessor", "n_out", "p_max", "modal_successor",
                          "delta_modal", "delta_max",
                          "eps_linear_k10.25", "eps_surprisal_g0.73",
                          "modal_safe_linear", "modal_safe_surprisal"])
            eL, _ = thresholds(P, p_bn, k=K_STAR)
            eS, _ = thresholds(P, p_bn, gamma=GAMMA_STAR)
            for i in np.where(live)[0]:
                wtr.writerow([states[i], int(row[i]), f"{pmax[i]:.4f}",
                              states[modal[i]], f"{d_modal[i]:.4f}",
                              f"{dmax[i]:.4f}", f"{eL[i]:.4f}", f"{eS[i]:.4f}",
                              int(d_modal[i] < eL[i]), int(d_modal[i] < eS[i])])
        p2 = os.path.join(out_dir, "mbdf_gamma_sweep.csv")
        with open(p2, "w", newline="", encoding="utf-8") as f:
            wtr = csv.writer(f)
            wtr.writerow(["gamma", "eps_median", "a4_success_weighted",
                          "benign_fpr", "mimicable_mass"])
            for r_ in sweep:
                wtr.writerow([f"{v:.6f}" for v in r_])
        print(f"\n  已写出 {os.path.relpath(p1, ROOT)} 与 {os.path.relpath(p2, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
