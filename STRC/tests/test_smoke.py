"""桥接 + E1/E2/E3 核心路径自检。在 STRC/ 下: py -m tests.test_smoke"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestSmoke(unittest.TestCase):
    def test_clbs_bridge_loads_instance(self):
        from algorithm.clbs_bridge import CLBS_INPUT, Network, blocking_opponents, load_instance

        path = os.path.join(CLBS_INPUT, "example_3x3x2.json")
        self.assertTrue(os.path.isfile(path), path)
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()
        self.assertGreater(len(inst.job_ids), 0)
        self.assertTrue(callable(blocking_opponents))

    def test_e1_and_repair_corridor(self):
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
        from algorithm.closure import (
            job_precedence_from_reservations,
            machine_chains_from_ops,
            spatiotemporal_closure,
            task_graph_direct,
        )
        from algorithm.disturbance import (
            Disturbance,
            schedule_still_valid_under_block,
            seed_failed_reservations,
        )
        from algorithm.repair import repair_with_strc
        from algorithm.schedule_io import build_baseline, pick_busy_corridor

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        self.assertGreater(len(bundle.reservations), 0)

        t_now = 0.35 * bundle.makespan
        cid, t0, t1, n = pick_busy_corridor(bundle.reservations, t_now=t_now)
        self.assertGreater(n, 0)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t0, t_end=t1)
        self.assertEqual(task_graph_direct(dist), set())
        seeds = seed_failed_reservations(dist, bundle.reservations)
        self.assertGreater(len(seeds), 0)
        chains = machine_chains_from_ops(bundle.result.ops)
        closure = spatiotemporal_closure(
            seeds, bundle.reservations, horizon=bundle.makespan + 1.0,
            t_now=t_now, machine_chains=chains,
        )
        self.assertGreaterEqual(closure.size, len(seeds))
        self.assertFalse(schedule_still_valid_under_block(bundle.reservations, dist))

        rep = repair_with_strc(inst, net, bundle, dist)
        self.assertTrue(rep.feasible, msg=rep.errors[:5])
        self.assertIsNotNone(rep.result)

    def test_abutting_yield_closes_known_leak(self):
        """example_3x3x2 seed 42:接壤占用必须进闭包,延后泄漏应为 0。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
        from algorithm.disturbance import Disturbance
        from algorithm.repair import release_set_r2
        from algorithm.schedule_io import build_baseline, pick_busy_corridor
        from tools.edge_probe import _probe

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42, mode="heuristic")
        t_now = 0.35 * bundle.makespan
        cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t0, t_end=t1)
        closed = release_set_r2(bundle, dist)
        tasks = {r.task for r in closed}
        self.assertIn("J2-1-loaded", tasks)
        self.assertIn("J3-3-loaded", tasks)
        _n, n_del, n_abut, _near, n_agv = _probe(bundle.reservations, closed, 1.0)
        self.assertEqual(n_del, 0)
        self.assertEqual(n_abut, 0)
        self.assertEqual(n_agv, 0)

    def test_r0_under_block_smoke(self):
        """R0 在阻断下能出解或干净失败;补丁不泄漏到后续 Router。"""
        from algorithm.block_context import corridor_block_active
        from algorithm.clbs_bridge import CLBS_INPUT, Network, Router, load_instance
        from algorithm.disturbance import Disturbance
        from algorithm.resolve import resolve_r0
        from algorithm.schedule_io import build_baseline, pick_busy_corridor

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        cid, _, _, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(
            type="corridor_block", t_now=t_now, corridor=cid,
            t_start=t_now, t_end=bundle.makespan + 1.0,
        )
        rep = resolve_r0(inst, net, bundle, dist, budget_sec=0.15,
                         seed=42, hot=True, pop=20)
        self.assertIn(rep.meta.get("arm"), ("R0", "R0+"))
        self.assertTrue(rep.meta.get("respect_a2"))
        from algorithm.metrics import reservation_delta_before
        from algorithm.schedule_io import reservations_from_result
        if rep.feasible and rep.result is not None:
            pc, _pt = reservation_delta_before(
                bundle.reservations, reservations_from_result(rep.result),
                t_now=t_now)
            self.assertEqual(pc, 0)
        # 补丁已拆除:新建 Router 不应自动带 BLOCK
        r = Router(net, conflict_free=True)
        blocked = any(task == "__BLOCK__"
                      for lst in r.table.all_reservations().values()
                      for _a, _b, _agv, task in lst)
        self.assertFalse(blocked)
        _ = corridor_block_active  # imported for side-doc

    def test_prefix_decode_keeps_history(self):
        """固定前缀解码不得改写 t_end <= t_now 的占用,且原染色体可续跑。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance, validate
        from algorithm.disturbance import Disturbance
        from algorithm.metrics import reservation_delta_before
        from algorithm.prefix_decode import decode_from_now
        from algorithm.schedule_io import (
            build_baseline, pick_busy_corridor, reservations_from_result,
        )

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t0, t_end=t1)
        res = decode_from_now(inst, net, bundle.ma, bundle.os_seq, bundle, dist,
                              dispatch="exact")
        self.assertLess(res.makespan, 1e17)
        self.assertEqual(validate(inst, res.to_timetable()), [])
        pc, pt = reservation_delta_before(
            bundle.reservations, reservations_from_result(res), t_now=t_now)
        self.assertGreater(pt, 0)
        self.assertEqual(pc, 0)

    def test_prefix_decode_keeps_demoted_empty(self):
        """同工件后道已出车时,历史空载前缀仍须出现在结果里(拥堵例已知泄漏格)。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance, validate
        from algorithm.disturbance import Disturbance
        from algorithm.metrics import reservation_delta_before
        from algorithm.prefix_decode import decode_from_now
        from algorithm.schedule_io import (
            build_baseline, pick_busy_corridor, reservations_from_result,
        )

        path = os.path.join(CLBS_INPUT, "congested_8x4x4.json")
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t0, t_end=t1)
        res = decode_from_now(inst, net, bundle.ma, bundle.os_seq, bundle, dist,
                              dispatch="exact")
        self.assertLess(res.makespan, 1e17)
        self.assertEqual(validate(inst, res.to_timetable()), [])
        pc, pt = reservation_delta_before(
            bundle.reservations, reservations_from_result(res), t_now=t_now)
        self.assertGreater(pt, 0)
        self.assertEqual(pc, 0)

    def test_piecewise_tau_only_scales_overlap(self):
        """窗外原速、窗内按倍率;擦边重叠不得整段乘 2。"""
        from algorithm.block_context import effective_tau, piecewise_duration

        self.assertAlmostEqual(piecewise_duration(0.0, 10.0, []), 10.0)
        self.assertAlmostEqual(effective_tau("e", 0.0, 10.0, []), 10.0)
        # 全程在窗内
        self.assertAlmostEqual(
            piecewise_duration(0.0, 10.0, [(0.0, 100.0, 2.0)]), 20.0)
        # 无重叠:窗在穿越之后
        self.assertAlmostEqual(
            piecewise_duration(0.0, 10.0, [(10.0, 20.0, 2.0)]), 10.0)
        # 前半原速、后半降速: 5 + 5*2 = 15
        self.assertAlmostEqual(
            piecewise_duration(0.0, 10.0, [(5.0, 100.0, 2.0)]), 15.0)
        # 窗在穿越中途结束: 6 个单位走完 0.3,余 0.7 原速 = 13
        self.assertAlmostEqual(
            piecewise_duration(0.0, 10.0, [(0.0, 6.0, 2.0)]), 13.0)
        # 进入时刻在窗外
        self.assertAlmostEqual(
            effective_tau("e", 20.0, 10.0, [("e", 0.0, 5.0, 2.0)]), 10.0)

    def test_slowdown_is_not_a_block(self):
        """降速不得写成 __BLOCK__;修复应能在拉长的 τ 下恢复可行。"""
        from algorithm.block_context import (
            attach_slowdown,
            block_windows_from_dist,
            slowdown_windows_from_dist,
        )
        from algorithm.clbs_bridge import CLBS_INPUT, Network, Router, load_instance
        from algorithm.disturbance import (
            Disturbance,
            schedule_still_valid_under_slowdown,
        )
        from algorithm.repair import repair_with_strc
        from algorithm.schedule_io import build_baseline, pick_busy_corridor

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(
            type="corridor_slowdown", t_now=t_now, corridor=cid,
            t_start=t0, t_end=t1, tau_mult=2.0,
        )
        self.assertEqual(block_windows_from_dist(dist), [])
        self.assertTrue(slowdown_windows_from_dist(dist))
        self.assertFalse(schedule_still_valid_under_slowdown(
            bundle.reservations, dist))

        router = Router(net, conflict_free=True)
        attach_slowdown(router, dist)
        blocked = any(task == "__BLOCK__"
                      for lst in router.table.all_reservations().values()
                      for _a, _b, _agv, task in lst)
        self.assertFalse(blocked)

        rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
        self.assertTrue(rep.feasible, msg=rep.errors[:5])

    def test_modules_import(self):
        import algorithm.escalate as escalate
        import algorithm.ladder as ladder

        self.assertEqual(ladder.R_ARMS, ("R0", "R0+", "R1", "R2"))
        self.assertEqual(int(escalate.EscalationLevel.REROUTE), 1)
        ladder.solve_arm  # ensure registrable
        self.assertTrue(callable(ladder.solve_arm))

    def test_agv_breakdown_swaps_vehicle(self):
        """车辆故障:故障车不再承运未来运输,第 1 级应能换车恢复。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
        from algorithm.disturbance import Disturbance
        from algorithm.repair import repair_with_strc
        from algorithm.schedule_io import build_baseline, reservations_from_result

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        fut = {}
        for r in bundle.reservations:
            if r.t_end > t_now:
                fut[r.agv] = fut.get(r.agv, 0) + 1
        agv = max(fut, key=fut.get)
        dist = Disturbance(type="agv_breakdown", t_now=t_now, agv=int(agv))
        rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
        self.assertTrue(rep.feasible, msg=rep.errors[:8])
        future = [r for r in reservations_from_result(rep.result)
                  if r.t_end > t_now + 1e-9]
        self.assertFalse(any(r.agv == agv for r in future))

    def test_ra_failure_reassigns_machine(self):
        """机械臂故障:未完工工序改派到其它可行机。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
        from algorithm.disturbance import Disturbance
        from algorithm.repair import repair_with_strc
        from algorithm.schedule_io import build_baseline

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        mfut = {}
        for rec in bundle.result.ops.values():
            if rec.pseudo or rec.machine is None or rec.finish <= t_now:
                continue
            mfut.setdefault(rec.machine, []).append((rec.job, rec.i))
        mac = max(mfut, key=lambda m: len(mfut[m]))
        dist = Disturbance(type="ra_failure", t_now=t_now, machine=str(mac),
                           extra={"failed_ops": mfut[mac]})
        rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
        self.assertTrue(rep.feasible, msg=rep.errors[:8])
        for rec in rep.result.ops.values():
            if rec.pseudo or rec.machine is None or rec.finish <= t_now:
                continue
            orig = bundle.result.ops.get((rec.job, rec.i))
            if orig is None or orig.finish <= t_now:
                continue
            if orig.machine == mac and orig.finish > t_now:
                self.assertNotEqual(rec.machine, mac)

    def test_ra_failure_hard_cells(self):
        """E6 曾失败的两格:前道改派后后道不得按原时刻冻结,也不得拽走正在执行的车。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
        from algorithm.disturbance import Disturbance
        from algorithm.repair import repair_with_strc
        from algorithm.schedule_io import build_baseline

        cases = [
            (os.path.join(CLBS_INPUT, "example_3x3x2.json"), 8),
            (os.path.join(CLBS_INPUT, "congested_8x4x4.json"), 123),
        ]
        for path, seed in cases:
            inst = load_instance(path)
            net = Network(inst.nodes, inst.corridors, inst.lu_node)
            bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = 0.35 * bundle.makespan
            mfut = {}
            for rec in bundle.result.ops.values():
                if rec.pseudo or rec.machine is None or rec.finish <= t_now:
                    continue
                mfut.setdefault(str(rec.machine), []).append((rec.job, rec.i))
            mac = max(mfut, key=lambda m: len(mfut[m]))
            dist = Disturbance(
                type="ra_failure", t_now=t_now, machine=mac,
                extra={"failed_ops": mfut[mac]})
            rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
            self.assertTrue(rep.feasible, msg=f"{path} seed={seed}: {rep.errors[:6]}")

    def test_redecode_respects_a2(self):
        """RD 默认走固定前缀,小例不得改写 t_end <= t_now 的占用。"""
        from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
        from algorithm.disturbance import Disturbance
        from algorithm.metrics import reservation_delta_before
        from algorithm.schedule_io import (
            build_baseline, pick_busy_corridor, reservations_from_result,
        )
        from tools.cheap_baselines import _redecode

        inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        bundle = build_baseline(inst, net, seed=42)
        t_now = 0.35 * bundle.makespan
        cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t0, t_end=t1)
        rep = _redecode(inst, net, bundle, dist)
        self.assertTrue(rep.meta.get("respect_a2"))
        self.assertTrue(rep.feasible, msg=rep.errors[:5])
        pc, pt = reservation_delta_before(
            bundle.reservations, reservations_from_result(rep.result),
            t_now=t_now)
        self.assertGreater(pt, 0)
        self.assertEqual(pc, 0)


if __name__ == "__main__":
    unittest.main()
