"""Shared style and data access for the experiment figures.

Every figure in this paper is generated from the CSV files written by
``clbs/tools/export_experiments.py`` (and the two companion sweeps), so no
number is hard-coded here.  If a CSV is missing the scripts fail loudly rather
than silently drawing something invented.

Data contract (see clbs/experiments/):
  runs.csv            one row per (instance, arm, seed)
  cells.csv           aggregated per (instance, arm)
  gains.csv           paired gain of `closed` over each baseline, per instance
  gains_by_seed.csv   the same, per seed, for error bars and paired tests
  instances.csv       instance features and the composite lower bound
  theta_sweep.csv     pricing strength sweep
  convergence.csv     best-so-far makespan against wall-clock time
  meta.json           seeds, budgets, validation failures
"""
from __future__ import annotations

import collections
import csv
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "..", "clbs", "experiments"))
# The ladder batch writes here directly, without going through the older
# export step; these CSVs are read with the stdlib so that a machine carrying
# only matplotlib can still draw the figures.
OUTPUT = os.path.abspath(os.path.join(HERE, "..", "..", "clbs", "output"))

# ACM two-column: a single column is about 3.33in, the full width about 7.0in.
COL = 3.33
FULL = 7.0

plt.rcParams.update({
    "font.size": 8,
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "axes.labelsize": 8.5,
    "axes.titlesize": 9,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "legend.frameon": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "lines.linewidth": 1.3,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

# Order of the progressive ablation chain; every figure uses it so that the
# reading order of the arms never changes between figures.
# 顺序按每次评价的成本从低到高:论文的核心观察是质量大体随成本递减,
# 图上按成本排序才能让这件事直接被看见,而不必读者自己去对照成本表。
ARM_ORDER = ["rule", "twostage", "opendispatch_nols", "opendispatch",
             "nofeedback", "nostagger", "closed", "priced"]

ARM_LABEL = {
    "rule": "Dispatch\nrule",
    "twostage": "Two-stage\nopen loop",
    "opendispatch_nols": "Evaluation loop\n(this paper)",
    "opendispatch": "+ guided\nsearch",
    "nofeedback": "+ exact\ndispatch",
    "nostagger": "+ both, no\nstaggering",
    "closed": "+ both\n(full loop)",
    "priced": "+ pricing\n(negative)",
}

# Short labels for axes where the multi-line version does not fit.
ARM_SHORT = {
    "rule": "rule",
    "twostage": "two-stage",
    "opendispatch_nols": "eval. loop",
    "opendispatch": "+ search",
    "nofeedback": "+ dispatch",
    "nostagger": "+ no stagger",
    "closed": "+ full loop",
    "priced": "+ pricing",
}

ARM_COLOR = {
    "rule": "#9e9e9e",
    "twostage": "#8c8c8c",
    "opendispatch_nols": "#08519c",   # 主方法:最深,与消融档区分
    "opendispatch": "#a6cee3",
    "nofeedback": "#6baed6",
    "nostagger": "#4292c6",
    "closed": "#2171b5",
    "priced": "#d62728",
}

TAG_LABEL = {"low": "low", "mid": "mid", "high": "high",
             "funnel": "funnel"}
TAG_COLOR = {"low": "#c7e9c0", "mid": "#a1d99b",
             "high": "#08519c", "funnel": "#d95f02"}

BASELINE_LABEL = {
    "twostage": "vs two-stage open loop",
    "nofeedback": "vs evaluation loop only",
    "opendispatch": "vs open dispatch",
    "nostagger": "vs no staggering",
}


def load(name):
    """Read one of the exported CSVs, failing loudly if it is absent.

    pandas is imported here rather than at module scope so that the figures
    which only need the stdlib reader below can be drawn on a machine that has
    matplotlib but no scientific stack.
    """
    import pandas as pd

    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        raise SystemExit(
            "missing %s\n  run:  py -m tools.export_experiments --runs p3\n"
            "  (from the clbs/ directory)" % path)
    return pd.read_csv(path)


def load_output(name, hint=""):
    """Read a CSV written directly by the ladder tools, as a list of dicts.

    Numeric-looking fields are converted; everything else stays a string.  The
    error message names the tool that produces the file, because the usual way
    to hit it is to draw a figure before its experiment has finished.
    """
    path = os.path.join(OUTPUT, name)
    if not os.path.exists(path):
        raise SystemExit("缺少 %s\n  在 clbs/ 目录下运行:%s" % (path, hint))
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out = {}
            for k, v in r.items():
                if v is None or v == "":
                    out[k] = None
                    continue
                try:
                    out[k] = float(v) if ("." in v or "e" in v.lower()) else int(v)
                except ValueError:
                    out[k] = v
            rows.append(out)
    if not rows:
        raise SystemExit("%s 是空的,不画图" % path)
    return rows


def by(rows, *keys):
    """Group rows by a tuple of column values, preserving insertion order."""
    out = collections.OrderedDict()
    for r in rows:
        out.setdefault(tuple(r[k] for k in keys), []).append(r)
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


# ---- the four ladder arms -------------------------------------------------
# One vocabulary for every ladder figure: the 2x2 factorial read row-major, so
# that colour carries "closed loop or not" and lightness carries the dispatch
# rule.  Keeping this in one place is what stops figure 3 and figure 7 from
# disagreeing about which blue is B1.
LADDER = ["B0", "B0+", "B1", "B2"]
LADDER_LABEL = {
    "B0": "B0\nopen loop,\nrule dispatch",
    "B0+": "B0$^+$\nopen loop,\nprobing dispatch",
    "B1": "B1\nclosed loop,\nrule dispatch",
    "B2": "B2 (proposed)\nclosed loop,\nprobing dispatch",
}
LADDER_SHORT = {"B0": "B0", "B0+": "B0$^+$", "B1": "B1", "B2": "B2"}
LADDER_COLOR = {"B0": "#bdbdbd", "B0+": "#737373",
                "B1": "#6baed6", "B2": "#08519c"}


def meta():
    path = os.path.join(DATA, "meta.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def require_seeds(min_seeds=10):
    """Refuse to emit a publication figure from an under-powered run.

    The paper's own methodology section argues that two-seed readings sit
    inside the noise, so it would be self-defeating to ship a figure built on
    them by accident.  Set CLBS_FIG_DRAFT=1 to override while developing.
    """
    m = meta()
    n = m.get("num_seeds", 0)
    if n >= min_seeds or os.environ.get("CLBS_FIG_DRAFT") == "1":
        return m
    raise SystemExit(
        "refusing to plot: the exported data has %d seed(s), fewer than the %d "
        "the protocol requires.\n  set CLBS_FIG_DRAFT=1 to draft anyway."
        % (n, min_seeds))


def meta_protocols():
    """Metadata for the dual-protocol comparison (its own instance/seed scope).

    The equal-generation run covers a subset of the instances of the
    wall-clock run, so the two protocols are compared only on what they share
    and the figure must quote that scope rather than the global one.
    """
    path = os.path.join(DATA, "protocols_meta.json")
    if not os.path.exists(path):
        raise SystemExit(
            "missing %s; run: py -m tools.export_experiments --runs p3 "
            "--gen-runs gen100" % path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stars(p):
    """Significance markers; blank when the test could not reject anything."""
    if p is None or p != p:          # NaN compares unequal to itself
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


_DRAFT_REASONS = []


def mark_draft(reason):
    """Record that this figure is not publication-ready, and why.

    The env-var switch below relies on whoever runs the script remembering to
    set it; this one does not, because the script checks its own input.  A
    figure built from an under-powered run is the single easiest thing to leave
    in a manuscript by accident, so the guard is on by default and the reason
    is stamped on the artwork where a reader cannot miss it.
    """
    _DRAFT_REASONS.append(str(reason))


def save(fig, stem):
    # A figure drawn from an under-powered run must never be mistaken for a
    # final one, so draft mode stamps the reason across the artwork itself
    # rather than relying on anyone remembering to regenerate it.
    reasons = list(_DRAFT_REASONS)
    # CLBS_FIG_DRAFT only unlocks require_seeds(); the watermark itself must
    # come from mark_draft() with a reason taken from *this* figure's input.
    # Quoting meta.json's seed count here used to stamp the wrong batch's size
    # on a draft built from a different CSV.
    if reasons:
        fig.text(0.5, 0.5, "DRAFT\n" + "\n".join(reasons),
                 transform=fig.transFigure, fontsize=20, color="red",
                 alpha=0.16, ha="center", va="center", rotation=22,
                 zorder=100, fontweight="bold", linespacing=1.2)
        print("  !! 草稿:%s" % "; ".join(reasons))
    out = os.path.join(HERE, stem + ".pdf")
    fig.savefig(out)
    if os.environ.get("CLBS_FIG_PNG") == "1":
        fig.savefig(os.path.join(HERE, stem + ".png"), dpi=160)
    plt.close(fig)
    print("wrote %s" % out)
