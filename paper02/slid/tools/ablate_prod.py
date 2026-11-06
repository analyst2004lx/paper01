"""E2 消融（生产配置）：在与主表完全相同的协议下逐项去掉硬约束层 / 时序 / 结构。

与旧版 tools.ablate 的区别：
  1. 检测器只用 train 拟合，与 tools.baseline_diag 一致（旧版用 train+calib）；
  2. 路集合取 Detector.path_weights 在 calib 上选出的生产路（旧版含互锁与
     Fisher 合成共五路）；
  3. 判决走 baselines.judge_detail，参照流与主表相同（测试折未注入版本）。

去掉一路时**每路预算固定**：其余各路仍得 alpha*w_i，总预算相应减少，
以免"去掉一路等于给其余路加预算"。每个 alpha 下同时报告偶然告警基线，
用于核对消融均值与主表均值的差异是否来自基线随 alpha 增大。

用法（在 paper02/slid/ 下）：  py -m tools.ablate_prod
"""
from __future__ import annotations

import argparse
import os

import numpy as np

from algorithm import archive, baselines, ingest, procmodel
from algorithm.detector import Detector, DetectorConfig
from tools.baseline_diag import FAMILIES, PATHS, _parts, attack_stream, split

OUT = os.path.join(archive.OUTPUT, "e2_prod_archive.json")
ARMS = {"full": None, "no_hard": 0, "no_timing": 1, "no_structural": 2}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alphas", default="0.05,0.01")
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--archive", default=OUT)
    args = ap.parse_args()
    alphas = [float(x) for x in args.alphas.split(",")]

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)
    benign = baselines.order_stream(test)

    records = []
    for alpha in alphas:
        det = Detector(DetectorConfig(alpha=alpha, online_update=False)).fit(
            train, model=model, rng=np.random.default_rng(0), temporal=True)
        w, _, keep = det.path_weights(baselines.order_stream(calib),
                                      alpha=alpha)
        w = [float(x) for x in w]
        print(f"alpha={alpha}: keep={[PATHS[i] for i in keep]} w={w}")
        for fam in FAMILIES:
            for s in range(args.seeds):
                stream, lab = attack_stream(test, fam, s, args.rate, args.rho,
                                            det.struct, det.model)
                rng = np.random.default_rng(300 + s)
                pb = _parts(det, benign,
                            np.random.default_rng(rng.integers(1 << 30)))
                pa = _parts(det, stream, rng)
                for arm, drop in ARMS.items():
                    wa = list(w)
                    if drop is not None:
                        wa[drop] = 0.0
                    if sum(wa) <= 0:
                        continue
                    a_arm = alpha * sum(wa) / sum(w)
                    r = baselines.judge_detail(pb, pa, lab, alpha=a_arm,
                                               weights=wa).to_dict()
                    records.append({"alpha": alpha, "family": fam, "seed": s,
                                    "arm": arm, "seq": r["seq"],
                                    "seq_fpr": r["seq_fpr"],
                                    "floor": r["floor"],
                                    "seq_net": r["seq_net"]})
            print(f"  {fam} done")

    path = archive.dump(args.archive, {
        "meta": {"alphas": alphas, "rho": args.rho, "rate": args.rate,
                 "seeds": args.seeds, "budget": 10,
                 "budget_rule": "per-path alpha fixed at alpha*w_i",
                 "reference": "uninjected test fold (same as main table)"},
        "runs": records,
    })
    print(f"archive {path} ({len(records)} runs)")

    for alpha in alphas:
        print(f"\n=== alpha={alpha} ===")
        print(f"{'arm':<15}" + "".join(f"{f:>7}" for f in FAMILIES)
              + f"{'mean':>8}{'Δ':>8}{'raw':>8}{'floor':>8}{'seqFPR':>8}")
        base = None
        for arm in ARMS:
            rs = [r for r in records if r["alpha"] == alpha and r["arm"] == arm]
            if not rs:
                continue
            cells = [np.mean([r["seq_net"] for r in rs if r["family"] == f])
                     for f in FAMILIES]
            m = float(np.mean(cells))
            base = m if arm == "full" else base
            d = "" if arm == "full" else f"{m - base:+.2f}"
            print(f"{arm:<15}" + "".join(f"{c:>7.2f}" for c in cells)
                  + f"{m:>8.2f}{d:>8}"
                  + f"{np.mean([r['seq'] for r in rs]):>8.2f}"
                  + f"{np.mean([r['floor'] for r in rs]):>8.3f}"
                  + f"{np.mean([r['seq_fpr'] for r in rs]):>8.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
