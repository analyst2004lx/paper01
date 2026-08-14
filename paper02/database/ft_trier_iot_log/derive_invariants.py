"""Derive the feasibility mask F and the cross-device interlock invariant set I
automatically from the 16 Camunda BPMN models, then validate both against the
cleaned MainProcess.xes.

The point of the exercise: hard constraints are only usable as a detection
channel if they are violated exactly zero times on benign data. Anything that
fires on normal traffic is a false-positive source, not an invariant.

Op semantics are inferred from the BPMN service URLs:
  - op carries start & end  -> consumes a token at `start`, emits one at `end`
  - op carries neither      -> acts at the resource's canonical position
                               `<resource>_pos`; whether it is a source, sink or
                               in-place step is decided by the rules below.
"""
import glob
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse, parse_qs

B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
C = "{http://camunda.org/schema/1.0/bpmn}"
XES = "{http://www.xes-standard.org/}"

# The only hand-specified semantics: which position-less ops create or destroy
# a token. Everything else (positions, moves, precedence) is derived.
SOURCE_OPS = {"/hbw/unload", "/hbw/get_empty_bucket"}
SINK_OPS = {"/hbw/store", "/hbw/store_empty_bucket"}


# --------------------------------------------------------------------------
# 1. Parse BPMN
# --------------------------------------------------------------------------
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
        acts[st.get("id")] = {
            "op": u.path,
            "resource": q.get("resource"),
            "start": q.get("start"),
            "end": q.get("end"),
        }
    for sf in proc.findall(B + "sequenceFlow"):
        edges.append((sf.get("sourceRef"), sf.get("targetRef")))
    return acts, edges


def canonical_pos(resource):
    return f"{resource}_pos"


def effect(a):
    """(required_position, produced_position) for a BPMN/log activity."""
    if a["start"] and a["end"]:
        return a["start"], a["end"]
    pos = canonical_pos(a["resource"])
    if a["op"] in SOURCE_OPS:
        return None, pos
    if a["op"] in SINK_OPS:
        return pos, None
    return pos, pos


