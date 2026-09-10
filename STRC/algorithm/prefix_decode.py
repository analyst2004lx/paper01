"""受假设 A2 约束的解码:已完成占用预提交,只从 t_now 接着排未开始的工序。

clbs.decode 每次从 t=0 重放。本模块不改 clbs 默认路径:
R0+ 在搜索期间把 ga.decode 临时换成 decode_from_now;
RD(cheap_baselines._redecode)直接调用本函数。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from algorithm.clbs_bridge import (
    DecodeResult,
    Instance,
    Network,
    OpRecord,
    RoutePlan,
    Router,
    TransportRecord,
)
from algorithm.clbs_bridge import _decoder as _clbs_dec
from algorithm.disturbance import Disturbance
from algorithm.repair import _reroute_tail
from algorithm.schedule_io import ScheduleBundle

EPS = 1e-9
OpKey = Tuple[int, int]


def _dest_of(inst: Instance, rec: OpRecord) -> str:
    if rec.pseudo or rec.machine is None:
        return inst.lu_node
    return inst.machine_node[rec.machine]


def _trip_started(tr: Optional[TransportRecord], t_now: float) -> bool:
    if tr is None:
        return False
    for plan in (tr.empty_plan, tr.loaded_plan):
        for s in plan.segments:
            if s.enter < t_now - EPS:
                return True
    return False


def _loaded_started(tr: Optional[TransportRecord], t_now: float) -> bool:
    if tr is None:
        return False
    return any(s.enter < t_now - EPS for s in tr.loaded_plan.segments)


def _current_trip_keys(
    tr_old: Dict[OpKey, TransportRecord], t_now: float,
) -> Set[OpKey]:
    """每辆车 t_now 正在执行的那一趟(最后一条 enter < t_now 的腿所属工序)。"""
    best: Dict[int, Tuple[OpKey, float]] = {}
    for key, tr in tr_old.items():
        last = None
        for plan in (tr.empty_plan, tr.loaded_plan):
            for s in plan.segments:
                if s.enter < t_now - EPS:
                    if last is None or s.enter > last + EPS:
                        last = s.enter
        if last is None:
            continue
        prev = best.get(tr.agv)
        if prev is None or last > prev[1] + EPS:
            best[tr.agv] = (key, last)
    return {item[0] for item in best.values()}


def _classify(
    inst: Instance, base: DecodeResult, t_now: float,
) -> Tuple[Set[OpKey], Set[OpKey], Set[OpKey], Set[OpKey]]:
    """返回 (done, proc, transit, demoted)。其余为 future。

    demoted:行程已开始,但同工件前道尚未完工/在制,不能按原时刻冻结。
    仍强制原车、用 _reroute_tail 保住已走完的空载前缀,否则 A2 审计会丢历史预约。
    """
    tr_map = {(t.job, t.i): t for t in base.transports}
    done: Set[OpKey] = set()
    proc: Set[OpKey] = set()
    transit: Set[OpKey] = set()
    for key, rec in base.ops.items():
        if rec.finish <= t_now + EPS:
            done.add(key)
        elif rec.start <= t_now + EPS:
            proc.add(key)
        elif _trip_started(tr_map.get(key), t_now):
            transit.add(key)
    demoted = set()
    for j, i in transit:
        for k in range(1, i):
            if (j, k) not in done and (j, k) not in proc:
                demoted.add((j, i))
                break
    transit -= demoted
    return done, proc, transit, demoted


def _precommit_history(router: Router, bundle: ScheduleBundle, t_now: float) -> None:
    for r in bundle.reservations:
        if r.t_end > t_now + EPS:
            continue
        router.table.reserve(r.corridor, r.t_start, r.t_end, r.agv, r.task)


def _install_block_from_now(router: Router, dist: Disturbance) -> None:
    from algorithm.block_context import block_windows_from_dist
    t_now = float(dist.t_now)
    for cid, t0, t1 in block_windows_from_dist(dist):
        a = max(float(t0), t_now)
        if a < float(t1) - EPS:
            router.table.reserve(cid, a, float(t1), 0, "__BLOCK__")


def _dummy(inst: Instance) -> DecodeResult:
    return DecodeResult(
        inst, 1e18, {}, [], [], {}, True, 0.0, {},
    )


def decode_from_now(
    inst: Instance,
    net: Network,
    ma: Dict[OpKey, int],
    os_seq: List[int],
    bundle: ScheduleBundle,
    dist: Disturbance,
    *,
    conflict_free: bool = True,
    forced_dispatch: Optional[List[int]] = None,
    prices=None,
    theta: float = 0.0,
    bucket_width: float = 0.0,
    capacity_override=None,
    max_entry_options: int = 3,
    collect_occupancy: bool = False,
    dispatch: str = "exact",
    forbid=None,
    dead_agv: Optional[int] = None,
    dead_machine: Optional[int] = None,
) -> DecodeResult:
    """与 clbs.decode 同签名的前缀冻结版;bundle/dist 由包装闭包注入。"""
    t_now = float(dist.t_now)
    base = bundle.result
    done, proc, transit, demoted = _classify(inst, base, t_now)
    tr_old = {(t.job, t.i): t for t in base.transports}
    if dead_agv is not None:
        extra = {key for key in transit
                 if tr_old.get(key) is not None and tr_old[key].agv == dead_agv}
        transit -= extra
        demoted |= extra
    # 故障机上已送达的工件停在原地,原车可能已离开;只保留历史到达,改派另派一趟。
    # 尚未送达的(空载/满载进行中)才走 demoted 同车改路。
    arrived_abort: Set[OpKey] = set()
    if dead_machine is not None:
        for key in list(proc | transit):
            if base.ops[key].machine != dead_machine:
                continue
            old = tr_old.get(key)
            loaded_here = key in proc or (
                old is not None and old.loaded_plan.arrive <= t_now + EPS)
            proc.discard(key)
            transit.discard(key)
            if loaded_here:
                arrived_abort.add(key)
                demoted.discard(key)
            else:
                demoted.add(key)
    # 前道不再冻结(改派/中止)时,后道不能再按原时刻走完。
    changed = True
    while changed:
        changed = False
        frozen_now = done | proc | transit
        for key in list(transit):
            j, i = key
            if any((j, k) not in frozen_now for k in range(1, i)):
                transit.discard(key)
                demoted.add(key)
                changed = True
    current_keys = _current_trip_keys(tr_old, t_now)
    hist_only = {
        key for key in demoted
        if key in tr_old and key not in current_keys
        and not (dead_agv is not None and tr_old[key].agv == dead_agv)
    }
    demoted -= hist_only
    frozen = done | proc | transit

    router = Router(
        net, conflict_free, prices=prices, theta=theta,
        max_entry_options=max_entry_options,
        bucket_width=bucket_width, capacity_override=capacity_override,
    )
    _install_block_from_now(router, dist)
    from algorithm.block_context import attach_slowdown
    attach_slowdown(router, dist)
    try:
        _precommit_history(router, bundle, t_now)
    except AssertionError:
        return _dummy(inst)

    loc = {k: inst.lu_node for k in range(1, inst.num_agvs + 1)}
    avail = {k: 0.0 for k in loc}
    pos = {j: inst.lu_node for j in inst.job_ids}
    ready = {j: 0.0 for j in inst.job_ids}
    free = {m: 0.0 for m in inst.machine_node}
    last_on: Dict[int, OpKey] = {}

    ops: Dict[OpKey, OpRecord] = {}
    transports: List[TransportRecord] = []
    dispatch_order: List[int] = []
    congestion: Dict[str, float] = {}

    def _process(j: int, i: int, m, dest: str, p: float, arrive: float, pseudo: bool):
        if pseudo:
            start = finish = arrive
            bind, mprev = "arrive", None
        else:
            mf = free[m]
            bind = "machine" if mf > arrive else "arrive"
            start = max(arrive, mf)
            finish = start + p
            mprev = last_on.get(m)
            free[m] = finish
            last_on[m] = (j, i)
        ops[(j, i)] = OpRecord(j, i, m, arrive, start, finish, bind, mprev, pseudo)
        pos[j], ready[j] = dest, finish

    try:
        # 按原扫描序回放冻结工序,车辆/工件状态与原时间轴一致。
        oc0 = {j: 0 for j in inst.job_ids}
        for j0 in bundle.os_seq:
            oc0[j0] += 1
            i0 = oc0[j0]
            key = (j0, i0)
            rec = base.ops[key]
            if key in done or key in proc:
                ops[key] = rec
                old = tr_old.get(key)
                dest = _dest_of(inst, rec)
                if old is not None:
                    transports.append(old)
                    dispatch_order.append(old.agv)
                    loc[old.agv] = dest
                    avail[old.agv] = old.arrive
                pos[j0], ready[j0] = dest, rec.finish
                if rec.machine is not None:
                    free[rec.machine] = rec.finish
                    last_on[rec.machine] = key
            elif key in transit:
                old = tr_old[key]
                k = old.agv
                dest = _dest_of(inst, rec)
                empty = _reroute_tail(
                    router, old.empty_plan, loc[k], old.pickup,
                    max(avail[k], t_now), k, f"J{j0}-{i0}-empty", t_now)
                t_load = max(empty.arrive, ready[j0], t_now, avail[k])
                loaded = _reroute_tail(
                    router, old.loaded_plan, old.pickup, dest,
                    t_load, k, f"J{j0}-{i0}-loaded", t_now)
                loc[k], avail[k] = dest, loaded.arrive
                transports.append(TransportRecord(
                    j0, i0, k, old.pickup, dest, ready[j0], empty, loaded))
                dispatch_order.append(k)
                p = 0.0 if rec.pseudo else inst.proc_time[(j0, i0)][rec.machine]
                _process(j0, i0, rec.machine, dest, p,
                         max(loaded.arrive, ready[j0], t_now), rec.pseudo)
            elif key in demoted:
                old = tr_old[key]
                k = old.agv
                stub_e = [s for s in old.empty_plan.segments if s.exit <= t_now + EPS]
                stub_l = [s for s in old.loaded_plan.segments if s.exit <= t_now + EPS]
                if dead_agv is not None and k == dead_agv and (stub_e or stub_l):
                    transports.append(TransportRecord(
                        j0, i0, k, old.pickup, old.dest, old.ready,
                        RoutePlan(old.empty_plan.start,
                                  stub_e[-1].v if stub_e else old.pickup,
                                  old.empty_plan.t0,
                                  stub_e[-1].exit if stub_e else old.empty_plan.t0,
                                  stub_e, {}, 0.0),
                        RoutePlan(old.loaded_plan.start,
                                  stub_l[-1].v if stub_l else old.dest,
                                  old.loaded_plan.t0,
                                  stub_l[-1].exit if stub_l else old.loaded_plan.t0,
                                  stub_l, {}, 0.0)))
            elif key in arrived_abort:
                old = tr_old.get(key)
                dest_old = inst.machine_node[rec.machine]
                if old is not None:
                    transports.append(old)
                pos[j0], ready[j0] = dest_old, max(t_now, ready[j0])
            elif key in hist_only:
                old = tr_old[key]
                stub_e = [s for s in old.empty_plan.segments if s.exit <= t_now + EPS]
                stub_l = [s for s in old.loaded_plan.segments if s.exit <= t_now + EPS]
                if stub_e or stub_l:
                    transports.append(TransportRecord(
                        j0, i0, old.agv, old.pickup, old.dest, old.ready,
                        RoutePlan(old.empty_plan.start,
                                  stub_e[-1].v if stub_e else old.pickup,
                                  old.empty_plan.t0,
                                  stub_e[-1].exit if stub_e else old.empty_plan.t0,
                                  stub_e, {}, 0.0),
                        RoutePlan(old.loaded_plan.start,
                                  stub_l[-1].v if stub_l else old.dest,
                                  old.loaded_plan.t0,
                                  stub_l[-1].exit if stub_l else old.loaded_plan.t0,
                                  stub_l, {}, 0.0)))

        parked: Dict[int, Tuple[str, float]] = {}
        for tr in transports:
            for plan in (tr.empty_plan, tr.loaded_plan):
                for s in plan.segments:
                    prev = parked.get(tr.agv)
                    if prev is None or s.exit > prev[1] + EPS:
                        parked[tr.agv] = (s.v, s.exit)
        for k, (v, t) in parked.items():
            if dead_agv is not None and k == dead_agv:
                continue
            loc[k] = v
            avail[k] = max(avail[k], t, t_now)
        for key in list(demoted):
            if key not in tr_old:
                continue
            old = tr_old[key]
            k = old.agv
            if dead_agv is not None and k == dead_agv:
                continue
            stub_e = [s for s in old.empty_plan.segments if s.exit <= t_now + EPS]
            stub_l = [s for s in old.loaded_plan.segments if s.exit <= t_now + EPS]
            at = loc[k]
            if stub_l:
                loc[k] = stub_l[-1].v
                avail[k] = max(avail[k], stub_l[-1].exit, t_now)
            elif stub_e and (
                    stub_e[-1].v == at
                    or stub_e[0].u == at
                    or any(s.u == at or s.v == at for s in stub_e)):
                loc[k] = stub_e[-1].v
                avail[k] = max(avail[k], stub_e[-1].exit, t_now)
            else:
                hist_only.add(key)
                demoted.discard(key)
        demoted_agvs = {
            tr_old[key].agv for key in demoted
            if key in tr_old and not (
                dead_agv is not None and tr_old[key].agv == dead_agv)
        }

        def _empty_to_pickup(key: OpKey) -> Optional[RoutePlan]:
            """先收完进行中的空载,占住该车;满载仍等前道完工再走。"""
            if dead_agv is not None and tr_old[key].agv == dead_agv:
                return None
            old = tr_old[key]
            k = old.agv
            j, _i = key
            pickup = pos[j]
            empty = _reroute_tail(
                router, old.empty_plan, loc[k], pickup,
                max(avail[k], t_now), k, f"J{j}-{_i}-empty", t_now)
            at = empty.segments[-1].v if empty.segments else old.pickup
            if at != pickup and not _loaded_started(old, t_now):
                extra = router.route(
                    at, pickup, max(empty.arrive, t_now, avail[k]),
                    k, f"J{j}-{_i}-empty")
                empty = RoutePlan(
                    empty.start, pickup, empty.t0, extra.arrive,
                    list(empty.segments) + list(extra.segments),
                    dict(extra.wait_by_corridor), extra.price_cost)
            if _loaded_started(old, t_now):
                avail[k] = max(avail[k], t_now)
            else:
                loc[k], avail[k] = pickup, max(empty.arrive, t_now)
            return empty

        demoted_empty: Dict[OpKey, RoutePlan] = {}
        pending_hold: Set[int] = set()
        for key in sorted(demoted, key=lambda ki: (ki[0], ki[1])):
            empty0 = _empty_to_pickup(key)
            if empty0 is not None:
                demoted_empty[key] = empty0
                pending_hold.add(tr_old[key].agv)

        def _finish_one_demoted(dk: OpKey) -> None:
            dj, di = dk
            old = tr_old[dk]
            kk = old.agv
            if inst.is_pseudo(dj, di):
                mm, ddest, pp, ps = None, inst.lu_node, 0.0, True
            else:
                mm = ma[(dj, di)]
                ddest = inst.machine_node[mm]
                pp = inst.proc_time[(dj, di)][mm]
                ps = False
            pickup = pos[dj]
            empty = demoted_empty.pop(dk)
            if empty.goal != pickup and not _loaded_started(old, t_now):
                extra = router.route(
                    empty.goal, pickup, max(empty.arrive, t_now, avail[kk]),
                    kk, f"J{dj}-{di}-empty")
                empty = RoutePlan(
                    empty.start, pickup, empty.t0, extra.arrive,
                    list(empty.segments) + list(extra.segments),
                    dict(extra.wait_by_corridor), extra.price_cost)
            t_load = max(empty.arrive, ready[dj], t_now, avail[kk])
            load_from = loc[kk] if _loaded_started(old, t_now) else pickup
            loaded = _reroute_tail(
                router, old.loaded_plan, load_from, ddest,
                t_load, kk, f"J{dj}-{di}-loaded", t_now)
            loc[kk], avail[kk] = ddest, loaded.arrive
            pending_hold.discard(kk)
            transports.append(TransportRecord(
                dj, di, kk, pickup, ddest, ready[dj], empty, loaded))
            dispatch_order.append(kk)
            _process(dj, di, mm, ddest, pp,
                     max(loaded.arrive, ready[dj], t_now), ps)

        def _drain_ready_demoted() -> None:
            progressed = True
            while progressed:
                progressed = False
                for dk in list(demoted_empty):
                    dj, di = dk
                    if di > 1 and (dj, di - 1) not in ops:
                        continue
                    _finish_one_demoted(dk)
                    progressed = True

        op_counter = {j: 0 for j in inst.job_ids}
        for j in os_seq:
            op_counter[j] += 1
            i = op_counter[j]
            key = (j, i)
            if key in frozen:
                continue
            pseudo = inst.is_pseudo(j, i)
            if pseudo:
                m, dest, p = None, inst.lu_node, 0.0
            else:
                m = ma[(j, i)]
                dest = inst.machine_node[m]
                p = inst.proc_time[(j, i)][m]

            _drain_ready_demoted()
            if key in ops:
                continue

            if pos[j] == dest:
                arrive = ready[j]
            else:
                pickup = pos[j]
                probed = None
                if forced_dispatch is not None:
                    k = forced_dispatch[len(dispatch_order)]
                else:
                    allowed = loc
                    if dead_agv is not None:
                        allowed = {kk: vv for kk, vv in allowed.items()
                                   if kk != dead_agv}
                    if pending_hold:
                        rest = {kk: vv for kk, vv in allowed.items()
                                if kk not in pending_hold}
                        if rest:
                            allowed = rest
                    if forbid:
                        banned = forbid.get((j, i))
                        if banned:
                            rest = {kk: vv for kk, vv in allowed.items()
                                    if kk not in banned}
                            if rest:
                                allowed = rest
                    sub_avail = {kk: max(avail[kk], t_now) for kk in allowed}
                    if dispatch in ("exact", "exact_noopt") and conflict_free:
                        opt = (dispatch == "exact")
                        k, probed = _clbs_dec.dispatch_exact(
                            router, net, allowed, sub_avail,
                            pickup, dest, max(ready[j], t_now),
                            prune=opt, reuse=opt)
                    else:
                        k = _clbs_dec.dispatch_rule(
                            inst, net, allowed, sub_avail,
                            pickup, dest, max(ready[j], t_now), prices, theta)
                dispatch_order.append(k)
                if probed is not None:
                    empty, loaded = probed
                    for plan, tag in ((empty, "empty"), (loaded, "loaded")):
                        for s in plan.segments:
                            router.table.reserve(
                                s.corridor, s.enter, s.exit, k, f"J{j}-{i}-{tag}")
                else:
                    empty = router.route(
                        loc[k], pickup, max(avail[k], t_now), k, f"J{j}-{i}-empty")
                    t_load = max(empty.arrive, ready[j], t_now)
                    loaded = router.route(
                        pickup, dest, t_load, k, f"J{j}-{i}-loaded")
                arrive = loaded.arrive
                loc[k], avail[k] = dest, arrive
                transports.append(TransportRecord(
                    j, i, k, pickup, dest, ready[j], empty, loaded))
                for plan in (empty, loaded):
                    for cid, w in plan.wait_by_corridor.items():
                        congestion[cid] = congestion.get(cid, 0.0) + w

            _process(j, i, m, dest, p, arrive, pseudo)
    except Exception:  # noqa: BLE001 — 搜索中的不可行染色体用大 Cmax 丢掉
        return _dummy(inst)

    if not ops:
        return _dummy(inst)
    makespan = max(r.finish for r in ops.values())
    occ = router.table.occupancy(router.bucket_width) if collect_occupancy else {}
    return DecodeResult(
        inst, makespan, ops, transports, dispatch_order,
        congestion, conflict_free, 0.0, occ,
    )
