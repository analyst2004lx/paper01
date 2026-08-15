"""Final derivation of F and I, plus a breakdown of every residual violation.

Progression of the benign-data violation rate for the token preconditions (I):
    v1  naive, one token type, immediate-successor F   14.87%
    v2  + two token colours, transitive F, sorter alias 2.96%
    v3  + alias closed over observed positions, retries  see below

v3 also separates *truncated* cases (traces that do not begin with a warehouse
source op, i.e. the recording started mid-process) from complete ones, because
a truncated trace cannot satisfy a token precondition no matter how good the
invariant is. That distinction is what decides whether I is usable as a hard
constraint in an online detector.

Run: python derive_invariants_v3.py
"""
import glob
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse, parse_qs

B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
C = "{http://camunda.org/schema/1.0/bpmn}"
XES = "{http://www.xes-standard.org/}"

WORKPIECE, BUCKET = "wp", "bk"
SOURCE_OPS = {"/hbw/unload", "/hbw/get_empty_bucket"}
HBW_EFFECTS = {
    "/hbw/unload":             ([], [WORKPIECE, BUCKET]),
    "/hbw/get_empty_bucket":   ([], [BUCKET]),
    "/hbw/store_empty_bucket": ([BUCKET], []),
    "/hbw/store":              ([WORKPIECE, BUCKET], []),
}
SORTER_POS = re.compile(r"(sm_\d+)_(automatic|sink_\d+)(_dropoff)?_pos$")


def parse_bpmn(path):
    proc = ET.parse(path).getroot().find(B + "process")
    acts, edges = {}, []
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
        acts[st.get("id")] = {"op": u.path, "resource": q.get("resource"),
                              "start": q.get("start"), "end": q.get("end")}
    for sf in proc.findall(B + "sequenceFlow"):
        edges.append((sf.get("sourceRef"), sf.get("targetRef")))
    return acts, edges


def effects(a):
    res, op = a["resource"], a["op"]
    if a["start"] and a["end"]:
        return [(WORKPIECE, a["start"])], [(WORKPIECE, a["end"])]
    pos = f"{res}_pos"
    if op in HBW_EFFECTS:
        cons, prod = HBW_EFFECTS[op]
        return [(t, pos) for t in cons], [(t, pos) for t in prod]
    return [(WORKPIECE, pos)], [(WORKPIECE, pos)]


def build_alias(positions):
    groups = defaultdict(set)
    for p in positions:
        m = SORTER_POS.match(p)
        if m:
            groups[m.group(1)].add(p)
    return {p: frozenset(g) for g in groups.values() for p in g}


def derive():
    move_graph, dev_reach, positions = set(), defaultdict(set), set()
    for f in sorted(glob.glob("bpmn-models/*.bpmn")):
        acts, edges = parse_bpmn(f)
        succ = defaultdict(set)
        for s, t in edges:
            succ[s].add(t)

        def reachable(node):
            seen, stack, out = set(), [node], set()
            while stack:
                n = stack.pop()
                for nxt in succ.get(n, ()):
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    stack.append(nxt)
                    if acts.get(nxt):
                        out.add(nxt)
            return out

        for aid, a in acts.items():
            if a is None:
                continue
            for p in (a["start"], a["end"]):
                if p:
                    positions.add(p)
            if not (a["start"] and a["end"]):
                positions.add(f"{a['resource']}_pos")
            if a["start"] and a["end"]:
                move_graph.add((a["start"], a["end"]))
            for bid in reachable(aid):
                b = acts[bid]
                if b and b["resource"] == a["resource"]:
                    dev_reach[a["resource"]].add((a["op"], b["op"]))
    return move_graph, dev_reach, positions


def parse_log(path):
    cases = defaultdict(dict)
    for trace in ET.parse(path).getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            a, params = {}, {}
            for child in ev:
                if child.tag == XES + "list" and child.get("key") == "parameters":
                    for vals in child:
                        for v in vals:
                            params[v.get("key")] = v.get("value")
                elif child.get("key"):
                    a[child.get("key")] = child.get("value")
            key = a.get("event_id")
            rec = cases[a.get("case")].setdefault(key, {
                "op": a.get("concept:name"), "resource": a.get("org:resource"),
                "start": params.get("parameter_start_position"),
                "end": params.get("parameter_end_position"),
                "order": int(key) if key and key.isdigit() else 0})
            if a.get("time:timestamp"):
                rec[f"t_{a.get('lifecycle:state')}"] = datetime.fromisoformat(
                    a["time:timestamp"])
            if a.get("lifecycle:state") in ("success", "failure"):
                rec["outcome"] = a["lifecycle:state"]
    return cases


