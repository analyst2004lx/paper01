#!/usr/bin/env python3
"""根据 data/plot_data.json 与 loss_sweep.csv 生成实验图 PDF。"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

FIG = Path(__file__).resolve().parent
DATA = FIG / "data"

# Publication-ish defaults (avoid purple glow / cream bias)
mpl.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.linewidth": 0.8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

C_OURS = "#1B4F72"
C_BASE = "#5D6D7E"
C_ACCENT = "#B9770E"
C_WARN = "#922B21"
C_OK = "#196F3D"
C_MUTED = "#AEB6BF"


def load():
    return json.loads((DATA / "plot_data.json").read_text(encoding="utf-8"))


def save(fig, name: str):
    path = FIG / name
    fig.savefig(path, format="pdf")
    plt.close(fig)
    print(f"  {path.name}")


def fig_tier1(d):
    t = d["tier1"]
    labels = t["labels"]
    x = np.arange(len(labels))
    w = 0.25
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    ax.bar(x - w, t["p1_dr"], w, label="P1 DR", color=C_OURS)
    ax.bar(x, t["p3_dr"], w, label="P3 DR", color=C_ACCENT)
    ax.bar(x + w, t["p2_dr"], w, label="P2 DR", color=C_BASE)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Detection rate")
    ax.set_ylim(0, 1.15)
    ax.axhline(1.0, color=C_MUTED, lw=0.6, ls=":")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.set_title("Tier-1 single-observer baselines (structural zero on P1/P3)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_tier1.pdf")


def fig_witness(d):
    t = d["tier2"]
    labels = t["labels"]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.7), gridspec_kw={"wspace": 0.32})

    colors = [C_OURS if L == "OURS" else C_BASE for L in labels]
    axes[0].bar(x, t["p1_dr"], color=colors, edgecolor="black", lw=0.4)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("P1 detection rate")
    axes[0].set_ylim(0, 1.15)
    axes[0].set_title("Same protocol, witness policy only")
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)

    axes[1].bar(x, t["witness_mean"], color=colors, edgecolor="black", lw=0.4)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("Mean witness-set size")
    axes[1].set_title("Bandwidth proxy ($|W|$)")
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)

    # annotate W4 recovery
    ours_dr = t["p1_dr"][labels.index("OURS")]
    w4_dr = t["p1_dr"][labels.index("W4")]
    axes[0].annotate(
        f"W4 recovers {w4_dr/ours_dr:.0%} of OURS",
        xy=(labels.index("W4"), w4_dr),
        xytext=(2.2, 0.85),
        fontsize=7,
        arrowprops=dict(arrowstyle="->", color=C_WARN, lw=0.8),
        color=C_WARN,
    )
    save(fig, "fig_witness.pdf")


def fig_ablation(d):
    a = d["ablation"]
    mat = np.array(a["dr"], dtype=float)
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    im = ax.imshow(mat, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4))
    ax.set_xticklabels(a["channel_labels"], rotation=18, ha="right")
    ax.set_yticks(range(4))
    ax.set_yticklabels(a["attacks"])
    for i in range(4):
        for j in range(4):
            val = mat[i, j]
            lat = a["latency_median_s"][i][j]
            txt = f"{val:.3f}"
            if lat is not None:
                txt += f"\n{lat:.1f}s"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="white" if val > 0.55 else "black")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("DR")
    ax.set_title("Ablation / coverage matrix (DR / median latency)")
    save(fig, "fig_ablation.pdf")


def fig_heartbeat(d):
    h = d["heartbeat"]
    x = np.arange(len(h["regimes"]))
    w = 0.35
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    ax.bar(x - w / 2, h["silence_tdet"], w, label="Accountable silence", color=C_OURS)
    ax.bar(x + w / 2, h["period_tdet"], w, label="Equal-bandwidth periodic (H1)", color=C_BASE)
    for i, b in enumerate(h["detect_budget_s"]):
        ax.hlines(b, i - 0.4, i + 0.4, colors=C_WARN, linestyles="--", lw=1.0)
    ax.plot([], [], color=C_WARN, ls="--", label="Detect budget")
    ax.set_xticks(x)
    ax.set_xticklabels(h["regime_labels"])
    ax.set_ylabel("Detection delay $T_{\\mathrm{detect}}$ (s)")
    ax.set_title("H1: equal-bandwidth periodic vs silence (~8×)")
    ax.legend(frameon=False, fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_heartbeat.pdf")


def fig_budget_bars(d):
    h = d["heartbeat"]
    pbft = d["budget_pbft_5hz_bps"]
    bps = h["silence_bps"]
    labels = h["regime_labels"]
    ratios = [pbft / b for b in bps]
    fig, ax = plt.subplots(figsize=(5.0, 2.7))
    bars = ax.bar(labels, bps, color=[C_BASE, C_ACCENT, C_OURS], edgecolor="black", lw=0.4)
    ax.set_ylabel("Heartbeat bandwidth (B/s)")
    ax.set_title("Silence bandwidth vs 5 Hz PBFT reference")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, r, b in zip(bars, ratios, bps):
        ax.text(bar.get_x() + bar.get_width() / 2, b + 120,
                f"PBFT/{r:.0f}", ha="center", va="bottom", fontsize=7)
    # note strictest
    ax.annotate("report this\n(strictest)",
                xy=(2, bps[2]), xytext=(1.15, 5500),
                fontsize=7, color=C_WARN,
                arrowprops=dict(arrowstyle="->", color=C_WARN, lw=0.8))
    save(fig, "fig_budget_bw.pdf")


def fig_loss_sweep():
    path = DATA / "loss_sweep.csv"
    if not path.exists():
        print("  skip fig_loss_sweep.pdf (no CSV)")
        return
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    for regime, color, marker in [
        ("motion_indep", C_BASE, "o"),
        ("motion_burst", C_OURS, "s"),
    ]:
        xs, ys = [], []
        for r in rows:
            if r["regime"] != regime:
                continue
            xs.append(float(r["p_loss"]))
            ys.append(float(r["bandwidth_bps"]))
        ax.plot(xs, ys, marker=marker, color=color, lw=1.2, ms=4, label=regime)
    ax.set_xscale("log")
    ax.set_xlabel("Packet loss probability $p$")
    ax.set_ylabel("Required bandwidth (B/s)")
    ax.set_title("Loss sweep (motion hazard; PISTIS landmark $p{=}0.5$)")
    ax.axvline(0.5, color=C_WARN, ls=":", lw=0.9)
    ax.text(0.52, max(ys) * 0.55, "$p{=}50\\%$", color=C_WARN, fontsize=7)
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_loss_sweep.pdf")


def fig_collusion(d):
    c = d["collusion"]
    hist = c.get("k_hist")
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    if hist:
        ks = sorted(int(k) for k in hist)
        ns = [hist[str(k)] for k in ks]
        ax.bar(ks, ns, color=C_OURS, edgecolor="black", lw=0.3, width=0.85)
        ax.set_xlabel("Collusion bound $k$ (forward closure size)")
        ax.set_ylabel("Number of chains")
        ax.set_title(
            f"Collusion bound histogram "
            f"(k_min={c['k_min']}, median={c['k_median']}, "
            f"k>=3: {c['frac_k_ge_3']*100:.0f}%)"
        )
    else:
        # schematic from summary stats only
        ax.text(0.5, 0.5,
                f"k_min={c['k_min']}, median={c['k_median']}, "
                f"k_max={c['k_max']}\n(run export_data without --anchored)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_collusion.pdf")


def fig_coverage(d):
    c = d["coverage"]
    covered = c["frac_corroborated"]
    gap = c["oracle_gap"]
    # residual for display consistency
    other = max(0.0, 1.0 - covered)
    fig, ax = plt.subplots(figsize=(4.2, 2.5))
    ax.barh([0], [covered], color=C_OK, height=0.45, label="Corroborated")
    ax.barh([0], [other], left=[covered], color=C_MUTED, height=0.45,
            label=f"Oracle gap {gap*100:.1f}%")
    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("Fraction of activities")
    ax.set_title("Coverage vs sensor-oracle ceiling (U1)")
    ax.legend(frameon=False, loc="lower right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    save(fig, "fig_coverage.pdf")


def main():
    d = load()
    print("plotting…")
    fig_tier1(d)
    fig_witness(d)
    fig_ablation(d)
    fig_heartbeat(d)
    fig_budget_bars(d)
    fig_loss_sweep()
    fig_collusion(d)
    fig_coverage(d)
    print("done.")


if __name__ == "__main__":
    main()
