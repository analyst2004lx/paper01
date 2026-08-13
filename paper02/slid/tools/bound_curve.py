"""影响-可检测性权衡:理论界 vs 实测检出率,以及序贯层把它推进多远。

攻击模型 A4-抢跑:设备谎报提前完工,观测时长缩为 (1-rho)*tau。对数空间里
这是一个纯位置平移 Delta = log(1-rho),故标准化位移是 Delta/sigma,
单消息功效在水平 alpha 上为
    单侧  DR(rho) = Phi(-z1 - Delta/sigma)
    双侧  DR(rho) = Phi(-z2 - Delta/sigma) + 1 - Phi(z2 - Delta/sigma)

两件事会让实测低于预测,本脚本的意义就是量化它们:
  - sigma 是有限训练样本估出来的,不是已知的;
  - 阈值由真实残差的 conformal 校准给出,其尾部并非精确高斯。

目标数字(probe_bound.py):
    20 个可建模分组,sigma 0.007~1.843,测试加权均值 0.239
    conformal 阈值 alpha=0.01:双侧 5.626 / 单侧 2.568(高斯参考 2.576/2.326)
    干净测试集经验 FPR:双侧 0.0028 / 单侧 0.0084
    换高斯阈值:双侧 0.0196 / 单侧 0.0140(名义 0.01)
    rho=0.50 单消息 DR:单侧 0.874(预测 0.851) 双侧 0.338(预测 0.357)
    CUSUM(ARL0>=500):rho=0.15 检出 0.868 中位延迟 10 条

用法(在 paper02/slid/ 下):  py -m tools.bound_curve
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from math import log, sqrt

import numpy as np

from algorithm import conformal, ingest, sequential, timing

RHOS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)
MIN_ROUTE_N = 8
MIN_GROUP_N = 30


def build_folds(acts, seed: int = 7):
    """逐 (分组, 路线) 划 fit/calib/test,再用 fit 折的位置与尺度标准化。

    按路线分层划分,保证三折都覆盖同样的路线集合——否则测试折里出现
    fit 折没见过的路线,量到的就不是检测功效而是外推误差(见 T6)。
    """
    rng = np.random.default_rng(seed)
    by_key = defaultdict(list)
    for a in acts:
        if a.outcome != "success" or a.duration_s is None:
            continue
        by_key[((a.device, a.op), a.route or timing.NO_ROUTE)].append(a)

    by_grp = defaultdict(list)
    for (grp, route), items in by_key.items():
        if len(items) >= MIN_ROUTE_N:
            by_grp[grp].append((route, items))

    cal, test, sigmas = [], [], {}
    for grp, routes in by_grp.items():
        if sum(len(v) for _, v in routes) < MIN_GROUP_N:
            continue
        fit_p, cal_p, test_p = [], [], []
        for route, items in routes:
            idx = rng.permutation(len(items))
            a, b = int(len(items) * 0.5), int(len(items) * 0.75)
            fit_p.append([items[i] for i in idx[:a]])
            cal_p.append([items[i] for i in idx[a:b]])
            test_p.append([items[i] for i in idx[b:]])

        mu, ss, df, resid = {}, 0.0, 0, []
        for (route, _), part in zip(routes, fit_p):
            if len(part) < 2:
                continue
            ys = np.array([log(p.duration_s) for p in part])
            mu[route] = float(ys.mean())
            ss += float(((ys - ys.mean()) ** 2).sum())
            df += len(ys) - 1
            resid.extend(list(ys - ys.mean()))
        if df < 5 or not mu:
            continue
        sigma = sqrt(ss / df)
        if sigma <= 1e-6:
            continue
        sigmas[grp] = sigma
        # NIG 后验预测:小样本下 sigma 本身有估计误差,后验预测把它折进
        # 更厚的尾部。scale > 1、自由度有限,正是插值 sigma 所缺的两件事。
        post = timing.nig_update(timing.NIGPrior(),
                                 np.asarray(resid) / sigma)
        for parts, sink in ((cal_p, cal), (test_p, test)):
            for (route, _), part in zip(routes, parts):
                if route not in mu:
                    continue
                for p in part:
                    z = (log(p.duration_s) - mu[route]) / sigma
                    sink.append({"z": z, "sigma": sigma, "grp": grp,
                                 "dev": p.device, "t": p.t_start,
                                 "t_scale": post.scale, "df": post.df})
    return cal, test, sigmas


def _scores(rows, shift=0.0, mode: str = "z"):
    """把记录折算成 (单侧, 双侧) 非一致性分数,越大越异常。

    mode='z'  插值 sigma 的原始 z(probe_bound 的口径)
    mode='t'  NIG -> Student-t 后验预测的概率积分变换
    """
    z = np.array([r["z"] for r in rows])
    if shift:
        z = z + shift / np.array([r["sigma"] for r in rows])
    if mode == "z":
        return -z, np.abs(z)
    pl = np.array([timing.student_t_cdf(zi / r["t_scale"], r["df"])
                   for zi, r in zip(z, rows)])
    return -pl, -2.0 * np.minimum(pl, 1.0 - pl)


def stability(acts, alpha: float, n_seeds: int) -> None:
    """阈值与功效对折划分种子的敏感性。

    这不是可有可无的诊断。混合校准把 sigma 相差两个数量级的分组放进同一个
    分位数里(dm_2 /dm/lower 的 0.008 与 hw_1 的 1.846),于是 |z| 的 99%
    分位由低 sigma 组的少数极端点决定,单个种子的结果不可信。
    """
    d = log(0.5)
    arms = (("z", False, "插值 sigma + 混合校准"),
            ("t", False, "Student-t 后验预测 + 混合校准"),
            ("z", True, "插值 sigma + Mondrian 逐组校准"))
    out = {}
    unreachable = []
    for mode, mondrian, _ in arms:
        rows = []
        for seed in range(n_seeds):
            cal, test, _ = build_folds(acts, seed=seed)
            if not cal or not test:
                continue
            c1, c2 = _scores(cal, mode=mode)
            t1, t2 = _scores(test, mode=mode)
            a1, a2 = _scores(test, shift=d, mode=mode)
            if not mondrian:
                h1 = np.full(len(t1), float(np.quantile(c1, 1 - alpha)))
                h2 = np.full(len(t2), float(np.quantile(c2, 1 - alpha)))
            else:
                q1, q2, n_bad = {}, {}, 0
                for g in {r["grp"] for r in cal}:
                    m = [i for i, r in enumerate(cal) if r["grp"] == g]
                    if len(m) + 1 < 1 / alpha:      # 规则 3:alpha 不可达
                        n_bad += 1
                        continue
                    q1[g] = float(np.quantile(c1[m], 1 - alpha))
                    q2[g] = float(np.quantile(c2[m], 1 - alpha))
                unreachable.append(n_bad / max(len({r["grp"] for r in cal}), 1))
                g1 = float(np.quantile(c1, 1 - alpha))
                g2 = float(np.quantile(c2, 1 - alpha))
                h1 = np.array([q1.get(r["grp"], g1) for r in test])
                h2 = np.array([q2.get(r["grp"], g2) for r in test])
            rows.append({"fpr1": float(np.mean(t1 > h1)),
                         "fpr2": float(np.mean(t2 > h2)),
                         "dr1": float(np.mean(a1 > h1)),
                         "dr2": float(np.mean(a2 > h2))})
        out[(mode, mondrian)] = rows

    print(f"=== 折划分稳定性({n_seeds} 个种子, alpha={alpha}) ===")
    print(f"  {'量':<20} {'方案':<32} {'均值':>8} {'标准差':>8} {'范围':>18}")
    print("  " + "-" * 90)
    for key, name in (("fpr1", "单侧经验 FPR"), ("fpr2", "双侧经验 FPR"),
                      ("dr1", "单侧 DR @ rho=0.5"),
                      ("dr2", "双侧 DR @ rho=0.5")):
        for i, (mode, mon, lab) in enumerate(arms):
            v = np.array([r[key] for r in out[(mode, mon)]])
            print(f"  {name if i == 0 else '':<20} {lab:<32} "
                  f"{v.mean():>8.3f} {v.std():>8.3f} "
                  f"  [{v.min():.3f}, {v.max():.3f}]")
    print()
    for mode, mon, lab in arms:
        adv = np.array([r["dr1"] - r["dr2"] for r in out[(mode, mon)]])
        print(f"  单侧对双侧的功效优势({lab}): {adv.mean():+.3f} ± "
              f"{adv.std():.3f}  范围 [{adv.min():+.3f}, {adv.max():+.3f}]")
    if unreachable:
        print(f"  Mondrian 下 alpha={alpha} 不可达而回落到混合校准的分组占比: "
              f"{np.mean(unreachable)*100:.1f}%")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--arl0", type=int, default=500)
    ap.add_argument("--seeds", type=int, default=0,
                    help="非零则只跑折划分稳定性报告")
    args = ap.parse_args()
    if args.seeds:
        acts = ingest.valid(ingest.read_xes(args.xes), drop_failure=False)
        stability(acts, args.alpha, args.seeds)
        return 0
    alpha = args.alpha

    acts = ingest.valid(ingest.read_xes(args.xes), drop_failure=False)
    cal, test, sigmas = build_folds(acts, seed=args.seed)
    print(f"可建模分组 {len(sigmas)}  校准 {len(cal)}  测试 {len(test)}")
    sig = np.array(list(sigmas.values()))
    w = np.array([sum(1 for r in test if r["grp"] == g) for g in sigmas],
                 dtype=float)
    sbar = float(np.average(sig, weights=w)) if w.sum() else float(sig.mean())
    print(f"逐组 sigma: 最小 {sig.min():.3f} 中位 {np.median(sig):.3f} "
          f"最大 {sig.max():.3f}  测试加权均值 {sbar:.3f}")
    print()

    z_cal = np.array([r["z"] for r in cal])
    z_test = np.array([r["z"] for r in test])
    s_test = np.array([r["sigma"] for r in test])

    thr2 = float(np.quantile(np.abs(z_cal), 1 - alpha))
    thr1 = float(np.quantile(-z_cal, 1 - alpha))
    g2 = timing.norm_ppf(1 - alpha / 2)
    g1 = timing.norm_ppf(1 - alpha)
    print(f"=== 阈值与误报率(alpha={alpha}) ===")
    print(f"  conformal 阈值: 双侧 |z|>{thr2:.3f}  单侧 -z>{thr1:.3f}")
    print(f"  高斯参考       : 双侧 {g2:.3f}        单侧 {g1:.3f}")
    print(f"  干净测试集经验 FPR: 双侧 "
          f"{np.mean(np.abs(z_test) > thr2):.4f}  单侧 "
          f"{np.mean(-z_test > thr1):.4f}")
    print(f"  改用高斯阈值      : 双侧 "
          f"{np.mean(np.abs(z_test) > g2):.4f}  单侧 "
          f"{np.mean(-z_test > g1):.4f}   (名义 {alpha})")
    print(f"  残差尾部不对称: q99(+z)={np.quantile(z_test, 0.99):.2f}  "
          f"q99(-z)={np.quantile(-z_test, 0.99):.2f}")
    print("  -> 高斯阈值把误报翻到名义值的约两倍,这是分布假设的代价。")
    print()

    print("=== 逐组 rho*(单侧) ===")
    for g, s in sorted(sigmas.items(), key=lambda kv: kv[1]):
        n = sum(1 for r in test if r["grp"] == g)
        print(f"  {g[0]:<7} {g[1]:<30} sigma={s:6.3f} n={n:>3}  "
              f"rho*={timing.rho_star(s, alpha)*100:5.1f}%")
    print()

    print("=== 单消息检出率:实测 vs 预测 ===")
    hdr = (f"{'rho':>6} {'|Delta|':>8} {'D/sig':>7} {'单侧实测':>9} "
           f"{'预测':>7} {'双侧实测':>9} {'预测':>7}")
    print(hdr)
    print("-" * len(hdr))
    errs = []
    for rho in RHOS:
        d = log(1 - rho)
        shift = d / s_test
        za = z_test + shift
        dr1 = float(np.mean(-za > thr1))
        dr2 = float(np.mean(np.abs(za) > thr2))
        pr1 = float(np.mean([timing.norm_cdf(-thr1 - s) for s in shift]))
        pr2 = float(np.mean([timing.norm_cdf(-thr2 - s)
                             + 1 - timing.norm_cdf(thr2 - s) for s in shift]))
        errs += [abs(dr1 - pr1), abs(dr2 - pr2)]
        print(f"{rho:>6.2f} {abs(d):>8.3f} {abs(d)/sbar:>7.2f} "
              f"{dr1:>9.3f} {pr1:>7.3f} {dr2:>9.3f} {pr2:>7.3f}")
    print()
    print(f"  理论与实测的平均绝对偏差 = {np.mean(errs):.3f}")
    print(f"  单侧对双侧的功效优势(rho=0.5): "
          f"{float(np.mean(-(z_test + log(0.5)/s_test) > thr1)):.3f} 对 "
          f"{float(np.mean(np.abs(z_test + log(0.5)/s_test) > thr2)):.3f}")
    print()

    # ---------------- 序贯层 ----------------
    print(f"=== CUSUM:给定延迟预算下的检出率(ARL0>={args.arl0}) ===")
    # 单侧左尾 p 值:抢跑使 z 变负,故 p = Phi(z) 越小越异常
    p_cal = np.array([timing.norm_cdf(z) for z in z_cal])
    h = sequential.calibrate_h(p_cal, args.arl0, k=1.5)
    print(f"  k=1.5, h={h:.2f}(在良性校准流上定标)")
    per_dev = defaultdict(list)
    for r in sorted(test, key=lambda r: (r["t"] is None, r["t"])):
        per_dev[r["dev"]].append(r)
    hdr = (f"  {'rho':>6} {'单消息':>8} {'检出率':>8} {'中位延迟':>9} "
           f"{'p90 延迟':>9}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for rho in RHOS:
        d = log(1 - rho)
        streams = []
        for dev, items in per_dev.items():
            if len(items) < 5:
                continue
            ps = [timing.norm_cdf(it["z"] + d / it["sigma"]) for it in items]
            for st in range(0, max(1, len(ps) - 20), 10):
                streams.append(ps[st:st + 40])
        prof = sequential.detection_profile(
            streams, lambda: sequential.CUSUM(k=1.5, h=h), budget=40)
        single = float(np.mean(-(z_test + d / s_test) > thr1))
        print(f"  {rho:>6.2f} {single:>8.3f} {prof['dr']:>8.3f} "
              f"{prof.get('median_delay', float('nan')):>9.1f} "
              f"{prof.get('p90_delay', float('nan')):>9.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
