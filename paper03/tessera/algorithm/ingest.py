"""XES 事件流解析与分链。

自 `paper02/slid/algorithm/ingest.py` 搬运加固化。下列约束是 paper02 在
**同一份日志**上的实测结论,不是本文的测量结果,改动前请先看 paper02 的
`README.md` 第三节:

  - 链的粒度必须是 **(设备, case)**。按设备全局时间线建链会让相邻两次操作
    分属不同 case,而参考模型的可达性是工作流内的,跨 case 边界不适用——
    曾据此误报出"仅 48.6% 转移落在 F 内",按 case 切分后是 100.0%(953/953)。
  - **本产线的设备是无状态服务端点**:2,109 条 (设备, case) 链中 65.1% 长度
    为 1,3,062 个活动只产出 953 次转移。设备内状态机在这个粒度上不存在。
    对 TESSERA 的推论是:观测单元取"任务交接事件"而非"设备内状态转移",
    这与耦合互证的设计吻合,因此本模块保留 `split_chains` 供对数用,
    互证逻辑不依赖它。
  - 时间必须取接收侧时间戳,绝不能用消息自带时间戳(后者攻击者可控)。

每个活动有三个生命周期事件,给出三个时刻:
    assigned    -> t_cmd    命令进入设备队列(命令账本的下发时刻)
    inProgress  -> t_start  操作开始
    complete    -> t_end    操作结束(取 inProgress 事件的 operation_end_time,
                            缺失时回落到 success/failure 事件的时间戳)
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Iterator, Sequence

XES = "{http://www.xes-standard.org/}"


@dataclass
class Activity:
    """一次活动实例,即协议的一个观测单元。"""
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
    planned_s: float | None = None   # planned_operation_time
    outcome: str | None = None       # success / failure
    params: dict = field(default_factory=dict)

    @property
    def order(self) -> int:
        """同一时刻的稳定排序键(event_id 在 Trier 中是递增整数)。"""
        return int(self.event_id) if self.event_id.isdigit() else 0

    @property
    def duration_s(self) -> float | None:
        if self.t_start and self.t_end:
            d = (self.t_end - self.t_start).total_seconds()
            return d if d > 0 else None
        return None

    @property
    def t_consume(self) -> datetime | None:
        """令牌消耗时刻(操作开始)。互证语义下即"我从某位置取走工件"。"""
        return self.t_start or self.t_cmd

    @property
    def t_produce(self) -> datetime | None:
        """令牌产出时刻(操作结束)。互证语义下即"我把工件放到某位置"。

        与 t_consume 分离是必须的:同时消耗产出会把并发活动误判为乱序
        (paper02 v3 -> v4 的修正)。
        """
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

    不要解压整包:含 IoT 传感器数据的子过程日志解压后达数十 GB,而任务级
    互证只需要主日志(约 11 MB)。传感层互证是待决项,见 `../../database/README.md`。
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


def valid(acts: Iterable[Activity], *, drop_failure: bool = True
          ) -> list[Activity]:
    """协议实际消费的活动:有设备、有操作、有开始时刻。

    `drop_failure=True` 是**离线建模**口径(paper02 实测 3,157 -> 3,062)。
    在线检测不得丢弃 failure:它本身就是需要解释的信号,且 P1 谎报完成攻击
    的一种形态正是把 failure 改写成 success。
    """
    out = [a for a in acts if a.device and a.op and a.t_consume is not None]
    if drop_failure:
        out = [a for a in out if a.outcome != "failure"]
    return out


def split_chains(acts: Iterable[Activity]
                 ) -> dict[tuple[str, str], list[Activity]]:
    """按 (设备, case) 切链,链内按操作开始时刻升序。仅供与 paper02 对数。"""
    chains: dict[tuple[str, str], list[Activity]] = {}
    for a in acts:
        chains.setdefault((a.device, a.case), []).append(a)
    for v in chains.values():
        v.sort(key=lambda a: (a.t_consume, a.order))
    return chains


def case_chains(acts: Iterable[Activity]) -> dict[str, list[Activity]]:
    """按 case 切链。互证的作用域是 case:位置是跨 case 共享的物理地点,
    跨 case 取对手方会把并发工件混为一谈(paper02 互锁通道 LATE 类违反的成因)。
    """
    chains: dict[str, list[Activity]] = {}
    for a in acts:
        chains.setdefault(a.case, []).append(a)
    for v in chains.values():
        v.sort(key=lambda a: (a.t_consume, a.order))
    return chains


def stream(acts: Sequence[Activity]) -> Iterator[Activity]:
    """按接收时刻回放为在线消息流,供协议逐条消费。"""
    yield from sorted(acts, key=lambda a: (a.t_consume, a.order))


def default_log_path() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(
        here, "..", "database", "ft_trier_iot_log", "MainProcess_cleaned.xes"))
