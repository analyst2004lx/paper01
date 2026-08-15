"""Probe the Trier IoT-enriched log for the quantities that decide whether the
timing channel has enough power: per-(resource, activity) dwell-time spread and
the actual-vs-planned residual.

Reads MainProcess.xes (top level only; sensor sublogs are not needed here).
"""
import re
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import numpy as np

XES = "{http://www.xes-standard.org/}"
PATH = "MainProcess_cleaned.xes"


def parse_ts(s):
    return datetime.fromisoformat(s)


def parse_planned(s):
    m = re.match(r"(\d+) days (\d+):(\d+):(\d+)", s or "")
    if not m:
        return None
    d, h, mi, sec = (int(x) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def attrs(event):
    out = {}
    for child in event:
        key = child.get("key")
        if key is not None and child.tag != XES + "list":
            out[key] = child.get("value")
    return out


def main():
    tree = ET.parse(PATH)
    root = tree.getroot()

    # (case, event_id) -> {phase: (start, end)} plus static fields
    acts = defaultdict(dict)
    n_traces = n_events = 0
    resources, activities, workflows = set(), set(), set()

    for trace in root.findall(XES + "trace"):
        n_traces += 1
        for ev in trace.findall(XES + "event"):
            n_events += 1
            a = attrs(ev)
            key = (a.get("case"), a.get("event_id"))
            state = a.get("lifecycle:state")
            rec = acts[key]
            rec.setdefault("resource", a.get("org:resource"))
            rec.setdefault("activity", a.get("concept:name"))
            rec.setdefault("wf", a.get("process_model_id"))
            rec.setdefault("planned", parse_planned(a.get("planned_operation_time")))
            rec[state] = (
                parse_ts(a["time:timestamp"]),
                parse_ts(a["operation_end_time"]) if a.get("operation_end_time") else None,
            )
            if a.get("org:resource"):
                resources.add(a["org:resource"])
            if a.get("concept:name"):
                activities.add(a["concept:name"])
            if a.get("process_model_id"):
                workflows.add(a["process_model_id"])

    print(f"traces={n_traces}  events={n_events}  activity_instances={len(acts)}")
    print(f"resources={len(resources)}  activities={len(activities)}  workflows={len(workflows)}")
    print("resources:", ", ".join(sorted(resources)))
    print()

    # Per-(resource, activity) execution duration and residual vs planned
    groups = defaultdict(list)
    dispatch = []
    for rec in acts.values():
        prog = rec.get("inProgress")
        if not prog or prog[1] is None:
            continue
        dur = (prog[1] - prog[0]).total_seconds()
        if dur <= 0:
            continue
        groups[(rec["resource"], rec["activity"])].append((dur, rec["planned"]))
        asg = rec.get("assigned")
        if asg and asg[1] is not None:
            d = (asg[1] - asg[0]).total_seconds()
            if d >= 0:
                dispatch.append(d)

    print(f"{'resource':<10} {'activity':<32} {'n':>5} {'med_s':>8} "
          f"{'sd_log':>7} {'cv':>6} {'plan_s':>7} {'ratio':>6}")
    print("-" * 92)
    rows = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    sds = []
    for (res, act), vals in rows:
        durs = np.array([v[0] for v in vals])
        if len(durs) < 5:
            continue
        lg = np.log(durs)
        sd_log = float(lg.std(ddof=1))
        sds.append((sd_log, len(durs)))
        plans = [v[1] for v in vals if v[1]]
        plan = float(np.median(plans)) if plans else float("nan")
        ratio = float(np.median(durs)) / plan if plans and plan > 0 else float("nan")
        print(f"{res:<10} {act:<32} {len(durs):>5} {np.median(durs):>8.2f} "
              f"{sd_log:>7.3f} {durs.std(ddof=1)/durs.mean():>6.3f} "
              f"{plan:>7.1f} {ratio:>6.3f}")

    if sds:
        w = np.array([n for _, n in sds], dtype=float)
        s = np.array([v for v, _ in sds])
        print()
        print(f"groups with n>=5: {len(sds)}   "
              f"weighted mean sd_log(tau) = {np.average(s, weights=w):.3f}   "
              f"median = {np.median(s):.3f}")

    if dispatch:
        d = np.array(dispatch)
        print(f"dispatch phase (assigned) n={len(d)}  "
              f"median={np.median(d):.3f}s  p95={np.percentile(d, 95):.3f}s  "
              f"sd_log={np.log(d[d > 0]).std(ddof=1):.3f}")


if __name__ == "__main__":
    main()