def take(tokens, ttype, pos, alias):
    if tokens[(ttype, pos)] > 0:
        tokens[(ttype, pos)] -= 1
        return True
    for p in alias.get(pos, ()):
        if tokens[(ttype, p)] > 0:
            tokens[(ttype, p)] -= 1
            return True
    return False


def main():
    move_graph, dev_reach, bpmn_pos = derive()
    cases = parse_log("MainProcess_cleaned.xes")

    log_pos = {p for acts in cases.values() for r in acts.values()
               for p in (r["start"], r["end"]) if p}
    alias = build_alias(bpmn_pos | log_pos)
    only_in_log = sorted(p for p in log_pos if p not in bpmn_pos)

    print("=== derived automatically from 16 BPMN models ===")
    print(f"  positions in BPMN    : {len(bpmn_pos)}")
    print(f"  material-flow edges  : {len(move_graph)}")
    print(f"  device op pairs (F)  : {sum(len(v) for v in dev_reach.values())}")
    print(f"  sorter alias classes : {len(set(alias.values()))}")
    print(f"  positions seen in log but absent from every BPMN: {only_in_log}")
    print()

    tot, detail = Counter(), Counter()
    bad_complete, bad_trunc = set(), set()
    for case, acts in cases.items():
        insts = sorted(acts.values(),
                       key=lambda r: (r.get("t_inProgress") or r.get("t_assigned")
                                      or datetime.min, r["order"]))
        insts = [r for r in insts if r["resource"] and r["op"]
                 and r.get("outcome") != "failure"]
        if not insts:
            continue
        truncated = insts[0]["op"] not in SOURCE_OPS
        tot["cases"] += 1
        tot["truncated_cases"] += truncated
        tokens, last_op = Counter(), {}
        for r in insts:
            tot["activities"] += 1
            bucket = "trunc" if truncated else "complete"
            cons, prod = effects(r)
            for ttype, pos in cons:
                tot[f"I_checked_{bucket}"] += 1
                if not take(tokens, ttype, pos, alias):
                    tot[f"I_viol_{bucket}"] += 1
                    detail[("I", bucket, r["resource"], r["op"], pos)] += 1
                    (bad_trunc if truncated else bad_complete).add(case)
            for ttype, pos in prod:
                tokens[(ttype, pos)] += 1
            if r["start"] and r["end"]:
                tot["move_checked"] += 1
                if (r["start"], r["end"]) not in move_graph:
                    tot["coverage_gap"] += 1
                    detail[("GAP", "", r["start"], r["end"], "")] += 1
            d = r["resource"]
            if d in last_op:
                tot[f"F_checked_{bucket}"] += 1
                # a device repeating the same op is a retry, not a new transition
                if last_op[d] != r["op"] and (last_op[d], r["op"]) not in dev_reach[d]:
                    tot[f"F_viol_{bucket}"] += 1
                    detail[("F", bucket, d, f"{last_op[d]} -> {r['op']}", "")] += 1
            last_op[d] = r["op"]

    print(f"=== validation ({tot['cases']} cases, {tot['activities']} activities, "
          f"failures excluded) ===")
    print(f"  truncated cases (do not start at a warehouse source op): "
          f"{tot['truncated_cases']} / {tot['cases']}")
    print()
    hdr = f"  {'':22s} {'checks':>8s} {'viol':>6s} {'rate':>8s}"
    print(hdr)
    for label, ck, vi in (("I  complete traces", "I_checked_complete", "I_viol_complete"),
                          ("I  truncated traces", "I_checked_trunc", "I_viol_trunc"),
                          ("F  complete traces", "F_checked_complete", "F_viol_complete"),
                          ("F  truncated traces", "F_checked_trunc", "F_viol_trunc")):
        pct = 100 * tot[vi] / max(tot[ck], 1)
        print(f"  {label:22s} {tot[ck]:8d} {tot[vi]:6d} {pct:7.2f}%")
    pct = 100 * tot["coverage_gap"] / max(tot["move_checked"], 1)
    print(f"  {'R4 BPMN coverage gap':22s} {tot['move_checked']:8d} "
          f"{tot['coverage_gap']:6d} {pct:7.2f}%")
    print()
    print(f"  complete cases with any I violation : {len(bad_complete)}")
    print(f"  truncated cases with any I violation: {len(bad_trunc)}")
    print()
    if detail:
        print("  residual signatures:")
        for k, v in detail.most_common(15):
            print(f"     {v:4d}  {k}")


if __name__ == "__main__":
    main()
