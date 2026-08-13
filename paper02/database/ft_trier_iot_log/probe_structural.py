"""Feasibility of the structural channel (M3) on the Trier log.

Three questions, in order of how badly a negative answer would hurt:

  Q1  After splitting the joint chain per device, how many states does each
      device chain have and how many transition samples back each row? The old
      method fitted a 7-state joint chain from 188 samples; if the real per
      device chains are similarly starved, the Dirichlet posterior is prior
      dominated and the channel carries no information.

  Q2  Does the structural channel add anything over F? F is already derived from
      BPMN with a 0.00% benign violation rate, so the structural channel only
      earns its place if it can grade *allowed but rare* transitions. If every
      observed transition is common, the channel is redundant.

  Q3  Does conformal calibration actually hold the nominal FPR on held-out
      benign data? This is the claim that replaces the old F1 grid search, so it
      has to be measured, not asserted.

A device's chain is its own global timeline, not a per-case one: the physical
machine is shared across concurrently running cases.

Run: python probe_structural.py
"""
import glob
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import numpy as np

XES = "{http://www.xes-standard.org/}"
B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
C = "{http://camunda.org/schema/1.0/bpmn}"
PATH = "MainProcess_cleaned.xes"
ALPHA0 = 0.5          # Jeffreys-style Dirichlet concentration per cell
ALPHAS = (0.05, 0.01, 0.001)


def load_timeline():
    """{resource: [(t, op)]} over the whole log, ordered by execution start."""
    acts = defaultdict(dict)
    for trace in ET.parse(PATH).getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            a = {c.get("key"): c.get("value") for c in ev if c.get("key")}
            rec = acts[(a.get("case"), a.get("event_id"))]
            rec.setdefault("resource", a.get("org:resource"))
            rec.setdefault("op", a.get("concept:name"))
            st = a.get("lifecycle:state")
            if st == "inProgress" and a.get("time:timestamp"):
                rec["t"] = datetime.fromisoformat(a["time:timestamp"])
            if st in ("success", "failure"):
                rec["outcome"] = st

    tl = defaultdict(list)
    for rec in acts.values():
        if rec.get("outcome") == "success" and rec.get("t") and rec.get("resource"):
            tl[rec["resource"]].append((rec["t"], rec["op"]))
    for d in tl:
        tl[d].sort()
    return tl


def bpmn_allowed():
    """F: same-device operation pairs reachable in any BPMN model."""
    allowed = defaultdict(set)
    for f in sorted(glob.glob("bpmn-models/*.bpmn")):
        proc = ET.parse(f).getroot().find(B + "process")
        acts, succ = {}, defaultdict(set)
        for st in proc.findall(B + "serviceTask"):
            url = None
            for ip in st.iter(C + "inputParameter"):
                if ip.get("name") == "url":
                    url = " ".join((ip.text or "").split())
            if not url or url == "TO_BE_SET":
                acts[st.get("id")] = None
                continue
            u = urlparse(url)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            acts[st.get("id")] = (u.path, q.get("resource"))
        for sf in proc.findall(B + "sequenceFlow"):
            succ[sf.get("sourceRef")].add(sf.get("targetRef"))

        def reach(node):
            seen, stack, out = set(), [node], set()
            while stack:
                n = stack.pop()
                for nx in succ.get(n, ()):
                    if nx in seen:
                        continue
                    seen.add(nx)
                    stack.append(nx)
                    if acts.get(nx):
                        out.add(nx)
            return out

        for aid, a in acts.items():
            if not a:
                continue
            for bid in reach(aid):
                b = acts[bid]
                if b and b[1] == a[1]:
                    allowed[a[1]].add((a[0], b[0]))
    return allowed


def pvalues(counts, states, seq):
    """Dirichlet posterior-predictive structural p-value for each transition."""
    k = len(states)
    idx = {s: i for i, s in enumerate(states)}
    out = []
    for prev, cur in zip(seq, seq[1:]):
        row = counts[idx[prev]] + ALPHA0
        pred = row / row.sum()
        p_obs = pred[idx[cur]]
        # p-value = total predictive mass on outcomes no more likely than observed
        out.append(float(pred[pred <= p_obs + 1e-15].sum()))
    return out


