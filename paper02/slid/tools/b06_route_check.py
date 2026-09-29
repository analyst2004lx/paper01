import numpy as np
from collections import Counter
from algorithm import baselines, ingest, procmodel, timing, structural
from algorithm.detector import Detector, DetectorConfig
from tools.baseline_diag import split

raw = ingest.read_xes(ingest.default_log_path())
live = ingest.valid(raw, drop_failure=True)
pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
model = procmodel.load_bpmn(procmodel.default_bpmn_glob(), log_positions=pos)
train, calib, test = split(live)
print("train/calib/test", len(train), len(calib), len(test))
det = Detector(DetectorConfig(alpha=0.01, online_update=False)).fit(
    train, model=model, rng=np.random.default_rng(0), temporal=True)
ms = det.timing
print("groups", len(ms), "informative", sum(m.informative for m in ms.values()))
nr = Counter()
for m in ms.values():
    keys = list(m.route_effect)
    nr[(len(keys), timing.NO_ROUTE in keys)] += 1
print("route_effect sizes (n_keys, has NO_ROUTE):", sorted(nr.items()))
routed = sum(1 for m in ms.values() if any(k != timing.NO_ROUTE for k in m.route_effect))
print("groups with own route effect:", routed)
# fraction of test activities scored with a route-specific location
n = own = unseen_grp = uninf = 0
for a in test:
    n += 1
    m = ms.get((a.device, a.op))
    if m is None:
        unseen_grp += 1
        continue
    if not m.informative:
        uninf += 1
        continue
    r = tuple(a.route) if a.route else timing.NO_ROUTE
    if r in m.route_effect and r != timing.NO_ROUTE:
        own += 1
print("test acts", n, "unseen group", unseen_grp, "uninformative", uninf, "route-specific", own)
w, qs, keep = det.path_weights(baselines.order_stream(calib), alpha=0.01)
print("weights", w, "q", qs, "keep", keep)
print("h (fused, arl0=1000)", det.h)
print("struct alpha0", getattr(det.struct, "alpha0", None))
