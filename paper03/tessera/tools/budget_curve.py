"""$T_{hb}$ 的可行区间、最省带宽配置、突发容忍的带宽代价。

定理链条按四段报，每段都可独立核对：

    危害模型 -> 时间预算 -> (r, T_hb) 可行区间 -> 带宽下界

  1. 预算分解：两种危害模型给出两个预算。借用汽车领域的 FHI 会**太松**——
     实测它对应的行驶距离是 ISO 3691-4 防护场的 256%，车早就冲出包络了。
  2. 可行区间与最省带宽配置，以及它在两条约束上各剩多少余量。
  3. **突发容忍的带宽代价**：为在成簇丢包下维持同样的误报与安全保证要多付多少。
  4. 与周期性 PBFT 的量级对照（基线 W1：全体设备法定人数）。

用法(在 paper03/tessera/ 下):  py -m tools.budget_curve
"""
from __future__ import annotations

import argparse

from algorithm import budget, silence

_BIND = {budget.SAFETY: "安全边界（FHI）",
         budget.AVAILABILITY: "可用性边界（误报预算）",
         budget.BOTH: "两条边界同时顶满",
         budget.NONE: "均未顶到（离散网格所致）"}


def _report(b: budget.SafetyBudget, label: str, kw: dict, rho: float) -> None:
    xs = budget.feasible(b, burst_rho=rho, **kw)
    tag = "独立丢包" if rho == 0.0 else f"突发 rho={rho}"
    if not xs:
        print(f"      [{label} / {tag}] 无可行解——预算给不出方案，"
              "须调 FHI、换网络或降设备数。")
        return
    d = xs[0]
    s = budget.slack(d, b, kw["far_target_per_hour"])
    bind = budget.binding_constraint(d, b, burst_rho=rho, **kw)
    print(f"      [{label} / {tag}] {len(xs)} 个可行点，"
          f"r 取值 {sorted({x.r_misses for x in xs})}")
    print(f"        最省带宽 {d}")
    print(f"        余量：安全 {s['safety_slack']*100:.1f}%，"
          f"误报 {s['availability_slack']*100:.1f}% -> 顶在 {_BIND[bind]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--devices", type=int, default=28)
    ap.add_argument("--p-loss", type=float, default=1e-2)
    ap.add_argument("--far", type=float, default=1.0, help="误报预算 次/小时")
    ap.add_argument("--rho", type=float, default=0.3, help="突发相关系数")
    ap.add_argument("--fhi", type=float, default=2.43)
    ap.add_argument("--t-react", type=float, default=0.25)
    ap.add_argument("--speed", type=float, default=1500.0, help="mm/s")
    args = ap.parse_args()

    auto = budget.SafetyBudget(fhi_s=args.fhi, t_react_s=args.t_react)
    pf = budget.protective_field_mm(v_mm_s=args.speed)
    motion = budget.SafetyBudget.from_protective_field(
        v_mm_s=args.speed, field_mm=pf["field_mm"], t_react_s=args.t_react)
    kw = dict(p_loss=args.p_loss, n_devices=args.devices,
              far_target_per_hour=args.far)

    print("一、只接可问责沉默，不接耦合互证")
    print("      沉默判定的 r·T_hb 与调度队列解耦，是无条件上界；任务完成类判定"
          "必须容纳派发排队")
    print("      （实测 p95 218.3s、max 1476.4s，无上界），只有条件上界，代进 "
          "FHI 是接错量纲。")
    print()

    print("二、危害模型定预算：借用通用 FHI 会太松")
    print(f"      ISO 3691-4 算例防护场 = 反应 {pf['react_mm']:.0f} + 制动 "
          f"{pf['brake_mm']:.0f} + 裕度 {pf['margin_mm']:.0f} = "
          f"{pf['field_mm']:.0f} mm")
    ratio = {}
    for label, b in (("汽车 FHI", auto), ("运动危害反推", motion)):
        trav = budget.detection_travel_mm(b.detect_budget_s, args.speed)
        ratio[label] = trav / pf["field_mm"]
        print(f"      [{label}] FHI={b.fhi_s:.2f}s 反应={b.t_react_s:.2f}s "
              f"检测预算={b.detect_budget_s:.2f}s "
              f"-> {args.speed/1000:.1f} m/s 下行驶 {trav:.0f} mm "
              f"= 防护场的 {ratio[label]*100:.0f}%")
        print(f"        来源：{b.source}")
    r_auto = ratio["汽车 FHI"]
    if r_auto > 1.0:
        print(f"      读法：借来的 FHI 让 AGV 在检测窗口内走出防护场 "
              f"{r_auto:.2f} 倍，即预算判『合规』而车已越界，故不能直接借用。")
    else:
        print(f"      读法：本例中借来的 FHI 恰好落在防护场内"
              f"（{r_auto*100:.0f}%），但这是参数巧合而非可依赖的性质——"
              f"FHI 与速度各自变动即失效。")
    print("      稳妥做法始终是让危害模型定预算（FHI = field / v），代价是预算"
          "收紧、带宽变贵——这是诚实的代价，不是缺陷。")
    print()

    print(f"三、可行区间  设备 {args.devices} 台，丢包 {args.p_loss}，"
          f"误报预算 {args.far}/h")
    for label, b in (("汽车 FHI", auto), ("运动危害反推", motion)):
        for rho in (0.0, args.rho):
            _report(b, label, kw, rho)
    print()

    print("四、两项代价的量化")
    prem = budget.burst_premium(motion, burst_rho=args.rho, **kw)
    a, c = prem["independent"], prem["bursty"]
    if prem["premium"]:
        print(f"      突发容忍（运动危害口径）：{prem['premium']:.2f}x")
        print(f"        机理：r {a.r_misses} -> {c.r_misses}，同一预算把 T_hb "
              f"从 {a.t_hb_s:.3f}s 压到 {c.t_hb_s:.3f}s，"
              f"带宽 {a.bandwidth_bps:.0f} -> {c.bandwidth_bps:.0f} B/s。")
        print("        只报独立丢包口径是不诚实的：工业无线的丢包成簇"
              "（阴影衰落与信道竞争）。")
    auto_c = budget.cheapest(auto, burst_rho=args.rho, **kw)
    if auto_c and c:
        print(f"      预算收紧（突发口径下 汽车 FHI -> 运动危害）："
              f"{c.bandwidth_bps/auto_c.bandwidth_bps:.2f}x")
        print(f"        {auto_c.bandwidth_bps:.0f} -> {c.bandwidth_bps:.0f} "
              f"B/s。这是把安全论断对齐到真实危害模型的价格。")
    print()

    print("五、与周期性 PBFT 的量级对照（基线 W1：全体设备法定人数）")
    for rate in (5.0, 10.0):
        pb = silence.pbft_bandwidth_bps(args.devices, rate)
        print(f"      PBFT {rate:.0f} Hz: {pb/1e6:.2f} MB/s = 本方案"
              f"（最贵口径 {c.bandwidth_bps:.0f} B/s）的 "
              f"{pb/c.bandwidth_bps:.0f} 倍")
    print("      省下的是共识频率 R，不是参与节点数——容错阈值未降低。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
