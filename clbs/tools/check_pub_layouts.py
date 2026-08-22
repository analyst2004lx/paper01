"""把 PUB_LAYOUTS 与工具集原始 `.data` 文件逐项对账。

用法(clbs/ 目录下):
    py -m tools.check_pub_layouts

为什么需要这个脚本。`algorithm.generator.PUB_LAYOUTS` 里的网格尺寸、装卸站与机器
落位、缺边三项是手工转录进来的,而"逐项忠实于公开文件"这句话是论文里的一条事实
主张。手工转录 + 口头声称不构成证据,所以这里改由程序重读
`database/raw/tjsp_toolset/data/benchmarks/lyu2019/layouts/*.data`,把三项与预设
逐字段比对,并顺带核对生成的算例路网(节点数、走廊数、缺边确实不在走廊表里)。

原始格式(见工具集 `library/model_data.py` 的 `__read_CFTFJSSP`):
    第 1 行  `<rows>x<cols>`,带 `d` 后缀表示允许对角移动
    第 2 行  [装货站, m1..mk, 卸货站] 的行主序 1 基网格节点号
    第 3 行  被拆掉的边,形如 `(8 13) (19 20)`;可缺省
节点号与坐标的换算为 `to_node(r,c) = (r-1)*rows + c`;六张布局都是方阵,故与本项目
的 `(r-1)*cols + c` 等价。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.generator import PUB_LAYOUTS

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "database", "raw", "tjsp_toolset",
                   "data", "benchmarks", "lyu2019", "layouts")
PUB_INPUT = os.path.join(HERE, "..", "input", "pub")

# 预设键 -> 原始文件相对路径。目录名里的机器台数含两个站点,故 `3machines` 实际是
# 1 个装货站 + 3 台机器 + 1 个卸货站 = 5 个节点号。
SOURCES = {
    "LyuL1": os.path.join("3machines", "1.data"),
    "LyuL2": os.path.join("4machines", "2.data"),
    "LyuL3": os.path.join("5machines", "3.data"),
    "LyuL4": os.path.join("6machines", "4.data"),
    "LyuL5": os.path.join("7machines", "5.data"),
    "LyuL6": os.path.join("8machines", "6.data"),
}


def parse_layout(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        lines = [ln.strip() for ln in fp.readlines()]
    lines = [ln for ln in lines if ln]
    dims = lines[0].split("x")
    rows = int(dims[0])
    diagonal = "d" in dims[1]
    cols = int(dims[1].replace("d", ""))
    locs = [int(v) for v in lines[1].split()]
    removed = []
    if len(lines) > 2:
        toks = [int(v.strip("()")) for v in lines[2].split()]
        removed = [[toks[i], toks[i + 1]] for i in range(0, len(toks), 2)]
    return {"grid_rows": rows, "grid_cols": cols, "diagonal": diagonal,
            "lu": locs[0], "machines": locs[1:-1], "unload": locs[-1],
            "removed": removed}


def main() -> int:
    fails = []
    print(f"{'布局':7s} {'网格':5s} {'装货':4s} {'机器落位':26s} "
          f"{'卸货':4s} {'缺边':16s} 对账")
    print("-" * 78)
    for key, rel in SOURCES.items():
        path = os.path.join(RAW, rel)
        if not os.path.isfile(path):
            fails.append(f"{key}: 原始文件缺失 {path}")
            continue
        src = parse_layout(path)
        pre = PUB_LAYOUTS[key]

        diffs = []
        for field, got, want in (
            ("grid_rows", pre["grid_rows"], src["grid_rows"]),
            ("grid_cols", pre["grid_cols"], src["grid_cols"]),
            ("grid_lu_node", pre["grid_lu_node"], src["lu"]),
            ("grid_machine_nodes", list(pre["grid_machine_nodes"]), src["machines"]),
            ("grid_removed_edges",
             [list(e) for e in pre["grid_removed_edges"]], src["removed"]),
        ):
            if got != want:
                diffs.append(f"{field}: 预设 {got} vs 原文件 {want}")
        if src["diagonal"]:
            diffs.append("原文件允许对角移动,本项目走廊为四邻接")
        # 卸货站必须既不是装卸点也不是机器点(本项目把它退化为普通节点)
        if src["unload"] in [pre["grid_lu_node"]] + list(pre["grid_machine_nodes"]):
            diffs.append(f"卸货站 {src['unload']} 与装卸点/机器点重合")

        mark = "OK" if not diffs else "FAIL"
        if diffs:
            fails.extend(f"{key}: {d}" for d in diffs)
        print(f"{key:7s} {src['grid_rows']}x{src['grid_cols']:<3d} "
              f"{src['lu']:<4d} {str(src['machines']):26s} "
              f"{src['unload']:<4d} {str(src['removed']):16s} {mark}")

    # 再核生成的算例:走廊数应为 2*R*C-R-C 减去缺边数,且缺边不在走廊表里
    print()
    for name in sorted(os.listdir(PUB_INPUT)) if os.path.isdir(PUB_INPUT) else []:
        if not name.endswith(".json"):
            continue
        with open(os.path.join(PUB_INPUT, name), "r", encoding="utf-8") as fp:
            data = json.load(fp)
        spec, net = data["_spec"], data["network"]
        r, c = spec["grid_rows"], spec["grid_cols"]
        removed = [tuple(e) for e in spec["grid_removed_edges"]]
        expect = 2 * r * c - r - c - len(removed)
        pairs = {frozenset((cd["u"], cd["v"])) for cd in net["corridors"]}
        bad = [e for e in removed if frozenset((f"g{e[0]}", f"g{e[1]}")) in pairs]
        ok = (len(net["nodes"]) == r * c and len(net["corridors"]) == expect
              and not bad and net["lu_node"] == f"g{spec['grid_lu_node']}")
        if not ok:
            fails.append(f"{name}: 路网与规格不符("
                         f"节点 {len(net['nodes'])}/{r * c}、"
                         f"走廊 {len(net['corridors'])}/{expect}、"
                         f"未删除的缺边 {bad})")
        print(f"{name:34s} 节点 {len(net['nodes']):3d}  走廊 "
              f"{len(net['corridors']):3d}/{expect:<3d} 缺边已删 "
              f"{'是' if not bad else '否'}  {'OK' if ok else 'FAIL'}")

    print()
    if fails:
        print(f"对账失败 {len(fails)} 项:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("全部对账通过:六张布局的三项与原始文件逐字段相同,"
          "生成算例的路网与规格一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
