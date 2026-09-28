"""M2 可行性掩码 F 与互锁不变量 I,从参考过程模型自动导出。

已在 Trier 的 16 个 Camunda BPMN 上验证:每个 serviceTask 的 http-connector
url 就是一条完整命令,形如
    /vgr/pick_up_and_transport?resource=vgr_1&start=dm_2_sink_pos&end=ov_1_pos
即**设备、操作、起点、终点四元组直接写在模型里**。自动抽出 15 个资源、
23 个位置、31 条物料流边、16 组设备内操作对。

实测违反率(清洗版 282 个 case、3,062 个活动、排除 failure):
    F  0.00%  (953/953)   -> 可作硬约束
    I  1.70%  (47/2768)   -> 只能作软证据

I 的残余成因已定位:29 次缺失事件、17 次跨 case 乱序、1 次生产者失败。
乱序的根因是位置为跨 case 共享的物理地点而令牌模型是逐 case 的;若产线
具备 RFID/NFC 工件身份(Trier 的 `use_nfc` 参数表明真实可得),I 可上升
为硬约束。

**领域知识用量核算**(回应"你手工塞了多少先验"):自动导出 23 个位置、
31 条物料流边、16 组设备内操作对;手工指定的只有下面 6 条规则,每条都是
关于产线的一句陈述,不含可调参数。

M2 feasibility mask F and interlock invariants I, exported automatically from the reference process model.

Validated on Trier's 16 Camunda BPMN models: each serviceTask's http-connector url is a complete command, of the form
    /vgr/pick_up_and_transport?resource=vgr_1&start=dm_2_sink_pos&end=ov_1_pos
so the **quadruple of device, operation, start, and end is written directly in the model**. Extraction yields 15 resources, 23 positions, 31 material-flow edges, and 16 within-device operation pairs.

Measured violation rates (cleaned edition, 282 cases, 3,062 activities, failures excluded):
    F  0.00%  (953/953)   -> may be a hard constraint
    I  1.70%  (47/2768)   -> soft evidence only

The residual causes of I are located: 29 missing events, 17 cross-case order violations, 1 producer failure. The order violations come from positions being physical places shared across cases while the token model is per case. If the line has RFID/NFC workpiece identity (Trier's `use_nfc` parameter shows it is really available), I can be raised to a hard constraint.

**Accounting of domain knowledge** (answering "how much prior did you insert by hand"): 23 positions, 31 material-flow edges, and 16 within-device operation pairs are exported automatically. Only the 6 rules below are specified by hand, each one sentence about the line, with no tunable parameter.
"""
from __future__ import annotations

import glob
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
CAMUNDA = "{http://camunda.org/schema/1.0/bpmn}"

WORKPIECE, BUCKET = "wp", "bk"

# 手工规则 1-4:仓库操作的令牌语义(消耗, 产出)。工件与料桶是两种令牌,
# 用单一令牌类型会把二者混为一谈(v1 的 14.87% 违反率主因之一)。
# Manual rules 1-4: token semantics of warehouse operations (consume, produce).
# Workpiece and bucket are two token types; one type conflates them (a main cause of the 14.87% violation rate in v1).
HBW_TOKEN_EFFECTS: dict[str, tuple[list[str], list[str]]] = {
    "/hbw/unload":             ([], [WORKPIECE, BUCKET]),
    "/hbw/get_empty_bucket":   ([], [BUCKET]),
    "/hbw/store_empty_bucket": ([BUCKET], []),
    "/hbw/store":              ([WORKPIECE, BUCKET], []),
}
# 手工规则 5:分拣机抽象输出位置的别名类。sm_N_automatic_pos 物理上解析为
# sm_N_sink_{1,2,3}_pos,由运行时检测到的颜色决定(eventBasedGateway 分支)。
# Manual rule 5: alias class of the sorter's abstract output position. sm_N_automatic_pos
# physically resolves to sm_N_sink_{1,2,3}_pos, chosen by the color detected at runtime (eventBasedGateway branch).
SORTER_POS = re.compile(r"(sm_\d+)_(automatic|sink_\d+)(_dropoff)?_pos$")
# 手工规则 6:同一设备连续重复同一操作视为重试,不算新转移(见 allows)。
# Manual rule 6: repeating the same operation on one device is a retry, not a new transition (see allows).


