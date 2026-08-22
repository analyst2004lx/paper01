"""外部来源布局上的批跑:E1/E2/E3 + E4(结构) + E5,结果写入 experiments/pub_layouts/。

用法(在 STRC/ 下):
    py -m tools.pub_batch
    py -m tools.pub_batch --seeds 42,7,2024

**这是一批独立账本,不并入 experiments/expanded/。** 主批次的 5 算例 × 10 种子 = 50 对
是论文里所有 `/50` 读数的来源;把外部布局混进那个批次会让全部门槛读数改口径,而本批要
回答的是另一个问题,不需要动它。两批的算例只差布局来源:工件数、AGV 数、每工件工序数、
H、F 与 T̄t/T̄p 标定目标一律相同(见 `clbs/tools/gen_pub_layouts.py`)。

要回答的问题。自建的三张同规模布局(mid/high/funnel)同属哑铃一族,彼此只差 LU 出口与
中段的并行通道数——只差容量,不差几何。闭包规模的结构可预测性在它们身上没测出来,但那个
负结果分不清两种成因:是结构指标太粗,还是同族变体的几何差异本就不足以被任何指标分辨。
本批换上五张不由本文设计、几何上真正不同的布局,把这两种解释分开。

E4 这一格的口径与 `tools.e4_structure` 一致:阻断 LU 最小割走廊,且从 t_now 一直封到
视界末端(结构性断路,而非只封繁忙子窗)。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "experiments", "pub_layouts")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC external-layout batch")
    ap.add_argument("--seeds", default="42,7,2024,99,123,13,1,777,31415,8")
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--e5-seeds", type=int, default=3)
    ap.add_argument("--skip-e5", action="store_true")
    ap.add_argument("--out-dir", default=OUT)
    return ap.parse_args()


# 布局键 -> 算例文件名。机器台数由布局决定,故基名各不相同。
# LyuL1(3 机)未列入:固定 F=0.6 时 F*NM=1.8<2,与 B1 冲突;为一张布局放宽 F 就等于
# 多引入一个变量,故宁可少一张(见 gen_pub_layouts 的 skipped 分支)。
_PUB = [
    ("LyuL2_4m", "S8x4x4-LyuL2-H0.3-F0.6-A4-s42.json"),
    ("LyuL3_5m", "S8x5x4-LyuL3-H0.3-F0.6-A4-s42.json"),
    ("LyuL4_6m", "S8x6x4-LyuL4-H0.3-F0.6-A4-s42.json"),
    ("LyuL5_7m", "S8x7x4-LyuL5-H0.3-F0.6-A4-s42.json"),
    ("LyuL6_8m", "S8x8x4-LyuL6-H0.3-F0.6-A4-s42.json"),
]


# 自建对照组:与外部布局**逐参数同口径**(8 工件、4 AGV、3 工序、H0.3、F0.6、
# T̄t/T̄p=1.0),只差布局来源。必须有这一组,否则"外部布局的闭包占比离散度更大"就没有
# 可比的基线——论文 tab:e4 那两张表用的是 12 工件/8 机/12 车/T̄t/T̄p=4.0 的另一套参数,
# 与本批不可直接对照。
_CONTROL = [
    ("self_high_LD21", "S8x4x4-LD21-H0.3-F0.6-A4-s42.json"),
    ("self_funnel_LD11", "S8x4x4-LD11-H0.3-F0.6-A4-s42.json"),
    ("self_mid_LD22", "S8x4x4-LD22-H0.3-F0.6-A4-s42.json"),
]


def _resolve(fname: str, clbs_subdir: str) -> str:
    """优先取 STRC/database/instances/ 下的本地副本,缺失时回落到 clbs。

    本批的输入算例在 `database/instances/` 有一份镜像(由 tools.sync_database 生成),
    读它而不是读 clbs,是为了让 paper04 这一支的数据与代码同处一地——归档、打包附件
    不必跨目录去捞。回落分支保留是为了在只更新了 clbs 生成器、还没同步时也能跑通。
    副本与 clbs 源是否一致,用 `py -m tools.sync_database --check` 查。
    """
    local = os.path.join(ROOT, "database", "instances", fname)
    if os.path.isfile(local):
        return local
    from algorithm.clbs_bridge import CLBS_INPUT
    return os.path.join(CLBS_INPUT, clbs_subdir, fname)


def _instances():
    return [(n, _resolve(f, "pub")) for n, f in _PUB]


def _controls():
    return [(n, _resolve(f, "ext")) for n, f in _CONTROL]


def _run_e4_struct(inst_path, inst_name, seed, t_frac, rows):
    """E4 口径:封死 LU 最小割走廊直到视界末端,量闭包占比。"""
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.closure import machine_chains_from_ops, spatiotemporal_closure
    from algorithm.disturbance import Disturbance, seed_failed_reservations
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    feats = net.structural_features(list(inst.machine_node.values()))
    cut_cids = list(feats.get("lu_cut_corridors") or [])

    bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
    t_now = t_frac * bundle.makespan
    prefer = None
    for c in cut_cids:
        if any(r.corridor == c and r.t_end > t_now for r in bundle.reservations):
            prefer = c
            break
    cid, _t0, _t1, n_hit = pick_busy_corridor(
        bundle.reservations, t_now=t_now, prefer=prefer)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                       t_start=t_now, t_end=bundle.makespan + 1.0)
    seeds_r = seed_failed_reservations(dist, bundle.reservations)
    chains = machine_chains_from_ops(bundle.result.ops)
    closure = spatiotemporal_closure(
        seeds_r, bundle.reservations, horizon=bundle.makespan + 1.0,
        t_now=t_now, machine_chains=chains)
    n_alive = sum(1 for r in bundle.reservations if r.t_end > t_now)
    rows.append({
        "instance": inst_name, "seed": seed,
        "num_machines": len(inst.machine_node),
        "n_nodes": len(inst.nodes), "n_corridors": len(inst.corridors),
        "lu_min_cut": feats["lu_min_cut"],
        "far_group_cut": feats["far_group_cut"],
        "funnel_share": feats["funnel_share"],
        "corridors_per_node": feats["corridors_per_node"],
        "blocked_on_cut": cid in cut_cids,
        "corridor": cid, "n_hits": n_hit,
        "makespan": round(bundle.makespan, 4),
        "n_reservations": len(bundle.reservations),
        "n_alive": n_alive,
        "n_seeds": len(seeds_r),
        "n_closure": closure.size,
        "closure_frac": round(closure.size / max(1, len(bundle.reservations)), 4),
        "closure_frac_alive": round(closure.size / max(1, n_alive), 4),
    })


def _write(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _spearman(xs, ys) -> float:
    """秩相关。样本很小,这里只作方向性参考,不做显著性判定。"""
    def rank(vs):
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        r = [0.0] * len(vs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return float("nan") if dx == 0 or dy == 0 else round(num / (dx * dy), 3)


def _summarize(out_dir, e1, e2, e3, e4, e5) -> str:
    lines = ["# 外部来源布局批次(Lyu 附录 A 拓扑)", "",
             "算例与主批次只差布局来源;边权为本文补齐的等权值,"
             "**不可**与 Lyu 或 van Os 的参照值比较。", ""]

    lines += ["## E1 任务图漏报", "",
              "| 算例 | n | C1 通过 | 均值 \\|Cl\\| | 均值种子 "
              "| Cl/\\|R\\| 中位 | 结构泄漏 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e1:
        by[r["instance"]].append(r)
    for name in [n for n, _ in _PUB if n in by]:
        rs = by[name]
        lines.append(
            f"| `{name}` | {len(rs)} | "
            f"{sum(1 for r in rs if r['pass_C1'])}/{len(rs)} | "
            f"{mean(r['n_closure'] for r in rs):.1f} | "
            f"{mean(r['n_seeds'] for r in rs):.1f} | "
            f"{median(r['closure_frac'] for r in rs):.3f} | "
            f"{sum(r['structural_leaks'] for r in rs)} |")

    lines += ["", "## E2 包含性", "",
              "| 算例 | E2a | E2b | 可行 |", "|---|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e2:
        by[r["instance"]].append(r)
    for name in [n for n, _ in _PUB if n in by]:
        rs = by[name]
        lines.append(
            f"| `{name}` | {sum(1 for r in rs if r['pass_E2a'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['pass_E2b'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['feasible'])}/{len(rs)} |")

    lines += ["", "## E3 边界消融(关闭扩域)", "",
              "| 算例 | B 类漏报 | R1 可行 | R2 可行 |", "|---|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e3:
        by[r["instance"]].append(r)
    for name in [n for n, _ in _PUB if n in by]:
        rs = by[name]
        lines.append(
            f"| `{name}` | {sum(1 for r in rs if r['miss_on_B'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['R1_feasible'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['R2_feasible'])}/{len(rs)} |")

    if e4:
        lines += ["", "## E4 结构(封死 LU 割走廊到视界末端)", "",
                  "两组算例逐参数同口径,只差布局来源。", "",
                  "| 来源 | 算例 | 机器 | 节点 | 走廊 | LU割 | 远端割 | 漏斗占比 "
                  "| 每节点走廊 | Cl/\\|R\\| 中位 | Cl/活 中位 |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        by = defaultdict(list)
        for r in e4:
            by[r["instance"]].append(r)
        for group, names in (("外部", [n for n, _ in _PUB]),
                             ("自建", [n for n, _ in _CONTROL])):
            for name in [n for n in names if n in by]:
                rs = by[name]
                f0 = rs[0]
                lines.append(
                    f"| {group} | `{name}` | {f0['num_machines']} | "
                    f"{f0['n_nodes']} | {f0['n_corridors']} | "
                    f"{f0['lu_min_cut']} | {f0['far_group_cut']} | "
                    f"{f0['funnel_share']} | {f0['corridors_per_node']} | "
                    f"{median(r['closure_frac'] for r in rs):.3f} | "
                    f"{median(r['closure_frac_alive'] for r in rs):.3f} |")

    if e5:
        lines += ["", "## E5 预算点", "",
                  "| 算例 | 预算 s | R0+ Cmax | R2 Cmax | R2 ms | R0+ ms |",
                  "|---|---:|---:|---:|---:|---:|"]
        by = defaultdict(list)
        for r in e5:
            by[(r["instance"], r["budget_sec"])].append(r)
        for key in sorted(by, key=lambda x: (x[0], x[1])):
            rs = by[key]
            f_ok = [r for r in rs if r["R0_feasible"]]
            r_ok = [r for r in rs if r["R2_feasible"]]
            lines.append(
                f"| `{key[0]}` | {key[1]:g} | "
                f"{(mean(r['R0_makespan'] for r in f_ok) if f_ok else float('nan')):.1f} | "
                f"{(mean(r['R2_makespan'] for r in r_ok) if r_ok else float('nan')):.1f} | "
                f"{mean(r['R2_wall_ms'] for r in rs):.1f} | "
                f"{mean(r['R0_wall_ms'] for r in rs):.0f} |")

    path = os.path.join(out_dir, "summary.md")
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main() -> int:
    args = parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]
    os.makedirs(args.out_dir, exist_ok=True)
    from tools.expand_batch import _run_e1e2e3, _run_e5  # 复用,不重写一遍

    e1, e2, e3, e4, e5 = [], [], [], [], []
    insts = _instances()
    missing = [p for _, p in insts if not os.path.isfile(p)]
    if missing:
        print("缺算例文件,请先在 clbs/ 下跑 py -m tools.gen_pub_layouts:")
        for p in missing:
            print(f"  {p}")
        return 2

    print("=== pub_batch: E1/E2/E3 ===")
    for name, path in insts:
        for seed in seeds:
            print(f"  E1-3 {name} seed={seed}")
            _run_e1e2e3(path, name, seed, args.t_now_frac, e1, e2, e3)

    print("=== pub_batch: E4 structure (外部 + 自建对照) ===")
    for name, path in insts + [c for c in _controls() if os.path.isfile(c[1])]:
        for seed in seeds:
            _run_e4_struct(path, name, seed, args.t_now_frac, e4)
            r = e4[-1]
            print(f"  e4 {name} seed={seed} cut={r['lu_min_cut']} "
                  f"on_cut={r['blocked_on_cut']} |cl|={r['n_closure']} "
                  f"frac={r['closure_frac']:.3f}")

    if not args.skip_e5:
        print("=== pub_batch: E5 ===")
        # 与主批次同口径:取最小与最大两张布局 × 前 3 个种子 × 3 个预算 = 18 点
        for name, path in [insts[0], insts[-1]]:
            for seed in seeds[:args.e5_seeds]:
                _run_e5(path, name, seed, args.t_now_frac, e5)

    _write(os.path.join(args.out_dir, "e1_miss.csv"), e1)
    _write(os.path.join(args.out_dir, "e2_containment.csv"), e2)
    _write(os.path.join(args.out_dir, "e3_boundary.csv"), e3)
    _write(os.path.join(args.out_dir, "e4_structure.csv"), e4)
    _write(os.path.join(args.out_dir, "e5_cross_curve.csv"), e5)
    md = _summarize(args.out_dir, e1, e2, e3, e4, e5)

    print(f"\nwrote summary {md}")
    print(f"E1 C1 pass  {sum(1 for r in e1 if r['pass_C1'])}/{len(e1)}")
    print(f"E2a pass    {sum(1 for r in e2 if r['pass_E2a'])}/{len(e2)}")
    print(f"E2b pass    {sum(1 for r in e2 if r['pass_E2b'])}/{len(e2)}")
    print(f"E3 R1 feas  {sum(1 for r in e3 if r['R1_feasible'])}/{len(e3)}")
    print(f"E3 R2 feas  {sum(1 for r in e3 if r['R2_feasible'])}/{len(e3)}")

    # E4 的判据分两问:(a) 闭包占比在布局之间到底有多大差异,(b) 结构指标能不能
    # 解释这个差异。先看指标本身有没有方差——指标恒定时谈相关系数是没有意义的。
    if e4:
        by = defaultdict(list)
        for r in e4:
            by[r["instance"]].append(r)
        for group, order in (("外部", [n for n, _ in _PUB]),
                             ("自建", [n for n, _ in _CONTROL])):
            names = [n for n in order if n in by]
            if not names:
                continue
            fracs = [median(r["closure_frac"] for r in by[n]) for n in names]
            cuts = [by[n][0]["lu_min_cut"] for n in names]
            funnels = [by[n][0]["funnel_share"] for n in names]
            cpn = [by[n][0]["corridors_per_node"] for n in names]
            print(f"\n[E4/{group}] 逐布局 Cl/|R| 中位:"
                  + ", ".join(f"{n}={v:.3f}" for n, v in zip(names, fracs)))
            print(f"[E4/{group}] 闭包占比极差 {max(fracs) - min(fracs):.3f}"
                  f"(min {min(fracs):.3f} / max {max(fracs):.3f})")
            print(f"[E4/{group}] LU割 {sorted(set(cuts))};"
                  f"漏斗占比 {sorted(set(funnels))};"
                  f"每节点走廊 {sorted(set(cpn))}")
            for label, xs in (("LU割", cuts), ("漏斗占比", funnels),
                              ("每节点走廊", cpn)):
                if len(set(xs)) == 1:
                    note = "指标在本组无方差,无法区分"
                else:
                    note = f"rho={_spearman(xs, fracs)}"
                print(f"[E4/{group}] {label} vs 闭包占比:{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
