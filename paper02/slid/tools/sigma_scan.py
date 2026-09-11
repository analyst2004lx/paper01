"""E5:时序变异增大时,抢跑可检测性如何塌掉。

在 bound_curve 的真实残差上把每组 sigma 放大 k 倍,等价于同一物理抢跑
在 z 空间被压缩。不重拟合检测器。k=1 对应该产线全局口径。

用法(在 paper02/slid/ 下):  py -m tools.sigma_scan
"""
from __future__ import annotations

import argparse
from math import log

import numpy as np

from algorithm import archive, ingest, sequential, timing
from tools.bound_curve import RHOS, build_folds


KS = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--rho", type=float, default=0.30)
    args = ap.parse_args()

    acts = ingest.valid(ingest.read_xes(args.xes), drop_failure=False)
    cal, test, sigmas = build_folds(acts, seed=7)
    z_cal = np.array([r["z"] for r in cal])
    z_test = np.array([r["z"] for r in test])
    s_test = np.array([r["sigma"] for r in test])
    thr = float(np.quantile(-z_cal, 1 - args.alpha))
    w = np.array([sum(1 for r in test if r["grp"] == g) for g in sigmas],
                 dtype=float)
    sbar = float(np.average(list(sigmas.values()), weights=w))
    print(f"校准 {len(cal)} 测试 {len(test)}  全局加权 sigma={sbar:.3f}  "
          f"单侧阈值 {thr:.3f}")
    print(f"{'k':>6} {'sigma':>8} {'rho*':>8} {'DR@0.30':>9} {'CUSUM':>8}")

    rows = []
    p_cal = np.array([timing.norm_cdf(z) for z in z_cal])
    h = sequential.calibrate_h(p_cal, 500, k=1.5)
    d = log(1 - args.rho)
    for k in KS:
        sigma_k = sbar * k
        rho_star = timing.rho_star(sigma_k, args.alpha)
        za = (z_test + d / s_test) / k
        dr = float(np.mean(-za > thr))
        streams = []
        # 按设备切短窗,残差除以 k
        by = {}
        for r, zi in zip(test, za):
            by.setdefault(r["dev"], []).append(timing.norm_cdf(zi))
        for items in by.values():
            if len(items) < 5:
                continue
            for st in range(0, max(1, len(items) - 20), 10):
                streams.append(items[st:st + 40])
        prof = sequential.detection_profile(
            streams, lambda: sequential.CUSUM(k=1.5, h=h), budget=40)
        print(f"{k:>6.1f} {sigma_k:>8.3f} {rho_star*100:>7.1f}% "
              f"{dr:>9.3f} {prof['dr']:>8.3f}")
        rows.append({
            "k": k, "sigma": sigma_k, "rho_star": rho_star,
            "single_dr": dr, "cusum_dr": prof["dr"],
            "delays": prof.get("delays", []),
        })
    archive.dump(archive.E5_PATH, {
        "meta": {"alpha": args.alpha, "rho": args.rho, "sbar": sbar,
                 "thr": thr, "n_cal": len(cal), "n_test": len(test)},
        "rows": rows,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
