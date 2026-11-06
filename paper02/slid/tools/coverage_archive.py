"""tab:coverage 的存档版：按 coverage_matrix 的口径重跑，逐种子写 JSON。

口径与 tools.coverage_matrix 相同（时间序 75/25 按 case 切分、online_update=False、
每通道单独判决、alpha=0.01、rate=0.2、rho=0.30、种子 0..2）。

用法（在 paper02/slid/ 下）:  py -m tools.coverage_archive [--timing-score pvalue]
输出: output/coverage_archive.json（pvalue 臂为 coverage_archive_pvalue.json）
"""
from __future__ import annotations

import json
import os

import numpy as np

from algorithm import ingest, procmodel
from algorithm.detector import CHANNELS, Detector, DetectorConfig
from tools.coverage_matrix import FAMILIES, measure

OUT = os.path.join("output", "coverage_archive.json")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing-score", default="z", choices=("z", "pvalue"))
    args = ap.parse_args()
    out = OUT if args.timing_score == "z" else OUT.replace(".json", "_pvalue.json")
    alpha, rate, rho, seeds = 0.01, 0.2, 0.30, 3
    raw = ingest.read_xes(ingest.default_log_path())
    live = ingest.valid(raw, drop_failure=True)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(procmodel.default_bpmn_glob(), log_positions=log_pos)

    by_case = {}
    for a in live:
        by_case.setdefault(a.case, []).append(a)
    keys = sorted(by_case, key=lambda k: min(
        (x.t_consume for x in by_case[k] if x.t_consume is not None),
        default=None) or 0)
    cut = int(len(keys) * 0.75)
    fit_acts = [a for k in keys[:cut] for a in by_case[k]]
    test = [a for k in keys[cut:] for a in by_case[k]]

    det = Detector(DetectorConfig(alpha=alpha, online_update=False,
                                  timing_score=args.timing_score)).fit(
        fit_acts, model=model, rng=np.random.default_rng(0), temporal=True)

    cols = ["hard"] + list(CHANNELS) + ["seq"]
    fam_out = {}
    for fam in FAMILIES:
        runs = []
        for s in range(seeds):
            r = measure(det, test, fam, alpha, s, rate, rho)
            if r is None:
                continue
            runs.append({"seed": s, "n_attacked": int(r["_n"]),
                         **{c: {"dr": float(r[c][0]), "fpr": float(r[c][1])}
                            for c in cols}})
        mean = {c: {"dr": float(np.mean([x[c]["dr"] for x in runs])),
                    "fpr": float(np.mean([x[c]["fpr"] for x in runs]))}
                for c in cols}
        fam_out[fam] = {"runs": runs, "mean": mean}
        print(fam, " ".join(f"{c}={mean[c]['dr']:.2f}({mean[c]['fpr']:.2f})"
                            for c in cols))

    doc = {"protocol": {"alpha": alpha, "rate": rate, "rho": rho,
                        "seeds": list(range(seeds)), "split": "temporal 75/25 by case",
                        "n_fit_acts": len(fit_acts), "n_test_acts": len(test),
                        "online_update": False, "q_inter": float(det.q_inter),
                        "timing_score": args.timing_score},
           "families": fam_out}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("written", out, "fit", len(fit_acts), "test", len(test))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
