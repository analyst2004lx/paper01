"""Build a flat submission folder ../CAIE_Clean_01 from the compiled CAIE sources.

Inlines \\input{tab/...}, moves figures to the root, and replaces
\\bibliography{...} with the contents of the matching .bbl, so each .tex
compiles with pdflatex alone (no subfolders, no BibTeX).
Run after paper01_CAIE.tex and paper01_CAIE_anonymized.tex have been compiled.
"""
import io
import os
import re
import shutil

SRC = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(os.path.dirname(SRC), "CAIE_Clean_01")
DOCS = ["paper01_CAIE", "paper01_CAIE_anonymized"]


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def flatten(name):
    s = read(os.path.join(SRC, name + ".tex"))

    def inline(m):
        body = read(os.path.join(SRC, m.group(1))).rstrip("\n")
        return "%% ---- begin " + m.group(1) + " ----\n" + body + "\n%% ---- end " + m.group(1) + " ----"
    s, n_tab = re.subn(r"\\input\{(tab/[^}]+)\}", lambda m: inline(m), s)

    figs = set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{fig/([^}]+)\}", s))
    s = re.sub(r"(\\includegraphics(?:\[[^\]]*\])?\{)fig/", r"\1", s)

    bbl = read(os.path.join(SRC, name + ".bbl")).rstrip("\n")
    pat = r"\\bibliography\{[^}]+\}"
    assert len(re.findall(pat, s)) == 1, name
    s = re.sub(pat, lambda m: bbl, s)

    assert "\\input{" not in s, name
    assert not re.search(r"\\includegraphics(?:\[[^\]]*\])?\{fig/", s), name
    write(os.path.join(DST, name + ".tex"), s)
    return n_tab, figs


def main():
    os.makedirs(DST, exist_ok=True)
    all_figs = set()
    for d in DOCS:
        n_tab, figs = flatten(d)
        all_figs |= figs
        print(d, "tables inlined:", n_tab, "figures:", len(figs))
    for f in sorted(all_figs):
        shutil.copy2(os.path.join(SRC, "fig", f), os.path.join(DST, f))
    shutil.copy2(os.path.join(SRC, "highlights.txt"), DST)
    print("written", DST)


if __name__ == "__main__":
    main()
