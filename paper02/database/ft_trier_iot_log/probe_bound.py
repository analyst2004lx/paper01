"""Validate the impact-detectability bound by injecting schedule-advance attacks
into the real log and comparing the measured detection rate with the prediction.

Attack model (A-advance): the attacker makes a device report completion earlier
than physically possible, shrinking the observed duration to (1 - rho) * tau.
In log space this is a pure location shift of Delta = log(1 - rho), so for a
route-conditioned lognormal dwell time the standardised shift is Delta / sigma
and the single-message detection power at level alpha is

    DR(rho) = Phi(-z - Delta/sigma) + 1 - Phi(z - Delta/sigma),   two-sided
    DR(rho) = Phi(-z1 - Delta/sigma),                             one-sided

with z = z_{1-alpha/2}, z1 = z_{1-alpha}. Defining rho* as the 50%-power point
gives rho* = 1 - exp(-z * sigma), the quantity the paper claims to bound.

Two things can make the measured curve fall short of that prediction, and the
point of the experiment is to size them:
  - sigma is estimated from finite training data, not known;
  - the threshold is set by conformal calibration on real residuals, whose tails
    are not exactly Gaussian.

The script also runs a CUSUM to measure how many messages the sequential test
needs, which is the number that actually matters for a detector.

Run: python probe_bound.py
"""
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import numpy as np
from math import erf, sqrt, log, exp

XES = "{http://www.xes-standard.org/}"
PATH = "MainProcess_cleaned.xes"
RHOS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)
ALPHA = 0.01
MIN_ROUTE_N = 8
MIN_GROUP_N = 30
RNG = np.random.default_rng(7)


def Phi(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def z_of(p):
    """Inverse normal CDF by bisection; adequate for the few values needed."""
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if Phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def load():
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
            st = a.get("lifecycle:state")
            if st == "inProgress":
                rec["t0"] = datetime.fromisoformat(a["time:timestamp"])
                if a.get("operation_end_time"):
                    rec["t1"] = datetime.fromisoformat(a["operation_end_time"])
            if st in ("success", "failure"):
                rec["outcome"] = st

    rows = []
    for rec in acts.values():
        if rec.get("outcome") != "success" or not (rec.get("t0") and rec.get("t1")):
            continue
        dur = (rec["t1"] - rec["t0"]).total_seconds()
        if dur <= 0:
            continue
        route = (rec.get("start") or "-", rec.get("end") or "-")
        rows.append({"grp": (rec["resource"], rec["op"]), "route": route,
                     "t": rec["t0"], "y": log(dur), "dev": rec["resource"]})
    rows.sort(key=lambda r: r["t"])
    return rows


def build_folds(rows):
    """Per (group, route): split into fit / calib / test, then standardise."""
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r["grp"], r["route"])].append(r)
    by_grp = defaultdict(list)
    for (grp, route), items in by_key.items():
        if len(items) < MIN_ROUTE_N:
            continue
        by_grp[grp].append((route, items))

    cal, test = [], []
    sigmas = {}
    for grp, routes in by_grp.items():
        n_tot = sum(len(v) for _, v in routes)
        if n_tot < MIN_GROUP_N:
            continue
        fit_parts, cal_parts, test_parts = [], [], []
        for route, items in routes:
            idx = RNG.permutation(len(items))
            a, b = int(len(items) * 0.5), int(len(items) * 0.75)
            fit_parts.append([items[i] for i in idx[:a]])
            cal_parts.append([items[i] for i in idx[a:b]])
            test_parts.append([items[i] for i in idx[b:]])
        # route means and a pooled within-route sigma, both from the fit fold
        mu, ss, df = {}, 0.0, 0
        for (route, _), part in zip(routes, fit_parts):
            if len(part) < 2:
                continue
            ys = np.array([p["y"] for p in part])
            mu[route] = float(ys.mean())
            ss += float(((ys - ys.mean()) ** 2).sum())
            df += len(ys) - 1
        if df < 5 or not mu:
            continue
        sigma = sqrt(ss / df)
        if sigma <= 1e-6:
            continue
        sigmas[grp] = sigma
        for parts, sink in ((cal_parts, cal), (test_parts, test)):
            for (route, _), part in zip(routes, parts):
                if route not in mu:
                    continue
                for p in part:
                    sink.append({"z": (p["y"] - mu[route]) / sigma,
                                 "sigma": sigma, "grp": grp, "dev": p["dev"],
                                 "t": p["t"]})
    return cal, test, sigmas


