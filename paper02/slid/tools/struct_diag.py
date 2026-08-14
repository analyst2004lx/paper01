"""M3 状态粒度:操作名 vs (设备, 操作)。

实测覆盖矩阵时暴露出一件事:case 级结构链的状态是**操作名**,于是"错误的
设备做了正确的操作"对结构通道完全不可见——A2 物理不可行注入只能靠 F 掩码,
而 F 只在同 case 同设备有前驱时可查,覆盖率 31%。

把状态换成 (设备, 操作) 二元组理应恢复设备敏感性,但会抬高状态数、稀释每个
转移的支撑度,还可能把校准集打散到 Dirichlet 平滑主导。收益与代价都要测:

  Q1 状态空间与支撑度:状态数、观测到的转移数、每转移平均支撑、p 值取值数
  Q2 时间序 conformal FPR:粒度变细后校准还站得住吗
  Q3 对 A2/A4 的检出:设备敏感性到底换来多少

用法(在 paper02/slid/ 下):  py -m tools.struct_diag
"""
from __future__ import annotations

import argparse

import numpy as np

from algorithm import attacks, conformal, ingest, procmodel, structural
from algorithm.detector import Detector, DetectorConfig

ARMS = ("op", "device_op")
ARM_ZH = {"op": "操作名", "device_op": "(设备,操作)"}


def build(live, model, *, arm: str, alpha: float, seed: int):
    by_case = {}
    for a in live:
        by_case.setdefault(a.case, []).append(a)
    keys = sorted(by_case, key=lambda k: min(
        (x.t_consume for x in by_case[k] if x.t_consume is not None),
        default=None) or 0)
    cut = int(len(keys) * 0.75)
    det = Detector(DetectorConfig(alpha=alpha, struct_state=arm,
                                  online_update=False)).fit(
        [a for k in keys[:cut] for a in by_case[k]], model=model,
        rng=np.random.default_rng(seed), temporal=True)
    return det, [a for k in keys[cut:] for a in by_case[k]]


def support(tm) -> dict:
    """转移矩阵的支撑度画像。Dirichlet 平滑会让低支撑转移的 p 值趋于一致,
    从而使结构通道钝化,所以支撑度是粒度取舍的核心量。"""
    counts = np.asarray(tm.counts, dtype=float)
    seen = counts[counts > 0]
    return {
        "states": len(tm.states),
        "edges": int((counts > 0).sum()),
        "mean_support": float(seen.mean()) if seen.size else 0.0,
        "median_support": float(np.median(seen)) if seen.size else 0.0,
        "singleton_frac": float((seen == 1).mean()) if seen.size else 0.0,
        "total": float(counts.sum()),
    }


def struct_pvalues(det, stream, rng):
    """只取结构通道的 conformal p 值。"""
    det._reset_online()
    out = []
    for a in stream:
        out.append(det._recalibrate(det._score_one(a, rng=rng), rng)[1])
    det._reset_online()
    return np.asarray(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--rate", type=float, default=0.2)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=log_pos)

    print("=== Q1 状态空间与转移支撑度 ===")
    print("  Dirichlet 平滑下,支撑度低的转移 p 值趋同,通道随之钝化")
    print(f"  {'粒度':<14}{'状态数':>7}{'转移数':>7}{'平均支撑':>10}"
          f"{'中位支撑':>10}{'仅见一次占比':>14}")
    for arm in ARMS:
        det, _ = build(live, model, arm=arm, alpha=0.01, seed=0)
        s = support(det.struct)
        print(f"  {ARM_ZH[arm]:<12}{s['states']:>7}{s['edges']:>7}"
              f"{s['mean_support']:>10.1f}{s['median_support']:>10.1f}"
              f"{s['singleton_frac']:>13.1%}")
    print()

    print("=== Q2 时间序 conformal FPR(结构通道单独) ===")
    print(f"  {'粒度':<14}{'a=0.05':>16}{'a=0.01':>16}{'可达下界':>12}")
    for arm in ARMS:
        acc = {0.05: [], 0.01: []}
        floor = 0.0
        for s in range(args.seeds):
            det, test = build(live, model, arm=arm, alpha=0.01, seed=s)
            p = struct_pvalues(det, test, np.random.default_rng(100 + s))
            for al in acc:
                acc[al].append(float((p <= al).mean()))
            n = len(det.cals["struct"].scores)
            floor = 1.0 / (n + 1)
        cells = "".join(f"{np.mean(v):>10.3f} ± {np.std(v):.3f}"
                        for v in (acc[0.05], acc[0.01]))
        print(f"  {ARM_ZH[arm]:<12}{cells}{floor:>12.4f}")
    print()

    print("=== Q3 结构通道对设备混淆类攻击的检出(alpha=0.01) ===")
    print("  A2 物理不可行注入 = 换成该设备不做的操作;A4 状态模仿 = 知模型伪造")
    print(f"  {'粒度':<14}{'A2 DR(误报)':>20}{'A4 DR(误报)':>20}")
    for arm in ARMS:
        cells = ""
        for fam in ("A2", "A4"):
            dr, fp = [], []
            for s in range(args.seeds):
                det, test = build(live, model, arm=arm, alpha=0.01, seed=s)
                rng = np.random.default_rng(200 + s)
                bad, lab = attacks.inject(test, attacks.AttackSpec(
                    family=fam, rate=args.rate, seed=s, knowledge="model",
                    struct_model=det.struct))
                idx = sorted(range(len(bad)), key=lambda i:
                             (bad[i].t_consume, bad[i].order))
                p = struct_pvalues(det, [bad[i] for i in idx], rng)
                lab = np.asarray([lab[i] for i in idx])
                if lab.sum():
                    dr.append(float((p[lab] <= 0.01).mean()))
                    fp.append(float((p[~lab] <= 0.01).mean()))
            cells += f"{np.mean(dr):>13.3f}({np.mean(fp):.3f})".rjust(20)
        print(f"  {ARM_ZH[arm]:<12}{cells}")
    print()
    print("  判据:细粒度只有在 A2 检出显著上升**且** Q2 的 FPR 未失控时才值得换。")
    _ = conformal, structural
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
