"""公开 FJSPT 基准 → 本项目 3.1 节 JSON schema 的格式转换器(规格 12.4 第 2 项)。

用法(在 clbs/ 目录下):

    py -m tools.convert_public --check          # 只做保真度体检,不落盘
    py -m tools.convert_public                  # 转换 hf 全部 20 个算例 -> database/json/hf/
    py -m tools.convert_public --out <dir>

输入是 `database/extracted/hf/` 下的**文本**,由下面这条命令从只读 PDF 生成一次:

    pdftotext -raw -enc UTF-8 database/raw/homayouni_fontes_2020/<f>.pdf \
              database/extracted/hf/<f>.txt

之所以把提取与转换切成两步,是因为提取需要外部二进制(poppler 的 pdftotext),
而转换必须纯标准库可跑。切开之后,转换器在任何装了 Python 的机器上都能复现,
提取物则连同 SHA256 记进 MANIFEST。

**提取错误不会静默通过**:每个算例头自带 `M*J*O` 三个声明值,解析器逐个核对
机器数、工件数、工序数、先后关系条数(= O - J),不符即报错退出。少一行、
串一行、数字粘连都会被这四个约束之一抓住。

口径(与文献一致,见 database/README.md):
- `delta_return = 0`:成品不回运,makespan = 末道工序完工。已用 SFJST01 核对——
  文献最优值 70 = LU→m1 行程 4 + 45 + 21,正是不含回运的工件链;
- `num_agvs = 2`:HF/Kumar/Deroussi 这几族公开算例统一为两辆车(Lim & Moon 2023
  §4:"All test instances involve two transporters");
- 布局按机器数选取:M 台机的算例用 `<M>-M` 布局矩阵。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "database")

NUM_AGVS = 2
DELTA_RETURN = 0
LU = "LU"

_HEADER_RE = re.compile(r"^([a-z]+\d+)\s+(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)")


# --------------------------------------------------------------------------
# 解析:工件集
# --------------------------------------------------------------------------

class JobSet:
    """一个公开算例的工件数据(机器标号沿用原文的 0 基)。"""

    def __init__(self, name: str, num_machines: int, num_jobs: int,
                 num_ops: int, precedence: List[Tuple[int, int]],
                 ops: List[Dict[int, float]]):
        self.name = name
        self.num_machines = num_machines
        self.num_jobs = num_jobs
        self.num_ops = num_ops
        self.precedence = precedence
        self.ops = ops                      # 全局工序号 -> {机器: 工时}
        self.chains = _chains_from_precedence(num_ops, precedence)

    def check(self) -> None:
        """把算例头的声明值当作独立校验源,核对解析结果(见模块 docstring)。"""
        if len(self.ops) != self.num_ops:
            raise ValueError(f"{self.name}: 声明 {self.num_ops} 道工序,解析到 {len(self.ops)}")
        want_arcs = self.num_ops - self.num_jobs
        if len(self.precedence) != want_arcs:
            raise ValueError(f"{self.name}: 声明 O-J={want_arcs} 条先后关系,"
                             f"解析到 {len(self.precedence)}")
        if len(self.chains) != self.num_jobs:
            raise ValueError(f"{self.name}: 声明 {self.num_jobs} 个工件,"
                             f"先后关系图给出 {len(self.chains)} 条链")
        used = {m for row in self.ops for m in row}
        if used and max(used) >= self.num_machines:
            raise ValueError(f"{self.name}: 声明 {self.num_machines} 台机,"
                             f"出现机器标号 {max(used)}")
        for idx, row in enumerate(self.ops):
            if not row:
                raise ValueError(f"{self.name}: 工序 {idx} 的可用机器集为空")


def _chains_from_precedence(num_ops: int,
                            precedence: Sequence[Tuple[int, int]]) -> List[List[int]]:
    """把先后关系还原成每个工件的工序链。

    原格式只给"U 必须先于 V"的两两关系,不显式说哪些工序属于同一个工件。各工件
    在这批数据里都是简单链(每个工序至多一个前驱、至多一个后继),故按链首出发
    顺着后继走一遍即可;链的条数必须等于声明的工件数,由 `check` 断言。
    """
    succ: Dict[int, int] = {}
    pred: Dict[int, int] = {}
    for u, v in precedence:
        if u in succ or v in pred:
            raise ValueError(f"工序 {u}->{v} 使先后关系不再是简单链(出现分叉)")
        succ[u] = v
        pred[v] = u
    chains: List[List[int]] = []
    for head in range(num_ops):
        if head in pred:
            continue
        chain, cur = [head], head
        while cur in succ:
            cur = succ[cur]
            chain.append(cur)
        chains.append(chain)
    return chains


def parse_jobsets(text: str) -> List[JobSet]:
    """解析 HF 工件集文本。返回顺序即文件中的出现顺序。"""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("--")]

    starts = []
    for i, ln in enumerate(lines):
        m = _HEADER_RE.match(ln)
        if m:
            starts.append((i, m))
    if not starts:
        raise ValueError("未找到任何算例头(形如 'sfjs01 2*2*4')")

    out: List[JobSet] = []
    for pos, (idx, m) in enumerate(starts):
        name = m.group(1)
        nm, nj, no = int(m.group(2)), int(m.group(3)), int(m.group(4))
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = [ln for ln in lines[idx + 1:end]]

        n_arcs = no - nj
        prec: List[Tuple[int, int]] = []
        for ln in body[:n_arcs]:
            parts = ln.split()
            if len(parts) != 2:
                raise ValueError(f"{name}: 先后关系行应为两个整数,得到 {ln!r}")
            prec.append((int(parts[0]), int(parts[1])))

        ops: List[Dict[int, float]] = []
        for ln in body[n_arcs:]:
            parts = [int(x) for x in ln.split()]
            k, rest = parts[0], parts[1:]
            if len(rest) != 2 * k:
                raise ValueError(f"{name}: 工序行声明 {k} 台备选机,"
                                 f"但后接 {len(rest)} 个数字: {ln!r}")
            ops.append({rest[2 * z]: float(rest[2 * z + 1]) for z in range(k)})

        js = JobSet(name, nm, nj, no, prec, ops)
        js.check()
        out.append(js)
    return out


# --------------------------------------------------------------------------
# 解析:布局矩阵
# --------------------------------------------------------------------------

def parse_layouts(text: str) -> Dict[int, List[List[float]]]:
    """解析行驶时间矩阵文本,返回 {机器数: 矩阵}。

    矩阵第 0 行/列为 LU,其后为机器 1..M(原文的 1 基标号)。行 = 出发地,
    列 = 目的地;矩阵**有向**(往返不等),这一点必须保留,见 network.Network 的
    docstring。
    """
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("--")]

    out: Dict[int, List[List[float]]] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^(\d+)-M\s+LU\s+(.+)$", lines[i])
        if not m:
            i += 1
            continue
        nm = int(m.group(1))
        cols = m.group(2).split()
        if [int(c) for c in cols] != list(range(1, nm + 1)):
            raise ValueError(f"{nm}-M 表头列标号异常: {cols}")
        rows: List[List[float]] = []
        for r, label in enumerate(["LU"] + [str(k) for k in range(1, nm + 1)]):
            ln = lines[i + 1 + r].split()
            if ln[0] != label:
                raise ValueError(f"{nm}-M 第 {r} 行标号应为 {label},得到 {ln[0]}")
            vals = [float(x) for x in ln[1:]]
            if len(vals) != nm + 1:
                raise ValueError(f"{nm}-M 第 {r} 行应有 {nm+1} 个数,得到 {len(vals)}")
            if abs(vals[r]) > 1e-9:
                raise ValueError(f"{nm}-M 第 {r} 行对角元非零: {vals[r]}")
            rows.append(vals)
        out[nm] = rows
        i += nm + 2
    return out


# --------------------------------------------------------------------------
# 保真度体检:矩阵是不是某张图的最短路闭包?
# --------------------------------------------------------------------------

def closure_violations(matrix: List[List[float]]
                       ) -> List[Tuple[int, int, int, float, float]]:
    """三角不等式的违反项 (a, b, c, 直达, 绕行) —— 满足 d[a][c] > d[a][b] + d[b][c]。

    为什么这是**是否可还原为走廊图**的判据:任何图的全对最短路矩阵必然满足三角
    不等式(否则那条绕行路径本身就是更短路)。所以只要存在违反项,这张矩阵就
    **不是任何图的最短路闭包**;强行为它造一张走廊图,得到的算例在这些位置对上
    比原算例更快,即换了一个更容易的算例。反之若无违反项,矩阵自身就是一张
    (完全有向图的)合法闭包,可以无损承载。
    """
    n = len(matrix)
    bad: List[Tuple[int, int, int, float, float]] = []
    for a in range(n):
        for b in range(n):
            if b == a:
                continue
            for c in range(n):
                if c in (a, b):
                    continue
                direct, detour = matrix[a][c], matrix[a][b] + matrix[b][c]
                if direct > detour + 1e-9:
                    bad.append((a, b, c, direct, detour))
    return bad


def is_symmetric(matrix: List[List[float]]) -> bool:
    n = len(matrix)
    return all(abs(matrix[a][b] - matrix[b][a]) < 1e-9
               for a in range(n) for b in range(n))


def fidelity_report(layouts: Dict[int, List[List[float]]],
                    label_fmt: str = "{}-M") -> List[dict]:
    """逐布局出一行体检结果。**两个"可还原"列必须分开看**,合看会得出相反的结论。

    `digraph_reconstructible` 只查三角不等式,即"能否还原为某张\u200b有向\u200b图的最短路
    闭包";`corridor_reconstructible` 还要求对称,即"能否还原为\u200b本项目\u200b的无向走廊
    网络"——后者才是能否跑争用档的判据,因为 `Instance.corridors` 是无向的、每条走廊只有
    一个 `time`,由它算出的 t* 必然对称。HF 的 7 个布局里有 5 个前者为真、但\u200b后者无一为真\u200b;
    只看前一列会误以为那 5 个可以拿去跑争用档。

    `label_fmt` 决定 `layout` 列怎么写。默认 `"{}-M"` 是 hf 的口径——那一族的布局**按机器数
    索引**,故 `3-M` 意为"3 台机的布局"。别的数据集若按序号索引布局(如 bu 的 4 个布局都是
    4 台机),必须改这个格式,否则 `1-M` 会被读成"1 台机",与事实相反。
    """
    rows = []
    for nm in sorted(layouts):
        mat = layouts[nm]
        bad = closure_violations(mat)
        worst = max((d - t for _a, _b, _c, d, t in bad), default=0.0)
        sym = is_symmetric(mat)
        rows.append({
            "layout": label_fmt.format(nm),
            "size": len(mat),
            "symmetric": sym,
            "closure_violations": len(bad),
            "max_excess": round(worst, 4),
            "digraph_reconstructible": not bad,
            "corridor_reconstructible": sym and not bad,
        })
    return rows


# --------------------------------------------------------------------------
# 生成算例 JSON
# --------------------------------------------------------------------------

def machine_node(m1: int) -> str:
    return f"m{m1}"


def build_instance(js: JobSet, matrix: List[List[float]], src: dict) -> dict:
    """产出 3.1 节 schema 的算例 dict(退化对标版,后缀 -ideal)。

    机器标号:原文 0 基 -> 本项目 1 基(m+1),节点名 `m{1..M}`;矩阵索引 0 为 LU、
    k 为机器 k,故本项目机器 id 与矩阵索引同号,无偏移风险。
    """
    if len(matrix) != js.num_machines + 1:
        raise ValueError(f"{js.name}: 需要 {js.num_machines} 机布局,"
                         f"给的矩阵是 {len(matrix)-1} 机")

    nodes = [LU] + [machine_node(k) for k in range(1, js.num_machines + 1)]
    idx = {LU: 0, **{machine_node(k): k for k in range(1, js.num_machines + 1)}}
    dist = {a: {b: matrix[idx[a]][idx[b]] for b in nodes} for a in nodes}

    jobs, proc = [], {}
    for jid, chain in enumerate(js.chains, start=1):
        jobs.append({"id": jid, "num_ops": len(chain)})
        for i, gop in enumerate(chain, start=1):
            proc[f"({jid},{i})"] = {str(m + 1): t for m, t in sorted(js.ops[gop].items())}

    return {
        "name": f"{js.name}-ideal",
        "delta_return": DELTA_RETURN,
        "jobs": jobs,
        "machines": [{"id": k, "node": machine_node(k)}
                     for k in range(1, js.num_machines + 1)],
        "proc_time": proc,
        "num_agvs": NUM_AGVS,
        "network": {"lu_node": LU, "nodes": nodes, "corridors": [], "ideal_dist": dist},
        "_spec": src,
    }


def sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 16), b""):
            h.update(blk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="公开 FJSPT 基准格式转换器")
    ap.add_argument("--dataset", default="hf", choices=["hf"],
                    help="数据集键;目前只实现 hf(Homayouni & Fontes 2020 set 1)")
    ap.add_argument("--out", default=None, help="输出目录,缺省 database/json/<key>/")
    ap.add_argument("--check", action="store_true", help="只做保真度体检,不落盘")
    args = ap.parse_args(argv)

    ex = os.path.join(DB, "extracted", args.dataset)
    f_jobs = os.path.join(ex, "jobsets.txt")
    f_lay = os.path.join(ex, "layouts_2to8.txt")
    for p in (f_jobs, f_lay):
        if not os.path.exists(p):
            print(f"缺少提取文本 {p};先按模块 docstring 里的 pdftotext 命令生成。")
            return 1

    with open(f_jobs, "r", encoding="utf-8") as f:
        jobsets = parse_jobsets(f.read())
    with open(f_lay, "r", encoding="utf-8") as f:
        layouts = parse_layouts(f.read())

    print(f"解析到 {len(jobsets)} 个算例,{len(layouts)} 个布局 "
          f"({', '.join(f'{k}-M' for k in sorted(layouts))})")

    print("\n== 布局保真度体检(能否还原为图)==")
    print(f"{'布局':<6} {'阶':<4} {'对称':<6} {'三角违反':<9} {'最大超出':<9} "
          f"{'有向图':<7} 无向走廊")
    fid = fidelity_report(layouts)
    for r in fid:
        print(f"{r['layout']:<6} {r['size']:<4} {str(r['symmetric']):<6} "
              f"{r['closure_violations']:<9} {r['max_excess']:<9} "
              f"{('是' if r['digraph_reconstructible'] else '否'):<7} "
              f"{'是' if r['corridor_reconstructible'] else '否'}")
    n_corr = sum(1 for r in fid if r["corridor_reconstructible"])
    print(f"  -> {n_corr}/{len(fid)} 个布局可还原为无向走廊网络;"
          f"其余只能跑退化对标档(规格 12.2)")

    need = sorted({js.num_machines for js in jobsets})
    missing = [n for n in need if n not in layouts]
    if missing:
        print(f"\n!! 缺少这些机器数的布局: {missing}")
        return 1

    if args.check:
        return 0

    out_dir = args.out or os.path.join(DB, "json", args.dataset)
    os.makedirs(out_dir, exist_ok=True)
    src_base = {
        "dataset": args.dataset,
        "converter": os.path.basename(__file__),
        "converter_version": 1,
        "delta_return": DELTA_RETURN,
        "num_agvs": NUM_AGVS,
        "jobsets_txt_sha256": sha256(f_jobs),
        "layouts_txt_sha256": sha256(f_lay),
    }

    written = []
    for js in jobsets:
        src = dict(src_base, instance=js.name, layout=f"{js.num_machines}-M")
        data = build_instance(js, layouts[js.num_machines], src)
        path = os.path.join(out_dir, data["name"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        written.append(data["name"])

    fid_path = os.path.join(out_dir, "_fidelity.json")
    with open(fid_path, "w", encoding="utf-8") as f:
        json.dump({"layouts": fid, "source": src_base}, f, ensure_ascii=False, indent=2)

    print(f"\n已写出 {len(written)} 个算例 -> {os.path.relpath(out_dir, HERE)}{os.sep}")
    print(f"布局体检表 -> {os.path.relpath(fid_path, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
