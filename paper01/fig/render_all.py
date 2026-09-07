# -*- coding: utf-8 -*-
"""Render every paper figure that has its data; skip the rest with a clear reason.

Supports unfinished runs: a figure whose CSV is incomplete still draws, but the
script that owns it calls mark_draft() so the PDF carries a DRAFT watermark and
cannot be mistaken for a final figure.  Figures whose CSV is entirely absent
are skipped, not invented.

Run from the repository root:
  py paper01/fig/render_all.py
  set CLBS_FIG_PNG=1 && py paper01/fig/render_all.py   # also write png previews
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "clbs", "output")

# (script, output stem, required paths relative to clbs/output or absolute markers)
JOBS = [
    ("fig_framework.py", "fig_framework", []),  # schematic, no data
    ("fig_motivating.py", "fig_motivating", ["motivating.json"]),
    ("fig_prediction3.py", "fig_prediction3", ["baseline_ladder.csv"]),
    ("fig_convergence.py", "fig_convergence_closedloop",
     ["ladder_convergence.csv", "ladder_cost.csv"]),
    ("fig_protocol.py", "fig_protocol", ["ladder_cost.csv"]),
    ("fig_protocols.py", "fig_protocols", []),  # reads clbs/experiments/protocols.csv
    ("fig_theta.py", "fig_theta", []),          # reads theta_sweep CSVs under experiments/
    ("fig_case_gantt.py", "fig_case_gantt", ["case_study"]),
    ("fig_case_chain.py", "fig_case_chain", ["case_study"]),
]


def ready(needs):
    missing = []
    for n in needs:
        p = os.path.join(OUT, n)
        if not os.path.exists(p):
            missing.append(n)
        elif os.path.isdir(p) and not os.listdir(p):
            missing.append(n + "/ (empty)")
    return missing


def main() -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    ok = skip = fail = 0
    print("渲染可用图;缺数据的跳过(不会用假数填)\n")
    for script, stem, needs in JOBS:
        miss = ready(needs)
        if miss:
            print("SKIP  %-28s 缺 %s" % (stem, ", ".join(miss)))
            skip += 1
            continue
        print("RUN   %-28s <- %s" % (stem, script))
        r = subprocess.run([sys.executable, os.path.join(HERE, script)],
                           cwd=ROOT, env=env)
        if r.returncode == 0:
            ok += 1
        else:
            print("  !! 失败 exit=%d" % r.returncode)
            fail += 1
    print("\n完成: %d 写出 / %d 跳过 / %d 失败" % (ok, skip, fail))
    if skip:
        print("跳过的图在下列数据落盘后重跑本脚本即可:")
        print("  tools/motivating.py --sweep -> motivating.json")
        print("  tools/baseline_ladder.py  -> baseline_ladder.csv")
        print("  tools/prune_ablation.py   -> prune_ablation.csv  (fig_protocol 的箭头可选)")
        print("  tools/ladder_diag.py      -> ladder_cost/convergence + case_study/")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
