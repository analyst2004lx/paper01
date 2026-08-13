"""E2 消融：逐项去除硬层 / 时序 / 结构 / 互锁 / 合成 / 序贯 / 协变量 / conformal。

与 E1 共用 `baselines.judge`：同一经验 p 值变换、同一 k、同一 ARL0=1/alpha、
同一延迟预算，并且**同样减去偶然地板**（结论三十八）。故本表的数字与 E1
的主结果行可以直接放在一起看。

两条口径是这张表能不能用的前提，都是被测量打出来的：

1. **去掉一个通道必须分两种臂**（结论二十五）。在线检测器同时跑"逐通道
   独立判决"与"Fisher 合成"两路，于是"去掉时序"有两个不同含义：
   `no_timing` 是连它的独立判决一起去掉，`fused_wo_timing` 是只把它从合成
   里摘掉、独立判决仍在。后者有时反而会**提高**某类攻击的检出率（少一个
   无信息通道摊薄证据），这个反直觉现象若不预先说明会被审稿人当成实现错误。

2. **并行路数受 m <= alpha*(n_b+1) 约束**（结论三十九，T35）。full 臂有
   5 条路（硬层 + 三通道 + 合成），良性参照流 508 条时 alpha=0.01 只够
   5 条路的极限，故本工具默认 alpha=0.05；用 0.01 跑会落在分辨率边缘，
   各臂之间的差值将不可信。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from algorithm import attacks, baselines, fusion, ingest, procmodel  # noqa: E402
from algorithm.detector import CHANNELS, Detector, DetectorConfig  # noqa: E402
from tools.baseline_diag import attack_stream, split  # noqa: E402

#: 臂名 -> (去掉的硬层?, 完全去掉的通道, 仅从合成去掉的通道, 去掉合成路?)
ARMS = {
    "full":                (False, (),         (),         False),
    "no_hard":             (True,  (),         (),         False),
    "no_timing":           (False, ("time",),  (),         False),
    "no_structural":       (False, ("struct",), (),        False),
    "no_interlock":        (False, ("inter",), (),         False),
    "fused_wo_timing":     (False, (),         ("time",),  False),
    "fused_wo_structural": (False, (),         ("struct",), False),
    "fused_wo_interlock":  (False, (),         ("inter",), False),
    "no_fusion":           (False, (),         (),         True),
}
#: 需要单独重新拟合检测器的臂
REFIT = ("no_covariate",)
#: 只改在线打分方式的臂
RESCORE = ("no_conformal",)

ZH = {
    "full": "完整方法",
    "no_hard": "去硬层 F 掩码",
    "no_timing": "去时序通道(含独立判决)",
    "no_structural": "去结构通道(含独立判决)",
    "no_interlock": "去互锁通道(含独立判决)",
    "fused_wo_timing": "时序仅退出合成",
    "fused_wo_structural": "结构仅退出合成",
    "fused_wo_interlock": "互锁仅退出合成",
    "no_fusion": "去合成路(只留逐通道)",
    "no_conformal": "去 conformal(用原始参数化 p)",
    "no_covariate": "去路线协变量",
}
FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")


def rows(det, stream, rng, *, conformal=True):
    """按在线语义逐消息取 (硬层指示, 三通道分数)。"""
    det._reset_online()
    out = []
    for a in stream:
        hard = 1.0 if det._hard_layer(a) is not None else 0.0
        raw = det._score_one(a, rng=rng)
        p = det._recalibrate(raw, rng) if conformal else tuple(raw)
        out.append((hard, tuple(p)))
    det._reset_online()
    return out


def paths(rs, arm: str):
    """把打分行装配成该臂的并行子检测器分数流(越大越异常)。"""
    no_hard, gone, fused_out, no_fuse = ARMS.get(arm, ARMS["full"])
    out = []
    if not no_hard:
        out.append([r[0] for r in rs])
    for j, ch in enumerate(CHANNELS):
        if ch not in gone:
            out.append([-r[1][j] for r in rs])
    if not no_fuse:
        idx = [j for j, ch in enumerate(CHANNELS)
               if ch not in gone and ch not in fused_out]
        if idx:
            out.append([-fusion.combine(tuple(r[1][j] for j in idx),
                                        "fisher") for r in rs])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--rate", type=float, default=0.20)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--interlock-scope", default="global",
                    choices=("case", "global"),
                    help="互锁令牌账作用域。global 把良性违反率 q 由 1.70% "
                         "压到 0.22%、LATE 归零,从而解开 min(1,alpha/q) 的"
                         "功效天花板;代价是全局池更宽松。")
    ap.add_argument("--fixed-path-alpha", action="store_true",
                    help="把**每路** alpha 固定为 alpha/5 而非把总 alpha 固定。"
                         "这是必须做的对照:总 alpha 固定时,去掉一条路等于给"
                         "剩下每条路加 25% 预算,于是「去掉某通道反而更好」"
                         "可能只是预算重分配而非该通道有害。")
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)
    benign = baselines.order_stream(test)

    def build(**kw):
        kw.setdefault("interlock_scope", args.interlock_scope)
        return Detector(DetectorConfig(alpha=args.alpha, online_update=False,
                                       **kw)).fit(
            train + calib, model=model, rng=np.random.default_rng(0),
            temporal=True)

    det = build()
    det_nc = build(min_route_n=10 ** 9)          # no_covariate 臂

    n_paths = len(paths(rows(det, benign[:5], np.random.default_rng(0)),
                        "full"))
    cap = max(1, int(args.alpha * (len(benign) + 1)))
    print(f"=== E2 消融(alpha={args.alpha}, rho={args.rho}, 注入率 "
          f"{args.rate}, {args.seeds} 个种子, 时间序划分) ===")
    print(f"  训练 {len(train)} / 校准 {len(calib)} / 测试 {len(test)} 个活动")
    print(f"  互锁作用域 = {args.interlock_scope}，训练折良性违反率 "
          f"q = {det.q_inter:.4f}，功效天花板 min(1, alpha/q) = "
          f"{min(1.0, args.alpha / max(det.q_inter, 1e-9)):.3f}")
    print(f"  完整方法有 {n_paths} 条并行路(硬层 + 三通道 + Fisher 合成);"
          f"良性参照流 {len(benign)} 条")
    print(f"  可容纳路数上限 m <= alpha*(n_b+1) = {cap}"
          f"{' —— 合格' if n_paths <= cap else ' —— 超限,结果不可信(T35)'}")
    print("  报告口径与 E1 主结果行完全一致:序贯累积、延迟预算 10 条、"
          "**已减去偶然地板**。")
    print()

    names = list(ARMS) + list(RESCORE) + list(REFIT)
    res = {n: {f: [] for f in FAMILIES} for n in names}
    fpr = {n: [] for n in names}

    for fam in FAMILIES:
        for s in range(args.seeds):
            stream, lab = attack_stream(test, fam, s, args.rate, args.rho,
                                        det.struct)
            for n in names:
                d = det_nc if n in REFIT else det
                cf = n not in RESCORE
                rb = rows(d, benign, np.random.default_rng(900 + s),
                          conformal=cf)
                ra = rows(d, stream, np.random.default_rng(300 + s),
                          conformal=cf)
                arm = n if n in ARMS else "full"
                pb, pa = paths(rb, arm), paths(ra, arm)
                a = args.alpha
                if args.fixed_path_alpha:
                    a = args.alpha * len(pb) / n_paths
                _, _, sdr, sfpr, floor = baselines.judge(
                    pb, pa, lab, alpha=a)
                res[n][fam].append(sdr - floor)
                fpr[n].append(sfpr)

    hdr = f"  {'臂':<26}" + "".join(f"{f:>7}" for f in FAMILIES) \
        + f"{'均值':>9}{'Δ均值':>9}{'序贯FPR':>9}"
    print(hdr)
    print("  " + "-" * 96)
    base = float(np.mean([np.mean(res["full"][f]) for f in FAMILIES]))
    for n in names:
        cells = [float(np.mean(res[n][f])) for f in FAMILIES]
        m = float(np.mean(cells))
        row = "".join(f"{c:>7.2f}" for c in cells)
        d = "" if n == "full" else f"{m - base:>+9.2f}"
        print(f"  {n:<12}{ZH[n][:11]:<11}{row}{m:>9.2f}{d:>9}"
              f"{np.mean(fpr[n]):>9.3f}")
    print("  " + "-" * 96)
    print()
    print("  Δ均值 = 该臂减完整方法。**负得越多说明被去掉的东西越必要。**")
    print("  「仅退出合成」三臂与「含独立判决」三臂之差，就是该通道通过合成")
    print("  路贡献的部分；两者相减即可把通道价值拆成「独立判决」与「合成」")
    print("  两份，这是结论二十五要求的拆分口径。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
