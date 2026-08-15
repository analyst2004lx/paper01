"""Follow-up to probe_aft.py.

v1 established two things and raised one problem:
  + conditioning on the route removes 90.4% of vgr_1's log-duration variance
    (sigma 0.480 -> 0.149), so the AFT covariate is necessary;
  + the additive parameterisation (mu + a_start + b_end) exactly matched the
    saturated per-route model (gap 0.000);
  - but leave-one-route-out prediction was almost as bad as not conditioning at
    all (vgr_1: 0.416 vs pooled 0.480), i.e. the additive model does not
    extrapolate to a route it has never seen.

The suspected cause is structural: if the bipartite start->end graph is close to
a forest, each position appears in very few routes, so holding a route out
destroys the information needed to identify its endpoint effects. That would
mean the exact additive/saturated match and the extrapolation failure are two
sides of the same property.

This script (a) measures the route-graph structure to test that, and (b) checks
whether `planned_operation_time` can serve as the cold-start predictor for
unseen routes, which is the role assigned to it after probe_timing.py showed it
is not a calibrated estimate of actual duration.

Run: python probe_aft_v2.py
"""
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import numpy as np

XES = "{http://www.xes-standard.org/}"
PATH = "MainProcess_cleaned.xes"
MIN_N = 15
MIN_ROUTES = 2


