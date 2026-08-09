"""在 clbs Router 构造时注入走廊阻断,使 run_ga / decode 与 STRC 修复面对同一扰动。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, List, Optional, Sequence, Tuple

from algorithm.clbs_bridge import Router
from algorithm.disturbance import Disturbance

BlockWin = Tuple[str, float, float]

# 当前激活的阻断列表(可多段);None 表示未激活
_ACTIVE_BLOCKS: Optional[List[BlockWin]] = None
_ORIG_INIT = Router.__init__


def block_windows_from_dist(dist: Disturbance) -> List[BlockWin]:
    """从 Disturbance 解析阻断窗:优先 extra['blocks'],否则单走廊字段。"""
    raw = dist.extra.get("blocks") if dist.extra else None
    if raw:
        return [(str(c), float(a), float(b)) for c, a, b in raw]
    if dist.type not in ("corridor_block", "corridor_slowdown"):
        return []
    if not dist.corridor:
        raise ValueError("corridor_block requires corridor or extra['blocks']")
    t0 = float(dist.t_start if dist.t_start is not None else dist.t_now)
    t1 = float(dist.t_end if dist.t_end is not None else dist.t_now + 1e6)
    return [(dist.corridor, t0, t1)]


def _patched_init(self, *args, **kwargs):
    _ORIG_INIT(self, *args, **kwargs)
    blocks = _ACTIVE_BLOCKS
    if not blocks:
        return
    for cid, t0, t1 in blocks:
        self.table.reserve(cid, t0, t1, 0, "__BLOCK__")


@contextmanager
def corridor_block_active(dist: Disturbance) -> Iterator[None]:
    """进入后,所有新建 Router 都会带上 dist 中的阻断窗。"""
    global _ACTIVE_BLOCKS
    blocks = block_windows_from_dist(dist)
    if not blocks:
        yield
        return
    prev = _ACTIVE_BLOCKS
    prev_init = Router.__init__
    try:
        _ACTIVE_BLOCKS = list(blocks)
        Router.__init__ = _patched_init  # type: ignore[method-assign]
        yield
    finally:
        _ACTIVE_BLOCKS = prev
        Router.__init__ = prev_init  # type: ignore[method-assign]
