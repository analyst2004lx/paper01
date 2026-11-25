import csv
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "experiments"
rows = list(csv.DictReader(open(root + "/expanded/scale_compare.csv", encoding="utf-8")))
print(list(rows[0].keys()))
rk = [k for k in rows[0] if "round" in k][0]
for inst in sorted({r["instance"] for r in rows}):
    for p in sorted({float(r["phi"]) for r in rows}):
        rs = [r for r in rows if r["instance"] == inst and float(r["phi"]) == p]
        g = [(float(r["r0_makespan"]), float(r["strc_makespan"])) for r in rs]
        w = sum(a < b for a, b in g); t = sum(a == b for a, b in g); l = sum(a > b for a, b in g)
        esc = [(r["seed"], r[rk]) for r in rs if r[rk] not in ("0", "")]
        below = sum(float(r["r0_makespan"]) < float(r["ref_makespan"]) for r in rs)
        print("%-16s phi %.2f GR w/t/l %d/%d/%d  esc %s  GR<ref %d" % (inst, p, w, t, l, esc, below))
