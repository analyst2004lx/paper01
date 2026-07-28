"""独立校验器(规格文档第九节):不复用解码器逻辑,直接按建模文档约束逐条检查时刻表。

校验项:
(a) 工序先后与工时:同工件按 i 递增,finish = start + p,start >= 前道 finish;
(c) 机器合法性:被指派 RA 必须在可行集 Ω 内;
(b) 机器互斥:同一 RA 上区间 [start, finish) 两两不重叠;
(d) AGV 一致性:同车分段时间不重叠、路径空间连续、区间长度 = 走廊通行时间;
(e) 走廊互斥:同一物理走廊(双向合并)上时间窗 [enter, exit) 两两不重叠;
(f) 运输-工序衔接:载货段完成 <= 对应工序 start,起运 >= 前道 finish;
(g) C_max 一致性:等于全部工件末道(伪)工序完成时刻的最大值,**不含空载段**;
(h) 载货段不得晚于 C_max(空载归位段允许,见 (g) 的口径注释)。
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .instance import Instance
from .network import corridor_id

EPS = 1e-6
_TASK_RE = re.compile(r"^J(\d+)-(\d+)-(empty|loaded)$")


def validate(inst: Instance, timetable: dict) -> List[str]:
    """返回违反约束的描述列表;空列表表示时刻表可行。"""
    errors: List[str] = []
    ops = timetable.get("operations", [])
    segs = timetable.get("agv_segments", [])
    returns = timetable.get("returns", [])

    # ---- (a)(c) 工序先后、工时、机器合法性 ----
    by_job: Dict[int, List[dict]] = {}
    for o in ops:
        by_job.setdefault(o["job"], []).append(o)
    for j, lst in by_job.items():
        lst.sort(key=lambda x: x["i"])
        expected_is = list(range(1, inst.num_ops[j] + 1))
        if [o["i"] for o in lst] != expected_is:
            errors.append(f"(a) 工件 {j} 工序编号缺失或重复: {[o['i'] for o in lst]}")
            continue
        prev_finish = 0.0
        for o in lst:
            key = (j, o["i"])
            m = o["machine"]
            if m not in inst.proc_time[key]:
                errors.append(f"(c) 工序 {key} 指派到不可行 RA{m}")
                continue
            p = inst.proc_time[key][m]
            if abs(o["finish"] - o["start"] - p) > EPS:
                errors.append(f"(a) 工序 {key} 工时不符: {o['finish']}-{o['start']} != {p}")
            if o["start"] < prev_finish - EPS:
                errors.append(f"(a) 工序 {key} 早于前道完工开工: {o['start']} < {prev_finish}")
            prev_finish = o["finish"]

    # ---- (b) 机器互斥 ----
    by_machine: Dict[int, List[dict]] = {}
    for o in ops:
        by_machine.setdefault(o["machine"], []).append(o)
    for m, lst in by_machine.items():
        lst.sort(key=lambda x: x["start"])
        for a, b in zip(lst, lst[1:]):
            if b["start"] < a["finish"] - EPS:
                errors.append(f"(b) RA{m} 上工序重叠: ({a['job']},{a['i']}) 与 ({b['job']},{b['i']})")

    # ---- (d) AGV 分段:时间不重叠、空间连续、区间长度合法 ----
    adj: Dict[Tuple[str, str], float] = {}
    for c in inst.corridors:
        adj[(c["u"], c["v"])] = c["time"]
        adj[(c["v"], c["u"])] = c["time"]
    by_agv: Dict[int, List[dict]] = {}
    for s in segs:
        by_agv.setdefault(s["agv"], []).append(s)
    for k, lst in by_agv.items():
        lst.sort(key=lambda x: x["enter"])
        for s in lst:
            if (s["u"], s["v"]) not in adj:
                errors.append(f"(d) AGV{k} 使用不存在的走廊 {s['u']}->{s['v']}")
            elif abs(s["exit"] - s["enter"] - adj[(s["u"], s["v"])]) > EPS:
                errors.append(f"(d) AGV{k} 走廊 {s['u']}->{s['v']} 通行时间不符: "
                              f"{s['exit']}-{s['enter']} != {adj[(s['u'], s['v'])]}")
        for a, b in zip(lst, lst[1:]):
            if b["enter"] < a["exit"] - EPS:
                errors.append(f"(d) AGV{k} 分段时间重叠: {a['u']}->{a['v']} 与 {b['u']}->{b['v']}")
            if b["u"] != a["v"]:
                errors.append(f"(d) AGV{k} 路径不连续: ...->{a['v']} 后从 {b['u']} 出发")

    # ---- (e) 走廊互斥(双向合并,半开区间) ----
    by_corridor: Dict[str, List[dict]] = {}
    for s in segs:
        by_corridor.setdefault(corridor_id(s["u"], s["v"]), []).append(s)
    for cid, lst in by_corridor.items():
        lst.sort(key=lambda x: x["enter"])
        for a, b in zip(lst, lst[1:]):
            if a["agv"] != b["agv"] and b["enter"] < a["exit"] - EPS:
                errors.append(f"(e) 走廊 {cid} 时间窗冲突: AGV{a['agv']}[{a['enter']},{a['exit']}) "
                              f"与 AGV{b['agv']}[{b['enter']},{b['exit']})")

    # ---- (f) 运输-工序衔接(按任务命名 J{j}-{i}-loaded 交叉核对) ----
    op_index = {(o["job"], o["i"]): o for o in ops}
    loaded_span: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for s in segs:
        mt = _TASK_RE.match(s.get("task", ""))
        if mt and mt.group(3) == "loaded":
            key = (int(mt.group(1)), int(mt.group(2)))
            lo, hi = loaded_span.get(key, (float("inf"), float("-inf")))
            loaded_span[key] = (min(lo, s["enter"]), max(hi, s["exit"]))
    for (j, i), (lo, hi) in loaded_span.items():
        if (j, i) in op_index:
            o = op_index[(j, i)]
            if hi > o["start"] + EPS:
                errors.append(f"(f) 工序 ({j},{i}) 在送达前开工: 送达 {hi} > start {o['start']}")
        if i >= 2 and (j, i - 1) in op_index:
            prev = op_index[(j, i - 1)]
            if lo < prev["finish"] - EPS:
                errors.append(f"(f) 工件 {j} 第 {i} 段起运早于前道完工: {lo} < {prev['finish']}")

    # ---- (g) C_max 一致性 ----
    # 口径(建模文档 E1 / 规格假设 8):全部工件末道(伪)工序完成时刻的最大值,
    # **不含任何空载段**。空载归位段允许晚于 C_max(车队收尾不属于工件完工),
    # 故此处不并入 agv_segments;越界检查改由下面 (h) 独立承担。
    events = [o["finish"] for o in ops] + [r["complete"] for r in returns]
    expected = max(events) if events else 0.0
    if abs(timetable.get("makespan", -1) - expected) > EPS:
        errors.append(f"(g) C_max 不一致: 报告 {timetable.get('makespan')} != 事件最大值 {expected}")

    # ---- (h) 载货段不得晚于 C_max ----
    # 载货段晚于 C_max 意味着某件工件在"报告完工"之后还在被搬运,属真实错误;
    # 这条与 (g) 分离,使 C_max 口径的收敛不会丢掉原先的越界防御。
    for s in segs:
        mt = _TASK_RE.match(s.get("task", ""))
        if mt and mt.group(3) == "loaded" and s["exit"] > expected + EPS:
            errors.append(f"(h) 载货段晚于 C_max: 任务 {s['task']} 于 {s['exit']} 结束 > {expected}")

    return errors
