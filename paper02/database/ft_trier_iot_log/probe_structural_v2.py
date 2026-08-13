"""Follow-up to probe_structural.py, which produced two alarming numbers:
only 48.6% of observed device transitions fell inside F, and the conformal FPR
was 0.69 against a nominal 0.05. Both need to be attributed before they can be
believed.

Hypothesis for the first: the chain was built over each device's *global*
timeline, so consecutive operations belong to different cases. F is derived from
within-workflow reachability and simply does not apply across a case boundary.
The fix is to segment every device chain by case.

Hypothesis for the second: the structural p-value is highly atomic (a device
with one operation emits p = 1.0 always). An empirical quantile of an atomic
distribution lands *on* an atom, so everything at that atom is flagged. The
standard remedy is the randomised (smoothed) p-value, which is exactly uniform
under the null even for discrete statistics.

This script tests both, and compares two chain formulations:
  A  per (device, case)  - the device's own state chain inside one job
  B  per case            - the workflow-level activity sequence

Run: python probe_structural_v2.py
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
ALPHA0 = 0.5
ALPHAS = (0.05, 0.01)
RNG = np.random.default_rng(0)


def load():
    acts = defaultdict(dict)
    for trace in ET.parse(PATH).getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            a = {c.get("key"): c.get("value") for c in ev if c.get("key")}
            rec = acts[(a.get("case"), a.get("event_id"))]
            rec.setdefault("case", a.get("case"))
            rec.setdefault("resource", a.get("org:resource"))
            rec.setdefault("op", a.get("concept:name"))
            st = a.get("lifecycle:state")
            if st == "inProgress" and a.get("time:timestamp"):
                rec["t"] = datetime.fromisoformat(a["time:timestamp"])
            if st in ("success", "failure"):
                rec["outcome"] = st
    out = [r for r in acts.values()
           if r.get("outcome") == "success" and r.get("t") and r.get("resource")]
    out.sort(key=lambda r: r["t"])
    return out


def bpmn_allowed():
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


def chains(events, mode):
    """mode 'A': per (device, case). mode 'B': per case, workflow level."""
    out = defaultdict(list)
    for r in events:
        key = (r["resource"], r["case"]) if mode == "A" else r["case"]
        out[key].append(r["op"] if mode == "B" else r["op"])
    return out


def p_struct(counts, idx, prev, cur, randomised):
    row = counts[idx[prev]] + ALPHA0
    pred = row / row.sum()
    p_obs = pred[idx[cur]]
    below = float(pred[pred < p_obs - 1e-15].sum())
    at = float(pred[np.abs(pred - p_obs) <= 1e-15].sum())
    if randomised:
        return below + RNG.random() * at
    return below + at


def evaluate(chain_dict, label, randomised):
    keys = sorted(chain_dict)
    n = len(keys)
    fit_k, cal_k, test_k = keys[:n // 2], keys[n // 2:int(n * .75)], keys[int(n * .75):]
    states = sorted({s for k in keys for s in chain_dict[k]})
    idx = {s: i for i, s in enumerate(states)}
    counts = np.zeros((len(states), len(states)))
    for k in fit_k:
        seq = chain_dict[k]
        for a, b in zip(seq, seq[1:]):
            counts[idx[a], idx[b]] += 1

    def collect(ks):
        ps = []
        for k in ks:
            seq = chain_dict[k]
            for a, b in zip(seq, seq[1:]):
                ps.append(p_struct(counts, idx, a, b, randomised))
        return np.array(ps)

    p_cal, p_test = collect(cal_k), collect(test_k)
    if len(p_cal) < 20 or len(p_test) < 20:
        return None
    res = {"states": len(states), "trans_fit": int(counts.sum()),
           "distinct": int((counts > 0).sum()),
           "n_cal": len(p_cal), "n_test": len(p_test),
           "uniq_p": len(np.unique(np.round(p_test, 9)))}
    for a in ALPHAS:
        thr = np.quantile(p_cal, a)
        res[a] = float((p_test <= thr).mean())
    return res


def main():
    events = load()
    allowed = bpmn_allowed()

    print("=== chain formulation A: per (device, case) ===")
    A = chains(events, "A")
    lens = Counter(len(v) for v in A.values())
    total = sum(lens.values())
    print(f"  {total} (device, case) chains")
    for L in sorted(lens):
        print(f"    length {L:>2}: {lens[L]:>5} chains "
              f"({100 * lens[L] / total:>5.1f}%)")
    trans = sum(max(0, len(v) - 1) for v in A.values())
    print(f"  usable transitions inside a (device, case) chain: {trans}")
    inF = 0
    for (d, _), seq in A.items():
        for a, b in zip(seq, seq[1:]):
            if a == b or (a, b) in allowed.get(d, set()):
                inF += 1
    print(f"  of which inside F (or self-loop): {inF} "
          f"({100 * inF / max(trans, 1):.1f}%)")
    print()

    print("=== chain formulation B: per case, workflow level ===")
    Bc = chains(events, "B")
    lens_b = [len(v) for v in Bc.values()]
    print(f"  {len(Bc)} case chains, median length {int(np.median(lens_b))}, "
          f"total transitions {sum(l - 1 for l in lens_b if l > 1)}")
    states_b = sorted({s for v in Bc.values() for s in v})
    print(f"  states (distinct activities): {len(states_b)}")
    variants = len({tuple(v) for v in Bc.values()})
    print(f"  distinct sequences (variants): {variants} / {len(Bc)} cases")
    print()

    print("=== conformal FPR: plain vs randomised p-values ===")
    hdr = (f"  {'formulation':<26} {'states':>6} {'fit tr':>7} {'uniq p':>7} "
           f"{'a=0.05':>8} {'a=0.01':>8}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for mode, cd in (("A per (device, case)", A), ("B per case (workflow)", Bc)):
        for rnd in (False, True):
            r = evaluate(cd, mode, rnd)
            if r is None:
                print(f"  {mode + (' randomised' if rnd else ' plain'):<26} "
                      f"insufficient data")
                continue
            tag = mode + (" randomised" if rnd else " plain")
            print(f"  {tag:<26} {r['states']:>6} {r['trans_fit']:>7} "
                  f"{r['uniq_p']:>7} {r[0.05]:>8.3f} {r[0.01]:>8.3f}")
    print()
    print("  nominal alpha is the target; a value far above it means the channel")
    print("  cannot honour the false-alarm budget in that formulation.")


if __name__ == "__main__":
    main()
