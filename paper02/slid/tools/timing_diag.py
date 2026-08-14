"""M4 落地后与 probe_aft*.py / probe_timing.py 对数。

目标数字:
    sigma_log  无条件                   = 0.355
    sigma_log  路线条件化(已见路线)     = 0.116
    sigma_log  加性 AFT 外推到未见路线  = 0.279
    sigma_log  计划工时冷启动先验       = 0.159
    加性与逐路线饱和模型残差之差         = 0.000(全部分组的路线图皆为森林)
    20 个分组的 rho* 跨度 1.6% ~ 98.6%,中位 sigma=0.207 -> 38.2%

用法(在 paper02/slid/ 下):  py -m tools.timing_diag
"""
from __future__ import annotations

import argparse

from algorithm import ingest, timing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=ingest.default_log_path())
    ap.add_argument("--alpha", type=float, default=0.01)
    args = ap.parse_args()

    acts = ingest.valid(ingest.read_xes(args.xes), drop_failure=False)
    diag = timing.sigma_diagnostics(acts)

    print("=== 逐 (设备, 操作) 的路线图结构与残差尺度 ===")
    hdr = (f"{'设备':<8} {'操作':<30} {'n':>4} {'路线':>5} {'森林':>5} "
           f"{'无条件':>8} {'条件化':>8} {'饱和':>8} {'留一加性':>9} "
           f"{'留一计划':>9}")
    print(hdr)
    print("-" * 100)
    for g in diag["groups"]:
        print(f"{g['device']:<8} {g['op']:<30} {g['n']:>4} {g['routes']:>5} "
              f"{str(g['forest']):>5} {g['pooled']:>8.3f} "
              f"{g['conditioned']:>8.3f} {g['saturated']:>8.3f} "
              f"{g['loo_additive']:>9.3f} {g['loo_planned']:>9.3f}")
    print()
    print(f"  全部分组的路线图皆为森林: {diag['all_forest']}")
    print(f"  加性 vs 饱和,最大残差差: {diag['additive_saturated_gap']:.6f}")
    print()
    for k, label in (("pooled", "无条件"),
                     ("conditioned", "路线条件化(已见路线)"),
                     ("loo_additive", "加性 AFT 外推到未见路线"),
                     ("loo_planned", "计划工时冷启动先验")):
        print(f"  sigma_log  {label:<26s} = {diag[k]:.3f}   "
              f"rho*={timing.rho_star(diag[k], args.alpha)*100:5.1f}%")
    print()

    print("=== 改进链条:分层与协变量各自贡献了多少 ===")
    hdr = (f"{'口径':<34} {'分组':>5} {'最小':>7} {'中位':>7} {'最大':>7} "
           f"{'中位 rho*':>10}")
    print(hdr)
    print("-" * 76)
    arms = (("probe_timing 基线(不分层,不条件化)", None, False),
            ("+ 按 success 分层", "success", False),
            ("+ 路线协变量条件化(M4 实用口径)", "success", True))
    for label, stratum, cond in arms:
        rows = timing.group_sigmas(acts, stratum=stratum, conditioned=cond)
        s = timing.sigma_summary(rows)
        print(f"{label:<34} {s['n_groups']:>5} {s['min']:>7.3f} "
              f"{s['median']:>7.3f} {s['max']:>7.3f} "
              f"{timing.rho_star(s['median'], args.alpha)*100:>9.1f}%")
    print()

    models = timing.fit(acts)
    print(f"=== 拟合出 {len(models)} 个分组模型,按 rho* 排序 "
          f"(alpha={args.alpha}, 单侧) ===")
    hdr = (f"{'设备':<8} {'操作':<30} {'n':>5} {'路线':>5} {'sigma':>7} "
           f"{'自由度':>6} {'rho*':>7} {'时序有效':>9}")
    print(hdr)
    print("-" * 90)
    rows = sorted(models.values(), key=lambda m: m.sigma)
    for m in rows:
        print(f"{m.device:<8} {m.op:<30} {m.n:>5} {len(m.route_effect):>5} "
              f"{m.sigma:>7.3f} {m.df:>6} "
              f"{timing.rho_star(m.sigma, args.alpha)*100:>6.1f}% "
              f"{('是' if m.informative else '否'):>9}")
    print()
    sig = sorted(m.sigma for m in rows)
    mid = sig[len(sig) // 2]
    print(f"  sigma 跨度 {sig[0]:.3f} ~ {sig[-1]:.3f},中位 {mid:.3f} "
          f"-> rho* {timing.rho_star(mid, args.alpha)*100:.1f}%")
    bad = [m for m in rows if not m.informative]
    print(f"  时序通道无效的分组 {len(bad)} 个: "
          f"{', '.join(m.device + ' ' + m.op for m in bad) or '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