def parse_planned(s):
    m = re.match(r"(\d+) days (\d+):(\d+):(\d+)", s or "")
    if not m:
        return None
    d, h, mi, sec = (int(x) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def load():
    groups = defaultdict(list)
    acts = defaultdict(dict)
    for trace in ET.parse(PATH).getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            a, params = {}, {}
            for child in ev:
                if child.tag == XES + "list" and child.get("key") == "parameters":
                    for vals in child:
                        for v in vals:
                            params[v.get("key")] = v.get("value")
                elif child.get("key"):
                    a[child.get("key")] = child.get("value")
            rec = acts[(a.get("case"), a.get("event_id"))]
            rec.setdefault("resource", a.get("org:resource"))
            rec.setdefault("op", a.get("concept:name"))
            rec.setdefault("start", params.get("parameter_start_position"))
            rec.setdefault("end", params.get("parameter_end_position"))
            rec.setdefault("plan", parse_planned(a.get("planned_operation_time")))
            state = a.get("lifecycle:state")
            if state == "inProgress":
                rec["t0"] = datetime.fromisoformat(a["time:timestamp"])
                if a.get("operation_end_time"):
                    rec["t1"] = datetime.fromisoformat(a["operation_end_time"])
            if state in ("success", "failure"):
                rec["outcome"] = state

    for rec in acts.values():
        if rec.get("outcome") != "success" or not (rec.get("t0") and rec.get("t1")):
            continue
        if not (rec.get("start") and rec.get("end")):
            continue
        dur = (rec["t1"] - rec["t0"]).total_seconds()
        if dur > 0:
            groups[(rec["resource"], rec["op"])].append(
                (rec["start"], rec["end"], dur, rec.get("plan")))
    return groups


def is_forest(routes):
    """Bipartite start->end graph: forest iff |edges| = |nodes| - |components|."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edges = 0
    cyc = False
    for s, e in routes:
        a, b = find(("s", s)), find(("e", e))
        if a == b:
            cyc = True
        else:
            parent[a] = b
        edges += 1
    nodes = len({("s", s) for s, _ in routes} | {("e", e) for _, e in routes})
    comps = len({find(n) for n in parent})
    return (not cyc), nodes, comps, edges


def design(starts, ends, s_idx, e_idx):
    X = np.zeros((len(starts), 1 + len(s_idx) + len(e_idx)))
    X[:, 0] = 1.0
    for i, (s, e) in enumerate(zip(starts, ends)):
        if s in s_idx:
            X[i, 1 + s_idx[s]] = 1.0
        if e in e_idx:
            X[i, 1 + len(s_idx) + e_idx[e]] = 1.0
    return X


def fit(starts, ends, y):
    s_idx = {p: i for i, p in enumerate(sorted(set(starts)))}
    e_idx = {p: i for i, p in enumerate(sorted(set(ends)))}
    X = design(starts, ends, s_idx, e_idx)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta, s_idx, e_idx


def main():
    groups = load()
    print("=== route-graph structure per (resource, operation) ===")
    hdr = (f"{'resource':<8} {'operation':<28} {'n':>4} {'routes':>6} "
           f"{'starts':>6} {'ends':>5} {'forest':>7} {'params':>7}")
    print(hdr)
    print("-" * len(hdr))
    keep = []
    for (res, op), vals in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        routes = sorted({(v[0], v[1]) for v in vals})
        if len(vals) < MIN_N or len(routes) < MIN_ROUTES:
            continue
        starts = {v[0] for v in vals}
        ends = {v[1] for v in vals}
        forest, nodes, comps, edges = is_forest(routes)
        params = 1 + len(starts) + len(ends)
        print(f"{res:<8} {op:<28} {len(vals):>4} {len(routes):>6} "
              f"{len(starts):>6} {len(ends):>5} {str(forest):>7} {params:>7}")
        keep.append(((res, op), vals))
    print()
    print("  A forest means every route is a bridge: removing one route makes its")
    print("  endpoint effects unidentifiable, which is exactly why LOO-route fails.")
    print()

    print("=== cold start on an unseen route: additive AFT vs planned-time prior ===")
    hdr = (f"{'resource':<8} {'operation':<28} {'sig_pool':>9} {'sig_cond':>9} "
           f"{'LOO_addi':>9} {'LOO_plan':>9} {'scorable':>9}")
    print(hdr)
    print("-" * len(hdr))

    agg = defaultdict(list)
    for (res, op), vals in keep:
        starts = [v[0] for v in vals]
        ends = [v[1] for v in vals]
        y = np.log(np.array([v[2] for v in vals], dtype=float))
        plans = [v[3] for v in vals]
        routes = sorted(set(zip(starts, ends)))

        s_pool = float(y.std(ddof=1))
        beta, si, ei = fit(starts, ends, y)
        s_cond = float((y - design(starts, ends, si, ei) @ beta).std(ddof=1))

        loo_a, loo_p, scorable = [], [], 0
        for r in routes:
            tr = [i for i in range(len(y)) if (starts[i], ends[i]) != r]
            te = [i for i in range(len(y)) if (starts[i], ends[i]) == r]
            if len(tr) < 5 or not te:
                continue
            # additive model trained without this route
            b, s2, e2 = fit([starts[i] for i in tr], [ends[i] for i in tr], y[tr])
            if r[0] in s2 and r[1] in e2:
                scorable += 1
                pred = design([starts[i] for i in te], [ends[i] for i in te],
                              s2, e2) @ b
                loo_a.extend(list(y[te] - pred))
            # planned-time prior: log tau ~ log(plan) + c, c learned on train
            tr_ok = [i for i in tr if plans[i]]
            te_ok = [i for i in te if plans[i]]
            if len(tr_ok) >= 5 and te_ok:
                c = float(np.mean([y[i] - np.log(plans[i]) for i in tr_ok]))
                loo_p.extend([y[i] - (np.log(plans[i]) + c) for i in te_ok])

        f_a = float(np.std(loo_a, ddof=1)) if len(loo_a) > 2 else float("nan")
        f_p = float(np.std(loo_p, ddof=1)) if len(loo_p) > 2 else float("nan")
        print(f"{res:<8} {op:<28} {s_pool:>9.3f} {s_cond:>9.3f} "
              f"{f_a:>9.3f} {f_p:>9.3f} {scorable:>4d}/{len(routes):<4d}")
        agg["pool"].append((s_pool, len(y)))
        agg["cond"].append((s_cond, len(y)))
        if not np.isnan(f_a):
            agg["loo_a"].append((f_a, len(loo_a)))
        if not np.isnan(f_p):
            agg["loo_p"].append((f_p, len(loo_p)))

    print()
    for k, label in (("pool", "unconditional (M0)"),
                     ("cond", "route-conditioned, seen route (M1)"),
                     ("loo_a", "additive AFT, UNSEEN route"),
                     ("loo_p", "planned-time prior, UNSEEN route")):
        if agg[k]:
            v = np.array([x[0] for x in agg[k]])
            w = np.array([x[1] for x in agg[k]], dtype=float)
            print(f"  sigma_log  {label:<38s} = {np.average(v, weights=w):.3f}")


if __name__ == "__main__":
    main()
