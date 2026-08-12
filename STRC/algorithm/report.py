"""STRC 运行摘要与闭包规模画像。"""
from __future__ import annotations

import json
import os
from typing import Any


def summary_line(record: dict) -> str:
    return (
        f"{record.get('arm', '?'):4s}  "
        f"feas={record.get('feasible')}  "
        f"|closure|={record.get('closure_size', '-')}  "
        f"Cmax={record.get('makespan', '-')}  "
        f"RΔ={record.get('reservation_delta', '-')}  "
        f"{record.get('wall_ms', 0):.1f}ms"
    )


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
