import statistics as st
import time

from algorithm.clbs_bridge import Network, load_instance
from algorithm.repair import precompute_dependence
from algorithm.schedule_io import build_baseline
from tools.expand_batch import _instances

SEEDS = [42, 7, 2024, 1, 13, 99, 123, 777, 31415, 8]
ms = []
for name, path in _instances():
    inst = load_instance(path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for s in SEEDS:
        b = build_baseline(inst, net, seed=s, mode="heuristic")
        t = time.perf_counter()
        precompute_dependence(b)
        ms.append((time.perf_counter() - t) * 1000)
print("n %d median %.2f max %.2f" % (len(ms), st.median(ms), max(ms)))
