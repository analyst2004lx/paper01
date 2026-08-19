"""可问责沉默诊断：机制自检、误报—时延—带宽权衡、与耦合互证的时延对照。

四件事：
  1. 协议自检——正常披露通过，伪造原像、提前披露、重放全部被拒。
  2. 误报—时延—带宽的解析权衡，含突发丢包口径。论文那张可行区间图的数据源。
  3. 与 paper02 二值通道天花板的对照：说明若把沉默当统计通道会落回天花板。
  4. **数据锚定的对照量**：设备沉默时只靠耦合互证要多久才能判定。日志没有
     通信层，故心跳与丢包是仿真的，但"互证要等多久"来自命令账本的计划时刻，
     是实测量。这一对照是消融"去掉可问责沉默"的直接材料。

用法(在 paper03/tessera/ 下):  py -m tools.silence_diag
"""
from __future__ import annotations

import argparse
from statistics import median

from algorithm import crypto, ingest, silence


def _pct(xs, q):
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def selftest() -> None:
    sk, pk = crypto.new_keypair()
    ch = crypto.HashChain("vgr_1", "s1", length=32)
    c = crypto.sign_commitment(
        crypto.Commitment("vgr_1", "s1", ch.root, 32, t0=0.0, t_hb_s=1.0), sk)
    print("协议自检")
    print(f"      承诺根签名核验 {crypto.verify_root(c, pk)}")

    cfg = silence.SilenceConfig(t_hb_s=1.0, r_misses=3, skew_s=0.01)
    mon = silence.SilenceMonitor(cfg)
    mon.register(c)

    print(f"      正常披露槽 1..3      "
          f"{[mon.on_reveal('vgr_1', k, ch.element(k), now=k - 0.5) is None for k in (1, 2, 3)]}")
    print(f"      重放槽 2(应被静默丢弃) "
          f"{mon.on_reveal('vgr_1', 2, ch.element(2), now=2.5) is None}")

    mon2 = silence.SilenceMonitor(cfg)
    mon2.register(c)
    bad = mon2.on_reveal("vgr_1", 1, b"\x00" * crypto.TOKEN_BYTES, now=0.5)
    print(f"      伪造原像             {bad.kind if bad else '未拒绝(错误)'}")

    mon3 = silence.SilenceMonitor(cfg)
    mon3.register(c)
    early = mon3.on_reveal("vgr_1", 5, ch.element(5), now=0.5)
    print(f"      提前披露槽 5         "
          f"{early.kind if early else '未拒绝(错误)'}   <- 前置条件 2")

    mon4 = silence.SilenceMonitor(cfg)
    mon4.register(c)
    print(f"      沉默 2 槽后          {mon4.sweep(2.5) or '无判决'}")
    v = mon4.sweep(3.5)
    print(f"      沉默 3 槽后          "
          f"{v[0].kind if v else '无判决(错误)'} @ t={v[0].t_decide:.2f}s"
          f"   (预期 {cfg.detect_delay_s:.2f}s)")

    mon5 = silence.SilenceMonitor(cfg)
    mon5.register(c)
    mon5.sweep(2.5)
    mon5.on_reveal("vgr_1", 3, ch.element(3), now=2.6)
    print(f"      复位后再沉默 2 槽    {mon5.sweep(5.5) or '无判决'}"
          f"   <- 计数必须复位")
    print()


def tradeoff(n_devices: int, rho: float) -> None:
    """按独立丢包与突发丢包两个口径各自选 r。

    **必须按突发口径设计。** 独立丢包下选出的 r 在 rho=0.3 时误报率会高出
    三个数量级——这不是保守起见，是工业无线的实际情形（阴影衰落与信道竞争
    使丢包成簇）。表中"独立 r"一列只用于说明这个差距有多大。
    """
    print(f"误报—时延—带宽权衡  ({n_devices} 台设备, 误报预算 1 次/小时)")
    print(f"      {'p_loss':>7} {'T_hb':>6} | {'独立r':>5} {'该r在突发下的误报':>18}"
          f" | {'突发r':>5} {'q':>9} {'T_detect':>9} {'带宽':>9}")
    for p in (1e-4, 1e-3, 1e-2, 5e-2):
        for t in (0.05, 0.2, 1.0):
            r0 = silence.min_misses(p, t, n_devices, 1.0)
            rb = silence.min_misses(p, t, n_devices, 1.0, burst_rho=rho)
            if rb is None:
                print(f"      {p:7.4f} {t:6.2f} | {'无解':>5}")
                continue
            naive = silence.far_per_hour(
                p, silence.SilenceConfig(t_hb_s=t, r_misses=r0),
                n_devices, burst_rho=rho)
            cfg = silence.SilenceConfig(t_hb_s=t, r_misses=rb)
            print(f"      {p:7.4f} {t:6.2f} | {r0:5d} {naive:15.1f} 次/h"
                  f" | {rb:5d} {silence.far_prob(p, rb, burst_rho=rho):9.2e}"
                  f" {cfg.detect_delay_s:8.2f}s"
                  f" {cfg.bandwidth_bps(n_devices):8.0f}B/s")
    print("      注：带宽只由 T_hb 决定，与 r 无关；r 只花时延，不花带宽。")
    print("          这是本机制相对周期性共识的结构优势——省的是共识频率 R。")
    print()


