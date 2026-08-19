"""把手写的"攻击类型 × 检测通道覆盖矩阵"换成实测的。

新想法.md 里那张矩阵(● / ○ / ✗)是**推理写出来的**,其中"A4 只有互锁
通道能抓"还是全文的头条主张之一。本项目里手写论断被实测推翻的记录不好
(结构通道的纵横之分、Fisher 可用性、首选校准架构都翻过),故必须测。

口径:
  - 逐通道**单独**判决,不走合成——问的是"这个通道看不看得见这类攻击",
    不是"整套系统抓不抓得到"。
  - 每个通道用自己的 conformal 校准器,阈值取同一个 alpha,故各通道的
    误报率对齐,DR 可横向比较。
  - 硬层(F 掩码、命令-响应因果)不是 p 值通道,单独统计触发率。
  - 时间序划分,与部署口径一致。

用法(在 paper02/slid/ 下):  py -m tools.coverage_matrix
"""
from __future__ import annotations

import argparse

import numpy as np

from algorithm import attacks, ingest, metrics, procmodel
from algorithm.detector import CHANNELS, Detector, DetectorConfig

FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")
#: 新想法.md 覆盖矩阵的手写声称,用于逐格对照
CLAIMED = {
    "A1": {"hard": "○", "struct": "●", "time": "●", "inter": "○"},
    "A2": {"hard": "●", "struct": "●", "time": "○", "inter": "○"},
    "A3": {"hard": "✗", "struct": "✗", "time": "●", "inter": "○"},
    "A4": {"hard": "✗", "struct": "✗", "time": "✗", "inter": "●"},
    "A5": {"hard": "✗", "struct": "○", "time": "○", "inter": "○"},
    "A6": {"hard": "✗", "struct": "✗", "time": "●", "inter": "○"},
}


def score_stream(det: Detector, stream, rng):
    """逐消息返回 (硬层是否触发, 三通道 conformal p 值)。

    与 observe 的差别:硬层触发后**不**丢弃消息,继续给出三通道 p 值——
    覆盖矩阵要问的是每个通道各自看得见什么,不是在线判决顺序。
    """
    det._reset_online()
    rows = []
    for a in stream:
        det._flush_pending(a.t_consume)
        hard = det._hard_layer(a) is not None
        p = det._recalibrate(det._score_one(a, rng=rng), rng)
        rows.append((hard, p))
    det._reset_online()
    return rows


def measure(det, benign, family, alpha, seed, rate, rho):
    rng = np.random.default_rng(seed)
    spec = attacks.AttackSpec(family=family, rho=rho, rate=rate, seed=seed,
                              knowledge="model", struct_model=det.struct,
                              proc_model=det.model)
    bad, labels = attacks.inject(benign, spec)
    order = sorted(range(len(bad)),
                   key=lambda i: (bad[i].t_consume, bad[i].order))
    stream = [bad[i] for i in order]
    labels = [labels[i] for i in order]
    rows = score_stream(det, stream, rng)

    pos = [i for i, v in enumerate(labels) if v]
    neg = [i for i, v in enumerate(labels) if not v]
    if not pos:
        return None
    out = {}
    out["hard"] = (np.mean([rows[i][0] for i in pos]),
                   np.mean([rows[i][0] for i in neg]))
    for j, ch in enumerate(CHANNELS):
        dr = np.mean([rows[i][1][j] <= alpha for i in pos])
        fp = np.mean([rows[i][1][j] <= alpha for i in neg])
        out[ch] = (dr, fp)
    out["_n"] = len(pos)

    # 序贯层:同一攻击流走完整在线流水线,按延迟预算算检出
    det._reset_online()
    alarms = det.replay(stream, rng=rng)
    rep = metrics.evaluate(alarms, labels, det.cfg, stream=stream)
    det._reset_online()
    out["seq"] = (rep.dr_by_delay.get(10, float("nan")), rep.fpr)
    return out


