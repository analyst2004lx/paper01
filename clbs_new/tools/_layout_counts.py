from algorithm.instance import simple_lower_bound
from tools.abc_matrix import CASES, build

for c in CASES:
    inst, net, _ = build(c)
    stores = {inst.lu_node, inst.out_node}
    machines = set(inst.machine_node.values())
    junctions = [n for n in inst.nodes if n not in stores and n not in machines]
    lb = simple_lower_bound(inst, net)
    far = max(net.ideal_dist[inst.lu_node][m] for m in machines)
    print(f"{c['name']:<14s} nodes {len(inst.nodes):3d} corr {len(inst.corridors):3d} "
          f"junctions {len(junctions):3d} c={inst.machine_capacity} h={inst.node_headway} "
          f"far {far:5.1f} in->out {net.ideal_dist[inst.lu_node][inst.out_node]:5.1f} LB {lb}")
