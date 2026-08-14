"""E1 主对比:同一误报预算下,本方法与基线在各攻击族上的检出率。

口径三条,缺一不可比:
  1. **同一误报预算。**各基线原始分数量纲不同(l2 距离、负对数似然、z 值),
     只能在同一良性校准折上把阈值定到同一名义 alpha 再比检出。
  2. **同一时间序划分。**训练 / 校准 / 测试按 case 首次出现时间切,与部署
     口径一致(规则 6)。
  3. **同一攻击流。**同一注入种子生成的同一条流喂给所有方法,包括同一个
     知模型的 A4 攻击者(规则 12)。

本方法给两个数:逐消息(与基线的逐观测判决同口径)和序贯@10(基线无累积,
故这一列本身就是 M7 的对照,不是不公平的比较)。

用法(在 paper02/slid/ 下):  py -m tools.baseline_diag
"""
from __future__ import annotations

import argparse

import numpy as np

from algorithm import attacks, baselines, ingest, metrics, procmodel
from algorithm.detector import Detector, DetectorConfig

FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")
#: 本方法的并行子检测器,顺序与 _parts 和 Detector.path_q 一致
PATHS = ("硬层", "时序", "结构", "互锁")


def split(live):
    by_case = {}
    for a in live:
        by_case.setdefault(a.case, []).append(a)
    keys = sorted(by_case, key=lambda k: min(
        (x.t_consume for x in by_case[k] if x.t_consume is not None),
        default=None) or 0)
    n = len(keys)
    a, b = int(n * 0.55), int(n * 0.75)
    take = lambda ks: [x for k in ks for x in by_case[k]]   # noqa: E731
    return take(keys[:a]), take(keys[a:b]), take(keys[b:])


def attack_stream(test, fam, seed, rate, rho, struct_model, proc_model=None):
    spec = attacks.AttackSpec(family=fam, rho=rho, rate=rate, seed=seed,
                              knowledge="model", struct_model=struct_model,
                              proc_model=proc_model)
    bad, lab = attacks.inject(test, spec)
    order = sorted(range(len(bad)),
                   key=lambda i: (bad[i].t_consume, bad[i].order))
    return [bad[i] for i in order], [lab[i] for i in order]


def _parts(det, stream, rng, *, conformal: bool = False):
    """本方法的四个子检测器分数流:硬层 + 三通道(越大越异常)。

    与基线同结构——每个子检测器一条流,交给同一个 judge 并行判决。

    `conformal=False` 交出**原始不符合度分数**,让 judge 的经验 p 值变换做
    唯一一次校准,与基线完全同构。**这是本表的正确口径。**若先过一遍冻结的
    随机化 conformal 再交给 judge,同一条流就被随机化两次:第一次的
    U*(1+eq)/(n+1) 项在并列密集处足以打乱相邻原子的次序,而基线只经一次,
    于是我方被**比较装置**而非设计本身罚掉一截(实测结构通道 -0.05)。
    部署时只有一层校准,即冻结的 conformal;这里的 judge 是它的替身,不是
    附加层。`conformal=True` 保留旧口径,仅用于复现这一测量。
    """
    det._reset_online()
    rows = []
    for a in stream:
        hard = 1.0 if det._hard_layer(a) is not None else 0.0
        raw = det._score_one(a, rng=rng)
        p = det._recalibrate(raw, rng) if conformal else raw
        rows.append((hard,) + tuple(-v for v in p))
    det._reset_online()
    return [[r[j] for r in rows] for j in range(len(rows[0]))]


