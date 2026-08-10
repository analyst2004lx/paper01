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
        # 补丁已拆除:新建 Router 不应自动带 BLOCK
        r = Router(net, conflict_free=True)
        blocked = any(task == "__BLOCK__"
                      for lst in r.table.all_reservations().values()
                      for _a, _b, _agv, task in lst)
        self.assertFalse(blocked)
        _ = corridor_block_active  # imported for side-doc

    def test_modules_import(self):
        import algorithm.escalate as escalate
        import algorithm.ladder as ladder

        self.assertEqual(ladder.R_ARMS, ("R0", "R0+", "R1", "R2"))
        self.assertEqual(int(escalate.EscalationLevel.REROUTE), 1)
        ladder.solve_arm  # ensure registrable
        self.assertTrue(callable(ladder.solve_arm))


if __name__ == "__main__":
    unittest.main()
