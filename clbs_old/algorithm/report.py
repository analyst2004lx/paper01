"""结果报告:文本甘特图、走廊占用率画像与汇总(规格文档 3.3)。"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .instance import Instance
from .network import corridor_id

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


def corridor_occupancy(timetable: dict, bucket_width: float) -> Dict[Tuple[str, int], float]:
    """走廊-时段占用率 util[(c,b)] = 桶内被占用时长 / 桶宽,由**时刻表独立重算**。

    与 ReservationTable.occupancy 语义相同,但不复用解码器/预约表的内部状态,
    而是从落盘的 agv_segments 反推——与校验器同一套哲学(独立重算才能当证据)。
    因此它对所有模式一致可用,包括 twostage / rule 这类不经 GA 的档。
    """
    util: Dict[Tuple[str, int], float] = {}
    if bucket_width <= 0:
        return util
    for s in timetable.get("agv_segments", []):
        cid = corridor_id(s["u"], s["v"])
        ts, te = float(s["enter"]), float(s["exit"])
        b = int(ts // bucket_width)
        while b * bucket_width < te:
            lo, hi = b * bucket_width, (b + 1) * bucket_width
            overlap = min(te, hi) - max(ts, lo)
            if overlap > 0:
                util[(cid, b)] = util.get((cid, b), 0.0) + overlap / bucket_width
            b += 1
    return util


def occupancy_profile(timetable: dict, bucket_width: float,
                      top_k: int = 8) -> Optional[dict]:
    """占用率画像:按走廊汇总的平均/峰值占用,以及最忙的若干走廊-时段。

    用途是**报告**而非驱动搜索(规格 5.2 中前瞻性信号的使用边界):
    用于实证"某条走廊是否真的是瓶颈",支撑算例设计主张与定性分析。
    """
    util = corridor_occupancy(timetable, bucket_width)
    if not util:
        return None
    span = max(1, int(timetable.get("makespan", 0) // bucket_width) + 1)

    per_corridor: Dict[str, List[float]] = {}
    for (cid, _b), v in util.items():
        per_corridor.setdefault(cid, []).append(v)
    by_corridor = {
        cid: {"mean": round(sum(vs) / span, 4),      # 按整个计划期取平均,非仅按有占用的桶
              "peak": round(max(vs), 4),
              "busy_buckets": len(vs)}
        for cid, vs in per_corridor.items()
    }
    ranked = sorted(by_corridor.items(), key=lambda kv: -kv[1]["mean"])
    hottest = sorted(util.items(), key=lambda kv: -kv[1])[:top_k]
    return {
        "bucket_width": round(bucket_width, 4),
        "num_buckets": span,
        "bottleneck_corridor": ranked[0][0] if ranked else None,
        "by_corridor": dict(ranked),
        "hottest_slots": [{"corridor": cid, "bucket": b,
                           "t_from": round(b * bucket_width, 2),
                           "t_to": round((b + 1) * bucket_width, 2),
                           "util": round(v, 4)}
                          for (cid, b), v in hottest],
    }


def summary_line(name: str, res: dict) -> str:
    extra = ""
    if "stage1_makespan" in res:
        extra = f"(阶段一理想值 {res['stage1_makespan']:.1f})"
    gen = f", {res['generations']} 代" if "generations" in res else ""
    return (f"  {name:<14s} C_max = {res['makespan']:>8.1f} {extra}"
            f"  [{res.get('runtime_sec', 0):.1f}s{gen}]")