@dataclass
class ProcessModel:
    """从 BPMN 导出的结构知识。

    Structural knowledge exported from BPMN.
    """
    positions: set[str] = field(default_factory=set)
    move_graph: set[tuple[str, str]] = field(default_factory=set)
    feasible: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    alias: dict[str, frozenset[str]] = field(default_factory=dict)
    resources: set[str] = field(default_factory=set)
    operations: set[str] = field(default_factory=set)
    #: 设备 -> 该设备在任一模型里承担过的操作集合(F 的**一元**部分)
    #: device -> operations that device performs in any model (the unary part of F)
    capable: dict[str, set[str]] = field(default_factory=dict)
    n_models: int = 0

    @property
    def n_feasible_pairs(self) -> int:
        return sum(len(v) for v in self.feasible.values())

    def allows(self, device: str, op_from: str, op_to: str) -> bool:
        """F 的二元部分。op_from == op_to 为重试(手工规则 6),恒允许。

        **只在同一 case 内同设备有前驱时才可查**,实测覆盖率仅 31%
        (3,062 个活动 -> 953 次检查)。跨 case 取前驱会误报 48.6%,不可行。

        Binary part of F. op_from == op_to is a retry (manual rule 6) and is always allowed.

        **Queryable only when the same device has a predecessor inside the same case.** Measured coverage is only 31% (3,062 activities -> 953 checks). Taking the predecessor across cases false-alarms at 48.6% and is not usable.
        """
        if op_from == op_to:
            return True
        return (op_from, op_to) in self.feasible.get(device, ())

    def can_perform(self, device: str, op: str) -> bool:
        """F 的**一元**部分:这台设备到底允不允许做这个操作。

        不需要前驱,故**覆盖 100% 的消息**,补上二元部分 31% 覆盖率的缺口。
        "错误的设备做了正确的操作"这类注入只能靠它——case 级结构通道的状态
        是操作名因而设备盲;把状态换成 (设备,操作) 又会让未见组合变成词表外
        状态而**弃权**,并且校准失效(见 tools/struct_diag.py)。
        能力集按**设备类**(去掉实例后缀)归并,不按实例:16 个 BPMN 只实例化
        了一台分选机,于是 `sm_2` 的 44 次 `/sm/sort` 会被实例级能力集误判为
        违反(1.44%),而按类归并后归零。这与已有的分选机别名类是同一条规则,
        物理上也成立——同型设备当然承担同样的操作。代价是失去"sm_2 做了只
        有 sm_1 该做的事"这种区分,但参考模型本就没有这个信息。

        未在任何模型中出现过的设备类按"未知"放过,与副产品一的口径一致:
        参考模型覆盖率不是 100%,未建模行为不算违反。

        **Unary** part of F: whether this device is allowed to perform this operation at all.

        No predecessor is required, so it **covers 100% of messages** and fills the 31% coverage gap of the binary part. Injections of the form "the wrong device performs the right operation" can only be caught here — the case-level structural channel's state is the operation name and is therefore device-blind; replacing the state with (device, operation) turns unseen pairs into out-of-vocabulary states and **abstains**, and calibration fails (see tools/struct_diag.py). The capability set is merged by **device class** (instance suffix removed), not by instance: the 16 BPMN models instantiate only one sorter, so an instance-level capability set would falsely flag sm_2's 44 `/sm/sort` events (1.44%), and merging by class brings that to zero. This is the same rule as the existing sorter alias class, and it holds physically — devices of the same type perform the same operations. The cost is losing the distinction "sm_2 did something only sm_1 should do", but the reference model does not contain that information.

        A device class that appears in no model is passed as "unknown", consistent with byproduct 1: reference-model coverage is not 100%, and unmodeled behavior is not a violation.
        """
        allowed = self.capable.get(device_class(device))
        return True if not allowed else op in allowed

    def token_effects(self, act) -> tuple[list[tuple[str, str]],
                                          list[tuple[str, str]]]:
        """活动的令牌消耗/产出对 [(令牌类型, 位置), ...]。

        三种形态:带起终点的搬运消耗起点产出终点;仓库操作按手工规则 1-4;
        其余原地加工在设备规范位置上消耗并产出(占位,表达"工件必须在此")。

        An activity's token consume/produce pairs [(token type, position), ...].

        Three shapes: a move with start and end consumes the start and produces the end; warehouse operations follow manual rules 1-4; other in-place processing consumes and produces at the device's canonical position (a placeholder meaning "the workpiece must be here").
        """
        if act.start_pos and act.end_pos:
            return ([(WORKPIECE, act.start_pos)], [(WORKPIECE, act.end_pos)])
        pos = canonical_position(act.device)
        if act.op in HBW_TOKEN_EFFECTS:
            cons, prod = HBW_TOKEN_EFFECTS[act.op]
            return ([(t, pos) for t in cons], [(t, pos) for t in prod])
        return ([(WORKPIECE, pos)], [(WORKPIECE, pos)])

    def resolve(self, pos: str) -> frozenset[str]:
        """位置的别名类,含自身。

        Alias class of a position, including itself.
        """
        return self.alias.get(pos) or frozenset({pos})


def device_class(device: str) -> str:
    """设备类 = 去掉实例后缀,如 sm_2 -> sm、vgr_1 -> vgr。

    Device class = drop the instance suffix, e.g. sm_2 -> sm, vgr_1 -> vgr.
    """
    head, sep, tail = device.rpartition("_")
    return head if sep and tail.isdigit() else device


def canonical_position(device: str) -> str:
    """无 start/end 参数的操作作用于设备的规范位置 `<device>_pos`。

    An operation with no start/end parameter acts at the device's canonical position `<device>_pos`.
    """
    return f"{device}_pos"


