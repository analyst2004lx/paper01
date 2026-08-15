"""M0/M9 在线回放实测:随机折验证出来的保证,在时间序部署下还剩多少。

这是本项目迄今唯一一个**效度**实验而非性能实验。此前全部结论都建立在
随机折划分上,而 M8 规则 3 要求随机划分来保交换性——可现场部署只能用
过去拟合、对未来判定。两件事直接冲突,只能实测:

  Q1 时间序划分下,逐通道 conformal 的经验 FPR 还守得住名义水平吗?
  Q2 逐消息处理时延是多少(E8,单核 CPU;O(1) 由复杂度论证,常数因子实测)
  Q3 门控更新是否真的挡住了投毒(与原专利"无条件在线更新"的差别)

用法(在 paper02/slid/ 下):  py -m tools.online_diag
"""
from __future__ import annotations

import argparse
import math
import time

import numpy as np

from algorithm import conformal, fusion, ingest, procmodel
from algorithm.detector import CHANNELS, Detector, DetectorConfig

ALPHAS = (0.05, 0.01)


def build(live, model, *, temporal: bool, seed: int):
    rng = np.random.default_rng(seed)
    by_case = _by_case(live)
    keys = sorted(by_case, key=lambda k: min(
        (a.t_consume for a in by_case[k] if a.t_consume is not None),
        default=None) or 0)
    if not temporal:
        keys = list(keys)
        rng.shuffle(keys)
    cut = int(len(keys) * 0.75)
    fit_keys, test_keys = keys[:cut], keys[cut:]
    det = Detector(DetectorConfig(alpha=0.01)).fit(
        [a for k in fit_keys for a in by_case[k]], model=model,
        rng=rng, temporal=temporal)
    test = [a for k in test_keys for a in by_case[k]]
    return det, test, rng


def _by_case(acts):
    out = {}
    for a in acts:
        out.setdefault(a.case, []).append(a)
    return out


def channel_fpr(det: Detector, test, rng):
    """在留出的未来数据上,逐通道 conformal p 值的经验 FPR。"""
    det._reset_online()
    rows = []
    for a in sorted((x for x in test if x.t_consume is not None),
                    key=lambda x: (x.t_consume, x.order)):
        det._flush_pending(a.t_consume)
        if det._hard_layer(a) is not None:
            continue
        rows.append(det._recalibrate(det._score_one(a, rng=rng), rng))
    det._reset_online()
    P = np.array(rows)
    out = {}
    for j, ch in enumerate(CHANNELS):
        out[ch] = {a: float((P[:, j] <= a).mean()) for a in ALPHAS}
    fused = np.array([fusion.combine(r, "fisher") for r in rows])
    out["fused"] = {a: float((fused <= a).mean()) for a in ALPHAS}
    out["_n"] = len(rows)
    return out


def latency(det: Detector, test, rng, reps: int = 3):
    """E8:逐消息处理时延。测的是 observe() 全流程,含硬层与序贯。"""
    stream = sorted((x for x in test if x.t_consume is not None),
                    key=lambda x: (x.t_consume, x.order))
    per = []
    for _ in range(reps):
        det._reset_online()
        for a in stream:
            t0 = time.perf_counter()
            det.observe(a, rng=rng)
            per.append((time.perf_counter() - t0) * 1e6)
    det._reset_online()
    return np.array(per)


