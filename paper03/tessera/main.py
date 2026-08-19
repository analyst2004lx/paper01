"""TESSERA 一键入口：载入日志 → 建互证超图 → 注入攻击 → 检测 → 写结果。

默认跑 P1–P4 的耦合互证检出，并把覆盖度、串谋界摘要、带宽预算一并写入
`output/<tag>/summary.json`。细项诊断仍走 `tools/*_diag`；本入口负责把论文
实验的**主路径**收成一次可复现的运行。

用法(在 paper03/tessera/ 下):
    py main.py
    py main.py --attack P1 P3 --rate 0.2 --seed 42
    py main.py --tag smoke --attack P1
"""
from __future__ import annotations

import argparse
import json
import os
import time
from statistics import median

from algorithm import (attacks, baselines, budget, collusion, corroborate,
                       coverage, ingest, silence, taskgraph)

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILIES = (attacks.P1, attacks.P2, attacks.P3, attacks.P4)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="TESSERA 一键入口")
    ap.add_argument("--xes", default=None, help="XES 路径；默认取 database/")
    ap.add_argument("--bpmn", default=None, help="BPMN glob；默认取 database/")
    ap.add_argument("--attack", nargs="+", default=list(FAMILIES),
                    choices=list(FAMILIES),
                    help="要注入的攻击族，默认 P1–P4 全跑")
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-refute", action="store_true",
                    help="关掉对手方显式否证（褐地传感器口径）")
    ap.add_argument("--devices", type=int, default=28)
    ap.add_argument("--tag", default=None, help="输出子目录名")
    return ap.parse_args()


def load(xes, bpmn):
    raw = ingest.read_xes(xes or ingest.default_log_path())
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(bpmn or taskgraph.default_bpmn_glob(),
                            log_positions=pos)
    return live, g, coverage.realized(live, g)


def _pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def evaluate(recs, g, family, *, refute: bool, rate: float, seed: int) -> dict:
    """与 `tools.detect_diag.evaluate` 同口径：分母 = 伪造声明数。"""
    reports, _ = attacks.inject(recs, attacks.AttackSpec(
        family=family, rate=rate, seed=seed, explicit_refutation=refute))
    primary = {id(r) for r in reports if r.forged and not r.accomplice}
    accomp = {id(r) for r in reports if r.accomplice}
    proto = corroborate.replay(reports, g, refute=refute)
    hit = [e for e in proto.evidence if e.claim_id in primary]
    hit_ids = {e.claim_id for e in hit}
    lat = [e.latency_s for e in hit]
    return {
        "family": family,
        "n_forged": len(primary),
        "n_accomplice": len(accomp),
        "n_hit": len(hit_ids),
        "dr": len(hit_ids) / max(len(primary), 1),
        "latency_median_s": median(lat) if lat else None,
        "latency_p95_s": _pct(lat, 0.95),
        "by_outcome": {
            corroborate.REFUTED: sum(1 for e in hit
                                     if e.outcome == corroborate.REFUTED),
            corroborate.EXPIRED: sum(1 for e in hit
                                     if e.outcome == corroborate.EXPIRED),
        },
        "n_self_incriminating": sum(1 for e in hit if e.self_incriminating),
    }


def coverage_summary(recs) -> dict:
    s = coverage.summarize(recs)
    return {
        "n_activities": s["n_activities"],
        "n_corroborated": s["n_corroborated"],
        "frac_corroborated": s["frac_corroborated"],
        "n_same_device_only": s["n_same_device_only"],
        "n_no_realized": s["n_no_realized"],
        "n_no_model": s["n_no_model"],
        "oracle_gap": baselines.sensor_oracle(recs).gap,
    }


def budget_summary(n_devices: int) -> dict:
    kw = dict(p_loss=1e-2, n_devices=n_devices, far_target_per_hour=1.0)
    auto = budget.SafetyBudget()
    motion = budget.SafetyBudget.from_protective_field(
        field_mm=budget.protective_field_mm()["field_mm"])
    out = {}
    for name, b, rho in (("auto_indep", auto, 0.0),
                         ("motion_indep", motion, 0.0),
                         ("motion_burst", motion, 0.3)):
        d = budget.cheapest(b, burst_rho=rho, **kw)
        out[name] = None if d is None else {
            "t_hb_s": d.t_hb_s, "r_misses": d.r_misses,
            "detect_delay_s": d.detect_delay_s,
            "bandwidth_bps": d.bandwidth_bps,
            "far_per_hour": d.far_per_hour,
            "binding": budget.binding_constraint(d, b, burst_rho=rho, **kw),
        }
    out["pbft_5hz_bps"] = silence.pbft_bandwidth_bps(n_devices, 5.0)
    return out


def collusion_summary(recs, g) -> dict:
    s = collusion.summarize(collusion.walk(recs))
    return {
        "n_chains": s["n_chains"],
        "n_in_scope": s["n_in_scope"],
        "k_min": s["k_min"],
        "k_median": s["k_median"],
        "k_max": s["k_max"],
        "frac_k_ge_3": s["frac_k_ge_3"],
    }


def main() -> int:
    args = parse_args()
    t0 = time.time()
    live, g, recs = load(args.xes, args.bpmn)
    refute = not args.no_refute

    print(f"===== TESSERA  活动 {len(live)}  互证边 {len(g.witness_edges)}  "
          f"rate={args.rate} seed={args.seed} =====")

    cov = coverage_summary(recs)
    print(f"覆盖 {cov['n_corroborated']}/{cov['n_activities']} = "
          f"{cov['frac_corroborated']*100:.2f}%  "
          f"先知缺口 {cov['oracle_gap']*100:.2f}%")

    benign = attacks.benign_stream(recs)
    bp = corroborate.replay(benign, g)
    far = (len([e for e in bp.evidence if e.claim_seen])
           / max(len(benign), 1))
    print(f"良性误报 {far*100:.2f}%")

    detections = {}
    for fam in args.attack:
        r = evaluate(recs, g, fam, refute=refute,
                     rate=args.rate, seed=args.seed)
        detections[fam] = r
        lat = (f"{r['latency_median_s']:.1f}s"
               if r["latency_median_s"] is not None else "-")
        print(f"  {fam:4s}  DR={r['dr']:.3f}  "
              f"({r['n_hit']}/{r['n_forged']})  时延中位 {lat}")

    bud = budget_summary(args.devices)
    col = collusion_summary(recs, g)
    print(f"串谋界 k_min={col.get('k_min')} 中位={col.get('k_median')}  "
          f"最严带宽 {bud['motion_burst']['bandwidth_bps']:.0f} B/s")

    tag = args.tag or (
        f"ft_trier-{'+'.join(args.attack)}-r{args.rate}-s{args.seed}")
    out_dir = os.path.join(HERE, "output", tag)
    os.makedirs(out_dir, exist_ok=True)
    summary = {
        "config": {k: getattr(args, k) for k in
                   ("rate", "seed", "attack", "devices")
                   } | {"refute": refute, "n_activities": len(live)},
        "coverage": cov,
        "benign_far": far,
        "detections": detections,
        "collusion": col,
        "budget": bud,
        "elapsed_s": time.time() - t0,
    }
    path = os.path.join(out_dir, "summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print(f"===== 完成 {time.time()-t0:.1f}s  → "
          f"{os.path.relpath(path, HERE)} =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
