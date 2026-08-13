"""Why does formulation B still overshoot the nominal FPR after randomisation?

probe_structural_v2.py split the case keys in sorted order. Case ids look like
"WF_101_0", so a lexicographic split puts entirely different workflows into the
fit, calibration and test folds. Conformal validity needs the calibration and
test sets to be exchangeable; splitting across product types breaks that.

This script re-runs formulation B under two split strategies, repeated over
several seeds, to separate a genuine calibration defect from a distribution
shift induced by the split.

Run: python probe_structural_v3.py
"""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import numpy as np

XES = "{http://www.xes-standard.org/}"
PATH = "MainProcess_cleaned.xes"
ALPHA0 = 0.5
ALPHAS = (0.05, 0.01)


def load_cases():
    acts = defaultdict(dict)
    for trace in ET.parse(PATH).getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            a = {c.get("key"): c.get("value") for c in ev if c.get("key")}
            rec = acts[(a.get("case"), a.get("event_id"))]
            rec.setdefault("case", a.get("case"))
            rec.setdefault("wf", a.get("process_model_id"))
            rec.setdefault("op", a.get("concept:name"))
            st = a.get("lifecycle:state")
            if st == "inProgress" and a.get("time:timestamp"):
                rec["t"] = datetime.fromisoformat(a["time:timestamp"])
            if st in ("success", "failure"):
                rec["outcome"] = st
    seqs, wf = defaultdict(list), {}
    for r in sorted((r for r in acts.values()
                     if r.get("outcome") == "success" and r.get("t")),
                    key=lambda r: r["t"]):
        seqs[r["case"]].append(r["op"])
        wf[r["case"]] = r["wf"]
    return seqs, wf


def run(seqs, fit_k, cal_k, test_k, randomised, rng):
    states = sorted({s for v in seqs.values() for s in v})
    idx = {s: i for i, s in enumerate(states)}
    counts = np.zeros((len(states), len(states)))
    for k in fit_k:
        for a, b in zip(seqs[k], seqs[k][1:]):
            counts[idx[a], idx[b]] += 1

    def collect(ks):
        ps = []
        for k in ks:
            for a, b in zip(seqs[k], seqs[k][1:]):
                row = counts[idx[a]] + ALPHA0
                pred = row / row.sum()
                po = pred[idx[b]]
                below = float(pred[pred < po - 1e-15].sum())
                at = float(pred[np.abs(pred - po) <= 1e-15].sum())
                ps.append(below + (rng.random() * at if randomised else at))
        return np.array(ps)

    p_cal, p_test = collect(cal_k), collect(test_k)
    out = {}
    for a in ALPHAS:
        out[a] = float((p_test <= np.quantile(p_cal, a)).mean())
    return out, len(p_test)


def main():
    seqs, wf = load_cases()
    keys = sorted(seqs)
    print(f"{len(keys)} cases, {len(set(wf.values()))} workflows, "
          f"{sum(max(0, len(v) - 1) for v in seqs.values())} transitions\n")

    hdr = (f"{'split':<28} {'randomised':>11} {'a=0.05':>9} {'a=0.01':>9}")
    print(hdr)
    print("-" * len(hdr))

    # 1. lexicographic split (what v2 did): folds contain different workflows
    n = len(keys)
    lex = (keys[:n // 2], keys[n // 2:int(n * .75)], keys[int(n * .75):])
    for rnd in (False, True):
        r, _ = run(seqs, *lex, rnd, np.random.default_rng(0))
        print(f"{'lexicographic (by workflow)':<28} {str(rnd):>11} "
              f"{r[0.05]:>9.3f} {r[0.01]:>9.3f}")

    # 2. random split, averaged over seeds: folds are exchangeable
    for rnd in (False, True):
        acc = {a: [] for a in ALPHAS}
        for seed in range(20):
            rng = np.random.default_rng(seed)
            ks = list(keys)
            rng.shuffle(ks)
            sp = (ks[:n // 2], ks[n // 2:int(n * .75)], ks[int(n * .75):])
            r, _ = run(seqs, *sp, rnd, rng)
            for a in ALPHAS:
                acc[a].append(r[a])
        print(f"{'random (exchangeable), x20':<28} {str(rnd):>11} "
              f"{np.mean(acc[0.05]):>9.3f} {np.mean(acc[0.01]):>9.3f}")

    # 3. how much do the workflows differ? entropy of the next-activity
    #    distribution, per workflow, to quantify the shift
    print()
    wf_states = defaultdict(lambda: defaultdict(Counter_) if False else None)
    from collections import Counter
    per_wf = defaultdict(Counter)
    for k, seq in seqs.items():
        for a, b in zip(seq, seq[1:]):
            per_wf[wf[k]][(a, b)] += 1
    wfs = sorted(per_wf)
    print(f"transition-set overlap between workflows (Jaccard):")
    ov = []
    for i in range(len(wfs)):
        for j in range(i + 1, len(wfs)):
            A, Bs = set(per_wf[wfs[i]]), set(per_wf[wfs[j]])
            if A and Bs:
                ov.append(len(A & Bs) / len(A | Bs))
    print(f"  median {np.median(ov):.3f}, mean {np.mean(ov):.3f} over "
          f"{len(ov)} workflow pairs")
    print("  low overlap means a fold containing unseen workflows is not")
    print("  exchangeable with the calibration fold, which is what breaks the")
    print("  nominal FPR under the lexicographic split.")


if __name__ == "__main__":
    main()
