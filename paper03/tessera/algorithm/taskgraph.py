"""从 BPMN 参考模型导出任务图与**互证超图**。

这是 TESSERA 相对 paper02 的关键差别所在。paper02 从同一批 BPMN 导出的是
可行性掩码 F(哪些转移允许)与物料流令牌不变量 I(工件守恒);本模块导出的是
**谁有资格为谁的状态迁移作证**。

导出原理:每个 serviceTask 的 Camunda http-connector url 是一条完整命令,
形如 `/vgr/pick_up_and_transport?resource=vgr_1&start=dm_2_sink_pos&end=ov_1_pos`,
设备/操作/起点/终点四元组直接可读。位置在活动间首尾相接,于是——

    活动 a 在位置 p 产出工件,活动 b 从位置 p 消耗工件,
    且 a、b 属于**不同设备类** ==> b 是 a "已完成并交付至 p" 的对手方见证者,
                                   同时 a 是 b "已从 p 取走" 的对手方见证者。

这个关系是**互证超图的边**。它的两个性质是本文第一贡献的依据:见证集合由
任务图而非无线拓扑决定,因此规模是 O(1) 且在任务下发时即可确定;串谋要求
边的两端同时被劫持,故抗串谋能力可归约到该图上的结构量(见 collusion.py)。

同设备类的连续操作**不构成互证**:没有独立的第二方传感证据,自证不成立。
这条是设计的核心,不是实现细节。

沿用 paper02 的两条手工规则(每条都是关于产线的一句陈述,不含可调参数):
  - 分拣机抽象输出位置 `sm_N_automatic_pos` 与 `sm_N_sink_{1,2,3}_pos` 同属
    一个别名类,运行时由检测到的颜色(eventBasedGateway 分支)决定。
  - 无 start/end 参数的原地操作作用于设备的规范位置 `<device>_pos`。
    这条使"搬运车把工件送到烤炉位、烤炉随后原地加工"被正确识别为一次交接。
  - 能力集与见证关系按**设备类**归并(`sm_2 -> sm`):16 个 BPMN 只实例化了
    一台分选机,按实例归并会误判 `sm_2` 的 44 次 `/sm/sort`(paper02 规则 13)。
"""
from __future__ import annotations

import glob
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
CAMUNDA = "{http://camunda.org/schema/1.0/bpmn}"

SORTER_POS = re.compile(r"(sm_\d+)_(automatic|sink_\d+)(_dropoff)?_pos$")


def device_class(device: str) -> str:
    """设备类 = 去掉实例后缀,如 sm_2 -> sm、vgr_1 -> vgr。"""
    head, sep, tail = device.rpartition("_")
    return head if sep and tail.isdigit() else device


def canonical_position(device: str) -> str:
    """无 start/end 参数的操作作用于设备的规范位置 `<device>_pos`。"""
    return f"{device}_pos"


@dataclass(frozen=True)
class WitnessEdge:
    """互证超图的一条边:`consumer` 为 `producer` 在 `pos` 的交付作证。

    两端是 (设备类, 操作) 而非设备实例:见证资格是设备类型的性质。
    """
    producer: tuple[str, str]
    consumer: tuple[str, str]
    pos: str
    workflow: str


@dataclass
class TaskGraph:
    """从 BPMN 导出的任务图与互证超图。"""
    positions: set[str] = field(default_factory=set)
    move_graph: set[tuple[str, str]] = field(default_factory=set)
    resources: set[str] = field(default_factory=set)
    operations: set[str] = field(default_factory=set)
    capable: dict[str, set[str]] = field(default_factory=dict)
    alias: dict[str, frozenset[str]] = field(default_factory=dict)
    witness_edges: set[WitnessEdge] = field(default_factory=set)
    n_models: int = 0
    #: 逐工作流的任务集合 {工作流: {(设备类, 操作)}}。**只供基线 `S3` 的一致性
    #: 检验使用**，本文的机制不读它。与 `witness_edges` 的区别是不过滤同类交接，
    #: 因为过程模型的语言包含同机顺序工序，一致性检验必须按完整语言判。
    wf_tasks: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    #: 逐工作流的顺序关系（传递闭包内的有序任务对），同样只供 `S3` 使用。
    wf_order: dict[str, set[tuple[tuple[str, str], tuple[str, str]]]] = field(
        default_factory=dict)

    def resolve(self, pos: str | None) -> frozenset[str]:
        """位置的别名类,含自身。"""
        if pos is None:
            return frozenset()
        return self.alias.get(pos) or frozenset({pos})

    def same_place(self, p: str | None, q: str | None) -> bool:
        return bool(self.resolve(p) & self.resolve(q))

    @property
    def handover_positions(self) -> set[str]:
        """发生跨设备类交接的位置。互证只可能发生在这些位置上。"""
        return {e.pos for e in self.witness_edges}

    def witnesses_of(self, device: str, op: str) -> set[tuple[str, str]]:
        """谁能为 (device, op) 的完成作证,返回 (设备类, 操作) 集合。"""
        key = (device_class(device), op)
        return {e.consumer for e in self.witness_edges if e.producer == key}

    def corroborable(self, device: str, op: str) -> bool:
        """该活动的完成在模型上是否存在对手方见证者。

        为假即落入**无对手方区间**——耦合互证在此失效,须由按需主动互证
        补足(见 coverage.py 与 `../paper03-NewIdea.md` 增补二)。
        """
        return bool(self.witnesses_of(device, op))


