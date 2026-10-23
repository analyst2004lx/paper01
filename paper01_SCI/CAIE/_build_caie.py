import io, os, re, shutil
SRC = r"c:\Users\Administrator\Desktop\AI_Folder\paper01"
DST = os.path.dirname(os.path.abspath(__file__))
t = io.open(os.path.join(SRC, "paper.tex"), encoding="utf-8").read()
lines = t.splitlines()

# ---- preamble: packages, theorem envs, macros (up to \setcopyright) ----
start = 1  # after \documentclass
stop = next(i for i, l in enumerate(lines) if l.startswith("\\setcopyright"))
pre = "\n".join(lines[start:stop])
pre = pre.replace("\\setlength{\\headheight}{20.48303pt}", "")
pre = re.sub(r"(?m)^% Ensure header height is sufficient for fancyhdr\n", "", pre)

# ---- body: from \section{Introduction} to before \bibliographystyle ----
b0 = t.index("\\section{Introduction}")
b1 = t.index("\\bibliographystyle{ACM-Reference-Format}")
body = t[b0:b1].rstrip() + "\n"

# narrative citations -> \citet / \Citet
name = r"(?:[Vv]an )?[A-Z][a-z]+(?: et al\.| and [A-Z][a-z]+)"
def narr(m):
    cmd = "\\Citet" if m.group(1).startswith("Van ") else "\\citet"
    return cmd + "{" + m.group(2) + "}"
body = re.sub(r"(" + name + r")~\\cite\{([^}]*)\}", narr, body)
# table cells
body = re.sub(r"& \\cite\{([^}]*)\}", r"& \\citealp{\1}", body)
# remaining parenthetical
body = re.sub(r"~\\cite\{([^}]*)\}", r"~\\citep{\1}", body)
body = re.sub(r"(?<![a-zA-Z])\\cite\{", r"\\citep{", body)

def sub1(s, old, new):
    assert old in s, old[:60]
    return s.replace(old, new)

# column specs sized for the elsarticle text block
body = sub1(body, r"\begin{tabular}{@{}p{2.5cm}cccp{2.9cm}p{3.1cm}@{}}",
            r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{2.3cm}>{\raggedright\arraybackslash}p{2.7cm}cc"
            r">{\raggedright\arraybackslash}p{2.8cm}>{\raggedright\arraybackslash}p{2.8cm}@{}}")
body = sub1(body, "\\begin{tabular}{@{}lcc@{}}\n\\toprule\n & Rule-based dispatching & Reservation-table-aware dispatching \\\\",
            "\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{6.4cm}>{\\centering\\arraybackslash}p{2.6cm}"
            ">{\\centering\\arraybackslash}p{3.2cm}@{}}\n\\toprule\n & Rule-based dispatching & Reservation-table-aware dispatching \\\\")
body = sub1(body, "\\mathrm{lb}(k)=\\max\\bigl(\\mathrm{avail}_k+t^{*}(\\mathrm{loc}_k,\\text{pickup}),\\,\n"
                  "\\mathrm{ready}_j\\bigr)+t^{*}(\\text{pickup},\\text{destination})\\ \\le\\ \\mathrm{est}(k),",
            "\\begin{split}\n\\mathrm{lb}(k)={}&\\max\\bigl(\\mathrm{avail}_k+t^{*}(\\mathrm{loc}_k,\\text{pickup}),\\,"
            "\\mathrm{ready}_j\\bigr)\\\\\n&+t^{*}(\\text{pickup},\\text{destination})\\ \\le\\ \\mathrm{est}(k),\n\\end{split}")

def wrap_tabulars(s):
    """Wrap top-level tabulars so they shrink only when wider than the text block."""
    out, depth = [], 0
    tok = re.compile(r"\\begin\{tabular\}|\\end\{tabular\}")
    pos = 0
    for m in tok.finditer(s):
        out.append(s[pos:m.start()])
        if m.group(0).startswith("\\begin"):
            if depth == 0:
                out.append("\\begin{adjustbox}{max width=\\linewidth}")
            depth += 1
            out.append(m.group(0))
        else:
            depth -= 1
            out.append(m.group(0))
            if depth == 0:
                out.append("\\end{adjustbox}")
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)

body = sub1(body, r"\begin{tabular}{@{}p{1.7cm}p{2.3cm}p{1.9cm}cp{1.6cm}c@{}}", r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{2.3cm}>{\raggedright\arraybackslash}p{3.2cm}>{\raggedright\arraybackslash}p{2.1cm}c>{\raggedright\arraybackslash}p{2.4cm}c@{}}")
body = sub1(body, "\\qquad\nA_{ji}=", "\\quad\nA_{ji}=")
body = re.sub(r"\\begin\{(table|figure|algorithm)(\*?)\}\[t\]", r"\\begin{\1\2}[!htbp]", body)
body = sub1(body, "\\renewcommand{\\arraystretch}{1.2}", "\\renewcommand{\\arraystretch}{1.05}")
body = re.sub(r"\\(begin|end)\{figure\*\}", r"\\\1{figure}", body)
body = wrap_tabulars(body)

