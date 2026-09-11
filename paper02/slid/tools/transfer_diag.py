"""E6:把在场景 A 上标定的检测器原样搬到 B、C,看误报是否守得住。

不问 AFT 系数好不好用(协变量已降级),问的是 (mu, sigma, 共形阈值)
换部署后还能否当同一个 alpha 用。A->B 是行程均值迁移,A->C 是时长变异迁移。
"""
from __future__ import annotations

import argparse

import numpy as np

from algorithm import archive, attacks, plant
from algorithm.detector import Detector, DetectorConfig
from tools.robust_diag import _score_fpr


def _split(acts, frac: float = 0.75):
    by = {}
    for a in acts:
        by.setdefault(a.case, []).append(a)
    keys = sorted(by, key=lambda k: min(
        (x.t_consume for x in by[k] if x.t_consume is not None),
        default=None) or 0)
    cut = max(1, int(len(keys) * frac))
    train = [a for k in keys[:cut] for a in by[k]]
    test = [a for k in keys[cut:] for a in by[k]]
    return train, test


def _fit(train, model, seed: int) -> Detector:
    rng = np.random.default_rng(seed)
    return Detector(DetectorConfig(alpha=0.01, online_update=False)).fit(
        train, model=model, rng=rng, temporal=True)


def _a3_dr(det, test, model, rho: float, seed: int) -> dict:
    spec = attacks.AttackSpec(family="A3", rho=rho, rate=0.20, seed=seed)
    attacked, labels = attacks.inject(test, spec)
    rng = np.random.default_rng(seed + 17)
    det._reset_online()
    n_pos = hits = 0
    idx = {id(a): i for i, a in enumerate(attacked)}
    for a in sorted((x for x in attacked if x.t_consume is not None),
                    key=lambda x: (x.t_consume, x.order)):
        if det._hard_layer(a) is not None:
            continue
        raw = det._score_one(a, rng=rng)
        p = det._recalibrate(raw, rng)
        if labels[idx[id(a)]]:
            n_pos += 1
            if p[0] <= 0.01:
                hits += 1
    det._reset_online()
    return {"n_pos": n_pos, "dr": hits / max(n_pos, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rho", type=float, default=0.30)
    args = ap.parse_args()

    model = plant.reference_model()
    streams = {name: plant.generate(name) for name in ("A", "B", "C")}
    splits = {name: _split(acts) for name, acts in streams.items()}

    print("=== 场景规模 ===")
    for name, acts in streams.items():
        cfg = plant.CONFIGS[name]
        print(f"  {name}  jobs={cfg.n_jobs}  sigma={cfg.sigma:.2f}  "
              f"dist={cfg.dist_arm}/{cfg.dist_wh}  n={len(acts)}")

    native = {}
    print("\n=== 本场景标定 (时间序, alpha=0.01) ===")
    for name, (tr, te) in splits.items():
        det = _fit(tr, model, seed=0)
        fpr = _score_fpr(det, te, np.random.default_rng(0))
        dr = _a3_dr(det, te, model, args.rho, seed=0)
        native[name] = {"fpr": fpr, "a3": dr}
        print(f"  {name}  n_test={fpr['n']:<4}  hard={fpr['hard']:.3f}  "
              f"time={fpr['time']['0.01']:.3f}  struct={fpr['struct']['0.01']:.3f}  "
              f"A3@0.30={dr['dr']:.3f}")

    xfer = {}
    print("\n=== 迁移 (源上拟合, 目标测试折上计分) ===")
    for src, dst in (("A", "B"), ("A", "C"), ("B", "A")):
        det = _fit(splits[src][0], model, seed=0)
        fpr = _score_fpr(det, splits[dst][1], np.random.default_rng(1))
        dr = _a3_dr(det, splits[dst][1], model, args.rho, seed=1)
        xfer[f"{src}->{dst}"] = {"fpr": fpr, "a3": dr}
        print(f"  {src}->{dst}  n={fpr['n']:<4}  hard={fpr['hard']:.3f}  "
              f"time={fpr['time']['0.01']:.3f}  struct={fpr['struct']['0.01']:.3f}  "
              f"A3@0.30={dr['dr']:.3f}")

    archive.dump(archive.E6_PATH, {
        "native": native, "transfer": xfer, "rho": args.rho,
        "note": "AFT 不迁移;迁移的是时长核与共形阈值。",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