def main():
    tl = load_timeline()
    allowed = bpmn_allowed()

    print("=== Q1: per-device chain size and transition sample support ===")
    hdr = (f"{'device':<8} {'ops':>4} {'trans':>6} {'distinct':>9} {'cells':>6} "
           f"{'density':>8} {'med n':>6} {'n<5':>6} {'inF':>7}")
    print(hdr)
    print("-" * len(hdr))

    per_dev = {}
    tot_obs_pairs = tot_in_f = 0
    for d, evs in sorted(tl.items(), key=lambda kv: -len(kv[1])):
        seq = [op for _, op in evs]
        if len(seq) < 20:
            continue
        states = sorted(set(seq))
        idx = {s: i for i, s in enumerate(states)}
        counts = np.zeros((len(states), len(states)))
        for a, b in zip(seq, seq[1:]):
            counts[idx[a], idx[b]] += 1
        distinct = int((counts > 0).sum())
        cells = len(states) ** 2
        nz = counts[counts > 0]
        in_f = sum(1 for a, b in {(a, b) for a, b in zip(seq, seq[1:])}
                   if (a, b) in allowed.get(d, set()) or a == b)
        tot_obs_pairs += distinct
        tot_in_f += in_f
        print(f"{d:<8} {len(states):>4} {len(seq) - 1:>6} {distinct:>9} {cells:>6} "
              f"{100 * distinct / cells:>7.1f}% {int(np.median(nz)):>6} "
              f"{int((nz < 5).sum()):>6} {in_f:>3}/{distinct:<3}")
        per_dev[d] = (seq, states, counts)

    print()
    print(f"  observed distinct transitions: {tot_obs_pairs}, "
          f"of which inside F (or self-loop): {tot_in_f} "
          f"({100 * tot_in_f / max(tot_obs_pairs, 1):.1f}%)")
    print()

    print("=== Q2: does the structural channel grade anything F cannot? ===")
    rare = 0
    for d, (seq, states, counts) in per_dev.items():
        tot = counts.sum()
        for i, a in enumerate(states):
            for j, b in enumerate(states):
                if 0 < counts[i, j] <= 2 and counts[i].sum() >= 10:
                    rare += 1
    print(f"  allowed-but-rare transitions (observed 1-2 times from a row with")
    print(f"  >=10 samples): {rare}. These are invisible to F but graded by M3.")
    print()

    print("=== Q3: conformal calibration on held-out benign data ===")
    print(f"  split each device timeline 50% fit / 25% calibrate / 25% test")
    hdr = f"  {'device':<8}" + "".join(f"{'a=' + str(a):>12}" for a in ALPHAS)
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    agg = defaultdict(list)
    for d, (seq, states, _) in sorted(per_dev.items()):
        n = len(seq)
        i1, i2 = int(n * 0.5), int(n * 0.75)
        fit_seq, cal_seq, test_seq = seq[:i1], seq[i1:i2], seq[i2:]
        if len(cal_seq) < 10 or len(test_seq) < 10:
            continue
        idx = {s: i for i, s in enumerate(states)}
        counts = np.zeros((len(states), len(states)))
        for a, b in zip(fit_seq, fit_seq[1:]):
            counts[idx[a], idx[b]] += 1
        p_cal = np.array(pvalues(counts, states, cal_seq))
        p_test = np.array(pvalues(counts, states, test_seq))
        if len(p_cal) < 5 or len(p_test) < 5:
            continue
        row = f"  {d:<8}"
        for a in ALPHAS:
            thr = np.quantile(p_cal, a)      # conformal threshold from calib set
            fpr = float((p_test <= thr).mean())
            agg[a].append((fpr, len(p_test)))
            row += f"{fpr:>11.3f} "
        print(row)
    print()
    for a in ALPHAS:
        if agg[a]:
            v = np.array([x[0] for x in agg[a]])
            w = np.array([x[1] for x in agg[a]], dtype=float)
            print(f"  nominal alpha={a:<6} -> empirical FPR "
                  f"{np.average(v, weights=w):.4f}  (weighted over devices)")


if __name__ == "__main__":
    main()
