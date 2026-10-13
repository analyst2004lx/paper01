"""Self-check for paper02_CN (PaperRefine S4).

Usage (in paper02/Latex):
    py paper02_CN_selfcheck.py [tex_file]      # default: paper02_CN_AI-Modify-26-09-29.tex
Run after compiling with latexmk; reads the .tex, .log and .blg next to it.
Exit code 0 = all checks pass, 1 = at least one FAIL.
"""
import io
import os
import re
import sys

MAX_PAGES = 25
FONT_WARNINGS_BASELINE = 6
ABSTRACT_RANGE = (400, 700)

FORBIDDEN = [
    ("相对提前量上界", "术语：统一为“临界相对提前量”"),
    ("规避检测的相对提前量", "术语：统一为“临界相对提前量”"),
    ("零误报的硬约束层", "过度主张：硬约束层只在清洗后的正常数据上零违反"),
    ("之所以", "防御句式"),
    ("并非因为", "防御句式"),
    ("需要说明的是", "防御句式"),
    ("攻击者难以同时伪造", "未证实主张（R072）"),
    ("其权重不与主表等同", "防御句（S4 已删）"),
    ("不作为外部效度的主要证据", "防御句（S4 已删）"),
    ("[ref_check", "未处理的引用核对标记"),
    ("[ref_insert", "未处理的补引标记"),
    ("<待填", "占位符（9B 清零）"),
]


def strip_comments(text):
    return "\n".join(re.split(r"(?<!\\)%", line)[0] for line in text.splitlines())


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    tex_name = sys.argv[1] if len(sys.argv) > 1 else "paper02_CN_AI-Modify-26-09-29.tex"
    stem = os.path.splitext(os.path.join(here, tex_name))[0]
    raw = read(stem + ".tex")
    body = strip_comments(raw)
    results = []

    def check(name, ok, detail=""):
        results.append((name, ok, detail))

    log = read(stem + ".log") if os.path.exists(stem + ".log") else ""
    check("log exists", bool(log))
    errors = len(re.findall(r"(?m)^!", log))
    check("LaTeX errors = 0", errors == 0, str(errors))
    overfull = log.count("Overfull")
    check("Overfull = 0", overfull == 0, str(overfull))
    undef_refs = len(re.findall(r"(Reference|Citation) `[^']*' .*undefined", log))
    check("undefined refs/cites = 0", undef_refs == 0, str(undef_refs))
    font = len(re.findall(r"Font shape .* undefined", log))
    check("font warnings <= baseline", font <= FONT_WARNINGS_BASELINE, str(font))
    m = re.search(r"Output written on .*?\((\d+) pages?", log)
    pages = int(m.group(1)) if m else -1
    check("pages <= %d" % MAX_PAGES, 0 < pages <= MAX_PAGES, str(pages))

    labels = re.findall(r"\\label\{([^}]*)\}", body)
    dup = sorted({l for l in labels if labels.count(l) > 1})
    check("no duplicate labels", not dup, ", ".join(dup))
    refs = set()
    for mm in re.finditer(r"\\(?:ref|eqref|autoref|cref)\{([^}]*)\}", body):
        refs.update(k.strip() for k in mm.group(1).split(","))
    missing = sorted(refs - set(labels))
    check("no refs to missing labels", not missing, ", ".join(missing))
    floats = re.findall(r"\\begin\{(?:table|figure)\*?\}(.*?)\\end\{(?:table|figure)\*?\}", body, re.S)
    unref = []
    for fl in floats:
        fl_labels = re.findall(r"\\label\{([^}]*)\}", fl)
        if fl_labels and not any(l in refs for l in fl_labels):
            unref.append(fl_labels[0])
    check("every float referenced", not unref, ", ".join(unref))

    for needle, why in FORBIDDEN:
        src = raw if needle.startswith("[ref_") else body
        n = src.count(needle)
        check("forbidden: %s" % needle, n == 0, "%d hit(s); %s" % (n, why) if n else "")

    am = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
    if am:
        a = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", am.group(1))
        a = re.sub(r"[{}$\\\s~]", "", a)
        n = len(a)
        check("abstract length in %d-%d" % ABSTRACT_RANGE, ABSTRACT_RANGE[0] <= n <= ABSTRACT_RANGE[1], str(n))
    else:
        check("abstract found", False)

    blg = stem + ".blg"
    if os.path.exists(blg):
        b = read(blg)
        berr = len(re.findall(r"(?mi)^.*error message", b))
        check("BibTeX errors = 0", berr == 0, str(berr))

    width = max(len(r[0]) for r in results)
    fails = 0
    for name, ok, detail in results:
        fails += not ok
        print("%s  %s  %s" % ("PASS" if ok else "FAIL", name.ljust(width), detail))
    print("\n%d checks, %d failed" % (len(results), fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