def ceiling_contrast(alpha: float) -> None:
    print(f"与 paper02 二值通道天花板的对照  (alpha={alpha})")
    print("      互锁通道 q 是数据性质、压不下去；沉默通道 q = p^r 是设计参数")
    print(f"      {'通道':<22} {'q':>9} {'min(1,a/q)':>12}")
    for name, q in (("paper02 互锁(训练折)", 0.0054),
                    ("paper02 互锁(部署流)", 0.047),
                    ("沉默 p=1e-2, r=1", silence.far_prob(1e-2, 1)),
                    ("沉默 p=1e-2, r=2", silence.far_prob(1e-2, 2)),
                    ("沉默 p=1e-2, r=3", silence.far_prob(1e-2, 3)),
                    ("沉默 p=1e-2, r=3 突发0.3",
                     silence.far_prob(1e-2, 3, burst_rho=0.3))):
        print(f"      {name:<22} {q:9.2e} "
              f"{silence.power_ceiling(alpha, q):12.3f}")
    print("      注：本文把沉默作硬层（协议违反），不走 p 值融合，故不受此限；")
    print("          上表是为回应'你的通道也是二值的'这一质疑而给的对照。")
    print()


def vs_corroboration(acts) -> None:
    """只靠耦合互证时，判定一次沉默要等多久。

    互证的 pending 超时必须以命令账本的计划完成时刻为基准（README 第五之二
    节第 3 条），故该时延 = planned_operation_time。这是实测量。
    """
    planned = [a.planned_s for a in acts if a.planned_s]
    dur = [a.duration_s for a in acts if a.duration_s]
    print(f"与耦合互证的时延对照  (命令账本计划时长, {len(planned)}/{len(acts)} "
          f"个活动有 planned_operation_time)")
    print(f"      计划时长   中位 {median(planned):7.1f}s  "
          f"p90 {_pct(planned, 0.9):7.1f}s  p95 {_pct(planned, 0.95):7.1f}s  "
          f"max {max(planned):7.1f}s")
    print(f"      实际时长   中位 {median(dur):7.1f}s  "
          f"p90 {_pct(dur, 0.9):7.1f}s  p95 {_pct(dur, 0.95):7.1f}s  "
          f"max {max(dur):7.1f}s")
    for t, r, note in ((0.2, 3, "独立丢包口径"), (0.2, 9, "突发口径 p=1e-2")):
        cfg = silence.SilenceConfig(t_hb_s=t, r_misses=r)
        gain = median(planned) / cfg.detect_delay_s
        print(f"      可问责沉默 T_hb={t:.2f}s r={r:2d} ({note}): "
              f"T_detect={cfg.detect_delay_s:5.2f}s，"
              f"快 {gain:.0f} 倍")
    print("      注：两者不可互相替代。互证判'是否说谎'、沉默判'是否缺席'；")
    print("          沉默时无任何待验证声明，互证无从发动，只能等计划时刻超时。")
    print()


def bandwidth_contrast(n_devices: int) -> None:
    print(f"带宽对照  ({n_devices} 台设备)")
    for rate in (1.0, 10.0):
        b = silence.pbft_bandwidth_bps(n_devices, rate)
        print(f"      周期性 PBFT @{rate:4.0f} Hz  {b/1e6:8.3f} MB/s  "
              f"({2*n_devices*n_devices:.0f} 条/轮)")
    for t in (0.05, 0.2, 1.0):
        cfg = silence.SilenceConfig(t_hb_s=t)
        print(f"      心跳 T_hb={t:.2f}s        "
              f"{cfg.bandwidth_bps(n_devices)/1024:8.3f} KB/s")
    print(f"      一次判决的密码学开销  "
          f"{silence.bytes_per_verdict(silence.SilenceConfig())}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--devices", type=int, default=28,
                    help="仿真车队规模，默认取引导例的 20 AGV + 8 机械臂")
    ap.add_argument("--alpha", type=float, default=0.001)
    ap.add_argument("--rho", type=float, default=0.3,
                    help="相邻槽丢包的条件相关系数，工业无线的突发口径")
    args = ap.parse_args()

    selftest()
    tradeoff(args.devices, args.rho)
    ceiling_contrast(args.alpha)
    bandwidth_contrast(args.devices)
    live = ingest.valid(ingest.read_xes(args.xes), drop_failure=True)
    vs_corroboration(live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
