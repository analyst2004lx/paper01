"""部署口径误报:时间序对照、含错版 C'、产品切换 E9。

C' 用 gold standard 拟合,在第三方含错日志(NTP/重复/缺失)上测 FPR,
不注入攻击。E9 把测试折按工作流是否在训练折出现过切开。

用法(在 paper02/slid/ 下):  py -m tools.robust_diag
"""
from __future__ import annotations

import argparse

import numpy as np

from algorithm import archive, ingest, procmodel
from algorithm.detector import CHANNELS, Detector, DetectorConfig
from tools import online_diag as OD


def _meanstd(xs):
    if not xs:
        return float("nan"), float("nan")
    return float(np.mean(xs)), float(np.std(xs))


def time_order_fpr(live, model, seeds: int) -> dict:
    acc = {lbl: {c: {a: [] for a in OD.ALPHAS}
                 for c in list(CHANNELS) + ["fused"]}
           for lbl in ("随机折", "时间序")}
    ns = []
    for seed in range(seeds):
        for temporal, lbl in ((False, "随机折"), (True, "时间序")):
            det, test, rng = OD.build(live, model, temporal=temporal, seed=seed)
            r = OD.channel_fpr(det, test, rng)
            ns.append(r["_n"])
            for c in list(CHANNELS) + ["fused"]:
                for a in OD.ALPHAS:
                    acc[lbl][c][a].append(r[c][a])
    out = {}
    for lbl, chs in acc.items():
        out[lbl] = {}
        for c, av in chs.items():
            out[lbl][c] = {str(a): {"mean": _meanstd(xs)[0],
                                    "std": _meanstd(xs)[1]}
                           for a, xs in av.items()}
    out["_n"] = float(np.mean(ns)) if ns else 0.0
    return out


def _score_fpr(det, stream, rng) -> dict:
    """生产三路在一段良性流上的经验误报(硬层或共形越界)。"""
    det._reset_online()
    n = hard = 0
    hits = {c: {a: 0 for a in OD.ALPHAS} for c in CHANNELS}
    for a in sorted((x for x in stream if x.t_consume is not None),
                    key=lambda x: (x.t_consume, x.order)):
        det._flush_pending(a.t_consume)
        n += 1
        if det._hard_layer(a) is not None:
            hard += 1
            continue
        raw = det._score_one(a, rng=rng)
        p = det._recalibrate(raw, rng)
        for j, ch in enumerate(CHANNELS):
            for a0 in OD.ALPHAS:
                if p[j] <= a0:
                    hits[ch][a0] += 1
    det._reset_online()
    n = max(n, 1)
    out = {"n": n, "hard": hard / n}
    for ch in CHANNELS:
        out[ch] = {str(a): hits[ch][a] / n for a in OD.ALPHAS}
    return out


def dirty_cprime(gold, dirty, model) -> dict:
    det, gold_test, rng = OD.build(gold, model, temporal=True, seed=0)
    return {
        "gold_test": _score_fpr(det, gold_test, rng),
        "dirty_all": _score_fpr(det, dirty, np.random.default_rng(1)),
        "n_gold": len(gold), "n_dirty": len(dirty),
    }


def product_shift(live, model) -> dict:
    """E9:测试折里未见工作流 vs 已见工作流的 FPR。"""
    by_case = OD._by_case(live)
    keys = sorted(by_case, key=lambda k: min(
        (a.t_consume for a in by_case[k] if a.t_consume is not None),
        default=None) or 0)
    cut = int(len(keys) * 0.75)
    fit_keys, test_keys = keys[:cut], keys[cut:]
    fit_wf = {a.workflow for k in fit_keys for a in by_case[k] if a.workflow}
    seen, unseen = [], []
    for k in test_keys:
        wfs = {a.workflow for a in by_case[k] if a.workflow}
        sink = unseen if wfs and wfs.isdisjoint(fit_wf) else seen
        sink.extend(by_case[k])
    rng = np.random.default_rng(0)
    det = Detector(DetectorConfig(alpha=0.01, online_update=False)).fit(
        [a for k in fit_keys for a in by_case[k]], model=model,
        rng=rng, temporal=True)
    return {
        "n_fit_wf": len(fit_wf),
        "n_seen": len(seen), "n_unseen": len(unseen),
        "seen": _score_fpr(det, seen, rng),
        "unseen": _score_fpr(det, unseen, np.random.default_rng(2)),
        "unseen_workflows": sorted({a.workflow for a in unseen if a.workflow}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    gold = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)

    print("=== 时间序 vs 随机折 FPR ===")
    fpr = time_order_fpr(gold, model, args.seeds)
    print(f"  {'通道':<8} {'划分':<8} {'a=0.05':>16} {'a=0.01':>16}")
    for c in list(CHANNELS) + ["fused"]:
        for lbl in ("随机折", "时间序"):
            cells = "  ".join(
                f"{fpr[lbl][c][str(a)]['mean']:.3f} +/- "
                f"{fpr[lbl][c][str(a)]['std']:.3f}" for a in OD.ALPHAS)
            print(f"  {c if lbl == '随机折' else '':<8} {lbl:<8} {cells}")
    print(f"  n={fpr['_n']:.0f}")

    zpath, member = ingest.default_dirty_log_path()
    dirty_raw = ingest.read_xes(zpath, member=member)
    dirty = ingest.valid(dirty_raw, drop_failure=True)
    print(f"\n=== C' 含错版 (gold {len(gold)} / dirty {len(dirty)}) ===")
    cprime = dirty_cprime(gold, dirty, model)
    for name, block in (("gold_test", cprime["gold_test"]),
                        ("dirty_all", cprime["dirty_all"])):
        t = block["time"].get("0.01", float("nan"))
        s = block["struct"].get("0.01", float("nan"))
        print(f"  {name:<12} n={block['n']:<5} hard={block['hard']:.3f}  "
              f"time@0.01={t:.3f}  struct@0.01={s:.3f}")

    print("\n=== E9 产品切换 (未见工作流) ===")
    e9 = product_shift(gold, model)
    print(f"  训练折工作流 {e9['n_fit_wf']}  已见 {e9['n_seen']}  "
          f"未见 {e9['n_unseen']}  {e9['unseen_workflows']}")
    for name in ("seen", "unseen"):
        b = e9[name]
        print(f"  {name:<8} n={b['n']:<5} hard={b['hard']:.3f}  "
              f"time@0.01={b['time']['0.01']:.3f}  "
              f"struct@0.01={b['struct']['0.01']:.3f}")

    archive.dump(archive.ROBUST_PATH, {
        "time_order_fpr": fpr, "cprime": cprime, "e9": e9,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
