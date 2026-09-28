"""受控扩展算例生成器(规格 12.3)。

设计目标是让"拥堵度 × 异构度"双因子实验的每个格子都**只变一个东西**:

- **路网**:模板化布局,拥堵由两个容量旋钮控制——`lu_exits`(LU 出口条数)与
  `mid_lanes`(中段并行通道数)。两个旋钮**只改容量、不改距离**:无论取值多少,
  v0 到近端枢纽恒为 2 个时间单位、近端到远端枢纽恒为 `mid_time`。因此同一布局
  下不同容量的算例之间,理想最短路矩阵 t* 完全相同,拥堵是唯一变量。
- **异构度 H**:先抽随机扰动,再**标准化后按 H 缩放**,使每行(工序)的总体
  变异系数精确等于 H(取整前);H=0 时同一工序在各机上耗时相同,退化为
  "柔性但零异构"对照(规格 12.1 中 Deroussi 那一档的合成版)。
- **柔性度 F**:按目标平均 |Ω| = F*NM 随机化取整,且恒保证 |Ω| >= 2(B1)。

为何要单独控制 LU 出口:LU 出口走廊承载每个工件的首道送达与成品回运,**其拥堵
与机器指派无关**,只抬高所有方案的基线延误而不提供改派/错峰可利用的差异(规格
3.1 实测修正、13.6 优先级 1)。把 `lu_exits` 与 `mid_lanes` 分开扫,才能把
"决策相关拥堵"与"决策无关拥堵"的效应分离——这是 `high` 与 `funnel` 两档
只差 LU 容量的受控对比的用意。

Controlled generator of extended instances (spec 12.3).

The design goal is that every cell of the "congestion × heterogeneity" two-factor experiment changes only one thing:

- Road network: templated layouts. Congestion is controlled by two capacity knobs — `lu_exits` (number of LU exits) and `mid_lanes` (number of parallel mid-segment lanes). Both knobs change capacity only, not distance: whatever their values, v0 to the near hub is always 2 time units, and the near hub to the far hub is always `mid_time`. Under the same layout, instances of different capacity therefore share the identical ideal shortest-path matrix t*, and congestion is the only variable.
- Heterogeneity H: draw random perturbations, standardize them, then scale by H, so the population coefficient of variation of each row (operation) equals H exactly before rounding. At H=0 the same operation takes the same time on every machine, which degenerates to a "flexible but zero-heterogeneity" control (the synthetic counterpart of the Deroussi arm in spec 12.1).
- Flexibility F: randomized rounding toward the target mean |Ω| = F*NM, always with |Ω| >= 2 (B1).

Why control the LU exits separately: the LU-exit corridors carry every job's first delivery and finished-goods return haul. Their congestion does not depend on machine assignment. It only raises the baseline delay of every solution and does not create a difference that reassignment or stagger can exploit (measured correction in spec 3.1; priority 1 in 13.6). Sweeping `lu_exits` and `mid_lanes` separately is what separates "decision-dependent congestion" from "decision-independent congestion". That is the point of the controlled comparison in which the `high` and `funnel` arms differ only in LU capacity.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# 规格 / Specification
# --------------------------------------------------------------------------


@dataclass
class InstanceSpec:
    """一个扩展算例的完整生成参数(随算例落盘,满足 F1 可复现)。

    Full generation parameters of an extended instance (stored with the instance, so F1 reproducibility holds).
    """
    num_jobs: int
    num_machines: int
    num_agvs: int
    ops_per_job: int
    layout: str = "dumbbell"          # dumbbell | grid | mesh | pubgrid
    lu_exits: int = 2                 # LU 出口条数 = 漏斗宽度(容量旋钮)
    # Number of LU exits = funnel width (capacity knob)
    mid_lanes: int = 1                # 中段并行通道数(容量旋钮)
    # Number of parallel mid-segment lanes (capacity knob)
    mid_time: float = 6.0             # 中段单程时间(拉大则远端更贵)
    # One-way mid-segment time (a larger value makes the far end more expensive)
    far_frac: float = 0.5             # 远端 RA 占比
    # Share of robotic arms placed at the far end
    spur_time: float = 2.0            # 枢纽到 RA 的支线时间
    # Spur time from a hub to a robotic arm
    grid_rows: int = 3                # layout=grid 时的网格规模
    # Grid size when layout=grid
    grid_cols: int = 3
    grid_time: float = 3.0
    heterogeneity: float = 0.3        # 目标 H(行内变异系数)
    # Target H (within-row coefficient of variation)
    flexibility: float = 0.6          # 目标 F(平均 |Ω| / NM)
    # Target F (mean |Ω| / NM)
    proc_lo: float = 8.0              # 工序名义难度区间(标定前的相对尺度)
    # Nominal operation-difficulty range (relative scale before calibration)
    proc_hi: float = 24.0
    tt_tp_target: Optional[float] = 1.0   # 目标 T̄t/T̄p;None = 不标定
    # Target T̄t/T̄p; None = do not calibrate
    delta_return: int = 1
    seed: int = 0
    tag: str = ""                     # 拥堵度档位名,仅用于命名与追溯
    # Congestion-level name, used only for naming and traceability
    # layout="pubgrid" 时使用:拓扑取自公开数据文件而非本文设计,见 PUB_LAYOUTS。
    # 节点号沿用原文件的行主序 1 基编号 n = (r-1)*grid_cols + c。
    # Used when layout="pubgrid": the topology is taken from a public data file, not designed in this paper; see PUB_LAYOUTS.
    # Node ids keep the source file's row-major 1-based numbering n = (r-1)*grid_cols + c.
    pub_source: str = ""              # 来源标签(非空即表示布局非本文设计)
    # Source label (nonempty means the layout was not designed in this paper)
    grid_lu_node: int = 0
    grid_machine_nodes: List[int] = field(default_factory=list)
    grid_removed_edges: List[List[int]] = field(default_factory=list)

    def base_name(self) -> str:
        return f"S{self.num_jobs}x{self.num_machines}x{self.num_agvs}"

    def name(self) -> str:
        """规格 12.3 的命名规则: <基础>-L<布局>-H<异构>-F<柔性>-A<AGV>[-s<种子>]。

        Naming rule of spec 12.3: <base>-L<layout>-H<heterogeneity>-F<flexibility>-A<AGV>[-s<seed>].
        """
        # 外部布局直接用来源标签作布局段(它自带来源名,再冠一个 L 只会变成 LLyuL4)。
        # An external layout uses its source label as the layout segment (the label already carries the source name; prefixing another L would yield LLyuL4).
        if self.pub_source:
            layout = self.pub_source
        else:
            layout = f"L{self.layout[:1].upper()}{self.lu_exits}{self.mid_lanes}"
        return (f"{self.base_name()}-{layout}-H{self.heterogeneity:g}"
                f"-F{self.flexibility:g}-A{self.num_agvs}-s{self.seed}")


# --------------------------------------------------------------------------
# 路网模板 / Road-network templates
# --------------------------------------------------------------------------


def _dumbbell(spec: InstanceSpec) -> Tuple[List[str], List[dict], List[str]]:
    """哑铃布局:LU --(lu_exits 条并行)--> 近端枢纽 --(mid_lanes 条并行)--> 远端枢纽。

    并行通道必须经由**互不相同的中间节点**实现:走廊的预约资源按端点对归并
    (network.corridor_id),同端点对的重复边会塌缩成同一个独占资源、达不到扩容
    效果。故每条通道插一个中间节点,并令两跳时间之和保持恒定。

    Dumbbell layout: LU --(lu_exits parallel lanes)--> near hub --(mid_lanes parallel lanes)--> far hub.

    Parallel lanes must pass through distinct intermediate nodes. Corridor reservation resources are merged by endpoint pair (network.corridor_id), so duplicate edges on the same endpoint pair collapse into one exclusive resource and do not add capacity. Each lane therefore inserts an intermediate node, and the sum of the two hop times is held constant.
    """
    nodes = ["v0", "h1", "h2"]
    corridors: List[dict] = []

    # LU -> 近端枢纽:k 条两跳通道,单程恒为 2
    # LU -> near hub: k two-hop lanes, one-way time fixed at 2
    for i in range(1, spec.lu_exits + 1):
        e = f"e{i}"
        nodes.append(e)
        corridors.append({"u": "v0", "v": e, "time": 1})
        corridors.append({"u": e, "v": "h1", "time": 1})

    # 近端 -> 远端:k 条两跳通道,单程恒为 mid_time
    # Near hub -> far hub: k two-hop lanes, one-way time fixed at mid_time
    half = spec.mid_time / 2.0
    for i in range(1, spec.mid_lanes + 1):
        g = f"g{i}"
        nodes.append(g)
        corridors.append({"u": "h1", "v": g, "time": half})
        corridors.append({"u": g, "v": "h2", "time": half})

    num_far = max(1, min(spec.num_machines - 1,
                         int(round(spec.num_machines * spec.far_frac))))
    machine_nodes: List[str] = []
    for m in range(1, spec.num_machines + 1):
        node = f"r{m}"
        nodes.append(node)
        hub = "h2" if m > spec.num_machines - num_far else "h1"
        corridors.append({"u": hub, "v": node, "time": spec.spur_time})
        machine_nodes.append(node)
    return nodes, corridors, machine_nodes


def _grid(spec: InstanceSpec) -> Tuple[List[str], List[dict], List[str]]:
    """网格布局:路径冗余度高,作为低拥堵对照。LU 置于角点,RA 尽量分散。

    Grid layout: high path redundancy, used as the low-congestion control. The LU sits at a corner, and robotic arms are spread out.
    """
    rows, cols = spec.grid_rows, spec.grid_cols
    if rows * cols < spec.num_machines + 1:
        raise ValueError(f"网格 {rows}x{cols} 容纳不下 {spec.num_machines} 台 RA 与 LU")

    def gid(r: int, c: int) -> str:
        return f"n{r}_{c}"

    nodes = [gid(r, c) for r in range(rows) for c in range(cols)]
    corridors: List[dict] = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                corridors.append({"u": gid(r, c), "v": gid(r, c + 1),
                                  "time": spec.grid_time})
            if r + 1 < rows:
                corridors.append({"u": gid(r, c), "v": gid(r + 1, c),
                                  "time": spec.grid_time})
    # LU 占角点;RA 按到 LU 的曼哈顿距离降序取,保证分散且远近有别
    # The LU takes a corner. Robotic arms are taken in descending Manhattan distance from the LU, so they are spread out and differ in distance.
    lu = gid(0, 0)
    rest = sorted((n for n in nodes if n != lu),
                  key=lambda n: (-(int(n[1:].split("_")[0]) + int(n.split("_")[1])), n))
    machine_nodes = rest[:spec.num_machines]
    nodes.remove(lu)
    nodes.insert(0, lu)
    return nodes, corridors, machine_nodes


def _mesh(spec: InstanceSpec) -> Tuple[List[str], List[dict], List[str]]:
    """错落布局:LU 置于一条边的中点,RA 用最远点采样散布到整片网格。

    另两种布局都让"换一台 RA"几乎换不掉任何**会被争用**的走廊,改派算子因而
    先天无从缓解拥堵:

      dumbbell  每台 RA 由一条专属支线挂在枢纽上,而所有运输必经 LU->近端枢纽。
                同挂一个枢纽的两台 RA 之间改派,变动的只有那条只有它自己会走的
                支线,争用暴露分毫不变(M8 时 43% 的 RA 对如此)。
      grid      按到 LU 的距离**降序**取点,实际把 RA 聚在远离 LU 的一角,通往
                它们的路径共享同一段主干。

    本布局改为最远点采样:每次选离已选点集(含 LU)最远的节点,使 RA 在各个方向
    上铺开,让"换一台臂"真正对应"换一条走廊"。诊断见 tools.layout_diag。

    LU 仍置于角点、网格尺寸与边权也与 grid 一致,故 grid 与 mesh 之间**只差
    RA 选点**一个因素,两者之差可干净地归因给摆放方式。LU 出口容量是另一个旋钮
    (哑铃布局的 lu_exits),不在此处混入。

    Staggered layout: the LU sits at the midpoint of one edge, and robotic arms are spread over the grid by farthest-point sampling.

    The other two layouts make "switching robotic arm" barely change any corridor that is actually contended, so the reassignment operator has no way to relieve congestion:

      dumbbell  each robotic arm hangs off a hub on its own spur, and every transport must pass LU->near hub.
                Reassignment between two arms on the same hub changes only the spur that only that arm uses,
                and the contended exposure does not move (43% of robotic-arm pairs are like this at M8).
      grid      points are taken in descending distance from the LU, which in practice clusters the arms in the corner far from the LU, so the paths to them share one trunk.

    This layout uses farthest-point sampling: each pick is the node farthest from the set already chosen (including the LU), so the arms spread in every direction and "changing arm" really means "changing corridor". See tools.layout_diag.

    The LU is still at a corner, and the grid size and edge weights match grid, so grid and mesh differ only in how robotic arms are placed. Their gap can be attributed cleanly to placement. LU-exit capacity is another knob (lu_exits of the dumbbell layout) and is not mixed in here.
    """
    rows, cols = spec.grid_rows, spec.grid_cols
    if rows * cols < spec.num_machines + 1:
        raise ValueError(f"网格 {rows}x{cols} 容纳不下 {spec.num_machines} 台 RA 与 LU")

    def gid(r: int, c: int) -> str:
        return f"n{r}_{c}"

    coord = {gid(r, c): (r, c) for r in range(rows) for c in range(cols)}
    corridors: List[dict] = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                corridors.append({"u": gid(r, c), "v": gid(r, c + 1),
                                  "time": spec.grid_time})
            if r + 1 < rows:
                corridors.append({"u": gid(r, c), "v": gid(r + 1, c),
                                  "time": spec.grid_time})

    lu = gid(0, 0)                               # 与 grid 对齐,保证只差 RA 选点
    # Aligned with grid, so the only difference is which robotic-arm nodes are chosen.
    chosen: List[str] = []
    for _ in range(spec.num_machines):
        anchor = [lu] + chosen
        best = max((n for n in coord if n != lu and n not in chosen),
                   key=lambda n: (min(abs(coord[n][0] - coord[a][0])
                                      + abs(coord[n][1] - coord[a][1])
                                      for a in anchor), n))
        chosen.append(best)

    nodes = [lu] + [n for n in coord if n != lu]
    return nodes, corridors, chosen


def _pubgrid(spec: InstanceSpec) -> Tuple[List[str], List[dict], List[str]]:
    """外部来源的网格布局:尺寸、装卸站与机器落位、缺边逐项读自公开数据文件。

    与 `_grid` 的唯一区别是选点方式。`_grid` 自己按到 LU 的距离挑机器节点,因此
    布局是本文设计的;本函数改为读入外部给定的节点号,于是"哪里放机器、哪里断路"
    这两件事都不由本文决定——这正是它存在的理由(见 PUB_LAYOUTS)。

    节点名保留原文件的行主序 1 基编号(`g<n>`,n = (r-1)*cols + c),使生成的算例
    可以和原始 `.data` 文件逐项对账。缺边必须确实是网格四邻接边,否则说明编号口径
    与原文件不一致,此时宁可报错也不能静默生成一张错的图。

    Grid layout from an external source: size, load/unload station, machine placement, and missing edges are read item by item from a public data file.

    The only difference from `_grid` is how nodes are chosen. `_grid` picks machine nodes by distance to the LU, so the layout is designed in this paper. This function reads externally given node ids, so neither "where the machines sit" nor "where edges are missing" is decided here. That is why it exists (see PUB_LAYOUTS).

    Node names keep the source file's row-major 1-based ids (`g<n>`, n = (r-1)*cols + c), so a generated instance can be checked item by item against the original `.data` file. A missing edge must really be a 4-adjacent grid edge; otherwise the numbering convention disagrees with the source file, and it is better to raise than to silently emit a wrong graph.
    """
    rows, cols = spec.grid_rows, spec.grid_cols
    total = rows * cols
    if len(spec.grid_machine_nodes) != spec.num_machines:
        raise ValueError(f"pubgrid: num_machines={spec.num_machines} 与机器节点数 "
                         f"{len(spec.grid_machine_nodes)} 不一致")

    def gid(n: int) -> str:
        return f"g{n}"

    def coord(n: int) -> Tuple[int, int]:
        return (n - 1) // cols + 1, (n - 1) % cols + 1

    for n in [spec.grid_lu_node] + list(spec.grid_machine_nodes):
        if not 1 <= n <= total:
            raise ValueError(f"pubgrid: 节点号 {n} 超出 {rows}x{cols} 网格")
    if spec.grid_lu_node in spec.grid_machine_nodes:
        raise ValueError(f"pubgrid: 装卸点 {spec.grid_lu_node} 同时被列为机器节点")

    removed = set()
    for pair in spec.grid_removed_edges:
        a, b = int(pair[0]), int(pair[1])
        (ra, ca), (rb, cb) = coord(a), coord(b)
        adjacent = (ra == rb and abs(ca - cb) == 1) or (ca == cb and abs(ra - rb) == 1)
        if not adjacent:
            raise ValueError(f"pubgrid: 缺边 ({a},{b}) 在 {rows}x{cols} 上不是四邻接边,"
                             f"坐标为 {(ra, ca)} 与 {(rb, cb)};编号口径可能不一致")
        removed.add(frozenset((a, b)))

    corridors: List[dict] = []
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            n = (r - 1) * cols + c
            for m in ([n + 1] if c < cols else []) + ([n + cols] if r < rows else []):
                if frozenset((n, m)) not in removed:
                    corridors.append({"u": gid(n), "v": gid(m),
                                      "time": spec.grid_time})

    lu = gid(spec.grid_lu_node)
    nodes = [lu] + [gid(n) for n in range(1, total + 1) if n != spec.grid_lu_node]
    return nodes, corridors, [gid(n) for n in spec.grid_machine_nodes]


_LAYOUTS = {"dumbbell": _dumbbell, "grid": _grid, "mesh": _mesh,
            "pubgrid": _pubgrid}


# --------------------------------------------------------------------------
# 加工时间(H / F 可控) / Processing times (H / F controllable)
# --------------------------------------------------------------------------


def _pop_std(vals: List[float]) -> float:
    mean = sum(vals) / len(vals)
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))


def _omega_size(rng: random.Random, target: float, num_machines: int) -> int:
    """随机化取整,使 |Ω| 的期望等于 target,并夹到 [2, NM](B1)。

    Randomized rounding so that the expectation of |Ω| equals target, clamped to [2, NM] (B1).
    """
    base = int(math.floor(target))
    size = base + (1 if rng.random() < target - base else 0)
    return max(2, min(num_machines, size))


def gen_proc_time(spec: InstanceSpec, rng: random.Random
                  ) -> Dict[Tuple[int, int], Dict[int, float]]:
    """生成 proc_time,使每行的总体变异系数(取整前)精确等于目标 H。

    做法:抽 |Ω| 个独立扰动后**标准化**为零均值单位方差,再乘 H 得到偏离量,
    故 CV = H 与 |Ω| 无关——直接用均匀扰动的话 CV 会随 |Ω| 漂移、小 |Ω| 上
    尤其不稳,H 就失去了作为实验因子的资格。取整会带来小偏差,因此生成后
    **实测并记录**真实 H(见 build_instance 的 features 头)。

    Build proc_time so that each row's population coefficient of variation equals the target H exactly before rounding.

    Method: draw |Ω| independent perturbations, standardize them to zero mean and unit variance, then multiply by H to get the deviation. CV = H is then independent of |Ω|. A raw uniform perturbation would let CV drift with |Ω|, especially at small |Ω|, and H would no longer qualify as an experimental factor. Rounding introduces a small bias, so the realized H is measured and recorded after generation (see the features header in build_instance).
    """
    machines = list(range(1, spec.num_machines + 1))
    target_omega = spec.flexibility * spec.num_machines
    if target_omega < 2:
        raise ValueError(f"柔性度 F={spec.flexibility} 过低:F*NM={target_omega:.2f} < 2,"
                         f"与 B1(多数工序 |Ω|>=2)冲突;请取 F >= {2 / spec.num_machines:.2f}")

    proc: Dict[Tuple[int, int], Dict[int, float]] = {}
    for j in range(1, spec.num_jobs + 1):
        for i in range(1, spec.ops_per_job + 1):
            size = _omega_size(rng, target_omega, spec.num_machines)
            omega = rng.sample(machines, size)
            nominal = rng.uniform(spec.proc_lo, spec.proc_hi)
            raw = [rng.uniform(0.5, 1.5) for _ in omega]
            sd = _pop_std(raw)
            if sd > 0:
                mean = sum(raw) / len(raw)
                # 夹住标准分,防止 H 较大时出现非正的加工时间
                # Clamp the z-score so a large H does not produce a nonpositive processing time.
                zs = [max(-2.0, min(2.0, (r - mean) / sd)) for r in raw]
            else:
                zs = [0.0] * size
            row = {}
            for m, z in zip(sorted(omega), zs):
                row[m] = float(max(1, round(nominal * (1.0 + spec.heterogeneity * z))))
            proc[(j, i)] = row
    return proc


# --------------------------------------------------------------------------
# 组装 / Assembly
# --------------------------------------------------------------------------


def _mean_pairwise_travel(nodes: List[str], corridors: List[dict], lu: str,
                          machine_nodes: List[str]) -> float:
    """取放点(RA 节点 + LU)两两平均理想最短路时间,即 T̄t(与 feature_params 同口径)。

    Mean pairwise ideal shortest-path time among pickup/dropoff points (robotic-arm nodes + LU), i.e. T̄t (same definition as feature_params).
    """
    from .network import Network
    net = Network(nodes, corridors, lu)
    points = sorted(set(machine_nodes) | {lu})
    ds = [net.ideal_dist[a][b] for a in points for b in points if a != b]
    return sum(ds) / len(ds) if ds else 0.0


def _calibrate_tt_tp(proc: Dict[Tuple[int, int], Dict[int, float]],
                     tt_bar: float, target: float, rounds: int = 4) -> None:
    """就地缩放加工时间,使 T̄t/T̄p 命中 target。

    只缩放加工时间、不动路网:T̄t 由拓扑决定,是各拥堵档位的**结构**特征;若改
    路网来调该比值,就会把"运输强度"和"网络结构"两件事混在一起。而缩放加工
    时间对 H(变异系数,尺度无关)与 F(|Ω| 大小)均无影响,是干净的标定杠杆。
    取整会带来漂移,故迭代若干轮。

    Scale processing times in place so that T̄t/T̄p hits target.

    Only processing times are scaled; the road network is not touched. T̄t is fixed by the topology and is a structural feature of each congestion level. Changing the road network to tune the ratio would mix "transport intensity" with "network structure". Scaling processing time does not affect H (a coefficient of variation, scale-free) or F (the size of |Ω|), so it is a clean calibration lever. Rounding causes drift, so the scaling is iterated for several rounds.
    """
    if target is None or target <= 0 or tt_bar <= 0:
        return
    for _ in range(rounds):
        vals = [t for row in proc.values() for t in row.values()]
        tp_bar = sum(vals) / len(vals)
        if tp_bar <= 0:
            return
        factor = (tt_bar / tp_bar) / target
        if abs(factor - 1.0) < 1e-3:
            return
        for row in proc.values():
            for m in row:
                row[m] = float(max(1, round(row[m] * factor)))


def build_instance(spec: InstanceSpec) -> dict:
    """按 spec 生成一个 3.1 节 JSON schema 的算例字典(含自描述特征头)。

    Build, from spec, an instance dict in the section-3.1 JSON schema, including a self-describing feature header.
    """
    if spec.layout not in _LAYOUTS:
        raise ValueError(f"未知布局 {spec.layout};可选 {sorted(_LAYOUTS)}")
    rng = random.Random(spec.seed)

    nodes, corridors, machine_nodes = _LAYOUTS[spec.layout](spec)
    lu = "v0" if spec.layout == "dumbbell" else nodes[0]
    proc = gen_proc_time(spec, rng)
    _calibrate_tt_tp(proc, _mean_pairwise_travel(nodes, corridors, lu, machine_nodes),
                     spec.tt_tp_target)

    data = {
        "name": spec.name(),
        "delta_return": spec.delta_return,
        "jobs": [{"id": j, "num_ops": spec.ops_per_job}
                 for j in range(1, spec.num_jobs + 1)],
        "machines": [{"id": m + 1, "node": machine_nodes[m]}
                     for m in range(spec.num_machines)],
        "proc_time": {f"({j},{i})": {str(m): t for m, t in row.items()}
                      for (j, i), row in sorted(proc.items())},
        "num_agvs": spec.num_agvs,
        "network": {"lu_node": lu, "nodes": nodes, "corridors": corridors},
        "_spec": {k: v for k, v in spec.__dict__.items()},
    }
    measure(data)      # 生成即自描述:避免调用方漏调 measure 而落盘无特征头的算例
    # Self-describing at generation time, so a caller cannot forget measure and store an instance with no feature header.
    return data


def measure(data: dict) -> dict:
    """对算例实测特征与下界,回填 `_features` 头(目标值 vs 实际值)。

    就地修改 `data` 并返回特征字典;幂等(`parse_instance` 忽略 `_` 开头的键)。
    对手写算例也可用。

    Measure features and the lower bound on an instance, and write them back into the `_features` header (targets versus realized values).

    Modifies `data` in place and returns the feature dict. Idempotent (`parse_instance` ignores keys that start with `_`). Also usable on hand-written instances.
    """
    from .instance import parse_instance, feature_params, simple_lower_bound
    from .network import Network

    inst = parse_instance(data)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    feat = feature_params(inst, net.ideal_dist, net)
    feat.update(simple_lower_bound(inst, net))
    spec = data.get("_spec", {})
    feat["target_heterogeneity"] = spec.get("heterogeneity")
    feat["target_flexibility"] = spec.get("flexibility")
    feat["congestion_tag"] = spec.get("tag")
    data["_features"] = feat
    return feat


# --------------------------------------------------------------------------
# 拥堵度档位预设 / Congestion-level presets
# --------------------------------------------------------------------------

# 拥堵度档位。关键在于 high 与 funnel **只差 LU 出口容量**:
# 两者的中段争用完全相同(mid_lanes=1),但 funnel 额外把 LU 出口收成单点漏斗。
# 若各机制只在 high 上显示增益而在 funnel 上消失,即直接证明"决策无关拥堵
# 稀释机制信号"这一诊断(规格 3.1 实测修正)。
#
# 前四档存在一个盲区:mid/high/funnel 全是哑铃布局,改派换不掉争用走廊;唯一的
# 网格布局 low 又按设计是低拥堵对照。于是"高争用"与"路径多样"在前四档里从未
# 同时出现,而这恰是改派算子唯一可能奏效的区间。scatter 档补上这一格。
# Congestion levels. The point is that high and funnel differ only in LU-exit capacity:
# mid-segment contention is identical (mid_lanes=1), but funnel further collapses the LU exits into a single-point funnel.
# If a mechanism shows a gain only on high and the gain disappears on funnel, that directly supports the diagnosis
# that decision-independent congestion dilutes the mechanism's signal (measured correction in spec 3.1).
#
# The first four levels have a blind spot: mid/high/funnel are all dumbbell layouts, so reassignment cannot escape the contended corridor,
# and the only grid layout, low, is by design the low-congestion control. "High contention" and "path diversity" therefore never
# occur together in the first four levels, which is exactly the regime where reassignment could work. The scatter level fills that cell.
CONGESTION_PRESETS: Dict[str, dict] = {
    "low":     {"layout": "grid", "grid_rows": 3, "grid_cols": 3, "grid_time": 3.0},
    "mid":     {"layout": "dumbbell", "lu_exits": 2, "mid_lanes": 2, "mid_time": 6.0},
    "high":    {"layout": "dumbbell", "lu_exits": 2, "mid_lanes": 1, "mid_time": 6.0},
    "funnel":  {"layout": "dumbbell", "lu_exits": 1, "mid_lanes": 1, "mid_time": 6.0},
    "scatter": {"layout": "mesh", "grid_rows": 4, "grid_cols": 4, "grid_time": 3.0},
}


def make_spec(tag: str, heterogeneity: float, flexibility: float,
              num_jobs: int, num_machines: int, num_agvs: int,
              ops_per_job: int, seed: int, **overrides) -> InstanceSpec:
    if tag not in CONGESTION_PRESETS:
        raise ValueError(f"未知拥堵度档位 {tag};可选 {sorted(CONGESTION_PRESETS)}")
    kwargs = dict(CONGESTION_PRESETS[tag])
    kwargs.update(overrides)
    return InstanceSpec(num_jobs=num_jobs, num_machines=num_machines,
                        num_agvs=num_agvs, ops_per_job=ops_per_job,
                        heterogeneity=heterogeneity, flexibility=flexibility,
                        seed=seed, tag=tag, **kwargs)


# --------------------------------------------------------------------------
# 外部来源布局(公开数据集) / Layouts from external sources (public datasets)
# --------------------------------------------------------------------------

# 拓扑三项——网格尺寸、装卸站与机器落位、缺边——逐项转录自
# `database/raw/tjsp_toolset/data/benchmarks/lyu2019/layouts/`,即 van Os 配套
# 工具集对 Lyu 等(2019)附录 A 图 10--15 的机读编码。本项目**只借这三项**,
# 目的是获得一批不由本文设计的拓扑(布局出处的可信度,不是求解质量的对标)。
#
# **边权不是原始数据。** Lyu 只为单个示例算例发表了逐段行驶时间(其 Table 4 取值
# 为 1/2/3,并不均匀),附录 A 那批测试算例的逐段时长从未发表。故此处按"所有边等权"
# 补齐:这与 van Os 模型里"单步时长为常量"的假设在结构上等价,只是时间单位的标度
# 不同(标度由 tt_tp 标定吸收)。**据此生成的算例不可与 Lyu 或 van Os 的参照值
# 比较**,两边的边权口径不同。
#
# 原文件第二行的节点序为 [装货站, m1..mk, 卸货站](见 model_data.py 中
# `VEHICLE_START_LOCATIONS = MACHINE_LOCATIONS[0]  # Vehicles start at loading
# station`)。本项目只有一个装卸点,故取装货站为 lu_node,卸货站退化为普通网格
# 节点——这是与原设定的一处实质差异,必须声明。
#
# Liu 等(2023)的四张布局未收入:其首行带 `d` 后缀,即允许对角移动,而本项目的
# 走廊为四邻接。接受对角移动要改的是下层路由层而不是算例,性质与 van Os 的节点
# 容量问题相同,故排除。
# Three topology items — grid size, load/unload station and machine placement, and missing edges — are transcribed item by item from
# `database/raw/tjsp_toolset/data/benchmarks/lyu2019/layouts/`, the machine-readable encoding in the van Os toolset of Figures 10--15
# in Appendix A of Lyu et al. (2019). This project borrows only those three items, to obtain topologies not designed in this paper
# (credibility of layout provenance, not a benchmark of solution quality).
#
# Edge weights are not original data. Lyu published per-segment travel times for a single example instance only (Table 4 takes values
# 1/2/3, and they are not uniform). Per-segment durations of the Appendix A test instances were never published. Edges are therefore
# filled in as equal-weight: structurally equivalent to the van Os assumption that a single step has constant duration, and different
# only in the scale of the time unit (the scale is absorbed by the tt_tp calibration). Instances generated this way must not be compared
# with the reference values of Lyu or van Os; the two sides use different edge-weight conventions.
#
# The node order on line 2 of the source file is [loading station, m1..mk, unloading station] (see model_data.py:
# `VEHICLE_START_LOCATIONS = MACHINE_LOCATIONS[0]  # Vehicles start at loading
# station`). This project has a single load/unload point, so the loading station is taken as lu_node and the unloading station
# degenerates to an ordinary grid node. That is a substantive difference from the original setting and must be stated.
#
# The four layouts of Liu et al. (2023) are not included: their first line carries a `d` suffix, i.e. diagonal moves are allowed,
# whereas corridors here are 4-adjacent. Accepting diagonal moves would change the lower-level routing layer, not the instance,
# which is the same kind of issue as van Os node capacities, so they are excluded.
PUB_LAYOUTS: Dict[str, dict] = {
    "LyuL1": {"grid_rows": 3, "grid_cols": 3, "grid_lu_node": 1,
              "grid_machine_nodes": [2, 5, 7],
              "grid_removed_edges": []},
    "LyuL2": {"grid_rows": 4, "grid_cols": 4, "grid_lu_node": 1,
              "grid_machine_nodes": [4, 6, 11, 13],
              "grid_removed_edges": [[7, 11]]},
    "LyuL3": {"grid_rows": 4, "grid_cols": 4, "grid_lu_node": 1,
              "grid_machine_nodes": [4, 7, 9, 11, 14],
              "grid_removed_edges": [[7, 11]]},
    "LyuL4": {"grid_rows": 5, "grid_cols": 5, "grid_lu_node": 1,
              "grid_machine_nodes": [3, 10, 11, 14, 17, 23],
              "grid_removed_edges": [[8, 13], [19, 20]]},
    "LyuL5": {"grid_rows": 5, "grid_cols": 5, "grid_lu_node": 1,
              "grid_machine_nodes": [3, 9, 12, 15, 16, 22, 24],
              "grid_removed_edges": [[8, 13], [19, 20]]},
    "LyuL6": {"grid_rows": 5, "grid_cols": 5, "grid_lu_node": 1,
              "grid_machine_nodes": [4, 6, 8, 10, 13, 16, 19, 23],
              "grid_removed_edges": [[8, 13], [19, 20]]},
}


def make_pub_spec(key: str, heterogeneity: float, flexibility: float,
                  num_jobs: int, num_agvs: int, ops_per_job: int, seed: int,
                  **overrides) -> InstanceSpec:
    """按外部布局 key 造 spec。

    `num_machines` 由布局决定而不接受调用方指定——外部布局的机器台数是数据的一部分,
    允许覆盖就等于把"借来的拓扑"改回"自己设计的拓扑"。

    Build a spec from an external-layout key.

    `num_machines` is determined by the layout and is not accepted from the caller. The machine count of an external layout is part of the data; allowing an override would turn a borrowed topology back into a topology designed here.
    """
    if key not in PUB_LAYOUTS:
        raise ValueError(f"未知外部布局 {key};可选 {sorted(PUB_LAYOUTS)}")
    kwargs = dict(PUB_LAYOUTS[key])
    kwargs.update(overrides)
    num_machines = len(kwargs["grid_machine_nodes"])
    if flexibility * num_machines < 2:
        raise ValueError(
            f"{key} 有 {num_machines} 台机器,F={flexibility} 给出 F*NM="
            f"{flexibility * num_machines:.2f} < 2,与 B1 冲突;"
            f"该布局需 F >= {2 / num_machines:.3f}")
    return InstanceSpec(num_jobs=num_jobs, num_machines=num_machines,
                        num_agvs=num_agvs, ops_per_job=ops_per_job,
                        layout="pubgrid", heterogeneity=heterogeneity,
                        flexibility=flexibility, seed=seed, tag="pub",
                        pub_source=key, **kwargs)
