"""M8 校准诊断:随机化 p 值与随机划分这两条规则各自值多少。

四个对照臂,两两正交:
    链粒度   (设备, case) 级  vs  case 级
    p 值形式 朴素            vs  随机化
    划分方式 字典序          vs  随机

关键在于**对等比较**。探针脚本曾拿单次字典序划分(0.076)对比 20 次随机
划分的平均(0.053),两边的随机化抽样次数不同,差距被放大。这里对两种
划分都跑同样多的种子,并报告均值与标准差。

目标数字(probe_structural_v2/v3):
    A 级 朴素        alpha=0.05 -> 1.000     (原子化,校准彻底失效)
    A 级 随机化      alpha=0.05 -> 0.051     alpha=0.01 -> 0.010
    B 级 字典序随机化 alpha=0.05 -> 0.058    (单种子)
    B 级 随机划分随机化 alpha=0.05 -> 0.053   (20 种子均值)
    工作流间转移集合 Jaccard 重叠中位 0.324

用法(在 paper02/slid/ 下):  py -m tools.calib_diag
"""
from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from algorithm import conformal, ingest, structural

ALPHAS = (0.05, 0.01)


def _fpr(seqs, fit_k, cal_k, test_k, randomised, rng, states):
    tm = structural.fit({k: seqs[k] for k in fit_k}, states=states)
    p_cal = structural.pvalue_stream(tm, seqs, cal_k, randomised, rng)
    p_test = structural.pvalue_stream(tm, seqs, test_k, randomised, rng)
    uniq = len(set(np.round(p_cal + p_test, 12)))
    return ({a: conformal.empirical_fpr(p_cal, p_test, a) for a in ALPHAS},
            uniq, len(p_cal), len(p_test))


def arm(seqs, splitter, randomised, seeds, states):
    acc = {a: [] for a in ALPHAS}
    uniqs, ncal = [], []
    for s in seeds:
        rng = np.random.default_rng(s)
        f, c, t = splitter(s)
        r, u, nc, _ = _fpr(seqs, f, c, t, randomised, rng, states)
        for a in ALPHAS:
            acc[a].append(r[a])
        uniqs.append(u)
        ncal.append(nc)
    return {a: (float(np.mean(v)), float(np.std(v))) for a, v in acc.items()}, \
        int(np.median(uniqs)), int(np.median(ncal))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--seeds", type=int, default=20)
    args = ap.parse_args()

    acts = ingest.valid(ingest.read_xes(args.xes), drop_failure=True)
    case_seqs = {k: [a.op for a in v]
                 for k, v in ingest.case_chains(acts).items()}
    dev_seqs = {k: [a.op for a in v]
                for k, v in structural.device_case_chains(acts).items()}
    states = sorted({a.op for a in acts})
    seeds = list(range(args.seeds))

    print(f"case 级链 {len(case_seqs)} 条,转移 "
          f"{sum(max(0, len(v)-1) for v in case_seqs.values())};"
          f"(设备, case) 链 {len(dev_seqs)} 条,转移 "
          f"{sum(max(0, len(v)-1) for v in dev_seqs.values())};"
          f"状态 {len(states)}")
    print()

    hdr = (f"{'链粒度':<14} {'划分':<10} {'p 值':<8} {'唯一取值':>8} "
           f"{'n_cal':>7} {'a=0.05':>16} {'a=0.01':>16}")
    print(hdr)
    print("-" * 92)

    for label, seqs in (("(设备, case)", dev_seqs), ("case 级", case_seqs)):
        keys = list(seqs)
        for sp_label, splitter in (
                ("字典序", lambda s: conformal.split_lexicographic(keys)),
                ("随机", lambda s: conformal.split(keys, seed=s))):
            for rnd_label, rnd in (("朴素", False), ("随机化", True)):
                res, uniq, nc = arm(seqs, splitter, rnd, seeds, states)
                cells = "  ".join(
                    f"{res[a][0]:.3f} ± {res[a][1]:.3f}" for a in ALPHAS)
                print(f"{label:<14} {sp_label:<10} {rnd_label:<8} "
                      f"{uniq:>8} {nc:>7}   {cells}")
    print()
    print("  '唯一取值' 是校准折与测试折上 p 值的不同取值个数。取值为 1 时")
    print("  校准分位数落在唯一的原子上,全部测试点被判异常,FPR 冲到 1.000。")
    print()

    # 有效校准集规模:规则 3
    print("=== 规则 3:校准集规模决定可达的最小名义水平 ===")
    n_tr = sum(max(0, len(v) - 1) for v in case_seqs.values())
    n_cal = int(n_tr * 0.25)
    print(f"  case 级混合校准:n_cal ≈ {n_cal},可达最小 alpha = "
          f"1/(n+1) = {1/(n_cal+1):.5f}")
    bank = conformal.ConformalBank(min_size=30)
    for a in acts:
        bank.add(conformal.mondrian_groups(a), 0.0)
    rep = bank.size_report()
    print(f"  若按 (设备, 操作, 结果) 做 Mondrian 分组:{rep['n_groups']} 组,"
          f"规模 {rep['min']}~{rep['max']},中位 {rep['median']}")
    print(f"  最小组可达 alpha = {rep['min_alpha_worst']:.4f}")
    for a in ALPHAS + (0.001,):
        bad = sum(1 for c in bank.groups.values() if not c.reachable(a))
        print(f"    alpha={a:<6} 有 {bad}/{rep['n_groups']} 组不可达,"
              f"这些组报出的'零误报'是假象")
    print()

    # 工作流异质性:为什么字典序切会坏
    per_wf = {}
    wf_of = {}
    for a in acts:
        wf_of[a.case] = a.workflow
    for k, seq in case_seqs.items():
        c = per_wf.setdefault(wf_of.get(k), Counter())
        for x, y in zip(seq, seq[1:]):
            c[(x, y)] += 1
    wfs = sorted(w for w in per_wf if w)
    ov = []
    for i in range(len(wfs)):
        for j in range(i + 1, len(wfs)):
            A, B = set(per_wf[wfs[i]]), set(per_wf[wfs[j]])
            if A and B:
                ov.append(len(A & B) / len(A | B))
    print(f"=== 为什么字典序划分会破坏交换性 ===")
    print(f"  {len(wfs)} 个工作流,两两转移集合 Jaccard 重叠:"
          f"中位 {np.median(ov):.3f},均值 {np.mean(ov):.3f}({len(ov)} 对)")
    print("  case id 形如 WF_101_0,字典序切把不同工作流整块分开,")
    print("  校准折与测试折因此不可交换。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
