"""把 paper04 用到的公开数据集与算例同步到 STRC/database/,并记 SHA256。

用法(在 STRC/ 下):
    py -m tools.sync_database            # 同步(覆盖本地副本)并重写 MANIFEST.csv
    py -m tools.sync_database --check    # 只校验:本地副本是否与 clbs 源逐字节相同

为什么要有本地副本。paper04 的算法代码在 STRC/ 下,而它依赖的公开数据原先只存在
`clbs/database/`。数据与用它的代码分居两处,归档、打包、投稿附件都要跨目录去捞,
而且看 STRC 的人不会知道数据在哪。故在此存一份副本。

**副本的风险是变成第二个真值来源**,所以这个脚本存在:副本一律由它生成而不手工拷,
`--check` 能查出漂移(逐字节比对 + 比对 MANIFEST 里记的 SHA256)。真值仍在
`clbs/database/`——那里有原始下载链接与完整的来源清单;本地副本只是它的镜像。

同步的是两类东西:
  raw/        公开发布件的原样副本(Lyu 与 Liu 的布局编码 + 决定其语义的解析源码)
  instances/  外部布局批次的全部输入算例,含 5 个外部布局算例与 3 个同参数自建对照
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
CLBS = os.path.join(REPO, "clbs")
DEST = os.path.join(ROOT, "database")

_TOOLSET = os.path.join(CLBS, "database", "raw", "tjsp_toolset")
_BENCH = os.path.join(_TOOLSET, "data", "benchmarks")

# 外部布局批次的输入算例。前五个由 clbs/tools/gen_pub_layouts.py 生成,后三个是
# 同参数自建对照(与外部组逐参数同口径,只差布局来源)——两组必须一起归档,
# 否则"外部布局的闭包占比离散度更大"这句话在本目录里就没有可比的基线。
_INSTANCES = [
    ("pub", os.path.join(CLBS, "input", "pub"),
     ["S8x4x4-LyuL2-H0.3-F0.6-A4-s42.json",
      "S8x5x4-LyuL3-H0.3-F0.6-A4-s42.json",
      "S8x6x4-LyuL4-H0.3-F0.6-A4-s42.json",
      "S8x7x4-LyuL5-H0.3-F0.6-A4-s42.json",
      "S8x8x4-LyuL6-H0.3-F0.6-A4-s42.json"]),
    ("self_built_control", os.path.join(CLBS, "input", "ext"),
     ["S8x4x4-LD21-H0.3-F0.6-A4-s42.json",
      "S8x4x4-LD11-H0.3-F0.6-A4-s42.json",
      "S8x4x4-LD22-H0.3-F0.6-A4-s42.json"]),
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="同步公开数据集副本到 STRC/database/")
    ap.add_argument("--check", action="store_true",
                    help="只校验副本与 clbs 源是否一致,不写任何文件")
    return ap.parse_args()


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _plan():
    """产出 (本地相对路径, clbs 源绝对路径, role, note) 四元组。"""
    plan = []
    for fam, used in (("lyu2019", True), ("liu2023", False)):
        base = os.path.join(_BENCH, fam, "layouts")
        if not os.path.isdir(base):
            continue
        for sub in sorted(os.listdir(base)):
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".data"):
                    continue
                note = ("已用:拓扑三项转录进 PUB_LAYOUTS" if used
                        else "已排除:首行带 d 后缀即允许对角移动,本项目走廊为四邻接")
                plan.append((os.path.join("raw", fam, "layouts", sub, fn),
                             os.path.join(d, fn), "layout_source", note))
    parser = os.path.join(_TOOLSET, "library", "model_data.py")
    if os.path.isfile(parser):
        plan.append((os.path.join("raw", "library", "model_data.py"), parser,
                     "parser_reference",
                     "布局文件三行的语义(节点序[0]=装货站、单位边权、缺边双向删除)"
                     "由此文件确定,而非由布局文件自述,故必须一并归档"))
    for role, src_dir, names in _INSTANCES:
        for fn in names:
            plan.append((os.path.join("instances", fn),
                         os.path.join(src_dir, fn), role,
                         "外部布局批次输入(py -m tools.pub_batch)"))
    return plan


def main() -> int:
    args = parse_args()
    plan = _plan()
    missing = [s for _, s, _, _ in plan if not os.path.isfile(s)]
    if missing:
        print("clbs 源缺文件,先在 clbs/ 下跑 py -m tools.gen_pub_layouts:")
        for m in missing:
            print(f"  {m}")
        return 2

    rows, drift = [], []
    for rel, src, role, note in plan:
        dst = os.path.join(DEST, rel)
        if args.check:
            if not os.path.isfile(dst):
                drift.append(f"{rel}: 本地副本缺失")
                continue
            if sha256(dst) != sha256(src):
                drift.append(f"{rel}: 与 clbs 源不一致")
                continue
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        rows.append({
            "relpath": rel.replace(os.sep, "/"),
            "role": role,
            "clbs_source": os.path.relpath(src, REPO).replace(os.sep, "/"),
            "bytes": os.path.getsize(src),
            "sha256": sha256(src),
            "note": note,
        })

    man = os.path.join(DEST, "MANIFEST.csv")
    if args.check:
        if os.path.isfile(man):
            with open(man, encoding="utf-8") as f:
                recorded = {r["relpath"]: r["sha256"] for r in csv.DictReader(f)}
            for r in rows:
                if recorded.get(r["relpath"]) != r["sha256"]:
                    drift.append(f"{r['relpath']}: MANIFEST 记的 SHA256 不匹配")
        else:
            drift.append("MANIFEST.csv 缺失")
        if drift:
            print(f"校验失败 {len(drift)} 项:")
            for d in drift:
                print(f"  - {d}")
            print("\n跑 py -m tools.sync_database 重新同步。")
            return 1
        print(f"校验通过:{len(rows)} 个文件与 clbs 源逐字节相同,"
              f"且与 MANIFEST 记录一致。")
        return 0

    os.makedirs(DEST, exist_ok=True)
    with open(man, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["relpath", "role", "clbs_source",
                                          "bytes", "sha256", "note"])
        w.writeheader()
        w.writerows(rows)

    by_role = {}
    for r in rows:
        by_role[r["role"]] = by_role.get(r["role"], 0) + 1
    print(f"已同步 {len(rows)} 个文件到 {os.path.relpath(DEST, ROOT)}{os.sep}")
    for role in sorted(by_role):
        print(f"  {role:20s} {by_role[role]}")
    print(f"清单写入 {os.path.relpath(man, ROOT)}")
    print("真值仍在 clbs/database/(那里有原始下载链接);"
          "本目录是镜像,用 --check 查漂移。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
