"""随算例规模变化的闭包规模与响应时间曲线。

正文此前的读数都落在 8 工件 4 机这一档,而"有界修复比全局重解便宜"这类主张,
读者关心的恰是它随规模怎么走——若闭包占比随规模上升到接近 1,有界性就名存实亡。
本工具沿一条**只变规模**的梯子测这件事:工件数 = 2k、机器数 = k、车数 = k,
k = 4..10(即 8x4x4 到 20x10x10),拥堵档、异构度 H、柔性度 F、运输/加工时长比
Tt/Tp 与 LU 割、远端割全部同口径(见 `clbs/tools/gen_instances.py` 的标定)。

三条臂与 tools.cheap_baselines 同定义(R2 闭包修复 / RS 全局右移 / RD 原染色体
重解码),扰动协议与 E1--E3 一致。

用法(STRC/ 目录下):
    py -m tools.scale_curve
    py -m tools.scale_curve --ks 4,6,8,10 --seeds 42,7
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_SEEDS = [42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="closure size / response time vs scale")
    ap.add_argument("--ks", default="4,5,6,7,8,9,10",
                    help="规模参数 k:工件 2k、机器 k、车 k")
    ap.add_argument("--seeds", default=",".join(str(s) for s in _SEEDS))
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--out", default="experiments/scale_curve.csv")
    return ap.parse_args()


def _path(k: int) -> str:
    from algorithm.clbs_bridge import CLBS_INPUT
    name = f"S{2*k}x{k}x{k}-LD22-H0.3-F0.6-A{k}-s42.json"
    return os.path.join(CLBS_INPUT, "ext", name)


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.repair import release_set_r2, repair_with_strc
    from algorithm.rightshift import repair_by_right_shift
    from algorithm.schedule_io import build_baseline, pick_busy_corridor
    from tools.cheap_baselines import _redecode, _row

    ks = [int(x) for x in args.ks.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]
    rows = []
    for k in ks:
        path = _path(k)
        if not os.path.isfile(path):
            print(f"  skip missing {os.path.basename(path)}")
            continue
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        for seed in seeds:
            bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = args.t_now_frac * bundle.makespan
            cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
            dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                               t_start=t0, t_end=t1)
            n_res = len(bundle.reservations)
            n_live = sum(1 for r in bundle.reservations if r.t_end > t_now)
            n_clo = len(release_set_r2(bundle, dist))
            arms = {
                "R2": repair_with_strc(inst, net, bundle, dist, expand_on_fail=False),
                "RS": repair_by_right_shift(inst, net, bundle, dist),
                "RD": _redecode(inst, net, bundle, dist),
            }
            # 首级失败的格用扩域阶梯兜一次,把轮数与总耗时记下来:正文声称阶梯
            # 存在就是为了这种情形,不记它等于只报了成功的那一半。
            esc_rounds = esc_ms = None
            if not arms["R2"].feasible:
                esc = repair_with_strc(inst, net, bundle, dist, expand_on_fail=True)
                esc_rounds = esc.meta.get("scope_rounds")
                esc_ms = round(esc.wall_ms, 3)
                if esc.feasible:
                    arms["R2"] = esc
            for arm, rep in arms.items():
                r = _row(f"S{2*k}x{k}x{k}", seed, arm, rep, bundle, t_now)
                r.update({"esc_rounds": esc_rounds if arm == "R2" else None,
                          "esc_wall_ms": esc_ms if arm == "R2" else None,
                          "k": k, "jobs": 2 * k, "machines": k,
                          "n_res": n_res, "n_live": n_live, "closure": n_clo,
                          "closure_frac": round(n_clo / n_live, 3) if n_live else None,
                          "n_nodes": len(inst.nodes),
                          "n_corridors": len(inst.corridors)})
                rows.append(r)
            print(f"  k={k:<3} s={seed:<6} |R|={n_res:<5} live={n_live:<5} "
                  f"clo={n_clo:<5}({n_clo/max(n_live,1):.2f})  " + "  ".join(
                      f"{a}:{r.wall_ms:>7.2f}ms" for a, r in arms.items()))

    out = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}  ({len(rows)} rows)")

    print(f"\n{'k':>3}{'工件':>5}{'|R|':>7}{'活跃':>7}{'闭包':>7}{'占比':>7}"
          f"{'R2/ms':>9}{'RS/ms':>9}{'RD/ms':>9}{'RD/R2':>8}{'首级':>7}{'终可行':>9}")
    for k in ks:
        rs = [r for r in rows if r["k"] == k]
        if not rs:
            continue
        g = {a: [r for r in rs if r["arm"] == a] for a in ("R2", "RS", "RD")}
        m = {a: st.median(r["wall_ms"] for r in g[a]) for a in g}
        r2 = g["R2"]
        print(f"{k:>3}{2*k:>5}{st.mean(r['n_res'] for r in r2):>7.0f}"
              f"{st.mean(r['n_live'] for r in r2):>7.0f}"
              f"{st.mean(r['closure'] for r in r2):>7.0f}"
              f"{st.mean(r['closure_frac'] for r in r2):>7.3f}"
              f"{m['R2']:>9.2f}{m['RS']:>9.2f}{m['RD']:>9.2f}"
              f"{m['RD']/m['R2']:>8.2f}"
              f"{sum(1 for r in r2 if r['esc_rounds'] is None)}/{len(r2)}"
              f"{sum(1 for r in r2 if r['feasible'])}/{len(r2):>7}")

    print("\n逐 k 的 Cmax 胜负(R2 赢/平/输):")
    idx = {(r["instance"], r["seed"], r["arm"]): r for r in rows}
    for k in ks:
        keys = sorted({(r["instance"], r["seed"]) for r in rows if r["k"] == k})
        if not keys:
            continue
        line = f"  k={k:<3}"
        for other in ("RS", "RD"):
            w = t = l = 0
            for key in keys:
                a, b = idx[(key[0], key[1], "R2")], idx[(key[0], key[1], other)]
                if not (a["feasible"] and b["feasible"]):
                    continue
                if a["makespan"] < b["makespan"] - 1e-9:
                    w += 1
                elif a["makespan"] > b["makespan"] + 1e-9:
                    l += 1
                else:
                    t += 1
            line += f"  vs {other}: {w}/{t}/{l}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