def poisoning(live, model, seed: int, rho: float = 0.30, n_inject: int = 200):
    """Q3:攻击者持续注入抢跑数据,门控与不门控的基线漂移对比。

    攻击者不求单条不被发现,而是求把自己的行为**喂进基线**——若在线更新
    无条件执行,注入数据会把该分组的位置参数拉向抢跑值,几轮之后同样幅度
    的抢跑就不再异常。这正是原专利"无条件 EWMA 更新"的结构性弱点。
    """
    out = {}
    for gated in (True, False):
        det, test, rng = build(live, model, temporal=True, seed=seed)
        det.cfg.online_update = True
        det.cfg.gated_update = gated        # 其余配置完全相同
        # 找一个样本最多且信息量足的分组做靶子
        key = max((k for k, m in det.timing.items() if m.informative),
                  key=lambda k: det.timing[k].n)
        m = det.timing[key]
        route = max(m.route_effect, key=lambda r: 1)
        before = m.route_effect[route]
        victims = [a for a in test
                   if (a.device, a.op) == key and a.duration_s]
        det._reset_online()
        for i in range(n_inject):
            a = victims[i % len(victims)]
            fake = _clone_faster(a, rho)
            det.observe(fake, rng=rng)
        after = det.timing[key].route_effect[route]
        out["门控" if gated else "无门控"] = {
            "组": f"{key[0]}/{key[1]}", "注入前位置": before,
            "注入后位置": after, "漂移": after - before,
            "等效被吸收的抢跑量": 1 - math.exp(after - before),
            "更新被拦": det.stats["update_blocked"],
            "更新生效": det.stats["update_applied"],
        }
    return out


def _clone_faster(a, rho: float):
    """抢跑 rho:把结束时刻提前。duration_s 是派生属性,只能改时间戳。"""
    import copy
    from datetime import timedelta
    b = copy.copy(a)
    b.t_end = a.t_start + timedelta(seconds=a.duration_s * (1.0 - rho))
    return b


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--bpmn", default=procmodel.default_bpmn_glob())
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    raw = ingest.read_xes(args.xes)
    live = ingest.valid(raw, drop_failure=True)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(args.bpmn, log_positions=log_pos)

    print("=== Q1 时间序 vs 随机折:逐通道 conformal 的经验 FPR ===")
    print("  (随机折是此前全部结论的口径;时间序是唯一可部署的口径)")
    acc = {("时间序" if t else "随机折"): {c: {a: [] for a in ALPHAS}
                                            for c in list(CHANNELS) + ["fused"]}
           for t in (True, False)}
    n_rows = []
    for seed in range(args.seeds):
        for temporal in (True, False):
            det, test, rng = build(live, model, temporal=temporal, seed=seed)
            r = channel_fpr(det, test, rng)
            n_rows.append(r["_n"])
            lbl = "时间序" if temporal else "随机折"
            for c in list(CHANNELS) + ["fused"]:
                for a in ALPHAS:
                    acc[lbl][c][a].append(r[c][a])

    print(f"  {'通道':<8} {'划分':<8} {'a=0.05':>16} {'a=0.01':>16}")
    print("  " + "-" * 52)
    for c in list(CHANNELS) + ["fused"]:
        for lbl in ("随机折", "时间序"):
            cells = "  ".join(f"{np.mean(acc[lbl][c][a]):.3f} ± "
                              f"{np.std(acc[lbl][c][a]):.3f}" for a in ALPHAS)
            print(f"  {c if lbl == '随机折' else '':<8} {lbl:<8} {cells}")
    print(f"  测试集逐消息数 {int(np.mean(n_rows))}")
    print()

    det, test, rng = build(live, model, temporal=True, seed=0)
    us = latency(det, test, rng)
    print("=== Q2 逐消息处理时延(E8,单核 CPU,observe 全流程) ===")
    print(f"  中位 {np.median(us):.1f} us   p95 {np.percentile(us, 95):.1f} us"
          f"   p99 {np.percentile(us, 99):.1f} us   n={len(us)}")
    print(f"  等效吞吐 {1e6 / np.median(us):,.0f} 消息/秒(单核)")
    print("  O(1) 由复杂度论证给出,此处只提供常数因子;未做硬件平台实测。")
    print()

    print("=== Q3 门控更新的抗投毒作用 ===")
    for lbl, r in poisoning(live, model, seed=0).items():
        print(f"  {lbl:<6} 组 {r['组']:<28} "
              f"位置漂移 {r['漂移']:+.4f}  "
              f"等效吸收抢跑 {r['等效被吸收的抢跑量']:+.1%}")
        print(f"         更新生效 {r['更新生效']} 次 / 被拦 {r['更新被拦']} 次")
    print()
    print("  漂移越大说明攻击者越成功地把自己的抢跑喂成了新常态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
