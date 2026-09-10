"""从已有存档导出论文表;可选重跑诊断。不重跑 E1,除非显式 --e1。"""
from __future__ import annotations

import argparse
import subprocess
import sys

STEPS = (
    ("robust", [sys.executable, "-m", "tools.robust_diag"]),
    ("sigma", [sys.executable, "-m", "tools.sigma_scan"]),
    ("online", [sys.executable, "-m", "tools.online_diag"]),
    ("transfer", [sys.executable, "-m", "tools.transfer_diag"]),
    ("walk", [sys.executable, "-m", "tools.alarm_walkthrough"]),
    ("bound", [sys.executable, "-m", "tools.bound_curve"]),
    ("export", [sys.executable, "-m", "tools.export_experiments"]),
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", action="store_true",
                    help="重跑诊断(不含 E1)")
    ap.add_argument("--e1", action="store_true",
                    help="另跑 baseline_diag,约数分钟")
    args = ap.parse_args()
    if args.e1:
        subprocess.check_call([sys.executable, "-m", "tools.baseline_diag"])
    if args.run:
        for name, cmd in STEPS[:-1]:
            print("==", name)
            subprocess.check_call(cmd)
    subprocess.check_call(STEPS[-1][1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
