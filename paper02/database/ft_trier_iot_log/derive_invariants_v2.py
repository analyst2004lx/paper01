"""Refined derivation of the interlock invariants, fixing the four causes of
false violations found by the naive version (derive_invariants.py).

Naive model scored 14.87% violations on benign data. The failures were not
random: they concentrated in four identifiable modelling gaps.

  R1  Two token colours. `hbw/unload` releases a workpiece *and* an empty
      bucket; `store_empty_bucket` consumes the bucket, not the workpiece. A
      single token type conflates them (60% of all naive violations).
  R2  F must use transitive reachability between same-device tasks, not
      immediate BPMN successors: a device's two operations are usually
      separated by other devices' tasks.
  R3  `sm_N_automatic_pos` is an abstract output of the sorter that physically
      resolves to one of `sm_N_sink_{1,2,3}_pos`, chosen by the colour detected
      at runtime (the eventBasedGateway branches). Treat them as one alias
      class.
  R4  Moves absent from all 16 BPMN models are a model-coverage gap, not an
      invariant violation. Reported separately.

Run: python derive_invariants_v2.py
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

# R1: token effects for the position-less warehouse ops, read off the op names.
HBW_EFFECTS = {
    "/hbw/unload":             ([], [WORKPIECE, BUCKET]),
    "/hbw/get_empty_bucket":   ([], [BUCKET]),
    "/hbw/store_empty_bucket": ([BUCKET], []),
    "/hbw/store":              ([WORKPIECE, BUCKET], []),
}


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
    """(consumed, produced) as lists of (token_type, position)."""
    res, op = a["resource"], a["op"]
    if a["start"] and a["end"]:
        return [(WORKPIECE, a["start"])], [(WORKPIECE, a["end"])]
    pos = f"{res}_pos"
    if op in HBW_EFFECTS:
        cons, prod = HBW_EFFECTS[op]
        return [(t, pos) for t in cons], [(t, pos) for t in prod]
    return [(WORKPIECE, pos)], [(WORKPIECE, pos)]


def build_alias(positions):
    """R3: sorter output alias classes, from the naming convention."""
    groups = defaultdict(set)
    for p in positions:
        m = re.match(r"(sm_\d+)_(automatic|sink_\d+)_pos$", p)
        if m:
            groups[m.group(1)].add(p)
    alias = {}
    for g in groups.values():
        for p in g:
            alias[p] = frozenset(g)
    return alias


def derive():
    move_graph, dev_reach, positions = set(), defaultdict(set), set()
    placeholders = 0
    for f in sorted(glob.glob("bpmn-models/*.bpmn")):
        acts, edges = parse_bpmn(f)
        placeholders += sum(1 for v in acts.values() if v is None)
        succ = defaultdict(set)
        for s, t in edges:
            succ[s].add(t)

        # R2: full transitive reachability over the flow graph
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
    return move_graph, dev_reach, positions, placeholders


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
    """Consume one token, honouring R3 alias classes. True if consumed."""
    if tokens[(ttype, pos)] > 0:
        tokens[(ttype, pos)] -= 1
        return True
    for p in alias.get(pos, ()):
        if tokens[(ttype, p)] > 0:
            tokens[(ttype, p)] -= 1
            return True
    return False


def validate(cases, move_graph, dev_reach, alias, skip_failures=True):
    tot, detail = Counter(), Counter()
    bad_cases = set()
    for case, acts in cases.items():
        insts = sorted(acts.values(),
                       key=lambda r: (r.get("t_inProgress") or r.get("t_assigned")
                                      or datetime.min, r["order"]))
        tokens, last_op = Counter(), {}
        for r in insts:
            if not r["resource"] or not r["op"]:
                continue
            if skip_failures and r.get("outcome") == "failure":
                continue
            tot["activities"] += 1
            cons, prod = effects(r)
            for ttype, pos in cons:
                tot["I_checked"] += 1
                if not take(tokens, ttype, pos, alias):
                    tot["I_violations"] += 1
                    detail[("I", r["resource"], r["op"], ttype, pos)] += 1
                    bad_cases.add(case)
            for ttype, pos in prod:
                tokens[(ttype, pos)] += 1
            if r["start"] and r["end"]:
                tot["move_checked"] += 1
                if (r["start"], r["end"]) not in move_graph:
                    tot["coverage_gap"] += 1
                    detail[("GAP", r["start"], r["end"], "", "")] += 1
            d = r["resource"]
            if d in last_op:
                tot["F_checked"] += 1
                if (last_op[d], r["op"]) not in dev_reach[d]:
                    tot["F_violations"] += 1
                    detail[("F", d, f"{last_op[d]} -> {r['op']}", "", "")] += 1
            last_op[d] = r["op"]
    return tot, detail, bad_cases


def main():
    move_graph, dev_reach, positions, placeholders = derive()
    alias = build_alias(positions)
    print("=== derived automatically from 16 BPMN models ===")
    print(f"  positions            : {len(positions)}")
    print(f"  material-flow edges  : {len(move_graph)}")
    print(f"  device op pairs (F)  : {sum(len(v) for v in dev_reach.values())}")
    print(f"  sorter alias classes : {len(set(alias.values()))}")
    print(f"  placeholder tasks    : {placeholders}")
    print()

    cases = parse_log("MainProcess_cleaned.xes")
    tot, detail, bad = validate(cases, move_graph, dev_reach, alias)
    print(f"=== validation on cleaned log ({len(cases)} cases, "
          f"{tot['activities']} activities, failures excluded) ===")
    for name, chk, vio in (("I  token preconditions", "I_checked", "I_violations"),
                           ("F  device transitions ", "F_checked", "F_violations")):
        pct = 100 * tot[vio] / max(tot[chk], 1)
        print(f"  {name}: {tot[chk]:5d} checks   {tot[vio]:4d} violations  ({pct:.2f}%)")
    pct = 100 * tot["coverage_gap"] / max(tot["move_checked"], 1)
    print(f"  R4 BPMN coverage gap  : {tot['move_checked']:5d} moves    "
          f"{tot['coverage_gap']:4d} unmodelled  ({pct:.2f}%)")
    print(f"  cases with any I violation: {len(bad)} / {len(cases)}")
    print()
    if detail:
        print("  remaining violation signatures:")
        for k, v in detail.most_common(15):
            print(f"     {v:4d}  {k}")


if __name__ == "__main__":
    main()
