import io, re
def load(f): return io.open(f, encoding="utf-8").read()
P, E = load("_cz/paper_old.tex"), load("paper_EN.tex")
pre = P[:P.index("\\begin{abstract}")]
body = "".join(load("_cz/c%d.tex" % k) for k in range(1, 5))
body = body.replace("[width=\\columnwidth]{fig/fig_protocol.pdf}", "[width=0.6\\columnwidth]{fig/fig_protocol.pdf}")
body = body.replace("[width=\\columnwidth]{fig/fig_prediction3.pdf}", "[width=0.8\\columnwidth]{fig/fig_prediction3.pdf}")
out = pre + body
io.open("paper.tex", "w", encoding="utf-8", newline="").write(out)
def keys(t):
    return set(k.strip() for c in re.findall(r"\\cite[tp]?\{([^}]*)\}", t) for k in c.split(","))
def labels(t): return set(re.findall(r"\\label\{([^}]*)\}", t))
def refs(t): return set(k for c in re.findall(r"\\(?:eq|auto|c)?ref\{([^}]*)\}", t) for k in c.split(","))
nc = lambda t: re.sub(r"(?m)^\s*%.*$", "", t)
eb = nc(E[E.index("\\begin{abstract}"):]); ob = nc(body)
print("cites missing:", keys(eb) - keys(ob), "extra:", keys(ob) - keys(eb))
print("labels missing:", sorted(labels(eb) - labels(ob)), "new:", sorted(labels(ob) - labels(eb)))
print("dangling refs:", sorted(refs(ob) - labels(nc(out))))
mac = set(re.findall(r"\\newcommand\{\\(\w+)\}", pre))
used = lambda t: set(m for m in re.findall(r"\\([A-Za-z]+)", t) if m in mac)
print("macros dropped vs EN:", sorted(used(eb) - used(ob)))
print("words:", len(re.findall(r"[A-Za-z]+", ob)))
