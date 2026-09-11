"""评测存档:逐次延迟、良性告警间隔、注入率扫描共用一份 JSON。

箱线图只读 `detected_delays`,不得把未检出填进分位;ARL0 只读纯良性流的
`benign_gaps`。图脚本不得再手写中位 / p90。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(ROOT, "output")

E1_PATH = os.path.join(OUTPUT, "e1_archive.json")
E4_PATH = os.path.join(OUTPUT, "e4_delay_archive.json")
WALK_PATH = os.path.join(OUTPUT, "alarm_walkthrough.json")
E8_PATH = os.path.join(OUTPUT, "e8_latency.json")
ROBUST_PATH = os.path.join(OUTPUT, "robust_archive.json")
E5_PATH = os.path.join(OUTPUT, "e5_sigma_archive.json")
E6_PATH = os.path.join(OUTPUT, "e6_transfer.json")


def dump(path: str, payload: dict) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = dict(payload)
    payload.setdefault("written_at", datetime.now(timezone.utc).isoformat())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def require(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"缺少评测存档 {path}。先在 paper02/slid 下跑对应诊断脚本。")
    return load(path)