def _parse_bpmn(path: str):
    proc = ET.parse(path).getroot().find(BPMN + "process")
    tasks, edges = {}, []
    for st in proc.findall(BPMN + "serviceTask"):
        url = None
        for ip in st.iter(CAMUNDA + "inputParameter"):
            if ip.get("name") == "url":
                url = " ".join((ip.text or "").split())
        if not url or url == "TO_BE_SET":
            tasks[st.get("id")] = None
            continue
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        tasks[st.get("id")] = {"op": u.path, "resource": q.get("resource"),
                               "start": q.get("start"), "end": q.get("end")}
    for sf in proc.findall(BPMN + "sequenceFlow"):
        edges.append((sf.get("sourceRef"), sf.get("targetRef")))
    return tasks, edges


def _reachable_tasks(node, succ, tasks) -> set[str]:
    """顺序流上传递可达闭包内的 serviceTask。

    取直接后继会漏掉被其他设备任务隔开的操作对——paper02 记录这是 F 违反率
    从 14.73% 降到 0.00% 的主因之一,互证边的抽取同理。
    """
    seen, stack, out = set(), [node], set()
    while stack:
        n = stack.pop()
        for nxt in succ.get(n, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            stack.append(nxt)
            if tasks.get(nxt):
                out.add(nxt)
    return out


def produced_at(device: str, end_pos: str | None) -> str:
    """活动把工件交付到哪个位置。"""
    return end_pos or canonical_position(device)


def consumed_at(device: str, start_pos: str | None) -> str:
    """活动从哪个位置取走工件。"""
    return start_pos or canonical_position(device)


def _out_pos(task: dict) -> str:
    return produced_at(task["resource"], task["end"])


def _in_pos(task: dict) -> str:
    return consumed_at(task["resource"], task["start"])


def build_alias(positions) -> dict[str, frozenset[str]]:
    """分拣机别名类。必须并入日志中出现的位置,否则模型里未出现的
    `sm_2_automatic_pos` 会被误判(paper02 v2 -> v3 的修正)。
    """
    groups: dict[str, set[str]] = defaultdict(set)
    for p in positions:
        m = SORTER_POS.match(p)
        if m:
            groups[m.group(1)].add(p)
    return {p: frozenset(g) for g in groups.values() for p in g}


def load_bpmn(pattern: str | None = None, *,
              log_positions: set[str] | None = None) -> TaskGraph:
    """解析全部 BPMN,导出任务图与互证超图。"""
    pattern = pattern or default_bpmn_glob()
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"没有匹配的 BPMN: {pattern}")

    positions: set[str] = set()
    move_graph: set[tuple[str, str]] = set()
    resources: set[str] = set()
    operations: set[str] = set()
    capable: dict[str, set[str]] = defaultdict(set)
    raw_pairs: list[tuple[dict, dict, str]] = []

    for f in files:
        wf = os.path.splitext(os.path.basename(f))[0]
        tasks, edges = _parse_bpmn(f)
        succ: dict[str, set[str]] = defaultdict(set)
        for s, t in edges:
            succ[s].add(t)
        for tid, a in tasks.items():
            if a is None:
                continue
            resources.add(a["resource"])
            operations.add(a["op"])
            capable[device_class(a["resource"])].add(a["op"])
            positions.add(_out_pos(a))
            positions.add(_in_pos(a))
            if a["start"] and a["end"]:
                move_graph.add((a["start"], a["end"]))
            for bid in _reachable_tasks(tid, succ, tasks):
                b = tasks[bid]
                if b:
                    raw_pairs.append((a, b, wf))

    wf_tasks: dict[str, set[tuple[str, str]]] = defaultdict(set)
    wf_order: dict[str, set] = defaultdict(set)
    for a, b, wf in raw_pairs:
        ka = (device_class(a["resource"]), a["op"])
        kb = (device_class(b["resource"]), b["op"])
        wf_tasks[wf].update((ka, kb))
        wf_order[wf].add((ka, kb))

    alias = build_alias(positions | (log_positions or set()))
    graph = TaskGraph(positions=positions, move_graph=move_graph,
                      resources=resources, operations=operations,
                      capable=dict(capable), alias=alias,
                      n_models=len(files),
                      wf_tasks=dict(wf_tasks), wf_order=dict(wf_order))
    graph.witness_edges = {
        WitnessEdge(producer=(device_class(a["resource"]), a["op"]),
                    consumer=(device_class(b["resource"]), b["op"]),
                    pos=_out_pos(a), workflow=wf)
        for a, b, wf in raw_pairs
        if device_class(a["resource"]) != device_class(b["resource"])
        and graph.same_place(_out_pos(a), _in_pos(b))
    }
    return graph


def default_bpmn_glob() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(
        here, "..", "database", "ft_trier_iot_log", "bpmn-models", "*.bpmn"))
