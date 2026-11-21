import glob, os, random, time
from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance, decode, clbs_ga, validate
from algorithm.schedule_io import build_baseline
paths = sorted(glob.glob(os.path.join(CLBS_INPUT, "**", "*.json"), recursive=True))
for p in paths:
    inst = load_instance(p); net = Network(inst.nodes, inst.corridors, inst.lu_node)
    for seed in (1, 7, 42):
        t=time.perf_counter()
        b = build_baseline(inst, net, seed=seed)
        rng = random.Random(seed); ma = clbs_ga.ma_min_time(inst); os_ = clbs_ga.random_os(inst, rng)
        ref = decode(inst, net, ma, os_, conflict_free=True, dispatch="exact")
        errs = validate(inst, b.result.to_timetable())
        nev = sum(1 for u in b.result.strc_units if u.evict is not None)
        nlv = sum(1 for u in b.result.strc_units if u.leave is not None)
        same = abs(ref.makespan-b.makespan)<1e-9 and len(ref.relocations)==len(b.result.relocations)
        print(f"{os.path.basename(p)[:34]:34s} s{seed:<2d} Cmax={b.makespan:7.2f} ref={ref.makespan:7.2f} same={same} errs={len(errs)} leave={nlv} evict={nev} node_model={inst.node_model} {time.perf_counter()-t:.2f}s")
