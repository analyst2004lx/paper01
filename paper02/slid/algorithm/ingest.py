"""M1 事件流解析与按设备分链。

把原始日志解析成统一的活动实例流,并切分成检测器实际消费的链。

关键约束(实测得出,不可改动):
  - 在线检测器一律按 **(设备, case)** 维护链上下文,不能按设备全局时间线。
    按设备全局建链会让相邻两次操作分属不同 case,而可行性掩码 F 来自工作流
    内可达性,跨 case 边界不适用——曾据此误报出"仅 48.6% 转移落在 F 内",
    按 case 切分后是 100.0%(953/953)。日志的 `case` 字段与命令 URL 的
    `business_key` 使这在工程上可行。
  - **结构通道消费哪一层的序列取决于设备语义**,见 chain_granularity():
    有状态设备用 (设备, case) 链,无状态服务端点用 case 级链。
  - 时间必须取接收侧时间戳,绝不能用消息自带时间戳(后者攻击者可控)。

Trier 数据集的每个活动有三个生命周期事件,给出三个时刻:
    scheduled/assigned  -> t_cmd    命令进入设备队列
    start/inProgress    -> t_start  操作开始
    complete/success    -> t_end    操作结束(取 inProgress 事件的
                                    operation_end_time,缺失时回落到
                                    success/failure 事件的时间戳)
"""
from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Iterator, Sequence

XES = "{http://www.xes-standard.org/}"


@dataclass
class Activity:
    """一次活动实例,即检测器的一个观测单元。"""
    case: str
    event_id: str
    device: str                      # org:resource
    op: str                          # concept:name,如 /vgr/pick_up_and_transport
    workflow: str | None = None      # process_model_id
    t_cmd: datetime | None = None    # assigned
    t_start: datetime | None = None  # inProgress
    t_end: datetime | None = None    # operation_end_time of inProgress
    t_done: datetime | None = None   # success / failure 事件时间戳
    start_pos: str | None = None     # parameter_start_position
    end_pos: str | None = None       # parameter_end_position
    planned_s: float | None = None   # planned_operation_time,仅作冷启动先验
    outcome: str | None = None       # success / failure
    params: dict = field(default_factory=dict)

    @property
    def order(self) -> int:
        """同一时刻的稳定排序键(event_id 在 Trier 中是递增整数)。"""
        return int(self.event_id) if self.event_id.isdigit() else 0

    @property
    def duration_s(self) -> float | None:
        """执行时长。派发阶段时长不在此暴露:实测 p95 达 253.6 s、
        sigma_log=1.475,由调度器排队竞争主导,不可作时长检验。"""
        if self.t_start and self.t_end:
            d = (self.t_end - self.t_start).total_seconds()
            return d if d > 0 else None
        return None

    @property
    def t_consume(self) -> datetime | None:
        """令牌消耗时刻(操作开始)。"""
        return self.t_start or self.t_cmd

    @property
    def t_produce(self) -> datetime | None:
        """令牌产出时刻(操作结束)。与 t_consume 分离是必须的:同时消耗产出
        会把并发活动误判为乱序(v3 -> v4 的修正)。"""
        return self.t_end or self.t_done or self.t_consume

    @property
    def route(self) -> tuple[str, str] | None:
        if self.start_pos and self.end_pos:
            return (self.start_pos, self.end_pos)
        return None

    @property
    def is_move(self) -> bool:
        return bool(self.start_pos and self.end_pos)


def _parse_planned(s: str | None) -> float | None:
    """`planned_operation_time` 形如 '0 days 00:00:52'。"""
    if not s:
        return None
    try:
        days, clock = s.split(" days ")
        h, m, sec = clock.split(":")
        return int(days) * 86400 + int(h) * 3600 + int(m) * 60 + float(sec)
    except (ValueError, AttributeError):
        return None


def _iter_events(source):
    for trace in ET.parse(source).getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            yield ev


def _event_fields(ev):
    attrs, params = {}, {}
    for child in ev:
        if child.tag == XES + "list" and child.get("key") == "parameters":
            for vals in child:
                for v in vals:
                    params[v.get("key")] = v.get("value")
        elif child.get("key"):
            attrs[child.get("key")] = child.get("value")
    return attrs, params


def read_xes(path: str, member: str | None = None) -> list[Activity]:
    """读 XES 主日志。`member` 非空或 path 是 zip 时从压缩包内流式读取。

    不要解压整包:清洗版解压后 66.6 GB、含错版 54.2 GB,而全部分析只需要
    其中的 MainProcess.xes(约 10 MB)。
    """
    if member or path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            name = member or next(n for n in zf.namelist()
                                  if n.endswith("MainProcess_cleaned.xes")
                                  or n.endswith("MainProcess.xes"))
            with zf.open(name) as fh:
                return _build(fh)
    with open(path, "rb") as fh:
        return _build(fh)


