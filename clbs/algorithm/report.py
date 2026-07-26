"""结果报告:文本甘特图与汇总(规格文档 3.3)。"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .instance import Instance

_TASK_RE = re.compile(r"^J(\d+)-(\d+)-(empty|loaded)$")
MAX_GANTT_WIDTH = 300


def _job_char(j: int) -> str:
    """工件 1..n 映射为 A..Z / a..z。"""
    if j <= 26:
        return chr(ord("A") + j - 1)
    return chr(ord("a") + (j - 27) % 26)


def gantt_text(inst: Instance, timetable: dict) -> Optional[str]:
    """整数时间粒度的文本甘特图;时间跨度过大时返回 None。"""
    width = int(round(timetable["makespan"]))
    if width <= 0 or width > MAX_GANTT_WIDTH:
        return None

    lines: List[str] = []
    ruler = "".join("|" if t % 10 == 0 else ("+" if t % 5 == 0 else "-")
                    for t in range(width))
    label_w = 6
    lines.append(" " * label_w + ruler)
    lines.append(" " * label_w + "".join(
        f"{t:<10d}" for t in range(0, width, 10))[:width])

    # ---- 机器行 ----
    by_machine: Dict[int, List[dict]] = {}
    for o in timetable["operations"]:
        by_machine.setdefault(o["machine"], []).append(o)
    for m in sorted(inst.machine_node):
        row = ["·"] * width
        for o in by_machine.get(m, []):
            ch = _job_char(o["job"])
            for t in range(int(round(o["start"])), min(int(round(o["finish"])), width)):
                row[t] = ch
        lines.append(f"RA{m:<4d}" + "".join(row))

    # ---- AGV 行:大写=载货,e=空驶,w=途中等待 ----
    by_agv: Dict[int, List[dict]] = {}
    for s in timetable["agv_segments"]:
        by_agv.setdefault(s["agv"], []).append(s)
    for k in sorted(by_agv):
        row = ["·"] * width
        segs = sorted(by_agv[k], key=lambda x: x["enter"])
        for idx, s in enumerate(segs):
            mt = _TASK_RE.match(s.get("task", ""))
            if mt and mt.group(3) == "loaded":
                ch = _job_char(int(mt.group(1)))
            else:
                ch = "e"
            for t in range(int(round(s["enter"])), min(int(round(s["exit"])), width)):
                row[t] = ch
            # 同一任务相邻分段间的间隙 = 途中等待
            if idx + 1 < len(segs) and segs[idx + 1].get("task") == s.get("task"):
                for t in range(int(round(s["exit"])),
                               min(int(round(segs[idx + 1]["enter"])), width)):
                    row[t] = "w"
        lines.append(f"AGV{k:<3d}" + "".join(row))

    lines.append("")
    lines.append("图例: 大写字母=对应工件加工/载运, e=空驶, w=途中等待, ·=空闲")
    return "\n".join(lines)


def summary_line(name: str, res: dict) -> str:
    extra = ""
    if "stage1_makespan" in res:
        extra = f"(阶段一理想值 {res['stage1_makespan']:.1f})"
    gen = f", {res['generations']} 代" if "generations" in res else ""
    return (f"  {name:<14s} C_max = {res['makespan']:>8.1f} {extra}"
            f"  [{res.get('runtime_sec', 0):.1f}s{gen}]")
