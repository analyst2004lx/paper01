"""按 clbs_new 的布局规则与节点模型重新生成 STRC 实验用算例。

旧算例(clbs/input)把毛坯库与成品库合在一个装卸站 v0,节点无容量。新算例统一为:
毛坯库 v0、成品库 w0 分设两端;机器挂在路口的支线上(机器节点是叶子);
节点模型取 paper01 的设定:路口容量 1,机器节点容量 c=2,净空时距 h=0.5,库区不限。

两个手工算例按上述规则重画,规模、加工时间与走廊时长尽量保持原样:
  example_3x3x2   去掉 r1-c2(机器不再作中转),在 c2 外挂成品库 w0;
  congested_8x4x4 去掉机器间的 r1-r2、r3-r4,在 c2 外挂成品库 w0。
生成器算例(S11/S21/S22、Lyu L2--L6、规模阶梯)沿用旧参数与旧文件名。

Regenerate the STRC instances under the clbs_new layout rules and node model.

    py -m tools.gen_instances
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from algorithm.clbs_bridge import (  # noqa: E402
    CLBS_INPUT,
    _generator,
    build_instance,
    make_pub_spec,
    make_spec,
)

OLD_INPUT = os.path.join(os.path.dirname(ROOT), "clbs", "input")
NODE_MODEL = {"machine_capacity": 2, "headway": 0.5}

HAND_LAYOUTS = {
    "example_3x3x2": {
        "nodes": ["v0", "c1", "c2", "r1", "r2", "r3", "w0"],
        "corridors": [
            {"u": "v0", "v": "c1", "time": 2},
            {"u": "c1", "v": "r1", "time": 2},
            {"u": "c1", "v": "c2", "time": 3},
            {"u": "c2", "v": "r2", "time": 2},
            {"u": "c2", "v": "r3", "time": 2},
            {"u": "c2", "v": "w0", "time": 2},
        ],
    },
    "congested_8x4x4": {
        "nodes": ["v0", "c1", "c2", "r1", "r2", "r3", "r4", "w0"],
        "corridors": [
            {"u": "v0", "v": "c1", "time": 2},
            {"u": "c1", "v": "r1", "time": 2},
            {"u": "c1", "v": "r2", "time": 3},
            {"u": "c1", "v": "c2", "time": 6},
            {"u": "c2", "v": "r3", "time": 2},
            {"u": "c2", "v": "r4", "time": 3},
            {"u": "c2", "v": "w0", "time": 2},
        ],
    },
}


def _write(data: dict, sub: str = "") -> str:
    folder = os.path.join(CLBS_INPUT, sub) if sub else CLBS_INPUT
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, data["name"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def hand_instance(name: str) -> dict:
    with open(os.path.join(OLD_INPUT, name + ".json"), encoding="utf-8") as f:
        old = json.load(f)
    data = copy.deepcopy(old)
    lay = HAND_LAYOUTS[name]
    data["network"] = {
        "lu_node": "v0",
        "out_node": "w0",
        "nodes": list(lay["nodes"]),
        "corridors": [dict(c) for c in lay["corridors"]],
        "node_model": dict(NODE_MODEL),
    }
    _generator.measure(data)
    return data


def generator_instances():
    out = []
    for tag in ("funnel", "high", "mid"):
        out.append(("ext", build_instance(make_spec(tag, 0.3, 0.6, 8, 4, 4, 3, 42))))
    for k in range(4, 11):
        if k == 4:
            continue
        out.append(("ext", build_instance(make_spec("mid", 0.3, 0.6, 2 * k, k, k, 3, 42))))
    for key in ("LyuL2", "LyuL3", "LyuL4", "LyuL5", "LyuL6"):
        out.append(("pub", build_instance(make_pub_spec(key, 0.3, 0.6, 8, 4, 3, 42))))
    return out


def main() -> None:
    for name in HAND_LAYOUTS:
        print("wrote", _write(hand_instance(name)))
    for sub, data in generator_instances():
        print("wrote", _write(data, sub))


if __name__ == "__main__":
    main()