def _parse_bpmn(path: str):
    proc = ET.parse(path).getroot().find(BPMN + "process")
    acts, edges = {}, []
    for st in proc.findall(BPMN + "serviceTask"):
        url = None
        for ip in st.iter(CAMUNDA + "inputParameter"):
            if ip.get("name") == "url":
                url = " ".join((ip.text or "").split())
        if not url or url == "TO_BE_SET":
            acts[st.get("id")] = None
            continue
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        acts[st.get("id")] = {"op": u.path, "resource": q.get("resource"),
                              "start": q.get("start"), "end": q.get("end")}
    for sf in proc.findall(BPMN + "sequenceFlow"):
        edges.append((sf.get("sourceRef"), sf.get("targetRef")))
    return acts, edges


def _reachable_tasks(node, succ, acts):
    """顺序流上的**传递可达闭包**内的 serviceTask。

    取直接后继会漏掉被其他设备任务隔开的同设备操作对——这是 F 违反率
    从 14.73% 降到 0.00% 的主因之一。

    serviceTasks inside the **transitive reachable closure** on the sequence flow.

    Taking only the direct successor misses same-device operation pairs separated by another device's task — one of the main reasons the F violation rate fell from 14.73% to 0.00%.
    """
    seen, stack, out = set(), [node], set()
    while stack:
        n = stack.pop()
        for nxt in succ.get(n, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            stack.append(nxt)
            if acts.get(nxt):
                out.add(nxt)
    return out


def build_alias(positions) -> dict[str, frozenset[str]]:
    """手工规则 5 的实现:按命名约定聚出分拣机别名类。

    别名闭包必须**同时包含日志里出现的位置**,否则模型中未出现的
    sm_2_automatic_pos 会被误判为违反(v2 -> v3 的修正)。

    Implementation of manual rule 5: group sorter alias classes by the naming convention.

    The alias closure must **also contain positions that appear in the log**. Otherwise sm_2_automatic_pos, which is absent from the model, is falsely flagged as a violation (the v2 -> v3 fix).
    """
    groups = defaultdict(set)
    for p in positions:
        m = SORTER_POS.match(p)
        if m:
            groups[m.group(1)].add(p)
    return {p: frozenset(g) for g in groups.values() for p in g}


def load_bpmn(pattern: str, *, log_positions: set[str] | None = None
              ) -> ProcessModel:
    """解析全部 BPMN。`log_positions` 用于把日志中出现的位置并入别名闭包。

    Parse every BPMN. `log_positions` merges positions that appear in the log into the alias closure.
    """
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"没有匹配的 BPMN: {pattern}")
    move_graph: set[tuple[str, str]] = set()
    feasible: dict[str, set[tuple[str, str]]] = defaultdict(set)
    positions: set[str] = set()
    resources: set[str] = set()
    operations: set[str] = set()
    capable: dict[str, set[str]] = defaultdict(set)

    for f in files:
        acts, edges = _parse_bpmn(f)
        succ = defaultdict(set)
        for s, t in edges:
            succ[s].add(t)
        for aid, a in acts.items():
            if a is None:
                continue
            resources.add(a["resource"])
            operations.add(a["op"])
            capable[device_class(a["resource"])].add(a["op"])
            for p in (a["start"], a["end"]):
                if p:
                    positions.add(p)
            if not (a["start"] and a["end"]):
                positions.add(canonical_position(a["resource"]))
            if a["start"] and a["end"]:
                move_graph.add((a["start"], a["end"]))
            for bid in _reachable_tasks(aid, succ, acts):
                b = acts[bid]
                if b and b["resource"] == a["resource"]:
                    feasible[a["resource"]].add((a["op"], b["op"]))

    alias = build_alias(positions | (log_positions or set()))
    return ProcessModel(positions=positions, move_graph=move_graph,
                        feasible=dict(feasible), alias=alias,
                        resources=resources, operations=operations,
                        capable=dict(capable), n_models=len(files))


def coverage(model: ProcessModel, activities) -> tuple[float, dict]:
    """参考模型对观测物料移动的覆盖率。

    Trier 上实测 97.4%——未建模的移动(如 sm_2_automatic_pos,在任何 BPMN
    中都不存在)必须按"未知"处理,不能记为违反。返回 (覆盖率, 未建模计数)。

    Coverage of observed material moves by the reference model.

    Measured 97.4% on Trier — unmodeled moves (such as sm_2_automatic_pos, which exists in no BPMN) must be treated as "unknown" and must not be counted as violations. Returns (coverage, unmodeled counts).
    """
    checked = 0
    gaps: dict[tuple[str, str], int] = defaultdict(int)
    for a in activities:
        if not a.is_move:
            continue
        checked += 1
        if (a.start_pos, a.end_pos) not in model.move_graph:
            gaps[(a.start_pos, a.end_pos)] += 1
    n_gap = sum(gaps.values())
    return (1.0 - n_gap / checked if checked else 1.0), dict(gaps)


def default_bpmn_glob() -> str:
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(
        here, "..", "database", "ft_trier_iot_log", "bpmn-models", "*.bpmn"))
