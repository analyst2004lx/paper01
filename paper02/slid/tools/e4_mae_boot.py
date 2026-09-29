"""表 tab:e4 理论与实测单侧检出率之平均绝对偏差(MAE)的自助区间。

与 tools.bound_curve 同一折划分(seed=7)、同一单侧共形阈值与分组混合预测。
每次自助对校准折与测试折分别有放回重抽,重估阈值后在 7 个 rho 上重算 MAE。
另报 20 个折划分种子下的 MAE 分布,作为划分敏感性。
不改写 E4 存档;输出 output/e4_mae_boot.json。

用法(在 paper02/slid/ 下):  py -m tools.e4_mae_boot
"""
from __future__ import annotations

import json
import os
from math import log

import numpy as np
from scipy.special import ndtr

from algorithm import ingest
from tools.bound_curve import RHOS, build_folds

OUT = os.path.join("output", "e4_mae_boot.json")
ALPHA = 0.01


def mae(z_cal, z_test, s_test):
    thr1 = float(np.quantile(-z_cal, 1 - ALPHA))
    errs, rows = [], []
    for rho in RHOS:
        shift = log(1 - rho) / s_test
        dr = float(np.mean(-(z_test + shift) > thr1))
        pr = float(np.mean(ndtr(-thr1 - shift)))
        errs.append(abs(dr - pr))
        rows.append((rho, dr, pr))
    return float(np.mean(errs)), rows


def main() -> int:
    acts = ingest.valid(ingest.read_xes(ingest.default_log_path()), drop_failure=False)
    cal, test, _ = build_folds(acts, seed=7)
    z_cal = np.array([r["z"] for r in cal])
    z_test = np.array([r["z"] for r in test])
    s_test = np.array([r["sigma"] for r in test])
    point, rows = mae(z_cal, z_test, s_test)
    print(f"n_cal={len(cal)} n_test={len(test)}  MAE(point)={point:.4f}")
    for rho, dr, pr in rows:
        print(f"  rho={rho:.2f}  measured {dr:.3f}  predicted {pr:.3f}")

    rng = np.random.default_rng(2026)
    B = 2000
    boot = []
    for _ in range(B):
        ic = rng.integers(0, len(z_cal), len(z_cal))
        it = rng.integers(0, len(z_test), len(z_test))
        boot.append(mae(z_cal[ic], z_test[it], s_test[it])[0])
    boot = np.array(boot)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"bootstrap B={B}: 95% percentile CI [{lo:.4f}, {hi:.4f}]  "
          f"median {np.median(boot):.4f}")

    seeds = []
    for s in range(20):
        c, t, _ = build_folds(acts, seed=s)
        seeds.append(mae(np.array([r["z"] for r in c]),
                         np.array([r["z"] for r in t]),
                         np.array([r["sigma"] for r in t]))[0])
    seeds = np.array(seeds)
    print(f"split seeds 0..19: mean {seeds.mean():.4f}  sd {seeds.std():.4f}  "
          f"range [{seeds.min():.4f}, {seeds.max():.4f}]")

    doc = {"protocol": {"alpha": ALPHA, "sided": "one", "split_seed": 7,
                        "rhos": list(RHOS), "bootstrap": B, "rng": 2026,
                        "resample": "calib and test folds independently, threshold re-estimated"},
           "n_cal": len(cal), "n_test": len(test),
           "point": point, "rows": rows,
           "ci95": [float(lo), float(hi)], "boot_median": float(np.median(boot)),
           "split_seeds": [float(x) for x in seeds]}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("written", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
