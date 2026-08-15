"""丢包率扫参：把可问责沉默放到 PISTIS 口径的极端丢包下仍能给出可行设计。

PISTIS（IEEE TPDS 2021）在 50% 丢包下报告毫秒级有界投递。那是**通信层**事件
触发的实时性主张，与本文的任务状态伪造检测不是同一问题，故不作为数值基线。
但审稿人会问：你们的心跳机制在同样恶劣的丢包下还站得住吗？

本工具回答的正是这个问题——扫 $p \\in [10^{-3}, 0.5]$，对每个丢包率报告：

  1. 独立 / 突发口径下满足误报预算所需的最小 $r$；
  2. 运动危害预算下最省带宽的 $(T_{hb}, r, B)$；
  3. 相对 5 Hz PBFT 的带宽比；
  4. 设计何时变为不可行（预算给不出方案）。

诚实边界：丢包率与突发相关系数是**仿真参数**（Trier 日志无通信层），不是本
产线实测。扫参的目的是给出可行区间对 $p$ 的敏感度，不是声称工厂无线就是
某个 $p$。

用法(在 paper03/tessera/ 下):  py -m tools.loss_sweep
"""
from __future__ import annotations

import argparse
import csv
import os

from algorithm import budget, silence

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 默认扫参点。0.5 是 PISTIS 报告的地标，必须保留。
DEFAULT_GRID = (1e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 2e-1, 5e-1)


def row(p: float, *, n: int, far: float, burst_rho: float,
        safety: budget.SafetyBudget) -> dict:
    kw = dict(p_loss=p, n_devices=n, far_target_per_hour=far)
    d = budget.cheapest(safety, burst_rho=burst_rho, **kw)
    # 固定 T_hb=0.2 s 时所需 r，用来单独展示"突发把 r 抬高多少"
    r_indep = silence.min_misses(p, 0.2, n, far, burst_rho=0.0)
    r_burst = silence.min_misses(p, 0.2, n, far, burst_rho=burst_rho)
    pbft = silence.pbft_bandwidth_bps(n, 5.0)
    if d is None:
        return {
            "p_loss": p, "feasible": False,
            "r_at_0.2s_indep": r_indep, "r_at_0.2s_burst": r_burst,
            "t_hb_s": None, "r_misses": None, "detect_delay_s": None,
            "bandwidth_bps": None, "pbft_ratio": None,
            "binding": None,
        }
    return {
        "p_loss": p, "feasible": True,
        "r_at_0.2s_indep": r_indep, "r_at_0.2s_burst": r_burst,
        "t_hb_s": d.t_hb_s, "r_misses": d.r_misses,
        "detect_delay_s": d.detect_delay_s,
        "bandwidth_bps": d.bandwidth_bps,
        "pbft_ratio": pbft / d.bandwidth_bps,
        "binding": budget.binding_constraint(
            d, safety, burst_rho=burst_rho, **kw),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--devices", type=int, default=28)
    ap.add_argument("--far", type=float, default=1.0)
    ap.add_argument("--burst-rho", type=float, default=0.3)
    ap.add_argument("--grid", type=float, nargs="+", default=list(DEFAULT_GRID))
    ap.add_argument("--csv", default=None,
                    help="写出 CSV；默认 experiments/loss_sweep.csv")
    args = ap.parse_args()

    motion = budget.SafetyBudget.from_protective_field(
        field_mm=budget.protective_field_mm()["field_mm"])
    pbft = silence.pbft_bandwidth_bps(args.devices, 5.0)

    print(f"设备 {args.devices}  误报预算 {args.far}/h  "
          f"突发 rho={args.burst_rho}  "
          f"检测预算 {motion.detect_budget_s:.2f} s  "
          f"PBFT@5Hz {pbft/1e3:.0f} KB/s\n")

    print("一、运动危害 + 独立丢包")
    print(f"      {'p':>7s} {'可行':>4s} {'T_hb':>8s} {'r':>4s} "
          f"{'T_det':>8s} {'B B/s':>8s} {'vs PBFT':>8s}")
    indep_rows = []
    for p in args.grid:
        r = row(p, n=args.devices, far=args.far, burst_rho=0.0, safety=motion)
        indep_rows.append(r)
        _print_row(r)

    print(f"\n二、运动危害 + 突发丢包 (rho={args.burst_rho})")
    print(f"      {'p':>7s} {'可行':>4s} {'T_hb':>8s} {'r':>4s} "
          f"{'T_det':>8s} {'B B/s':>8s} {'vs PBFT':>8s}  "
          f"{'r@0.2s 独立→突发':>16s}")
    burst_rows = []
    for p in args.grid:
        r = row(p, n=args.devices, far=args.far,
                burst_rho=args.burst_rho, safety=motion)
        burst_rows.append(r)
        extra = (f"{r['r_at_0.2s_indep']}→{r['r_at_0.2s_burst']}"
                 if r["r_at_0.2s_indep"] is not None else "-")
        _print_row(r, extra=extra)

    print("\n三、读法")
    p50 = next((r for r in burst_rows if abs(r["p_loss"] - 0.5) < 1e-12), None)
    if p50 and p50["feasible"]:
        print(f"      PISTIS 地标 p=50% 下，突发口径仍可行："
              f"T_hb={p50['t_hb_s']:.3f}s r={p50['r_misses']} "
              f"B={p50['bandwidth_bps']:.0f} B/s "
              f"= PBFT 的 1/{p50['pbft_ratio']:.0f}。")
        print("      这不是说我们在做 PISTIS 的事——事件语义完全不同"
              "（通信层连通性 vs 任务状态伪造）；")
        print("      只说明可问责沉默的误报—时延—带宽关系在极端丢包下"
              "仍给出安全预算内的方案。")
    elif p50:
        print("      PISTIS 地标 p=50% 下突发口径无可行解——"
              "须调 FHI、换网络或降设备数。")

    # 带宽随 p 的增长
    b0 = next((r["bandwidth_bps"] for r in burst_rows
               if abs(r["p_loss"] - 1e-2) < 1e-12 and r["feasible"]), None)
    b50 = p50["bandwidth_bps"] if p50 and p50["feasible"] else None
    if b0 and b50:
        print(f"      相对默认 p=1%：p=50% 的带宽代价 "
              f"{b50/b0:.1f}×（{b0:.0f} → {b50:.0f} B/s）。")

    csv_path = args.csv or os.path.join(HERE, "experiments", "loss_sweep.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "regime", "p_loss", "feasible", "t_hb_s", "r_misses",
            "detect_delay_s", "bandwidth_bps", "pbft_ratio", "binding",
            "r_at_0.2s_indep", "r_at_0.2s_burst"])
        w.writeheader()
        for r in indep_rows:
            w.writerow({"regime": "motion_indep", **r})
        for r in burst_rows:
            w.writerow({"regime": "motion_burst", **r})
    print(f"\nCSV → {os.path.relpath(csv_path, HERE)}")
    return 0


def _print_row(r: dict, *, extra: str = "") -> None:
    if not r["feasible"]:
        print(f"      {r['p_loss']:7.3f} {'否':>4s}  —")
        return
    ratio = (f"1/{r['pbft_ratio']:.0f}" if r["pbft_ratio"] else "-")
    tail = f"  {extra}" if extra else ""
    print(f"      {r['p_loss']:7.3f} {'是':>4s} {r['t_hb_s']:8.4f} "
          f"{r['r_misses']:4d} {r['detect_delay_s']:8.3f} "
          f"{r['bandwidth_bps']:8.0f} {ratio:>8s}{tail}")


if __name__ == "__main__":
    raise SystemExit(main())