def ours(det, benign, attacked, labels, alpha, rng, weights=None):
    """本方法走**与基线完全相同**的 judge:同一阈值机器、同一 ARL0、同一
    预算划分规则。不用 `det.replay` 的自带 h,否则比的是两套阈值机器。
    完整流水线的数字(含门控更新与看门狗)在 main.py 与 online_diag 里单独
    报告,不混进这张对比表。

    `weights` 由 `Detector.path_weights` 在**良性选择折**上算出并冻结,不碰
    测试折。实测在相邻折上按攻击表现选配额会选出测试折上最差的那个(结论
    四十八),只有良性天花板判据可用(结论四十九)。
    """
    pb = _parts(det, benign, np.random.default_rng(rng.integers(1 << 30)))
    pa = _parts(det, attacked, rng)
    dr, fpr, sdr, sfpr, floor = baselines.judge(pb, pa, labels, alpha=alpha,
                                                weights=weights)
    return {"dr": dr, "fpr": fpr, "seq": sdr, "seq_fpr": sfpr,
            "seq_net": sdr - floor, "floor": floor}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--rate", type=float, default=0.2)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)
    benign = baselines.order_stream(test)       # 同一批 case 的未注入版本

    # 本方法**只用 train 拟合**,与基线一致(fit_baseline 也只吃 train)。
    # 原先吃 train+calib 是给自己让利,且会把 calib 变成样本内,使天花板判据
    # 读到训练折的 q(0.005)而非部署折的 q(0.03),互锁就剔不掉了(结论四十七)。
    det = Detector(DetectorConfig(alpha=args.alpha,
                                  online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)

    # alpha 配额:在**良性选择折 calib** 上按天花板判据选,冻结后搬到 test。
    w, qs, keep = det.path_weights(baselines.order_stream(calib),
                                   alpha=args.alpha)
    names = list(baselines.IMPLEMENTED)
    fitted = {n: baselines.fit_baseline(n, train) for n in names}
    print(f"=== E1 同一误报预算下的检出率(alpha={args.alpha}, "
          f"rho={args.rho}, 注入率={args.rate}, {args.seeds} 个种子) ===")
    print(f"  训练 {len(train)} / 选择 {len(calib)} / 测试 {len(test)} 个活动,"
          f"时间序划分;本方法与基线**同用 train 拟合**")
    print(f"  阈值一律定在**同一批 case 的未注入版本**上使经验误报为 alpha,")
    print(f"  故各列横向可比。不能用受攻击流内部的良性消息定阈值——A2 这类")
    print(f"  原地改写会造成攻击引起的级联触发,算成误报会把检出率假性归零。")
    print(f"  oracle 阈值对基线是让利,本方法的优势因此偏保守。校准漂移另表。")
    print()
    a_i = args.alpha / max(len(keep), 1)
    print(f"  --- 本方法的 alpha 配额:在良性 calib 折上按天花板判据选出 ---")
    print(f"  {'路':<6}{'良性异常率 q':>15}{'天花板 alpha_i/q':>18}{'配额':>10}")
    for i, p in enumerate(PATHS):
        c = 1.0 if qs[i] <= 0 else min(1.0, a_i / qs[i])
        print(f"  {p:<6}{qs[i]:>15.4f}{c:>18.3f}"
              f"{(f'{a_i:.4f}' if i in keep else '不给'):>10}")
    print(f"  选中 {len(keep)}/{len(PATHS)} 条路:"
          f"{', '.join(PATHS[i] for i in keep)}。"
          f"判据只用良性数据,不碰攻击标签也不碰测试折(结论四十九)。")
    print()
    cols = names + ["ours"]
    keys = ("msg", "seq", "seq_net", "seq_fpr", "floor")
    tally = {c: {k: [] for k in keys} for c in cols}
    drift = {n: [] for n in names}
    raw = {}
    for fam in FAMILIES:
        acc = {c: {k: [] for k in keys} for c in cols}
        for s in range(args.seeds):
            stream, lab = attack_stream(test, fam, s, args.rate, args.rho,
                                        det.struct, det.model)
            for n in names:
                r = baselines.run_baseline(n, train, calib, benign, stream,
                                           lab, alpha=args.alpha,
                                           model=fitted[n])
                for k in keys:
                    acc[n][k].append(r[{"msg": "dr"}.get(k, k)])
                drift[n].append(r["fpr_calib"])
            o = ours(det, benign, stream, lab, args.alpha,
                     np.random.default_rng(300 + s), weights=w)
            for k in keys:
                acc["ours"][k].append(o[{"msg": "dr"}.get(k, k)])
        raw[fam] = {c: {k: float(np.mean(v)) for k, v in d.items()}
                    for c, d in acc.items()}
        for c in cols:
            for k in keys:
                tally[c][k].append(raw[fam][c][k])

    for mode, title in (
            ("msg", "逐消息判决"),
            ("seq", "序贯累积后,延迟预算 10 条消息(未减偶然地板)"),
            ("seq_net", "序贯累积后**减去偶然地板** 1-(1-FPR)^11")):
        print(f"  --- {title} ---")
        print(f"  {'攻击':<18}" + "".join(f"{n:>12}" for n in names)
              + f"{'本方法':>14}")
        for fam in FAMILIES:
            row = "".join(f"{raw[fam][n][mode]:>12.2f}" for n in names)
            row += f"{raw[fam]['ours'][mode]:>14.2f}"
            print(f"  {fam} {attacks.FAMILY_ZH[fam][:6]:<14}{row}")
        avg = "".join(f"{np.mean(tally[n][mode]):>12.2f}" for n in names)
        print(f"  {'均值':<17}{avg}"
              f"{np.mean(tally['ours'][mode]):>14.2f}")
        print()
    print(f"  序贯一臂给**基线也套上同一套 CUSUM**,与本方法共用一个 judge:")
    print(f"  同一经验 p 值变换、同一 k、同一 ARL0=1/alpha、同一延迟预算。")
    print(f"  不这样做,比的就不是通道设计而是两套阈值机器。")
    print(f"  序贯误报(应都接近 {args.alpha}): " + "  ".join(
        f"{c}={np.mean(tally[c]['seq_fpr']):.3f}" for c in cols))
    print(f"  偶然地板: " + "  ".join(
        f"{c}={np.mean(tally[c]['floor']):.3f}" for c in cols))
    print("  地板是「什么都不检测」能拿到的分:延迟预算窗口里有 11 个机会")
    print("  撞上一次误报。B1 MBDF 六族全部贴地板,这正是 T-a 不可能性的预期")
    print("  表现;不减地板会把它误读成「原方法也有三成检出率」。")
    print("  **减地板后的那一行才是可比的。**")
    print()
    nb = len(benign)
    per = args.alpha / 4
    print(f"  ⚠ 逐消息一行的分辨率上限:良性参照流 {nb} 条,经验 p 下界 "
          f"{1/(nb+1):.5f};")
    print(f"  四路均分后每路 {per:.5f},阈值下仅容 {int(per*(nb+1))} 个良性秩位。"
          f"每路 alpha 不分时")
    print(f"  A3 由 0.027 升到 0.266、A5 由 0.034 升到 0.242(约 10 倍),而 A2 "
          f"不变——失真是")
    print(f"  攻击特异的,且**系统性歧视多通道方法**。逐消息一行在本数据集规模下"
          f"不可作主结果。")
    print()
    print(f"=== 校准漂移:按良性校准折定阈值后在测试折的实测误报"
          f"(名义 {args.alpha}) ===")
    for n in names:
        d = float(np.mean(drift[n]))
        print(f"  {n:<10}{d:>8.3f}   = 名义值的 {d / args.alpha:>5.1f} 倍")
    print(f"  基线普遍没有无分布保证,阈值靠人工容差;这一列本身是 M8 的对照。")
    print()
    todo = tuple(n for n in baselines.BASELINES if n not in names)
    print(f"  未实现的基线 {todo} 一律不报告数字。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
