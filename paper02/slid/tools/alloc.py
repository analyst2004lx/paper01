"""在**校准折**上选 alpha 预算的分配，再到测试折上评。

E2 已经证明均分不是最优：互锁、Fisher 合成、路线协变量三项净贡献为负
（结论四十二至四十四），它们白吃的预算本可以给时序通道。但"哪一路该多拿"
**必须在校准折上定**——在测试折上挑权重就是调参作弊，而且是审稿人最容易
抓住的一种，因为它会让消融表和主表自相矛盾。

于是这里有一条硬纪律：本工具把日志切成 train / calib / test 三折，
**权重只在 calib 上选、冻结后原样搬到 test**，两折的数字都报出来。若 calib
选出的配额在 test 上不奏效，那就是过拟合，如实报告即可——这本身是一个结论。

搜索空间取"哪些路给预算"的子集 + 给时序通道加倍的粗档，而不是连续权重：
子集选择可解释（"互锁该不该拿预算"是个能写进论文的问题），且在 5 条路时
只有 31 个候选，不存在搜索噪声。连续权重在 508 条良性流上分辨不出来
（T35：每路配额低于 1/509 就没有意义）。
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from algorithm import baselines, ingest, procmodel  # noqa: E402
from algorithm.detector import Detector, DetectorConfig  # noqa: E402
from tools.ablate import paths, rows  # noqa: E402
from tools.baseline_diag import attack_stream, split  # noqa: E402

PATHS = ("硬层", "时序", "结构", "互锁", "合成")
FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")


def candidates(m: int, n_b: int, alpha: float):
    """候选配额：非空子集内均分，再加"时序双倍"一档。

    每路配额必须 >= 1/(n_b+1)，否则该路的经验 p 值根本达不到阈值（T35）。
    达不到的候选直接剔除，而不是让它悄悄退化成"取良性最大值作阈值"。
    """
    floor = 1.0 / (n_b + 1)
    out = []
    for r in range(1, m + 1):
        for sub in itertools.combinations(range(m), r):
            w = [0.0] * m
            for i in sub:
                w[i] = 1.0 / r
            if alpha / r >= floor:
                out.append((f"均分{{{','.join(PATHS[i] for i in sub)}}}", w))
            if 1 in sub and r > 1:          # 时序通道拿双份
                w2 = [0.0] * m
                for i in sub:
                    w2[i] = 2.0 if i == 1 else 1.0
                s = sum(w2)
                if alpha * min(x for x in w2 if x > 0) / s >= floor:
                    out.append((
                        f"时序双份{{{','.join(PATHS[i] for i in sub)}}}",
                        [x / s for x in w2]))
    return out


def benign_q(det, ref):
    """各路"离散异常事件"在良性折上的发生率 q，只用良性数据。

    **通用的原子统计量做不到这件事，已试过并失败：**硬层的良性分数全部并列
    在 0（良性零违反），"最异常处的原子质量"因此读成 1.0、把它误剔；互锁那
    边随机化 p 值把 q 那个原子摊成了 [0,q] 上的连续区间，也读不出 4.7%。
    天花板来自**通道语义**，必须逐通道声明它的离散异常事件是什么：

    - 硬层：F 违反或因果缺失（良性实测 0）
    - 互锁软层：物料令牌缺失（良性实测 2%-5%，且部署折比训练折高 9 倍）
    - 时序 / 结构 / 合成：连续，无原子，天花板不生效

    这不是取巧：结论四十七的公式 power <= 触发率 * min(1, alpha_i/q) 本身就
    是对二值通道的分析结果，而 q 可由良性数据估计，故整条判据不碰攻击标签。
    """
    det._reset_online()
    n = hard = tok = 0
    for a in ref:
        det._flush_pending(a.t_consume)
        n += 1
        if det._hard_layer(a) is not None:
            hard += 1
            continue
        tok += bool(det._token_check(a))
    det._reset_online()
    n = max(n, 1)
    return [hard / n, 0.0, 0.0, tok / n, 0.0]


def ceiling_weights(det, ref, alpha, *, min_ceiling=0.5):
    """只用良性数据定配额：天花板过低的路不给预算，其余均分。

    天花板要用**该路自己的配额**算，而配额又依赖给谁预算，故迭代到不动点；
    保留集单调递减，最多 m 轮收敛。
    """
    qs = benign_q(det, ref)
    m = len(qs)
    keep = list(range(m))
    for _ in range(m):
        a = alpha / max(len(keep), 1)
        nxt = [i for i in keep if qs[i] <= 0 or a / qs[i] >= min_ceiling]
        if nxt == keep or not nxt:
            break
        keep = nxt
    w = [0.0] * m
    for i in keep:
        w[i] = 1.0 / len(keep)
    return w, qs, keep


def evaluate(det, ref, target, alpha, weights, seeds, rho, rate):
    """在一条参照良性流与一条目标流上，按给定配额评平均净检出率。"""
    tot = []
    for fam in FAMILIES:
        per = []
        for s in range(seeds):
            stream, lab = attack_stream(target, fam, s, rate, rho, det.struct)
            rb = rows(det, baselines.order_stream(ref),
                      np.random.default_rng(900 + s))
            ra = rows(det, stream, np.random.default_rng(300 + s))
            _, _, sdr, _, floor = baselines.judge(
                paths(rb, "full"), paths(ra, "full"), lab,
                alpha=alpha, weights=weights)
            per.append(sdr - floor)
        tot.append(float(np.mean(per)))
    return float(np.mean(tot)), tot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--rho", type=float, default=0.30)
    ap.add_argument("--rate", type=float, default=0.20)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=pos)
    train, calib, test = split(live)

    # 拟合只用 train：calib 要留作选配额的"held-out 攻击模拟"折，
    # 若把 calib 也拿去拟合，选出的配额就见过自己的校准数据了。
    det = Detector(DetectorConfig(alpha=args.alpha, online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)

    m = len(PATHS)
    cands = candidates(m, len(calib), args.alpha)
    print(f"=== alpha 预算分配（在 calib 折上选，alpha={args.alpha}, "
          f"rho={args.rho}, {args.seeds} 个种子）===")
    print(f"  train {len(train)} / calib {len(calib)} / test {len(test)} 个活动")
    print(f"  拟合只用 train；配额在 calib 上选、冻结后搬到 test")
    print(f"  候选配额 {len(cands)} 个（已剔除每路配额低于 1/(n+1) 的，T35）")
    print()

    scored = []
    for name, w in cands:
        mean, _ = evaluate(det, calib, calib, args.alpha, w,
                           args.seeds, args.rho, args.rate)
        scored.append((mean, name, w))
    scored.sort(reverse=True, key=lambda x: x[0])

    uni = [1.0 / m] * m
    u_cal, _ = evaluate(det, calib, calib, args.alpha, uni,
                        args.seeds, args.rho, args.rate)
    u_test, u_cells = evaluate(det, test, test, args.alpha, uni,
                               args.seeds, args.rho, args.rate)

    print(f"  {'配额':<34}{'calib 均值':>11}{'test 均值':>11}{'test−calib':>12}")
    print("  " + "-" * 68)
    print(f"  {'均分五路（现行）':<30}{u_cal:>11.3f}{u_test:>11.3f}"
          f"{u_test - u_cal:>12.3f}")
    best = None
    for mean, name, w in scored[:args.top]:
        t, cells = evaluate(det, test, test, args.alpha, w,
                            args.seeds, args.rho, args.rate)
        mark = ""
        if best is None:
            best = (name, w, t, cells)
            mark = "  <- calib 最优"
        print(f"  {name[:30]:<30}{mean:>11.3f}{t:>11.3f}{t - mean:>12.3f}{mark}")
    print("  " + "-" * 68)
    print()

    # --- 只用良性数据的天花板判据 -------------------------------------
    cw, qs, keep = ceiling_weights(det, baselines.order_stream(calib),
                                   args.alpha)
    c_cal, _ = evaluate(det, calib, calib, args.alpha, cw,
                        args.seeds, args.rho, args.rate)
    c_test, c_cells = evaluate(det, test, test, args.alpha, cw,
                               args.seeds, args.rho, args.rate)
    print("  --- 只用良性数据的天花板判据（不碰任何攻击标签）---")
    print(f"  {'路':<8}{'良性异常率 q':>15}{'天花板 alpha_i/q':>18}{'给预算':>8}")
    a_i = args.alpha / max(len(keep), 1)
    for i, p in enumerate(PATHS):
        c = 1.0 if qs[i] <= 0 else min(1.0, a_i / qs[i])
        print(f"  {p:<8}{qs[i]:>15.4f}{c:>18.3f}"
              f"{('是' if i in keep else '否'):>8}")
    print(f"  选中 {len(keep)} 条路，各 {a_i:.4f}；"
          f"calib {c_cal:.3f} / test {c_test:.3f}"
          f"（对均分 {c_test - u_test:+.3f}）")
    print()

    name, w, t, cells = best
    print(f"  calib 折按攻击表现选出的配额：{name}")
    print(f"  权重 = " + ", ".join(f"{p}:{x:.2f}" for p, x in zip(PATHS, w)))
    print(f"  在 test 折上 {u_test:.3f} -> {t:.3f}（{t - u_test:+.3f}）")
    print()
    print(f"  {'攻击':<8}{'均分五路':>10}{'calib 最优':>12}{'差':>8}")
    for f, a, b in zip(FAMILIES, u_cells, cells):
        print(f"  {f:<8}{a:>10.2f}{b:>12.2f}{b - a:>+8.2f}")
    print()
    print("  若 test−calib 一列普遍为负，说明配额在 calib 上过拟合；此时应当")
    print("  退回均分并如实报告——那也是一个结论：本数据集规模不足以可靠地选")
    print("  出配额。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
