"""Test whether the AFT covariates (transport route) are necessary, and whether
an additive parameterisation generalises to routes never seen in training.

Motivation: probe_timing.py measured sigma_log = 0.480 for vgr_1 against 0.110
for vgr_2, same device type. The hypothesis is that vgr_1 simply serves a more
diverse set of routes, so its spread is heterogeneity, not noise. If true, the
timing channel must condition on the route.

Three nested models for log-duration within each (resource, operation) group:

  M0  pooled          log tau = mu + eps                       1 param
  M1  additive AFT    log tau = mu + a_start + b_end + eps      <= 2|P| params
  M2  saturated       log tau = mu_route + eps                  1 per route

M1 is the interesting one: it has few parameters and, crucially, can score a
route never seen in training as long as both of its endpoints were seen. That is
tested explicitly by leave-one-route-out cross-validation.

Run: python probe_aft.py
"""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import numpy as np

XES = "{http://www.xes-standard.org/}"
PATH = "MainProcess_cleaned.xes"
MIN_N = 25          # minimum samples for a (resource, op) group
MIN_ROUTES = 3      # minimum distinct routes to make conditioning meaningful


def load():
    """Return {(resource, op): [(start, end, duration_s)]} for successful runs."""
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
            key = (a.get("case"), a.get("event_id"))
            rec = acts[key]
            rec.setdefault("resource", a.get("org:resource"))
            rec.setdefault("op", a.get("concept:name"))
            rec.setdefault("start", params.get("parameter_start_position"))
            rec.setdefault("end", params.get("parameter_end_position"))
            state = a.get("lifecycle:state")
            if state == "inProgress":
                rec["t0"] = datetime.fromisoformat(a["time:timestamp"])
                if a.get("operation_end_time"):
                    rec["t1"] = datetime.fromisoformat(a["operation_end_time"])
            if state in ("success", "failure"):
                rec["outcome"] = state

    for rec in acts.values():
        if rec.get("outcome") != "success":
            continue
        if not (rec.get("t0") and rec.get("t1")):
            continue
        if not (rec.get("start") and rec.get("end")):
            continue
        dur = (rec["t1"] - rec["t0"]).total_seconds()
        if dur <= 0:
            continue
        groups[(rec["resource"], rec["op"])].append((rec["start"], rec["end"], dur))
    return groups


def design(starts, ends, s_idx, e_idx):
    """Additive design matrix: intercept + start dummies + end dummies."""
    n = len(starts)
    X = np.zeros((n, 1 + len(s_idx) + len(e_idx)))
    X[:, 0] = 1.0
    for i, (s, e) in enumerate(zip(starts, ends)):
        if s in s_idx:
            X[i, 1 + s_idx[s]] = 1.0
        if e in e_idx:
            X[i, 1 + len(s_idx) + e_idx[e]] = 1.0
    return X


def fit_additive(starts, ends, y):
    s_idx = {p: i for i, p in enumerate(sorted(set(starts)))}
    e_idx = {p: i for i, p in enumerate(sorted(set(ends)))}
    X = design(starts, ends, s_idx, e_idx)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta, s_idx, e_idx


def robust_sigma(y):
    """MAD-based sigma; insensitive to the heavy left tails seen earlier."""
    return 1.4826 * np.median(np.abs(y - np.median(y)))


def main():
    groups = load()
    print(f"loaded {sum(len(v) for v in groups.values())} successful activity "
          f"instances carrying a route, in {len(groups)} (resource, op) groups\n")

    hdr = (f"{'resource':<8} {'operation':<28} {'n':>4} {'rt':>3} "
           f"{'M0 pool':>8} {'M1 addi':>8} {'M2 satu':>8} {'robust':>7} "
           f"{'var expl':>9} {'LOO-route':>10}")
    print(hdr)
    print("-" * len(hdr))

    rows = []
    for (res, op), vals in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        starts = [v[0] for v in vals]
        ends = [v[1] for v in vals]
        y = np.log(np.array([v[2] for v in vals]))
        routes = sorted(set(zip(starts, ends)))
        if len(y) < MIN_N or len(routes) < MIN_ROUTES:
            continue

        s0 = float(y.std(ddof=1))                       # M0
        beta, s_idx, e_idx = fit_additive(starts, ends, y)
        resid1 = y - design(starts, ends, s_idx, e_idx) @ beta
        s1 = float(resid1.std(ddof=1))                  # M1

        rmean = {}
        for r in routes:
            sel = [i for i, (s, e) in enumerate(zip(starts, ends)) if (s, e) == r]
            rmean[r] = y[sel].mean()
        resid2 = np.array([y[i] - rmean[(starts[i], ends[i])] for i in range(len(y))])
        s2 = float(resid2.std(ddof=1))                  # M2

        # leave-one-route-out: can M1 score a route it never trained on?
        loo_err = []
        for r in routes:
            tr = [i for i, (s, e) in enumerate(zip(starts, ends)) if (s, e) != r]
            te = [i for i, (s, e) in enumerate(zip(starts, ends)) if (s, e) == r]
            if len(tr) < 5 or not te:
                continue
            b, si, ei = fit_additive([starts[i] for i in tr],
                                     [ends[i] for i in tr], y[tr])
            # only scorable if both endpoints were seen in training
            if r[0] not in si or r[1] not in ei:
                continue
            pred = design([starts[i] for i in te], [ends[i] for i in te], si, ei) @ b
            loo_err.extend(list(y[te] - pred))
        loo = float(np.std(loo_err, ddof=1)) if len(loo_err) > 2 else float("nan")

        var_expl = 100 * (1 - (s1 ** 2) / (s0 ** 2)) if s0 > 0 else 0.0
        print(f"{res:<8} {op:<28} {len(y):>4} {len(routes):>3} "
              f"{s0:>8.3f} {s1:>8.3f} {s2:>8.3f} {robust_sigma(y):>7.3f} "
              f"{var_expl:>8.1f}% {loo:>10.3f}")
        rows.append((res, op, len(y), s0, s1, s2, loo))

    if not rows:
        print("no group met the sample-size threshold")
        return

    n = np.array([r[2] for r in rows], dtype=float)
    s0 = np.array([r[3] for r in rows])
    s1 = np.array([r[4] for r in rows])
    s2 = np.array([r[5] for r in rows])
    print()
    print(f"sample-weighted mean sigma_log   M0 pooled    = {np.average(s0, weights=n):.3f}")
    print(f"                                 M1 additive  = {np.average(s1, weights=n):.3f}")
    print(f"                                 M2 saturated = {np.average(s2, weights=n):.3f}")
    print(f"variance explained by the route covariate      = "
          f"{100 * (1 - np.average(s1, weights=n) ** 2 / np.average(s0, weights=n) ** 2):.1f}%")
    gap = np.average(s1, weights=n) - np.average(s2, weights=n)
    print(f"additive vs saturated gap (cost of few params) = {gap:+.3f}")

    print()
    print("detection-power implication at alpha=0.001 (two-sided, normal approx):")
    for label, s in (("pooled  (M0)", np.average(s0, weights=n)),
                     ("additive (M1)", np.average(s1, weights=n))):
        # schedule advance rho detectable at ~3.29 sigma from a single observation
        rho = 1 - np.exp(-3.29 * s)
        print(f"  {label}: sigma={s:.3f} -> single-message detectable advance "
              f"rho ~ {100 * rho:.1f}%")


if __name__ == "__main__":
    main()
