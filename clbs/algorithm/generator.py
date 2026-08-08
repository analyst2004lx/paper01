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
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# 规格
# --------------------------------------------------------------------------


@dataclass
class InstanceSpec:
    """一个扩展算例的完整生成参数(随算例落盘,满足 F1 可复现)。"""
    num_jobs: int
    num_machines: int
    num_agvs: int
    ops_per_job: int
    layout: str = "dumbbell"          # dumbbell | grid
    lu_exits: int = 2                 # LU 出口条数 = 漏斗宽度(容量旋钮)
    mid_lanes: int = 1                # 中段并行通道数(容量旋钮)
    mid_time: float = 6.0             # 中段单程时间(拉大则远端更贵)
    far_frac: float = 0.5             # 远端 RA 占比
    spur_time: float = 2.0            # 枢纽到 RA 的支线时间
    grid_rows: int = 3                # layout=grid 时的网格规模
    grid_cols: int = 3
    grid_time: float = 3.0
    heterogeneity: float = 0.3        # 目标 H(行内变异系数)
    flexibility: float = 0.6          # 目标 F(平均 |Ω| / NM)
    proc_lo: float = 8.0              # 工序名义难度区间(标定前的相对尺度)
    proc_hi: float = 24.0
    tt_tp_target: Optional[float] = 1.0   # 目标 T̄t/T̄p;None = 不标定
    delta_return: int = 1
    seed: int = 0
    tag: str = ""                     # 拥堵度档位名,仅用于命名与追溯

    def base_name(self) -> str:
        return f"S{self.num_jobs}x{self.num_machines}x{self.num_agvs}"

    def name(self) -> str:
        """规格 12.3 的命名规则: <基础>-L<布局>-H<异构>-F<柔性>-A<AGV>[-s<种子>]。"""
        layout = f"{self.layout[:1].upper()}{self.lu_exits}{self.mid_lanes}"
        return (f"{self.base_name()}-L{layout}-H{self.heterogeneity:g}"
                f"-F{self.flexibility:g}-A{self.num_agvs}-s{self.seed}")


# --------------------------------------------------------------------------
# 路网模板
# --------------------------------------------------------------------------


def _dumbbell(spec: InstanceSpec) -> Tuple[List[str], List[dict], List[str]]:
    """哑铃布局:LU --(lu_exits 条并行)--> 近端枢纽 --(mid_lanes 条并行)--> 远端枢纽。

    并行通道必须经由**互不相同的中间节点**实现:走廊的预约资源按端点对归并
    (network.corridor_id),同端点对的重复边会塌缩成同一个独占资源、达不到扩容
    效果。故每条通道插一个中间节点,并令两跳时间之和保持恒定。
    """
    nodes = ["v0", "h1", "h2"]
    corridors: List[dict] = []

    # LU -> 近端枢纽:k 条两跳通道,单程恒为 2
    for i in range(1, spec.lu_exits + 1):
        e = f"e{i}"
        nodes.append(e)
        corridors.append({"u": "v0", "v": e, "time": 1})
        corridors.append({"u": e, "v": "h1", "time": 1})

    # 近端 -> 远端:k 条两跳通道,单程恒为 mid_time
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
    """网格布局:路径冗余度高,作为低拥堵对照。LU 置于角点,RA 尽量分散。"""
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


_LAYOUTS = {"dumbbell": _dumbbell, "grid": _grid, "mesh": _mesh}


# --------------------------------------------------------------------------
# 加工时间(H / F 可控)
# --------------------------------------------------------------------------


def _pop_std(vals: List[float]) -> float:
    mean = sum(vals) / len(vals)
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))


def _omega_size(rng: random.Random, target: float, num_machines: int) -> int:
    """随机化取整,使 |Ω| 的期望等于 target,并夹到 [2, NM](B1)。"""
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
                zs = [max(-2.0, min(2.0, (r - mean) / sd)) for r in raw]
            else:
                zs = [0.0] * size
            row = {}
            for m, z in zip(sorted(omega), zs):
                row[m] = float(max(1, round(nominal * (1.0 + spec.heterogeneity * z))))
            proc[(j, i)] = row
    return proc


# --------------------------------------------------------------------------
# 组装
# --------------------------------------------------------------------------


def _mean_pairwise_travel(nodes: List[str], corridors: List[dict], lu: str,
                          machine_nodes: List[str]) -> float:
    """取放点(RA 节点 + LU)两两平均理想最短路时间,即 T̄t(与 feature_params 同口径)。"""
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
    """按 spec 生成一个 3.1 节 JSON schema 的算例字典(含自描述特征头)。"""
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
    return data


def measure(data: dict) -> dict:
    """对算例实测特征与下界,回填 `_features` 头(目标值 vs 实际值)。

    就地修改 `data` 并返回特征字典;幂等(`parse_instance` 忽略 `_` 开头的键)。
    对手写算例也可用。
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
# 拥堵度档位预设
# --------------------------------------------------------------------------

# 拥堵度档位。关键在于 high 与 funnel **只差 LU 出口容量**:
# 两者的中段争用完全相同(mid_lanes=1),但 funnel 额外把 LU 出口收成单点漏斗。
# 若各机制只在 high 上显示增益而在 funnel 上消失,即直接证明"决策无关拥堵
# 稀释机制信号"这一诊断(规格 3.1 实测修正)。
#
# 前四档存在一个盲区:mid/high/funnel 全是哑铃布局,改派换不掉争用走廊;唯一的
# 网格布局 low 又按设计是低拥堵对照。于是"高争用"与"路径多样"在前四档里从未
# 同时出现,而这恰是改派算子唯一可能奏效的区间。scatter 档补上这一格。
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