def _build(source) -> list[Activity]:
    by_key: dict[tuple[str, str], Activity] = {}
    for ev in _iter_events(source):
        a, params = _event_fields(ev)
        case, eid = a.get("case"), a.get("event_id")
        if case is None or eid is None:
            continue
        act = by_key.get((case, eid))
        if act is None:
            act = Activity(
                case=case, event_id=eid,
                device=a.get("org:resource") or "",
                op=a.get("concept:name") or "",
                workflow=a.get("process_model_id"),
                start_pos=params.get("parameter_start_position"),
                end_pos=params.get("parameter_end_position"),
                planned_s=_parse_planned(a.get("planned_operation_time")),
                params=params,
            )
            by_key[(case, eid)] = act
        st = a.get("lifecycle:state")
        ts = a.get("time:timestamp")
        when = datetime.fromisoformat(ts) if ts else None
        if st == "assigned":
            act.t_cmd = when
        elif st == "inProgress":
            act.t_start = when
            if a.get("operation_end_time"):
                act.t_end = datetime.fromisoformat(a["operation_end_time"])
        elif st in ("success", "failure"):
            act.t_done = when
            act.outcome = st
    return list(by_key.values())


def read_hai(path: str) -> list[Activity]:
    """读 HAI。1 Hz 轮询,时序通道须走区间删失分支。"""
    raise NotImplementedError("HAI 适配器待实现;时序通道须用 interval 分支")


def valid(acts: Iterable[Activity], *, drop_failure: bool = True):
    """检测器实际消费的活动:有设备、有操作、有开始时刻。

    `drop_failure=True` 时排除 failure——这是**离线建模**的口径(时长分布
    必须按 success/failure 分层,见结论三)。在线检测不得丢弃 failure,
    它本身就是需要解释的信号。
    """
    out = [a for a in acts if a.device and a.op and a.t_consume is not None]
    if drop_failure:
        out = [a for a in out if a.outcome != "failure"]
    return out


def split_chains(acts: Iterable[Activity]) -> dict[tuple[str, str], list[Activity]]:
    """按 (设备, case) 切链,链内按操作开始时刻升序。"""
    chains: dict[tuple[str, str], list[Activity]] = {}
    for a in acts:
        chains.setdefault((a.device, a.case), []).append(a)
    for v in chains.values():
        v.sort(key=lambda a: (a.t_consume, a.order))
    return chains


def case_chains(acts: Iterable[Activity]) -> dict[str, list[Activity]]:
    """按 case 切链,用于 case 级工作流结构通道。"""
    chains: dict[str, list[Activity]] = {}
    for a in acts:
        chains.setdefault(a.case, []).append(a)
    for v in chains.values():
        v.sort(key=lambda a: (a.t_consume, a.order))
    return chains


def chain_granularity(acts: Iterable[Activity], *,
                      min_mean_len: float = 2.0) -> tuple[str, dict]:
    """自动判别结构通道该用哪一层的序列。

    判据:设备是否具有跨作业持续的内部状态机。可用两个可观测量代理——
    每条 (设备, case) 链的平均长度,以及产生的转移总数。平均长度 < 2 说明
    设备是被调用的无状态服务端点,设备级结构通道退化(Trier 实测:65.1% 的
    链长度为 1,3,062 个活动只产出 953 次转移,结构 p 值取值唯一)。

    返回 ('device'|'case', 诊断量)。
    """
    chains = split_chains(acts)
    if not chains:
        return "case", {"n_chains": 0}
    lens = [len(v) for v in chains.values()]
    n_trans = sum(max(0, n - 1) for n in lens)
    mean_len = sum(lens) / len(lens)
    frac_singleton = sum(1 for n in lens if n == 1) / len(lens)
    diag = {"n_chains": len(chains), "mean_len": mean_len,
            "frac_singleton": frac_singleton, "n_transitions": n_trans}
    return ("device" if mean_len >= min_mean_len else "case"), diag


def stream(acts: Sequence[Activity]) -> Iterator[Activity]:
    """按接收时刻回放为在线消息流,供检测器逐条消费。"""
    yield from sorted(acts, key=lambda a: (a.t_consume, a.order))


def default_log_path() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(
        here, "..", "database", "ft_trier_iot_log", "MainProcess_cleaned.xes"))
