"""受假设 A2 约束的解码:t_now 前的历史预提交,只从 t_now 接着排。

clbs.decode 每次从 t=0 重放。本模块不改 clbs 默认路径:
R0+ 在搜索期间把 ga.decode 临时换成 decode_from_now;
RD(cheap_baselines._redecode)直接调用本函数。实现见 node_engine.prefix_decode_nodes。

Decoding constrained by assumption A2: precommit the history before t_now and schedule only from
t_now on. R0+ swaps ga.decode for decode_from_now during search; RD calls it directly.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from algorithm.clbs_bridge import DecodeResult, Instance, Network
from algorithm.disturbance import Disturbance
from algorithm.node_engine import prefix_decode_nodes
from algorithm.schedule_io import ScheduleBundle

OpKey = Tuple[int, int]


def decode_from_now(
    inst: Instance,
    net: Network,
    ma: Dict[OpKey, int],
    os_seq: List[int],
    bundle: ScheduleBundle,
    dist: Disturbance,
    *,
    dead_agv: Optional[int] = None,
    dead_machine: Optional[int] = None,
    **_kwargs,
) -> DecodeResult:
    """与 clbs.decode 同签名的前缀冻结版;bundle/dist 由包装闭包注入。

    派车固定为节点模型下的试探派车(clbs_new 的 dispatch="exact");
    不可行染色体返回 makespan=1e18 的哑结果。

    Prefix-frozen version with the same signature as clbs.decode; bundle/dist are injected by
    the wrapping closure. An infeasible chromosome returns a dummy with makespan 1e18.
    """
    return prefix_decode_nodes(inst, net, ma, os_seq, bundle.tracked, bundle.result, dist,
                               dead_agv=dead_agv, dead_machine=dead_machine)