def main():
    rows = load()
    cal, test, sigmas = build_folds(rows)
    print(f"instances={len(rows)}  groups modelled={len(sigmas)}  "
          f"calib={len(cal)}  test={len(test)}")
    sig = np.array([s for s in sigmas.values()])
    w = np.array([sum(1 for r in test if r['grp'] == g) for g in sigmas], dtype=float)
    sigma_bar = float(np.average(sig, weights=w)) if w.sum() else float(sig.mean())
    print(f"sigma per group: min={sig.min():.3f} median={np.median(sig):.3f} "
          f"max={sig.max():.3f}  test-weighted mean={sigma_bar:.3f}")
    print()

    z_cal = np.array([r["z"] for r in cal])
    z_test = np.array([r["z"] for r in test])
    s_test = np.array([r["sigma"] for r in test])

    # conformal thresholds from the calibration fold
    thr_two = float(np.quantile(np.abs(z_cal), 1 - ALPHA))
    thr_one = float(np.quantile(-z_cal, 1 - ALPHA))
    print(f"conformal thresholds at alpha={ALPHA}: "
          f"two-sided |z|>{thr_two:.3f}   one-sided -z>{thr_one:.3f}")
    print(f"  (Gaussian reference: {z_of(1 - ALPHA / 2):.3f} / {z_of(1 - ALPHA):.3f})")
    print(f"empirical FPR on clean test data: "
          f"two-sided {np.mean(np.abs(z_test) > thr_two):.4f}   "
          f"one-sided {np.mean(-z_test > thr_one):.4f}")
    g2, g1 = z_of(1 - ALPHA / 2), z_of(1 - ALPHA)
    print(f"  if a Gaussian threshold were used instead of conformal: "
          f"two-sided {np.mean(np.abs(z_test) > g2):.4f}   "
          f"one-sided {np.mean(-z_test > g1):.4f}   (nominal {ALPHA})")
    print(f"  residual tail asymmetry: q99(+z)={np.quantile(z_test, 0.99):6.2f}   "
          f"q99(-z)={np.quantile(-z_test, 0.99):6.2f}")
    print()
    print("  per-group sigma (sorted), test instances in brackets:")
    order = sorted(sigmas.items(), key=lambda kv: kv[1])
    for g, s in order:
        n = sum(1 for r in test if r["grp"] == g)
        rho_star = 100 * (1 - exp(-z_of(1 - ALPHA) * s))
        print(f"    {g[0]:<7} {g[1]:<30} sigma={s:6.3f}  n={n:>3}  "
              f"rho*(1-sided)={rho_star:5.1f}%")
    print()

    print("=== single-message detection: measured vs predicted ===")
    hdr = (f"{'rho':>6} {'|Delta|':>8} {'D/sig':>7} "
           f"{'DR 2-sided':>11} {'pred':>7} {'DR 1-sided':>11} {'pred':>7}")
    print(hdr)
    print("-" * len(hdr))
    for rho in RHOS:
        d = log(1 - rho)                      # negative
        shift = d / s_test                    # per-instance standardised shift
        za = z_test + shift
        dr2 = float(np.mean(np.abs(za) > thr_two))
        dr1 = float(np.mean(-za > thr_one))
        pr2 = float(np.mean([Phi(-thr_two - s) + 1 - Phi(thr_two - s)
                             for s in shift]))
        pr1 = float(np.mean([Phi(-thr_one - s) for s in shift]))
        print(f"{rho:>6.2f} {abs(d):>8.3f} {abs(d) / sigma_bar:>7.2f} "
              f"{dr2:>11.3f} {pr2:>7.3f} {dr1:>11.3f} {pr1:>7.3f}")
    print()

    zc = z_of(1 - ALPHA / 2)
    print(f"predicted rho* (50% power, two-sided, alpha={ALPHA}):")
    for name, s in (("best group ", sig.min()), ("median group", float(np.median(sig))),
                    ("worst group", sig.max())):
        print(f"  {name} sigma={s:.3f} -> rho* = {100 * (1 - exp(-zc * s)):5.1f}%")
    print()

    # ---------------- sequential CUSUM ----------------
    print("=== CUSUM: detection delay in messages ===")
    delta = 1.0          # design shift in sigma units
    # calibrate h on the clean calibration stream for a target ARL0
    def run_cusum(zs, h):
        S = 0.0
        for i, z in enumerate(zs):
            S = max(0.0, S - delta * z - delta * delta / 2)
            if S > h:
                return i + 1
        return None

    target_arl0 = 500
    lo, hi = 0.5, 30.0
    for _ in range(40):
        h = (lo + hi) / 2
        runs, i = [], 0
        zc_stream = z_cal
        S, since = 0.0, 0
        for z in zc_stream:
            S = max(0.0, S - delta * z - delta * delta / 2)
            since += 1
            if S > h:
                runs.append(since)
                S, since = 0.0, 0
        arl = np.mean(runs) if runs else len(zc_stream) * 2
        if arl < target_arl0:
            lo = h
        else:
            hi = h
    h = (lo + hi) / 2
    print(f"  design shift delta={delta} sigma, threshold h={h:.2f} "
          f"calibrated for ARL0>={target_arl0} on clean data")
    print(f"  {'rho':>6} {'det rate':>9} {'median delay':>13} {'p90 delay':>10}")
    per_dev = defaultdict(list)
    for r in sorted(test, key=lambda r: r["t"]):
        per_dev[r["dev"]].append(r)
    for rho in RHOS:
        d = log(1 - rho)
        delays, det = [], 0
        trials = 0
        for dev, items in per_dev.items():
            if len(items) < 5:
                continue
            zs = np.array([it["z"] + d / it["sigma"] for it in items])
            for startpos in range(0, max(1, len(zs) - 20), 10):
                trials += 1
                k = run_cusum(zs[startpos:startpos + 40], h)
                if k is not None:
                    det += 1
                    delays.append(k)
        if trials:
            md = int(np.median(delays)) if delays else -1
            p90 = int(np.percentile(delays, 90)) if delays else -1
            print(f"  {rho:>6.2f} {det / trials:>9.3f} {md:>13d} {p90:>10d}")


if __name__ == "__main__":
    main()
