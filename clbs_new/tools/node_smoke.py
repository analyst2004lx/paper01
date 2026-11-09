"""节点模型冒烟测试:各拥堵档位 × 机器容量 c,随机染色体解码后全部过独立校验。

Node-model smoke test: for every congestion level and machine capacity c, random chromosomes
must all decode to timetables that pass the independent validator.

用法 / Usage:  python -m tools.node_smoke [--samples 30]
"""
from __future__ import annotations

import argparse
import dataclasses
import random
import time

from algorithm.decoder import decode
from algorithm.ga import random_ma, random_os
from algorithm.generator import CONGESTION_PRESETS, build_instance, make_spec
from algorithm.instance import parse_instance
from algorithm.network import Network
from algorithm.validator import validate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--caps", nargs="+", default=["1", "2", "3", "inf"])
    args = ap.parse_args()
    bad = 0
    for tag in CONGESTION_PRESETS:
        spec = make_spec(tag, 0.3, 0.6, 12, 8, 12, 4, seed=0)
        base = parse_instance(build_instance(spec))
        net = Network(base.nodes, base.corridors, base.lu_node)
        for c in args.caps:
            inst = dataclasses.replace(base, machine_capacity=None if c == "inf" else int(c))
            rng = random.Random(1)
            chroms = [(random_ma(inst, rng), random_os(inst, rng)) for _ in range(args.samples)]
            for dispatch in ("rule", "exact"):
                spans, relocs, t0 = [], 0, time.perf_counter()
                for ma, os_seq in chroms:
                    res = decode(inst, net, ma, os_seq, dispatch=dispatch)
                    errs = validate(inst, res.to_timetable())
                    if errs:
                        bad += 1
                        print(f"  FAIL {tag} c={c} {dispatch}: {errs[:3]}")
                    spans.append(res.makespan)
                    relocs += len(res.relocations)
                ms = (time.perf_counter() - t0) / args.samples * 1000
                print(f"{tag:8s} c={c:>3s} {dispatch:5s} mean Cmax={sum(spans)/len(spans):8.2f}"
                      f"  reloc/decode={relocs/args.samples:5.2f}  {ms:7.1f} ms/decode")
    print("ALL PASS" if bad == 0 else f"{bad} FAILURES")


if __name__ == "__main__":
    main()
