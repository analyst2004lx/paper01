"""同一组随机染色体下,旧模型(clbs)与节点模型(clbs_new)的单次解码耗时对比。"""
import dataclasses
import importlib
import random
import sys
import time

ROOT = r"c:\Users\analy\Desktop\AI_Folder"


def bench(pkg_dir: str, node_cap, n: int = 20):
    for mod in [m for m in sys.modules if m == "algorithm" or m.startswith("algorithm.")]:
        del sys.modules[mod]
    sys.path.insert(0, pkg_dir)
    try:
        dec = importlib.import_module("algorithm.decoder")
        ga = importlib.import_module("algorithm.ga")
        gen = importlib.import_module("algorithm.generator")
        ins = importlib.import_module("algorithm.instance")
        nwm = importlib.import_module("algorithm.network")
        out = {}
        for tag in ("high", "scatter"):
            inst = ins.parse_instance(gen.build_instance(
                gen.make_spec(tag, 0.3, 0.6, 12, 8, 12, 4, seed=0)))
            if node_cap != "old":
                inst = dataclasses.replace(inst, machine_capacity=node_cap)
            net = nwm.Network(inst.nodes, inst.corridors, inst.lu_node)
            for dispatch in ("rule", "exact"):
                rng = random.Random(7)
                chroms = [(ga.random_ma(inst, rng), ga.random_os(inst, rng)) for _ in range(n)]
                t0 = time.perf_counter()
                spans = [dec.decode(inst, net, ma, os_, dispatch=dispatch).makespan
                         for ma, os_ in chroms]
                ms = (time.perf_counter() - t0) / n * 1000
                out[(tag, dispatch)] = (ms, sum(spans) / n)
        return out
    finally:
        sys.path.pop(0)


old = bench(ROOT + r"\clbs", "old")
new2 = bench(ROOT + r"\clbs_new", 2)
for key in old:
    print(f"{key[0]:8s} {key[1]:5s}  old {old[key][0]:7.1f} ms  Cmax {old[key][1]:7.1f}   "
          f"new(c=2) {new2[key][0]:7.1f} ms  Cmax {new2[key][1]:7.1f}")
