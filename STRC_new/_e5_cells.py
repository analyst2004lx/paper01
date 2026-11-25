import csv
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "experiments"
for f in (root + "/expanded/e5_cross_curve.csv", root + "/pub_layouts/e5_cross_curve.csv"):
    print("==", f)
    for r in csv.DictReader(open(f, encoding="utf-8")):
        a, b = float(r["R0_makespan"] or "nan"), float(r["R2_makespan"] or "nan")
        tag = "W" if a < b else ("T" if a == b else "L")
        print("  %-16s %5s %4s R0 %7.1f R2 %7.1f %s  R0res %s R2res %s ref %s" % (
            r["instance"], r["seed"], r["budget_sec"], a, b, tag,
            r["R0_res_frac"][:5], r["R2_res_frac"][:5], r["ref_makespan"]))
