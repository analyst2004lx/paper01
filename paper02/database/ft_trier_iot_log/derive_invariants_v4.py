"""v4: proper timed Petri-net firing semantics + diagnosis of every residual.

v3 consumed and produced a token at the same instant, ordering activities by
their start time. That is wrong when two activities overlap: a transport that
ends at P and a processing step at P can appear "out of order" purely because
the processing step's `assigned` event precedes the transport's `complete`.

v4 builds a proper timeline: a token is consumed at t_start of the consumer and
produced at t_end of the producer, and events are replayed in timestamp order.
Every residual violation is then classified as
    LATE     - the required token is produced later in the same case (ordering)
    NEVER    - no activity in the case ever produces it (missing event)
    FAILED   - only a failed activity would have produced it

Run: python derive_invariants_v4.py
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
            st = a.get("lifecycle:state")
            if a.get("time:timestamp"):
                rec[f"t_{st}"] = datetime.fromisoformat(a["time:timestamp"])
            if a.get("operation_end_time") and st == "inProgress":
                rec["t_op_end"] = datetime.fromisoformat(a["operation_end_time"])
            if st in ("success", "failure"):
                rec["outcome"] = st
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

    tot, detail, cause = Counter(), Counter(), Counter()
    bad_cases = set()

    for case, acts in cases.items():
        insts = [r for r in acts.values() if r["resource"] and r["op"]]
        live = [r for r in insts if r.get("outcome") != "failure"]
        if not live:
            continue
        tot["cases"] += 1

        # timeline: consume at start, produce at operation end
        timeline = []
        for r in live:
            t0 = r.get("t_inProgress") or r.get("t_assigned")
            t1 = r.get("t_op_end") or r.get("t_success") or t0
            if t0 is None:
                continue
            timeline.append((t0, 0, r["order"], "C", r))
            timeline.append((t1, 1, r["order"], "P", r))
        timeline.sort(key=lambda x: (x[0], x[1], x[2]))

        # what this case can ever produce, for diagnosing residuals
        produced_later = defaultdict(list)
        for r in live:
            for ttype, pos in effects(r)[1]:
                produced_later[(ttype, pos)].append(
                    r.get("t_op_end") or r.get("t_success") or datetime.min)
        failed_prod = set()
        for r in insts:
            if r.get("outcome") == "failure":
                for ttype, pos in effects(r)[1]:
                    failed_prod.add((ttype, pos))

        tokens, last_op = Counter(), {}
        for t, _, _, kind, r in timeline:
            cons, prod = effects(r)
            if kind == "C":
                tot["activities"] += 1
                for ttype, pos in cons:
                    tot["I_checked"] += 1
                    if not take(tokens, ttype, pos, alias):
                        tot["I_viol"] += 1
                        bad_cases.add(case)
                        detail[(r["resource"], r["op"], pos)] += 1
                        later = [x for x in produced_later.get((ttype, pos), [])
                                 if x > t]
                        if later:
                            cause["LATE (ordering)"] += 1
                        elif (ttype, pos) in failed_prod:
                            cause["FAILED (producer failed)"] += 1
                        else:
                            cause["NEVER (missing event)"] += 1
                d = r["resource"]
                if d in last_op:
                    tot["F_checked"] += 1
                    if last_op[d] != r["op"] and (last_op[d], r["op"]) not in dev_reach[d]:
                        tot["F_viol"] += 1
                        detail[("F", d, f"{last_op[d]} -> {r['op']}")] += 1
                last_op[d] = r["op"]
                if r["start"] and r["end"]:
                    tot["move_checked"] += 1
                    if (r["start"], r["end"]) not in move_graph:
                        tot["gap"] += 1
            else:
                for ttype, pos in prod:
                    tokens[(ttype, pos)] += 1

    print(f"=== v4 timed firing semantics ({tot['cases']} cases, "
          f"{tot['activities']} activities, failures excluded) ===")
    for label, ck, vi in (("I  token preconditions", "I_checked", "I_viol"),
                          ("F  device transitions ", "F_checked", "F_viol")):
        pct = 100 * tot[vi] / max(tot[ck], 1)
        print(f"  {label}: {tot[ck]:5d} checks  {tot[vi]:4d} violations  {pct:6.2f}%")
    pct = 100 * tot["gap"] / max(tot["move_checked"], 1)
    print(f"  R4 BPMN coverage gap  : {tot['move_checked']:5d} moves   "
          f"{tot['gap']:4d} unmodelled   {pct:6.2f}%")
    print(f"  cases with any I violation: {len(bad_cases)} / {tot['cases']}")
    print()
    print("  residual cause breakdown:")
    for k, v in cause.most_common():
        print(f"     {v:4d}  {k}")
    print()
    print("  residual signatures:")
    for k, v in detail.most_common(12):
        print(f"     {v:4d}  {k}")


if __name__ == "__main__":
    main()
