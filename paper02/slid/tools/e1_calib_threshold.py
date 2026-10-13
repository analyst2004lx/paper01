"""E1 附表：阈值与 CUSUM 门限改在校准折上标定后的主对比。

主表（tools.baseline_diag）把每个方法的经验 p 值参照与 CUSUM 门限都放在
测试折的未注入版本上，使各方法经验误报对齐到 alpha。本工具只改这一处：
参照流换成与 train、test 都不重叠的校准折 calib，门限 h 在 calib 的 p 值流上
按 ARL0=1/alpha 反解，然后在测试折的未注入版本上实测序贯误报、在受攻击流上
实测检出。偶然告警基线按各方法**在测试折上实测**的序贯误报计算。

其余一切与主表相同：只用 train 拟合、同一注入流、同一预算划分与路权重
（本方法的路权重仍在 calib 上按天花板判据选出）、同一延迟预算 10 条。
每个 run 同时重算主表口径（oracle 参照），用于核对与 e1_archive.json 一致。

用法（在 paper02/slid/ 下）：  py -m tools.e1_calib_threshold
"""
from __future__ import annotations

import argparse
import os

import numpy as np

from algorithm import archive, baselines, ingest, procmodel, sequential
from algorithm.detector import Detector, DetectorConfig
from tools.baseline_diag import FAMILIES, _parts, attack_stream, split

OUT = os.path.join(archive.OUTPUT, "e1_calib_archive.json")


def _run_cusum(ps, h, k):
    c = sequential.CUSUM(k=k, h=h)
    out = []
    for i, p in enumerate(ps):
        if c.update(p):
            out.append(i)
            c.reset()
    return out


def judge_ref(ref_parts, benign_parts, attack_parts, labels, *, alpha,
              budget=10, weights=None, k=1.5):
    """与 baselines.judge_detail 同一规则，但 p 值参照与 h 取自 ref_parts。"""
    m = len(ref_parts)
    ws = [1.0 / m] * m if weights is None else \
        [w / float(sum(weights)) for w in weights]
    fired, fp_seq = set(), set()
    for w, pr_raw, pb_raw, pa_raw in zip(ws, ref_parts, benign_parts,
                                         attack_parts):
        if w <= 0:
            continue
        a = alpha * w
        pr = baselines.empirical_p(pr_raw, pr_raw)
        pb = baselines.empirical_p(pr_raw, pb_raw)
        pa = baselines.empirical_p(pr_raw, pa_raw)
        # 与 baselines._cusum_alarms 一致：每路按其自身预算 a 反解 ARL0=1/a
        h = sequential.calibrate_h(pr, max(int(1.0 / a), 2), k=k)
        fired |= set(_run_cusum(pa, h, k))
        fp_seq |= set(_run_cusum(pb, h, k))
    pos = [i for i, v in enumerate(labels) if v]
    fired_s = sorted(fired)
    delays = []
    for i in pos:
        j = baselines._first_at_least(fired_s, i)
        delays.append(int(j - i) if j is not None and j - i <= budget else None)
    n_b = len(benign_parts[0])
    sdr = sum(d is not None for d in delays) / len(pos) if pos else float("nan")
    sfpr = len(fp_seq) / max(n_b, 1)
    floor = baselines.chance_floor(sfpr, budget)
    return {"seq": sdr, "seq_fpr": sfpr, "floor": floor,
            "seq_net": sdr - floor, "delays": delays,
            "benign_gaps": baselines._alarm_gaps(fp_seq, n_b),
            "n_pos": len(pos)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--archive", default=OUT)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)
    benign = baselines.order_stream(test)
    calib_s = baselines.order_stream(calib)

    det = Detector(DetectorConfig(alpha=args.alpha, online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)
    w, _, keep = det.path_weights(calib_s, alpha=args.alpha)
    names = list(baselines.IMPLEMENTED)
    fitted = {n: baselines.fit_baseline(n, train) for n in names}
    print(f"train {len(train)} / calib {len(calib)} / test {len(test)}; "
          f"alpha={args.alpha}; keep paths={keep}; baselines={names}")

    ref_ours = _parts(det, calib_s, np.random.default_rng(11))
    ref_base = {}
    ben_base = {}
    for n in names:
        pc = fitted[n].parts_stream(calib_s)
        pb = fitted[n].parts_stream(benign)
        mcol = len(pc[0])
        ref_base[n] = [[r[j] for r in pc] for j in range(mcol)]
        ben_base[n] = [[r[j] for r in pb] for j in range(mcol)]

    records = []
    for fam in FAMILIES:
        for s in range(args.seeds):
            stream, lab = attack_stream(test, fam, s, args.rate, args.rho,
                                        det.struct, det.model)
            for n in names:
                st = baselines.order_stream(stream)
                idx = {id(a): i for i, a in enumerate(stream)}
                lb = [lab[idx[id(a)]] for a in st]
                pa = fitted[n].parts_stream(st)
                pa = [[r[j] for r in pa] for j in range(len(pa[0]))]
                cal = judge_ref(ref_base[n], ben_base[n], pa, lb,
                                alpha=args.alpha)
                ora = baselines.judge_detail(ben_base[n], pa, lb,
                                             alpha=args.alpha).to_dict()
                records.append({"family": fam, "seed": s, "method": n,
                                "calib": cal, "oracle_seq_net": ora["seq_net"],
                                "oracle_seq_fpr": ora["seq_fpr"]})
            rng = np.random.default_rng(300 + s)
            pb = _parts(det, benign, np.random.default_rng(rng.integers(1 << 30)))
            pa = _parts(det, stream, rng)
            cal = judge_ref(ref_ours, pb, pa, lab, alpha=args.alpha, weights=w)
            ora = baselines.judge_detail(pb, pa, lab, alpha=args.alpha,
                                         weights=w).to_dict()
            records.append({"family": fam, "seed": s, "method": "ours",
                            "calib": cal, "oracle_seq_net": ora["seq_net"],
                            "oracle_seq_fpr": ora["seq_fpr"]})
        print(f"  {fam} done")

    path = archive.dump(args.archive, {
        "meta": {"alpha": args.alpha, "rho": args.rho, "rate": args.rate,
                 "seeds": args.seeds, "budget": 10,
                 "arl0_per_path": "1/(alpha*w)",
                 "reference": "calib fold", "n_calib": len(calib),
                 "n_test": len(test), "keep_paths": list(keep)},
        "runs": records,
    })
    print(f"archive {path} ({len(records)} runs)")

    cols = names + ["ours"]
    print(f"\n{'攻击':<6}" + "".join(f"{c:>18}" for c in cols))
    for fam in FAMILIES:
        row = ""
        for c in cols:
            v = [r["calib"]["seq_net"] for r in records
                 if r["family"] == fam and r["method"] == c]
            o = [r["oracle_seq_net"] for r in records
                 if r["family"] == fam and r["method"] == c]
            row += f"{np.mean(v):>8.2f}±{np.std(v):.2f}({np.mean(o):.2f})"
        print(f"{fam:<6}{row}")
    print("序贯误报(测试折实测,校准折门限): " + "  ".join(
        f"{c}={np.mean([r['calib']['seq_fpr'] for r in records if r['method']==c]):.3f}"
        for c in cols))
    print("括号内为主表口径(oracle)重算值,应与 e1_archive.json 一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
