"""引言动机算例:常数运输时间矩阵与无冲突路由给出相反的指派次序。

这不是统计结论,而是一个**存在性演示**——它要说明的是"次序反转会发生",而不是"次序反转
普遍发生"。因此算例是手工构造的、可完全复算的,几何形状与论文图 1(a) 逐一对应。
--sweep 另给出一条稳健性读数:反转不是参数空间里的孤点。

算例(4 工件 / 3 机械臂 / 6 节点 / 5 走廊 / 2 AGV)。一条排他的干道 v1--v2(tau=6)是通往
远端两台机械臂 M1/M3 的唯一通路;近端的 M2 挂在自己的支路上(v1--m2, tau=2),不与干道争用。

      m2                        m1
       |                         |
      (2)                       (1)
       |                         |
      v1 ==========(6)========= v2          == 排他干道,唯一深层瓶颈
       |                         |
      (1)                       (1)
       |                         |
    v0(LU)                      m3

焦点工件 J1 的那道工序有两个候选:M1 快(t^P=3)但在干道之后,M2 慢(t^P=14)但在干道之前。
背景工件 J2..J4 只能上 M3,因而反复穿越干道,把它占满。delta_return=1,成品需回运 LU。

为什么参数是这几个值。理想矩阵下选 M1 要求 2*tau+4+FAST < 6+SLOW,即 SLOW > 2*tau+FAST-2;
tau=6、FAST=3 时 SLOW 最小取 14。也就是说,这里的异构度已取到"能让反转发生"的最小值,
不是为了把效果做大而挑的。

两种评价。
  理想矩阵   conflict_free=False:行驶时间取最短路,车辆互不相见(文献主流约定)。
  无冲突路由 conflict_free=True :走廊排他、半开时窗,让行等待真实发生。

运行(clbs/ 目录下):
  py -u -m tools.motivating            # 打印四个数并写 output/motivating.json
  py -u -m tools.motivating --sweep    # 附带在参数网格上统计反转出现的比例
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.decoder import decode
from algorithm.instance import parse_instance
from algorithm.network import Network

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TRUNK = 6.0      # 干道 v1--v2 的通过时间,排他
FAST = 3.0       # 焦点工序在 M1(远端快臂)上的加工时间
SLOW = 14.0      # 焦点工序在 M2(近端慢臂)上的加工时间
N_BG = 3         # 背景工件数,全部只能上 M3
BG_PROC = 3.0    # 背景工序的加工时间
N_AGV = 2


def build(trunk=TRUNK, fast=FAST, slow=SLOW, n_bg=N_BG,
          bg_proc=BG_PROC, n_agv=N_AGV):
    nodes = ["v0", "v1", "v2", "m1", "m2", "m3"]
    corridors = [
        {"u": "v0", "v": "v1", "time": 1.0},
        {"u": "v1", "v": "v2", "time": trunk},   # 排他干道
        {"u": "v2", "v": "m1", "time": 1.0},
        {"u": "v2", "v": "m3", "time": 1.0},
        {"u": "v1", "v": "m2", "time": 2.0},
    ]
    jobs = [{"id": 1, "num_ops": 1}]
    proc = {"(1,1)": {"1": fast, "2": slow}}
    for j in range(2, 2 + n_bg):
        jobs.append({"id": j, "num_ops": 1})
        proc[f"({j},1)"] = {"3": bg_proc}

    inst = parse_instance({
        "name": "motivating",
        "delta_return": 1,
        "jobs": jobs,
        "machines": [{"id": 1, "node": "m1"},
                     {"id": 2, "node": "m2"},
                     {"id": 3, "node": "m3"}],
        "proc_time": proc,
        "num_agvs": n_agv,
        "network": {"lu_node": "v0", "nodes": nodes, "corridors": corridors},
    })
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    return inst, net


def evaluate(inst, net, focal_machine: int, n_bg: int = N_BG) -> dict:
    """把 J1 的工序指派给 focal_machine,其余不变;两种评价各算一次。"""
    ma = {(1, 1): focal_machine}
    for j in range(2, 2 + n_bg):
        ma[(j, 1)] = 3
    os_seq = []                       # delta_return=1,故每个工件出现两次
    for j in [1] + list(range(2, 2 + n_bg)):
        os_seq += [j, j]
    return {tag: round(decode(inst, net, ma, os_seq,
                              conflict_free=cf, dispatch="rule").makespan, 4)
            for tag, cf in (("ideal", False), ("routed", True))}


def sweep() -> dict:
    """反转在参数网格上出现得有多普遍(用于图注的稳健性说明)。"""
    total = rev = 0
    for trunk in (4.0, 5.0, 6.0, 7.0, 8.0):
        for fast in (3.0, 4.0):
            for slow in (8.0, 10.0, 12.0, 14.0, 16.0):
                for n_bg in (3, 4, 5, 6):
                    for n_agv in (2, 3):
                        for bg in (3.0, 4.0, 5.0):
                            inst, net = build(trunk, fast, slow, n_bg, bg, n_agv)
                            a = evaluate(inst, net, 1, n_bg)
                            b = evaluate(inst, net, 2, n_bg)
                            total += 1
                            if (a["ideal"] - b["ideal"]) < 0 < (a["routed"] - b["routed"]):
                                rev += 1
    return {"grid": total, "reversed": rev, "share": round(rev / total, 4)}


def main() -> int:
    inst, net = build()
    m1 = evaluate(inst, net, 1)   # 快臂,在干道之后
    m2 = evaluate(inst, net, 2)   # 慢臂,在干道之前

    print(f"焦点工序 (1,1):M1 t^P={FAST:.0f} / M2 t^P={SLOW:.0f};"
          f"干道 tau={TRUNK:.0f} 排他,背景工件 {N_BG} 个只能上 M3,{N_AGV} 辆 AGV\n")
    print(f"{'指派':<26s} {'理想矩阵':>10s} {'无冲突路由':>12s}")
    print("-" * 52)
    for name, v in (("M1 快臂(远端,干道之后)", m1), ("M2 慢臂(近端,自有支路)", m2)):
        print(f"{name:<26s} {v['ideal']:>10.1f} {v['routed']:>12.1f}")
    print("-" * 52)
    print(f"差值 C(M1)-C(M2):理想矩阵 {m1['ideal'] - m2['ideal']:+.1f},"
          f"无冲突路由 {m1['routed'] - m2['routed']:+.1f}")

    ideal_pick = 1 if m1["ideal"] <= m2["ideal"] else 2
    routed_pick = 1 if m1["routed"] <= m2["routed"] else 2
    print(f"理想矩阵选 M{ideal_pick},无冲突路由选 M{routed_pick} -> "
          f"{'次序反转' if ideal_pick != routed_pick else '未反转'}")
    if ideal_pick == routed_pick:
        print("\n未出现反转,需重新标定 TRUNK / FAST / SLOW / N_BG。")
        return 1

    payload = {
        "note": "引言动机算例;手工构造的存在性演示,非统计结论",
        "params": {"trunk_tau": TRUNK, "proc_fast": FAST, "proc_slow": SLOW,
                   "n_background": N_BG, "bg_proc": BG_PROC, "num_agvs": N_AGV,
                   "travel_M1_round": 2 * (1 + TRUNK + 1), "travel_M2_round": 2 * (1 + 2)},
        "M1": m1, "M2": m2,
        "ideal_pick": ideal_pick, "routed_pick": routed_pick,
    }
    if "--sweep" in sys.argv[1:]:
        payload["sweep"] = sweep()
        s = payload["sweep"]
        print(f"\n参数网格 {s['grid']} 组中有 {s['reversed']} 组出现反转"
              f"({s['share']:.0%})——反转不是参数空间里的孤点。")

    out_path = os.path.join(HERE, "output", "motivating.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n已写 {os.path.relpath(out_path, HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