abstract = r"""Flexible job shop scheduling with transport reads travel times from a constant matrix, assuming vehicles never interfere.
When a finite AGV fleet shares a sparse corridor network, travel time becomes the outcome of conflict-free routing, and one job's corridor occupancy delays others.
Where transport takes longer than processing, congestion concentrates on a few corridors and each operation may use arms of different efficiency, a slower but better-connected arm can beat a fast arm behind a congested corridor; prior work has not measured this trade-off inside the search objective.
We propose a closed-loop bilevel framework: the upper level assigns machines and sequences operations, and the lower level plans conflict-free paths by time-window reservation.
Routing-in-the-loop evaluation takes each candidate's fitness as its makespan after conflict-free routing, so yielding delay enters the search objective instead of a post-hoc check.
Reservation-table-aware dispatching trial-queries the transport legs on the current reservation table and selects the vehicle with the earliest delivery; two speed-ups provably change neither the selected vehicle nor the timetable.
On \NCases{} controlled instances (contention intensity \ContentionLo{} to \ContentionHi{}), with \NSeeds{} seeds each, an equal wall-clock budget and corrected paired tests, the complete method reduces the realized makespan by \GainEndToEnd{} (\WinEndToEnd{} wins, \LoseEndToEnd{} losses) over the open-loop structure of the literature.
Most comes from the closed loop, which alone cuts makespan by \GainLoopRule{} and is significant on the vast majority of instances; dispatching is a much smaller effect, significant only when all instances are pooled, and the two do not amplify each other."""

highlights = [
    "Schedules are scored by their makespan after conflict-free AGV routing",
    "Dispatching trial-queries the reservation table for the earliest delivery",
    "Two speed-ups provably leave the chosen vehicle and the timetable unchanged",
    "Controlled instance families vary corridor contention intensity",
    "The closed loop is the main effect; dispatching adds a much smaller one",
]
for h in highlights:
    assert len(h) <= 85, (len(h), h)

keywords = ["Flexible job shop scheduling", "Automated guided vehicles",
            "Conflict-free routing", "Bilevel optimization",
            "Memetic algorithm", "Vehicle dispatching"]

doc = r"""%% Computers & Industrial Engineering submission (elsarticle, author-year / APA-like).
%% Built from ../../paper01/paper.tex by _build_caie.py; edit paper.tex and rebuild,
%% or edit this file directly once the CAIE version diverges.
%% Double-anonymized review: compile paper01_CAIE_anonymized.tex for the manuscript
%% file; this file (with authors) serves as the title-page version.
\documentclass[preprint,review,12pt,authoryear]{elsarticle}
""" + pre + r"""

\usepackage{booktabs}
\usepackage{array}
\usepackage{adjustbox}
\usepackage{lineno}
\emergencystretch=1.5em
% single-spaced floats under the review option
\usepackage{etoolbox}
\AtBeginEnvironment{table}{\renewcommand{\baselinestretch}{1}\selectfont}
\AtBeginEnvironment{figure}{\renewcommand{\baselinestretch}{1}\selectfont}
\AtBeginEnvironment{algorithm}{\renewcommand{\baselinestretch}{1}\selectfont}
\usepackage[hidelinks]{hyperref}
% acmart-only accessibility text for figures; not used by elsarticle
\newcommand{\Description}[2][]{}

\journal{Computers \& Industrial Engineering}

\begin{document}

\begin{frontmatter}

\title{A Closed-Loop Bilevel Framework with Routing-in-the-Loop Evaluation for Flexible Job Shop Scheduling and Conflict-Free AGV Routing}

\author[cse]{Qi Yu}
\ead{230240012@seu.edu.cn}
\author[cs]{Wei Li\corref{cor1}}
\ead{xchlw@seu.edu.cn}
\cortext[cor1]{Corresponding author.}

\affiliation[cse]{organization={School of Cyber Science and Engineering, Southeast University},
            city={Nanjing},
            state={Jiangsu},
            country={China}}
\affiliation[cs]{organization={School of Computer Science and Engineering, Southeast University},
            city={Nanjing},
            state={Jiangsu},
            country={China}}

\begin{abstract}
""" + abstract + r"""
\end{abstract}

\begin{highlights}
""" + "\n".join("\\item " + h for h in highlights) + r"""
\end{highlights}

\begin{keyword}
""" + " \\sep ".join(keywords) + r"""
\end{keyword}

\end{frontmatter}

\linenumbers

""" + body + r"""
\bibliographystyle{elsarticle-harv}
\bibliography{reference-base}

\end{document}
"""
io.open(os.path.join(DST, "paper01_CAIE.tex"), "w", encoding="utf-8", newline="\n").write(doc)
io.open(os.path.join(DST, "paper01_CAIE_anonymized.tex"), "w", encoding="utf-8", newline="\n").write(
    "%% Anonymized manuscript for double-anonymized review: same source, authors hidden.\n"
    "\\PassOptionsToClass{doubleblind}{elsarticle}\n\\input{paper01_CAIE}\n")
io.open(os.path.join(DST, "highlights.txt"), "w", encoding="utf-8", newline="\n").write(
    "\n".join("- " + h for h in highlights) + "\n")

# ---- assets ----
os.makedirs(os.path.join(DST, "fig"), exist_ok=True)
os.makedirs(os.path.join(DST, "tab"), exist_ok=True)
for f in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", body):
    shutil.copy2(os.path.join(SRC, f), os.path.join(DST, f))
for f in re.findall(r"\\input\{([^}]*)\}", body):
    s = io.open(os.path.join(SRC, f), encoding="utf-8").read()
    io.open(os.path.join(DST, f), "w", encoding="utf-8", newline="\n").write(wrap_tabulars(s))
shutil.copy2(os.path.join(SRC, "reference-base.bib"), os.path.join(DST, "reference-base.bib"))

words = len(re.findall(r"\S+", re.sub(r"\\[A-Za-z]+\{\}", "X", abstract)))
print("abstract words:", words)
print("highlight lengths:", [len(h) for h in highlights])
print("citet:", body.count("\\citet{") + body.count("\\Citet{"), "citep:", body.count("\\citep{"),
      "citealp:", body.count("\\citealp{"), "bare cite:", len(re.findall(r"\\cite\{", body)))
