"""把评测存档汇总成 experiments/ 下的论文级 CSV。只读 JSON,不重跑实验。"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

from algorithm import archive

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "experiments"))

PAPER_METHODS = ("butla", "tabor", "hsmm", "markov", "ours")
FAMILIES = ("A1", "A2", "A3", "A4", "A5", "A6")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _write(name: str, rows: list, fields: list) -> str:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


def main_table(blob: dict) -> list:
    rate = blob["meta"]["primary_rate"]
    acc = defaultdict(lambda: defaultdict(list))
    arl = defaultdict(list)
    seq_fpr = defaultdict(list)
    for r in blob["runs"]:
        if r.get("rate") != rate or r.get("method") not in PAPER_METHODS:
            continue
        acc[r["method"]][r["family"]].append(r.get("seq_net"))
        seq_fpr[r["method"]].append(r.get("seq_fpr"))
        if r.get("benign_gaps"):
            arl[r["method"]].extend(r["benign_gaps"])
    rows = []
    for fam in FAMILIES:
        row = {"family": fam}
        for m in PAPER_METHODS:
            row[m] = None if _mean(acc[m][fam]) is None else round(_mean(acc[m][fam]), 3)
        rows.append(row)
    mean_row = {"family": "mean"}
    for m in PAPER_METHODS:
        vals = [row[m] for row in rows if row[m] is not None]
        mean_row[m] = round(sum(vals) / len(vals), 3) if vals else None
    rows.append(mean_row)
    return rows, {
        m: {"seq_fpr": _mean(seq_fpr[m]), "arl0": _mean(arl[m])}
        for m in PAPER_METHODS
    }


def delay_rows(blob: dict) -> list:
    rate = blob["meta"]["primary_rate"]
    rows = []
    for r in blob["runs"]:
        if r.get("rate") != rate or r.get("method") not in PAPER_METHODS:
            continue
        for d in r.get("detected_delays") or []:
            rows.append({
                "family": r["family"], "method": r["method"],
                "seed": r["seed"], "delay": d,
            })
    return rows


def robust_rows(blob: dict) -> list:
    rows = []
    fpr = blob.get("time_order_fpr", {})
    for split in ("随机折", "时间序"):
        block = fpr.get(split, {})
        for ch in ("time", "struct"):
            for a in ("0.05", "0.01"):
                cell = (block.get(ch) or {}).get(a) or {}
                rows.append({
                    "table": "fpr_split", "split": split, "channel": ch,
                    "alpha": a, "mean": cell.get("mean"), "std": cell.get("std"),
                })
    for name, block in (blob.get("cprime") or {}).items():
        if not isinstance(block, dict) or "hard" not in block:
            continue
        rows.append({
            "table": "cprime", "split": name, "channel": "hard",
            "alpha": "hard", "mean": block.get("hard"), "n": block.get("n"),
        })
        for ch in ("time", "struct"):
            rows.append({
                "table": "cprime", "split": name, "channel": ch,
                "alpha": "0.01", "mean": (block.get(ch) or {}).get("0.01"),
                "n": block.get("n"),
            })
    for name in ("seen", "unseen"):
        block = (blob.get("e9") or {}).get(name) or {}
        if not block:
            continue
        rows.append({
            "table": "e9", "split": name, "channel": "hard",
            "alpha": "hard", "mean": block.get("hard"), "n": block.get("n"),
        })
        for ch in ("time", "struct"):
            rows.append({
                "table": "e9", "split": name, "channel": ch,
                "alpha": "0.01", "mean": (block.get(ch) or {}).get("0.01"),
                "n": block.get("n"),
            })
    return rows


def transfer_rows(blob: dict) -> list:
    rows = []
    for kind, block in (("native", blob.get("native") or {}),
                        ("transfer", blob.get("transfer") or {})):
        for name, rec in block.items():
            fpr = rec.get("fpr") or {}
            rows.append({
                "kind": kind, "name": name, "n": fpr.get("n"),
                "hard": fpr.get("hard"),
                "time": (fpr.get("time") or {}).get("0.01"),
                "struct": (fpr.get("struct") or {}).get("0.01"),
                "a3_dr": (rec.get("a3") or {}).get("dr"),
            })
    return rows


def main() -> int:
    written = []
    e1 = archive.require(archive.E1_PATH)
    table, extras = main_table(e1)
    written.append(_write("main_table.csv", table,
                          ["family", "butla", "tabor", "hsmm", "markov", "ours"]))
    written.append(_write("arl0.csv", [
        {"method": m, "seq_fpr": v["seq_fpr"], "arl0": v["arl0"]}
        for m, v in extras.items()
    ], ["method", "seq_fpr", "arl0"]))
    written.append(_write("delay.csv", delay_rows(e1),
                          ["family", "method", "seed", "delay"]))

    if os.path.isfile(archive.E5_PATH):
        rows = archive.load(archive.E5_PATH)["rows"]
        written.append(_write("e5_sigma.csv", rows,
                              ["k", "sigma", "rho_star", "single_dr", "cusum_dr"]))
    if os.path.isfile(archive.E6_PATH):
        written.append(_write("e6_transfer.csv",
                              transfer_rows(archive.load(archive.E6_PATH)),
                              ["kind", "name", "n", "hard", "time", "struct", "a3_dr"]))
    if os.path.isfile(archive.ROBUST_PATH):
        written.append(_write("robust.csv",
                              robust_rows(archive.load(archive.ROBUST_PATH)),
                              ["table", "split", "channel", "alpha", "mean", "std", "n"]))
    if os.path.isfile(archive.E8_PATH):
        e8 = archive.load(archive.E8_PATH)
        written.append(_write("cost.csv", [
            {"stat": "median_us", "value": e8.get("median_us")},
            {"stat": "p95_us", "value": e8.get("p95_us")},
            {"stat": "p99_us", "value": e8.get("p99_us")},
            *[{"stat": f"M{r['M']}_median_us", "value": r["median_us"],
               "n_seq": r.get("n_seq")} for r in e8.get("scale") or []],
        ], ["stat", "value", "n_seq"]))

    meta = {
        "e1": e1.get("meta"),
        "files": written,
        "note": "CSV 由存档汇总,与 paper02_CN.tex 表内数字同源。",
    }
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("wrote", len(written), "csv + meta.json")
    for p in written:
        print(" ", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
