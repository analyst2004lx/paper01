"""Extract the full vocabulary (resources, operations, positions, parameters)
from all 16 Camunda BPMN models shipped with the Trier dataset."""
import glob
import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from urllib.parse import urlparse, parse_qs

B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
C = "{http://camunda.org/schema/1.0/bpmn}"


def activities(path):
    """Yield (activity_id, name, op, params) for each serviceTask."""
    proc = ET.parse(path).getroot().find(B + "process")
    for st in proc.findall(B + "serviceTask"):
        url = None
        for ip in st.iter(C + "inputParameter"):
            if ip.get("name") == "url":
                url = " ".join((ip.text or "").split())
        if not url:
            continue
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        yield st.get("id"), st.get("name"), u.path, q


ops = Counter()
resources = Counter()
param_keys = Counter()
positions = Counter()
op_params = defaultdict(Counter)
op_resources = defaultdict(set)
moves = Counter()

files = sorted(glob.glob("bpmn-models/*.bpmn"))
for f in files:
    for aid, name, op, q in activities(f):
        ops[op] += 1
        r = q.get("resource")
        if r:
            resources[r] += 1
            op_resources[op].add(r)
        for k, v in q.items():
            if k == "business_key":
                continue
            param_keys[k] += 1
            op_params[op][k] += 1
            if k in ("start", "end"):
                positions[v] += 1
        if "start" in q and "end" in q:
            moves[(q["start"], q["end"])] += 1

print(f"parsed {len(files)} BPMN files\n")

print("== operations (path) -> count, resources, param keys ==")
for op, n in sorted(ops.items()):
    ps = ",".join(sorted(op_params[op]))
    rs = ",".join(sorted(op_resources[op]))
    print(f"  {op:34s} n={n:3d}  res=[{rs}]  params=[{ps}]")
print()

print("== resources ==")
for r, n in sorted(resources.items()):
    print(f"  {r:10s} {n}")
print()

print("== positions ==")
for p, n in sorted(positions.items()):
    print(f"  {p:32s} {n}")
print()

print("== all param keys ==")
for k, n in sorted(param_keys.items()):
    print(f"  {k:20s} {n}")
print()

print("== distinct moves (start -> end) ==")
for (s, e), n in sorted(moves.items()):
    print(f"  {s:30s} -> {e:30s}  {n}")
