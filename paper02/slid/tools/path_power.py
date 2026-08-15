"""每条路**单独拿满 alpha** 时的净检出率，与同样拿满 alpha 的基线对齐。

E1 里我方在 A1/A4/A6 上输给 B2 markov，这有两种完全不同的解释，对论文的
含义相反，必须分开：

1. **预算摊薄。**我方结构通道本身不弱，只是三路均分后每路只有 alpha/3，
   而 markov 一条路独吞 alpha。这是多通道方法的固有代价，属于"覆盖广度换
   单点灵敏度"的权衡，可以写成一条诚实的限制。
2. **M3 本身弱于一阶马尔可夫。**若结构通道独吞 alpha 后仍打不过 markov，
   那是实现缺陷（Mondrian 分组把小样本组的分辨率切碎、Dirichlet 平滑把罕见
   转移抹平），必须修，不能当权衡写。

本工具把每条路单独放大到满预算来判定：weights 只给一条路，其余为 0，走的
仍是同一个 `baselines.judge`。这不是新方法，只是诊断——**主表不能这样报**，
因为"哪一路满预算"要在良性折上选，而单路满预算的选择依赖攻击族。

用法（在 paper02/slid/ 下）:  py -m tools.path_power
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from algorithm import baselines, ingest, procmodel  # noqa: E402
from algorithm.detector import (Detector, DetectorConfig, _group,  # noqa: E402
                               _order_cases)
from tools.baseline_diag import PATHS, _parts, attack_stream, split  # noqa: E402

FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")


def fit_fold(train, frac=0.67):
    """复现 Detector.fit 的内部划分,取出它真正用于拟合的那一折。

    split conformal 必须留出校准折,于是本方法的转移矩阵只见到 train 的
    67%,而基线吃满 100%。这不是实现失误而是**分布无关校准的数据代价**,
    但要把它与"M3 本身弱"分开,只能让基线也只吃这 67% 再比一次。
    """
    by_case = _group(train)
    keys = _order_cases(by_case, temporal=True, rng=None)
    cut = int(len(keys) * frac)
    return [a for k in keys[:cut] for a in by_case[k]]


def solo(det, benign, attacked, labels, alpha, rng, idx, *, conformal=False):
    """只给第 idx 条路预算，其余为 0。"""
    w = [0.0] * len(PATHS)
    w[idx] = 1.0
    pb = _parts(det, benign, np.random.default_rng(rng.integers(1 << 30)),
                conformal=conformal)
    pa = _parts(det, attacked, rng, conformal=conformal)
    _, _, sdr, _, floor = baselines.judge(pb, pa, labels, alpha=alpha,
                                          weights=w)
    return sdr - floor


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)
    benign = baselines.order_stream(test)

    det = Detector(DetectorConfig(alpha=args.alpha,
                                  online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)
    mk = baselines.fit_baseline("markov", train)
    mk67 = baselines.fit_baseline("markov", fit_fold(train))

    print(f"=== 单路满预算的净检出率(alpha={args.alpha} 全给一条路, "
          f"rho={args.rho}, {args.seeds} 个种子, 序贯@10 减偶然地板) ===")
    print(f"  与 markov 同口径:同一 judge、同一 ARL0、同一延迟预算。")
    print(f"  本表只用于判定 A1/A4/A6 的落后是预算摊薄还是 M3 缺陷,不进主表。")
    print()
    head = "".join(f"{p:>12}" for p in PATHS)
    print(f"  {'攻击':<8}{head}{'结构双校':>10}{'markov':>10}{'mk同折':>9}"
          f"{'结构−同折':>12}")
    gaps, costs = [], []
    for fam in FAMILIES:
        cells, mks, m67s, dbl = [[] for _ in PATHS], [], [], []
        for s in range(args.seeds):
            stream, lab = attack_stream(test, fam, s, args.rate, args.rho,
                                        det.struct, det.model)
            for i in range(len(PATHS)):
                cells[i].append(solo(det, benign, stream, lab, args.alpha,
                                     np.random.default_rng(300 + s), i))
            dbl.append(solo(det, benign, stream, lab, args.alpha,
                            np.random.default_rng(300 + s), 2, conformal=True))
            for mdl, sink in ((mk, mks), (mk67, m67s)):
                r = baselines.run_baseline("markov", train, calib, benign,
                                           stream, lab, alpha=args.alpha,
                                           model=mdl)
                sink.append(r["seq_net"])
        v = [float(np.mean(c)) for c in cells]
        m, m67 = float(np.mean(mks)), float(np.mean(m67s))
        d = float(np.mean(dbl))
        gaps.append(v[2] - m67)
        costs.append(v[2] - d)
        row = "".join(f"{x:>12.2f}" for x in v)
        print(f"  {fam:<8}{row}{d:>10.2f}{m:>10.2f}{m67:>9.2f}"
              f"{v[2] - m67:>+12.2f}")
    print()
    g, c = float(np.mean(gaps)), float(np.mean(costs))
    print(f"  结构:单次校准 − 双次校准,六族均值 {c:+.2f}")
    print(f"  => 这一项是**比较装置的伪影**:judge 本身要做经验 p 值变换,再")
    print(f"     叠一层冻结 conformal 就随机化了两次。部署时只有一层。")
    print(f"  结构通道满预算 − markov 同折满预算,六族均值 {g:+.2f}")
    if g >= -0.05:
        print(f"  => 同数据同预算下 M3 不弱于一阶马尔可夫。E1 里的落后由两项")
        print(f"     构成:预算摊薄(三路均分)与校准折的数据代价,都是多通道 +")
        print(f"     分布无关校准的固有开销,应如实写成限制而不是当缺陷修。")
    else:
        print(f"  => 同数据同预算下 M3 仍弱于一阶马尔可夫,是**实现缺陷**:查")
        print(f"     弃权语义(未见状态判成最正常)与 Dirichlet 浓度,不能当权衡写。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
