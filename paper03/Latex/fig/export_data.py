#!/usr/bin/env python3
"""从 tessera 导出论文作图数据 → data/plot_data.json + loss_sweep.csv

用法（在 paper03/Latex/fig 下）::
    py export_data.py              # 锚定表 + smoke + 现场串谋直方图
    py export_data.py --anchored   # 仅锚定表（不 import tessera）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIG = Path(__file__).resolve().parent
DATA = FIG / "data"
TESSERA = FIG.parents[1] / "tessera"


def anchored() -> dict:
    return {
        "source": "anchored_readme_assertions",
        "tier1": {
            "labels": ["R0", "S1", "S2", "S3", "OURS"],
            "far": [0.019, 0.042, 0.004, 0.000, 0.023],
            "p1_dr": [0.014, 0.000, 0.003, 0.000, 1.000],
            "p3_dr": [0.014, 0.000, 0.003, 0.000, 1.000],
            "p2_dr": [0.000, 1.000, 1.000, 1.000, 1.000],
        },
        "tier2": {
            "labels": ["OURS", "W1", "W2", "W3", "W4"],
            "witness_mean": [2.18, 2.18, 9.00, 1.00, 2.92],
            "far": [0.023, 0.000, 0.023, 0.002, 0.000],
            "p1_dr": [1.000, 0.000, 1.000, 0.105, 0.518],
            "margin": [0.977, 0.000, 0.977, 0.103, 0.518],
        },
        "ablation": {
            "attacks": ["P1", "P2", "P3", "P4"],
            "channels": ["S1", "corr", "silence", "both"],
            "channel_labels": ["S1 watchdog", "corr. only", "silence only", "combined"],
            "dr": [
                [0.000, 1.000, 1.000, 1.000],
                [1.000, 0.746, 1.000, 1.000],
                [0.000, 1.000, 0.000, 1.000],
                [0.000, 0.184, 0.000, 0.184],
            ],
            "latency_median_s": [
                [None, 54.6, 1.8, 1.8],
                [334.0, 325.0, 1.8, 1.8],
                [None, 54.6, None, 54.6],
                [None, 355.4, None, 355.4],
            ],
            "p4_accomplice_dr": 0.750,
        },
        "heartbeat": {
            "regimes": ["auto_indep", "motion_indep", "motion_burst"],
            "regime_labels": ["auto+indep", "motion+indep", "motion+burst"],
            "silence_bps": [621, 2311, 7675],
            "silence_tdet": [2.175, 0.592, 0.594],
            "period_tdet": [17.328, 4.662, 4.680],
            "ratio": [7.97, 7.88, 7.88],
            "detect_budget_s": [2.18, 0.60, 0.60],
        },
        "collusion": {
            "k_min": 1,
            "k_median": 5,
            "k_max": 13,
            "frac_k_ge_3": 0.8099,
            "n_in_scope": 2373,
            "k_hist": None,
        },
        "coverage": {
            "frac_corroborated": 0.7005,
            "oracle_gap": 0.2995,
            "benign_far": 0.0225,
        },
        "budget_pbft_5hz_bps": 1003520.0,
    }


def enrich_from_tessera(obj: dict) -> dict:
    sys.path.insert(0, str(TESSERA))
    from algorithm import collusion, coverage, ingest, taskgraph, baselines

    raw = ingest.read_xes(ingest.default_log_path())
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(taskgraph.default_bpmn_glob(), log_positions=pos)
    recs = coverage.realized(live, g)

    chains = collusion.walk(recs)
    summary = collusion.summarize(chains)
    obj["collusion"] = {
        "k_min": summary["k_min"],
        "k_median": summary["k_median"],
        "k_max": summary["k_max"],
        "frac_k_ge_3": summary["frac_k_ge_3"],
        "n_in_scope": summary["n_in_scope"],
        "k_hist": {str(k): n for k, n in summary["k_hist"]},
    }
    s = coverage.summarize(recs)
    obj["coverage"] = {
        "frac_corroborated": s["frac_corroborated"],
        "oracle_gap": baselines.sensor_oracle(recs).gap,
        "benign_far": obj["coverage"]["benign_far"],
    }
    smoke = TESSERA / "output" / "smoke" / "summary.json"
    if smoke.exists():
        obj["smoke_summary"] = json.loads(smoke.read_text(encoding="utf-8"))
        if "benign_far" in obj["smoke_summary"]:
            obj["coverage"]["benign_far"] = obj["smoke_summary"]["benign_far"]
    obj["source"] = "anchored_tables+live_collusion_coverage"
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchored", action="store_true")
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)

    obj = anchored()
    if not args.anchored:
        try:
            print("enriching from tessera (collusion hist + coverage)…")
            obj = enrich_from_tessera(obj)
        except Exception as e:
            print(f"tessera enrich failed: {e!r}; using anchored only")

    out = DATA / "plot_data.json"
    out.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")

    src = TESSERA / "experiments" / "loss_sweep.csv"
    if src.exists():
        dst = DATA / "loss_sweep.csv"
        dst.write_bytes(src.read_bytes())
        print(f"wrote {dst}")


if __name__ == "__main__":
    main()
