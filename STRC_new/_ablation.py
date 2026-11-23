import csv
import math
import statistics as st

from tools.paper_numbers import _signrank_p

t = lambda x: x in ("True", "true", "1")
FILES = [("主批次", "整段", "cheap_baselines"), ("主批次", "L=5", "cheap_baselines_L5"),
         ("主批次", "L=2", "cheap_baselines_L2"), ("规模序列", "整段", "cheap_scale_full"),
         ("规模序列", "L=5", "cheap_scale_L5"), ("规模序列", "L=2", "cheap_scale_L2")]
tests = []


def pairs(idx, keys, a, b):
    return [(idx[(i, s, a)], idx[(i, s, b)]) for i, s in keys
            if (i, s, a) in idx and (i, s, b) in idx
            and t(idx[(i, s, a)]["feasible"]) and t(idx[(i, s, b)]["feasible"])]


def wtl(xs):
    return "%d/%d/%d" % (sum(v < -1e-9 for v in xs), sum(abs(v) <= 1e-9 for v in xs),
                         sum(v > 1e-9 for v in xs))


for suite, proto, f in FILES:
    R = list(csv.DictReader(open("experiments/%s.csv" % f, encoding="utf-8")))
    idx = {(r["instance"], r["seed"], r["arm"]): r for r in R}
    keys = sorted({(r["instance"], r["seed"]) for r in R})
    feas = {a: sum(t(idx.get((i, s, a), {}).get("feasible", "")) for i, s in keys)
            for a in ("RAF", "RA", "R2")}
    for name, a, b in (("layer", "RA", "RAF"), ("bound", "R2", "RA"), ("both", "R2", "RAF")):
        P = pairs(idx, keys, a, b)
        dr = [float(x["res_frac"]) - float(y["res_frac"]) for x, y in P]
        dc = [float(x["makespan"]) / float(y["makespan"]) - 1 for x, y in P]
        lt = [math.log(float(x["wall_ms"]) / float(y["wall_ms"])) for x, y in P]
        p_res, p_time, p_c = _signrank_p(dr), _signrank_p(lt), _signrank_p(dc)
        if name == "layer":
            tests.append(("layer-time", suite, proto, p_time))
        if name == "bound":
            tests.append(("bound-res", suite, proto, p_res))
        print("%s %s %-5s n=%d feas(RAF/RA/R2)=%s dres %+.4f %s p_res %.2g | Cmax %+.3f%% %s p_c %.2g | "
              "time %.2f p_time %.2g" % (suite, proto, name, len(P), "/".join(str(feas[k]) for k in ("RAF", "RA", "R2")),
                                          st.mean(dr), wtl(dr), p_res, 100 * st.mean(dc), wtl(dc), p_c,
                                          math.exp(st.median(lt)), p_time))
R = list(csv.DictReader(open("experiments/cheap_baselines.csv", encoding="utf-8")))
idx = {(r["instance"], r["seed"], r["arm"]): r for r in R}
keys = sorted({(r["instance"], r["seed"]) for r in R})
d = [float(x["makespan"]) / float(x["makespan_ref"]) - float(y["makespan"]) / float(y["makespan_ref"])
     for x, y in pairs(idx, keys, "R2", "RD")]
tests.append(("RD", "主批次", "整段", _signrank_p(d)))
valid = sorted([x for x in tests if not math.isnan(x[3])], key=lambda x: x[3])
m = len(valid)
run = 0
print("\nHolm m=%d" % m)
for k, (n, su, pr, p) in enumerate(valid):
    run = max(run, min(1, (m - k) * p))
    print("  %-10s %s %-4s raw %.2g holm %.2g" % (n, su, pr, p, run))