def grade(dr: float, fpr: float) -> str:
    """把实测 DR 折成与手写矩阵同一套符号,便于逐格对照。

    阈值是报告约定而非统计判据:相对基准误报有实质提升才算 ○,
    显著高于其它通道才算 ●。
    """
    lift = dr - fpr
    if lift >= 0.25:
        return "●"
    if lift >= 0.05:
        return "○"
    return "✗"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--timing-score", default="z", choices=("z", "pvalue"),
                    help="时序通道的不符合度分数;pvalue 臂仅用于展示裁剪"
                         "下界如何摧毁尾部分辨率")
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=log_pos)

    by_case = {}
    for a in live:
        by_case.setdefault(a.case, []).append(a)
    keys = sorted(by_case, key=lambda k: min(
        (x.t_consume for x in by_case[k] if x.t_consume is not None),
        default=None) or 0)
    cut = int(len(keys) * 0.75)
    fit_acts = [a for k in keys[:cut] for a in by_case[k]]
    test = [a for k in keys[cut:] for a in by_case[k]]

    # **必须关掉在线更新。** replay 会触发 M9 的 EWMA 改写时长模型,于是
    # 测完一类攻击后模型已经变了,后面几类测的不是同一个检测器——覆盖矩阵
    # 要求横向可比,只能在固定模型上测。
    det = Detector(DetectorConfig(alpha=args.alpha, online_update=False,
                                  timing_score=args.timing_score)).fit(
        fit_acts, model=model, rng=np.random.default_rng(0), temporal=True)

    cols = ["hard"] + list(CHANNELS) + ["seq"]
    zh = {"hard": "硬层", "time": "时序", "struct": "结构", "inter": "互锁",
          "seq": "序贯@10"}
    print(f"=== 实测覆盖矩阵(alpha={args.alpha}, rate={args.rate}, "
          f"rho={args.rho}, {args.seeds} 个种子, 时间序划分) ===")
    print(f"  DR 为受攻击消息上的逐通道单独检出率;括号内是同通道在良性")
    print(f"  消息上的误报率,两者之差才是该通道的真实能力。")
    print()
    hdr = f"  {'攻击':<20}" + "".join(f"{zh[c]:>18}" for c in cols)
    print(hdr)
    print("  " + "-" * (len(hdr) + 8))

    disagree = []
    for fam in FAMILIES:
        acc = {c: [] for c in cols}
        n = 0
        for s in range(args.seeds):
            r = measure(det, test, fam, args.alpha, s, args.rate, args.rho)
            if r is None:
                continue
            n = r["_n"]
            for c in cols:
                acc[c].append(r[c])
        if not n:
            continue
        cells, marks = "", {}
        for c in cols:
            dr = float(np.mean([x[0] for x in acc[c]]))
            fp = float(np.mean([x[1] for x in acc[c]]))
            marks[c] = grade(dr, fp)
            cells += f"{marks[c]} {dr:.2f}({fp:.2f})".rjust(18)
        print(f"  {fam} {attacks.FAMILY_ZH[fam][:8]:<16}{cells}")
        for c in cols:
            if c in CLAIMED[fam] and marks[c] != CLAIMED[fam][c]:
                disagree.append((fam, c, CLAIMED[fam][c], marks[c]))
    print(f"\n  每类受攻击消息数约 {n}")
    print()

    q = det.q_inter
    cap = min(args.alpha / q, 1.0) if q > 0 else 1.0
    print("=== 二值通道的功效上界(与不变量质量无关的硬天花板) ===")
    print(f"  互锁软层良性违反率 q = {q:.4f}")
    print(f"  二值通道的随机化 p 值在违反时均匀落在 [0, q],故 "
          f"alpha={args.alpha} 下")
    print(f"  单消息检出率**上界 = min(1, alpha/q) = {cap:.3f}**,"
          f"再完美的不变量也超不过。")
    if cap >= 1.0:
        print(f"  (本折 q <= alpha,天花板不生效;但 q 随训练折波动,"
              f"alpha=0.001 时上界只有 {min(0.001 / q, 1.0):.3f})")
    print(f"  抬高它只有两条路:把 q 压下去(RFID/NFC 工件身份可使 q->0,"
          f"软层升硬层),或靠序贯层跨消息累积。")
    print()

    print("=== 与 新想法.md 手写矩阵的逐格对照 ===")
    if not disagree:
        print("  全部一致。")
    else:
        for fam, c, claim, got in disagree:
            print(f"  {fam} {attacks.FAMILY_ZH[fam]:<12} {zh[c]:<4} "
                  f"声称 {claim}  实测 {got}")
        print()
        print("  不一致处必须以实测为准改矩阵,或说明为何实测口径不能反映")
        print("  该格的意图——两者选一,不能放着。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
