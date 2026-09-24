# -*- coding: utf-8 -*-
"""核验审计报告里几条涉及算术的断言，一律回到原始 CSV，不用反推。

查三件事：
  A. E8 的「影响集占比」用的是哪个分母，换成 Cl/|R_alive| 后是多少
     （关系到「占比会不会涨到接近 1」这一问是否被正确回答）
  B. tab:cheap 的「平均退化」两列之差，是否等于正文所报的配对差均值
  C. RA 与 R2 有多少格是「两法恒等」（释放集 = 全部未结束占用），
     剔除后胜负平与平均降幅变成多少
"""
import csv
import io
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, os.pardir, "experiments")
OUT = os.path.join(EXP, "audit_checks.txt")
buf = io.StringIO()


def w(s=""):
    buf.write(s + "\n")


def load(name):
    with open(os.path.join(EXP, name), encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def mean(v):
    return sum(v) / len(v) if v else float("nan")


def median(v):
    s = sorted(v)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# ---------------------------------------------------------------- A
w("=" * 72)
w("A. E8 影响集占比的两个分母")
w("=" * 72)
rows = load("scale_curve.csv")
byk = defaultdict(list)
for r in rows:
    if r["arm"] != "R2":
        continue
    nres, nlive, clo = float(r["n_res"]), float(r["n_live"]), float(r["closure"])
    byk[int(r["k"])].append((clo / nres, clo / nlive, nlive / nres,
                             float(r["closure_frac"])))
w("k    Cl/|R|   Cl/|R_alive|   |R_alive|/|R|   csv:closure_frac")
for k in sorted(byk):
    a, b, c, f = (mean([x[i] for x in byk[k]]) for i in range(4))
    w("%-4d %.3f    %.3f          %.3f           %.3f" % (k, a, b, c, f))
allv = [x for v in byk.values() for x in v]
w("")
w("全七档：Cl/|R| 均值 %.3f（极差 %.3f--%.3f）" % (
    mean([x[0] for x in allv]), min(x[0] for x in allv), max(x[0] for x in allv)))
w("全七档：Cl/|R_alive| 均值 %.3f（极差 %.3f--%.3f）" % (
    mean([x[1] for x in allv]), min(x[1] for x in allv), max(x[1] for x in allv)))
w("全七档：|R_alive|/|R| 均值 %.3f  <= 这就是 Cl/|R| 的天花板" % mean([x[2] for x in allv]))
w("csv 的 closure_frac 与 Cl/|R| 是否同一列: %s" % all(
    abs(x[0] - x[3]) < 1e-6 for x in allv))

# ---------------------------------------------------------------- B
w("")
w("=" * 72)
w("B. tab:cheap 的「平均退化」与配对差均值")
w("=" * 72)
rows = load("cheap_baselines.csv")
cell = defaultdict(dict)
for r in rows:
    cell[(r["instance"], r["seed"])][r["arm"]] = r
arms = sorted({r["arm"] for r in rows})
w("臂 = %s;格数 = %d" % (", ".join(arms), len(cell)))
w("")


def deg(r):
    """完工时间相对扰动前参照的退化率。"""
    return (float(r["makespan"]) - float(r["makespan_ref"])) / float(r["makespan_ref"])


w("臂      n    平均退化   中位退化   平均 res_frac  耗时中位/ms")
for a in arms:
    rs = [d[a] for d in cell.values() if a in d]
    w("%-6s %-4d %.4f     %.4f     %.4f        %.2f" % (
        a, len(rs), mean([deg(r) for r in rs]), median([deg(r) for r in rs]),
        mean([float(r["res_frac"]) for r in rs]),
        median([float(r["wall_ms"]) for r in rs])))

base = "R2"
for a in arms:
    if a == base:
        continue
    d = [(deg(c[a]) - deg(c[base])) for c in cell.values() if a in c and base in c]
    if not d:
        continue
    w("")
    w("配对差 deg(%s) - deg(%s):  n=%d  均值=%+.4f  中位=%+.4f" % (
        a, base, len(d), mean(d), median(d)))
    w("  两臂平均退化之差（必须与上面的均值恒等）= %+.4f" % (
        mean([deg(c[a]) for c in cell.values() if a in c and base in c])
        - mean([deg(c[base]) for c in cell.values() if a in c and base in c])))
    cm = [float(c[base]["makespan"]) / float(c[a]["makespan"])
          for c in cell.values() if a in c and base in c]
    w("  Cmax 比值 R2/%s 均值 = %.4f" % (a, mean(cm)))

# ---------------------------------------------------------------- C
w("")
w("=" * 72)
w("C. RA 与 R2 的「两法恒等」格")
w("=" * 72)
ra = [(k, v) for k, v in cell.items() if "RA" in v and "R2" in v]
w("RA/R2 同时存在的格数 = %d" % len(ra))
ident = [(k, v) for k, v in ra
         if float(v["R2"]["release_size"]) >= float(v["R2"]["alive_size"])]
w("R2 的释放集 = 全部未结束占用（即与 RA 恒等）的格数 = %d" % len(ident))
w("  这些格: %s" % ", ".join("%s/%s" % (k[0], k[1]) for k, _ in ident[:10]))


def wtl(pairs):
    win = tie = loss = 0
    ds = []
    for _k, v in pairs:
        a, b = float(v["RA"]["res_frac"]), float(v["R2"]["res_frac"])
        ds.append(a - b)
        if b < a - 1e-12:
            win += 1
        elif abs(b - a) <= 1e-12:
            tie += 1
        else:
            loss += 1
    return win, tie, loss, ds


for lbl, pairs in (("全部格", ra),
                   ("剔除恒等格", [p for p in ra if p not in ident])):
    win, tie, loss, ds = wtl(pairs)
    nz = [x for x in ds if abs(x) > 1e-12]
    w("")
    w("%s (n=%d): R2 改动比例更低/持平/更高 = %d/%d/%d" % (lbl, len(pairs), win, tie, loss))
    w("  平均降幅 (RA - R2) = %.4f;中位 = %.4f;非零差格数 = %d" % (
        mean(ds), median(ds), len(nz)))

open(OUT, "w", encoding="utf-8").write(buf.getvalue())
print("written: " + OUT)
