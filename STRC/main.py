"""STRC 一键入口:载入排程 → 注入扰动 → 闭包修复 → 校验。

用法(在 STRC/ 目录下):
    py main.py --help
    py main.py --instance ../clbs/input/example_3x3x2.json \\
               --disturbance input/disturbances/corridor_block_example.json
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="STRC - Spatiotemporal Reservation Closure repair")
    ap.add_argument("--instance", default=None,
                    help="车间算例 JSON;默认 clbs/input/example_3x3x2.json")
    ap.add_argument("--schedule", default=None,
                    help="初始排程 JSON;缺省则提示先导出")
    ap.add_argument("--disturbance",
                    default=os.path.join(
                        HERE, "input", "disturbances", "corridor_block_example.json"))
    ap.add_argument("--arm", default="R2", choices=["R0", "R0+", "R1", "R2"],
                    help="修复档位")
    ap.add_argument("--out", default=None, help="结果目录;默认 output/<name>/")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, load_instance
    from algorithm.disturbance import load_disturbance

    inst_path = args.instance or os.path.join(CLBS_INPUT, "example_3x3x2.json")
    if not os.path.isfile(inst_path):
        print(f"instance not found: {inst_path}", file=sys.stderr)
        return 1
    if not os.path.isfile(args.disturbance):
        print(f"disturbance not found: {args.disturbance}", file=sys.stderr)
        return 1

    inst = load_instance(inst_path)
    dist = load_disturbance(args.disturbance)
    print(f"STRC arm={args.arm}")
    print(f"  instance     : {inst_path}  "
          f"(n={len(inst.job_ids)}, m={inst.num_machines}, A={inst.num_agvs})")
    print(f"  disturbance  : {dist.type}  class={dist.class_label}  t_now={dist.t_now}")
    print(f"  schedule     : {args.schedule or '(none — export a clbs closed-loop plan first)'}")
    print()
    print("Core repair path not wired yet. Next:")
    print("  1) py -m tests.test_smoke")
    print("  2) implement algorithm/closure.py + tools/e1_miss.py")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
