"""扰动注入:走廊阻断装进预约表,路段降速改路由层 τ。

二者必须分开。旧实现把 corridor_slowdown 写成一段 __BLOCK__,路由层无法再走
那条走廊,修复可行率因此是假阳性(过近似成了阻断)。降速的物理含义是走廊仍可通行,
只把与扰动窗重叠的那一段进度按倍率拉长,窗外仍走原 τ。
"""
from __future__ import annotations

import heapq
from contextlib import contextmanager
from typing import Callable, Iterator, List, Optional, Sequence, Tuple

from algorithm.clbs_bridge import Router
from algorithm.disturbance import Disturbance

BlockWin = Tuple[str, float, float]
SlowWin = Tuple[str, float, float, float]  # cid, t0, t1, mult
TauFn = Callable[[str, float, float], float]

# 当前激活的阻断列表(可多段);None 表示未激活
_ACTIVE_BLOCKS: Optional[List[BlockWin]] = None
_ORIG_INIT = Router.__init__


def block_windows_from_dist(dist: Disturbance) -> List[BlockWin]:
    """从 Disturbance 解析阻断窗:优先 extra['blocks'],否则单走廊字段。

    只对 corridor_block 生效。降速不再走这条通道。
    """
    raw = dist.extra.get("blocks") if dist.extra else None
    if raw:
        return [(str(c), float(a), float(b)) for c, a, b in raw]
    if dist.type != "corridor_block":
        return []
    if not dist.corridor:
        raise ValueError("corridor_block requires corridor or extra['blocks']")
    t0 = float(dist.t_start if dist.t_start is not None else dist.t_now)
    t1 = float(dist.t_end if dist.t_end is not None else dist.t_now + 1e6)
    return [(dist.corridor, t0, t1)]


def slowdown_windows_from_dist(dist: Disturbance) -> List[SlowWin]:
    """降速窗:走廊仍可走,与窗重叠的那一段进度按 tau_mult 拉长。

    路由层只缩放 t_now 之后的占用——t_now 之前已经走完的腿按假设 A2 保持原时长。
    """
    if dist.type != "corridor_slowdown":
        return []
    if not dist.corridor:
        raise ValueError("corridor_slowdown requires corridor")
    raw0 = float(dist.t_start if dist.t_start is not None else dist.t_now)
    t1 = float(dist.t_end if dist.t_end is not None else dist.t_now + 1e6)
    t0 = max(raw0, float(dist.t_now))
    if t0 >= t1:
        return []
    mult = float(dist.tau_mult if dist.tau_mult is not None else 2.0)
    return [(dist.corridor, t0, t1, mult)]


def _mult_at(t: float, segs: Sequence[Tuple[float, float, float]]) -> float:
    m = 1.0
    for t0, t1, mm in segs:
        if t0 <= t < t1:
            m = max(m, mm)
    return m


def piecewise_duration(
    enter: float, tau0: float,
    segs: Sequence[Tuple[float, float, float]],
) -> float:
    """走廊标准化为长度 1:窗外速度 1/τ,窗内 1/(τ·mult),按时间切段积分。

    segs 为该走廊上的 (t0, t1, mult);重叠窗取较大倍率。无窗则退回 τ。
    """
    tau0 = float(tau0)
    if tau0 <= 0.0:
        return 0.0
    if not segs:
        return tau0
    max_m = max(m for _a, _b, m in segs)
    cuts = {enter}
    for t0, t1, _m in segs:
        if t1 > enter:
            cuts.add(max(float(t0), enter))
            cuts.add(float(t1))
    times = sorted(c for c in cuts if c >= enter - 1e-12)
    times.append(enter + tau0 * (max_m + 1.0) + 1.0)

    progress = 0.0
    t = enter
    i = 0
    while progress < 1.0 - 1e-12:
        while i < len(times) and times[i] <= t + 1e-12:
            i += 1
        t_next = times[i] if i < len(times) else t + tau0 * 10.0
        speed = 1.0 / (tau0 * _mult_at(t, segs))
        need = (1.0 - progress) / speed
        if t + need <= t_next + 1e-12:
            return (t + need) - enter
        progress += (t_next - t) * speed
        t = t_next
    return t - enter


def effective_tau(cid: str, t: float, tau: float,
                  windows: Sequence[SlowWin]) -> float:
    """进入时刻 t 穿越 cid 的有效时长:只缩放与降速窗重叠的进度。"""
    segs = [(t0, t1, m) for c, t0, t1, m in windows if c == cid]
    return piecewise_duration(t, tau, segs)


def _earliest_var(
    router: Router, cid: str, t_ready: float, tau0: float, tau_of: TauFn,
) -> Tuple[float, float]:
    """变时长占用的最早进入:对每个候选时刻用该时刻的有效 τ 检查空档。

    旧的两步 earliest_entry 会在「窗内 2τ 无空档、窗外 τ 有空档」时把进入时刻
    拉回窗内却仍按原 τ 落盘,校验再按倍率拒掉。这里进入时刻与时长必须一致。
    """
    table = router.table
    for cand in table._entry_candidates(cid, t_ready):
        tau = tau_of(cid, cand, tau0)
        if table._is_free(cid, cand, tau):
            return cand, tau
    ends = [b for _a, b, _agv, _task in table._res.get(cid, [])]
    enter = max([t_ready] + ends)
    return enter, tau_of(cid, enter, tau0)