# --------------------------------------------------------------------------
# 2. Derive F (per-device operation transitions) and I (position graph)
# --------------------------------------------------------------------------
def derive():
    move_graph = set()          # (from_pos, to_pos)
    op_at_pos = defaultdict(set)  # (resource, op) -> required positions
    dev_ops = defaultdict(set)    # resource -> ops
    dev_transitions = defaultdict(set)  # resource -> {(op_i, op_j)}
    placeholders = 0

    for f in sorted(glob.glob("bpmn-models/*.bpmn")):
        acts, edges = parse_bpmn(f)
        placeholders += sum(1 for v in acts.values() if v is None)
        succ = defaultdict(set)
        for s, t in edges:
            succ[s].add(t)

        # Reachability between service tasks through gateways/events
        def next_tasks(node, seen=None):
            seen = seen or set()
            out = set()
            for nxt in succ.get(node, ()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                if nxt in acts and acts[nxt] is not None:
                    out.add(nxt)
                else:
                    out |= next_tasks(nxt, seen)
            return out

        for aid, a in acts.items():
            if a is None:
                continue
            req, prod = effect(a)
            dev_ops[a["resource"]].add(a["op"])
            if req:
                op_at_pos[(a["resource"], a["op"])].add(req)
            if req and prod:
                move_graph.add((req, prod))
            for bid in next_tasks(aid):
                b = acts[bid]
                if b and b["resource"] == a["resource"]:
                    dev_transitions[a["resource"]].add((a["op"], b["op"]))
    return move_graph, op_at_pos, dev_ops, dev_transitions, placeholders


# --------------------------------------------------------------------------
# 3. Parse the log
# --------------------------------------------------------------------------
def parse_log(path):
    """Return {case: [activity_instance]} with start/end times and params."""
    tree = ET.parse(path)
    cases = defaultdict(dict)
    for trace in tree.getroot().findall(XES + "trace"):
        for ev in trace.findall(XES + "event"):
            a, params = {}, {}
            for child in ev:
                if child.tag == XES + "list" and child.get("key") == "parameters":
                    for vals in child:
                        for v in vals:
                            params[v.get("key")] = v.get("value")
                elif child.get("key"):
                    a[child.get("key")] = child.get("value")
            case = a.get("case")
            key = a.get("event_id")
            rec = cases[case].setdefault(key, {
                "op": a.get("concept:name"),
                "resource": a.get("org:resource"),
                "start": params.get("parameter_start_position"),
                "end": params.get("parameter_end_position"),
                "wf": a.get("process_model_id"),
                "order": int(key) if key and key.isdigit() else 0,
            })
            state = a.get("lifecycle:state")
            ts = a.get("time:timestamp")
            if ts:
                rec[f"t_{state}"] = datetime.fromisoformat(ts)
            if state in ("success", "failure"):
                rec["outcome"] = state
    return cases


# --------------------------------------------------------------------------
# 4. Validate
# --------------------------------------------------------------------------
def validate(cases, move_graph, dev_transitions, skip_failures):
    tot = Counter()
    viol_detail = Counter()
    per_case_viol = Counter()

    for case, acts in cases.items():
        insts = sorted(acts.values(), key=lambda r: (r.get("t_inProgress")
                                                     or r.get("t_assigned")
                                                     or datetime.min, r["order"]))
        tokens = Counter()
        last_op = {}
        for r in insts:
            if not r["resource"] or not r["op"]:
                continue
            if skip_failures and r.get("outcome") == "failure":
                continue
            tot["activities"] += 1
            req, prod = effect(r)

            # --- I: token/position precondition ---
            if req is not None:
                tot["I_checked"] += 1
                if tokens[req] <= 0:
                    tot["I_violations"] += 1
                    viol_detail[(r["resource"], r["op"], req)] += 1
                    per_case_viol[case] += 1
                else:
                    tokens[req] -= 1
            if prod is not None:
                tokens[prod] += 1

            # --- I2: the move itself must be in the derived material-flow graph ---
            if req and prod:
                tot["move_checked"] += 1
                if (req, prod) not in move_graph:
                    tot["move_violations"] += 1
                    viol_detail[("MOVE", req, prod)] += 1

            # --- F: per-device operation transition ---
            d = r["resource"]
            if d in last_op:
                tot["F_checked"] += 1
                if (last_op[d], r["op"]) not in dev_transitions[d]:
                    tot["F_violations"] += 1
                    viol_detail[("F", d, f"{last_op[d]} -> {r['op']}")] += 1
            last_op[d] = r["op"]

        # leftover tokens = material never stored back
        tot["leftover_tokens"] += sum(v for v in tokens.values() if v > 0)
    return tot, viol_detail, per_case_viol


def main():
    move_graph, op_at_pos, dev_ops, dev_transitions, placeholders = derive()
    print("=== derived from 16 BPMN models (no hand-crafted topology) ===")
    print(f"  positions             : {len({p for m in move_graph for p in m})}")
    print(f"  material-flow edges   : {len(move_graph)}")
    print(f"  devices               : {len(dev_ops)}")
    print(f"  device-local op pairs : {sum(len(v) for v in dev_transitions.values())}")
    print(f"  placeholder tasks     : {placeholders} (URL = TO_BE_SET)")
    print(f"  hand-specified rules  : {len(SOURCE_OPS)} source + {len(SINK_OPS)} sink ops")
    print()

    cases = parse_log("MainProcess_cleaned.xes")
    print(f"=== log: {len(cases)} cases, "
          f"{sum(len(v) for v in cases.values())} activity instances ===")
    print()

    for skip in (False, True):
        label = "excluding failed activities" if skip else "all activities"
        tot, detail, per_case = validate(cases, move_graph, dev_transitions, skip)
        print(f"--- validation ({label}) ---")
        print(f"  activities replayed     : {tot['activities']}")
        print(f"  I  precondition checks  : {tot['I_checked']:5d}   "
              f"violations: {tot['I_violations']:4d}  "
              f"({100 * tot['I_violations'] / max(tot['I_checked'], 1):.2f}%)")
        print(f"  I2 material-flow edges  : {tot['move_checked']:5d}   "
              f"violations: {tot['move_violations']:4d}  "
              f"({100 * tot['move_violations'] / max(tot['move_checked'], 1):.2f}%)")
        print(f"  F  device op transitions: {tot['F_checked']:5d}   "
              f"violations: {tot['F_violations']:4d}  "
              f"({100 * tot['F_violations'] / max(tot['F_checked'], 1):.2f}%)")
        print(f"  cases with any I violation: {len(per_case)} / {len(cases)}")
        print(f"  leftover tokens (unstored): {tot['leftover_tokens']}")
        if detail:
            print("  top violation signatures:")
            for k, v in detail.most_common(12):
                print(f"     {v:4d}  {k}")
        print()


if __name__ == "__main__":
    main()