def _search_earliest_scaled(
    router: Router, start: str, goal: str, t0: float, tau_of: TauFn,
) -> Tuple[list, float, float]:
    """与 Router._search_earliest 同构,只把 tau 换成 tau_of(cid, enter, tau0)。"""
    from algorithm.clbs_bridge import Segment

    if start == goal:
        return [], t0, 0.0
    best = {start: t0}
    prev = {}
    heap: List[Tuple[float, str]] = [(t0, start)]
    while heap:
        t, u = heapq.heappop(heap)
        if t > best.get(u, float("inf")):
            continue
        if u == goal:
            break
        for cid, v, tau0 in router.net.adj[u]:
            enter, tau = _earliest_var(router, cid, t, tau0, tau_of)
            arr = enter + tau
            if arr < best.get(v, float("inf")):
                best[v] = arr
                prev[v] = (u, cid, enter, arr)
                heapq.heappush(heap, (arr, v))
    if goal not in best:
        raise RuntimeError(f"路由失败: {start} -> {goal}(路网不连通?)")
    segs = []
    node = goal
    while node != start:
        u, cid, enter, exit_ = prev[node]
        segs.append(Segment(cid, u, node, enter, exit_))
        node = u
    segs.reverse()
    cost = 0.0
    if router.prices is not None:
        cost = sum(router.prices.interval_cost(s.corridor, s.enter, s.exit)
                   for s in segs)
    return segs, best[goal], cost


def attach_slowdown(router: Router, dist: Disturbance) -> None:
    """把降速窗绑到这一台 Router 上,不改类方法,避免泄漏到后续构造。"""
    wins = slowdown_windows_from_dist(dist)
    if not wins:
        return

    def tau_of(cid: str, t: float, tau0: float) -> float:
        return effective_tau(cid, t, tau0, wins)

    def earliest(start: str, goal: str, t0: float):
        return _search_earliest_scaled(router, start, goal, t0, tau_of)

    router._search_earliest = earliest  # type: ignore[method-assign]
    router._search_priced = earliest  # type: ignore[method-assign]


def is_expected_slowdown_duration_error(msg: str, dist: Disturbance, net) -> bool:
    """clbs 校验 (d) 按静态 τ 卡时长;降速窗内的占用本就该是 τ×mult。"""
    import re
    wins = slowdown_windows_from_dist(dist)
    if not wins or "通行时间不符" not in msg:
        return False
    m = re.search(
        r"走廊 (\S+)->(\S+) 通行时间不符: ([\d.]+)-([\d.]+) !=", msg)
    if not m:
        return False
    u, v, exit_s, enter_s = m.group(1), m.group(2), m.group(3), m.group(4)
    enter, exit_ = float(enter_s), float(exit_s)
    cid = f"{u}|{v}" if u <= v else f"{v}|{u}"
    dur = exit_ - enter
    for c, t0, t1, mult in wins:
        if c != cid or not (enter < t1 and exit_ > t0):
            continue
        tau0 = net.corridor_time.get(cid)
        if tau0 is None:
            continue
        need = effective_tau(c, enter, tau0, wins)
        if abs(dur - need) <= 1e-6 or abs(dur - tau0 * mult) <= 1e-6:
            return True
    return False


def check_slowdown_durations(result, dist: Disturbance, net) -> List[str]:
    """修复后仍按未缩放 τ 占用降速窗,视为未吸收扰动。"""
    wins = slowdown_windows_from_dist(dist)
    if not wins:
        return []
    from algorithm.schedule_io import reservations_from_result
    errs: List[str] = []
    for r in reservations_from_result(result):
        for cid, t0, t1, m in wins:
            if r.corridor != cid or not r.overlaps(t0, t1):
                continue
            tau0 = net.corridor_time.get(cid)
            if tau0 is None:
                continue
            need = effective_tau(cid, r.t_start, tau0, wins)
            if (r.t_end - r.t_start) + 1e-6 < need:
                errs.append(
                    f"slowdown too short: {r.task}@{r.corridor} "
                    f"dur={r.t_end - r.t_start:.3f} need={need:.3f} (piecewise)"
                )
    return errs


def _patched_init(self, *args, **kwargs):
    _ORIG_INIT(self, *args, **kwargs)
    blocks = _ACTIVE_BLOCKS
    if not blocks:
        return
    for cid, t0, t1 in blocks:
        self.table.reserve(cid, t0, t1, 0, "__BLOCK__")


@contextmanager
def corridor_block_active(dist: Disturbance) -> Iterator[None]:
    """进入后,所有新建 Router 都会带上 dist 中的阻断窗。降速不走这条通道。"""
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
