"""
fig_concurrent_disturbance.py  (revised)
=========================================
Three-panel figure for RQ6 — Concurrent Disturbance Robustness
  (a) Optimality Gap (%) vs. k
  (b) Computation Time (s) vs. k  — log-scale y-axis  ← FIXED
  (c) Schedule Stability Φ (%) vs. k                  ← NEW

Data: Table tab:concurrent, Section 5.6
      Smart Manufacturing, n=300, 50 instances per k
"""

import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

# ── 0. Global style ──────────────────────────────────────────────────────────
matplotlib.rcParams.update({
    "font.family":      "serif",
    "font.serif":       ["Times New Roman", "DejaVu Serif"],
    "font.size":        11,
    "axes.titlesize":   12,
    "axes.labelsize":   11,
    "xtick.labelsize":  10,
    "ytick.labelsize":  10,
    "legend.fontsize":  9.5,
    "figure.dpi":       150,
    "pdf.fonttype":     42,
    "ps.fonttype":      42,
    "axes.spines.top":  False,
    "axes.spines.right": False,
})

# ── 1. Data — strictly from Table tab:concurrent ─────────────────────────────
k_vals = np.array([1, 2, 3, 4])

gap = {
    "Global-MIP":      np.array([0.0,  0.0,  0.0,  0.0]),
    "Global-GA":       np.array([3.5,  4.8,  6.1,  7.9]),
    "Rolling-Horizon": np.array([9.4, 13.7, 17.2, 21.4]),
    "NOSR":            np.array([2.0,  3.4,  4.9,  6.8]),
}

# k=4 Global-MIP: table says ">120 s"; use 130 as plotting proxy (log axis)
time = {
    "Global-MIP":      np.array([45.3,  68.4,  89.7, 130.0]),
    "Global-GA":       np.array([18.7,  31.2,  44.5,  58.3]),
    "Rolling-Horizon": np.array([12.3,  15.6,  18.9,  22.1]),
    "NOSR":            np.array([ 5.1,   7.8,   9.3,  11.4]),
}

# Success rate (%) — from SR column of Table tab:concurrent
sr = {
    "Global-MIP": np.array([67.2, 44.0, 20.0,  4.0]),
    "NOSR":       np.array([100., 100., 100., 92.0]),
}

# Schedule stability Φ (%) — from Φ column of Table tab:concurrent
phi = {
    "Global-MIP":      np.array([12.4, 10.1,  8.3,  6.7]),
    "Global-GA":       np.array([15.6, 12.8, 10.4,  8.9]),
    "Rolling-Horizon": np.array([58.3, 49.6, 41.2, 33.5]),
    "NOSR":            np.array([82.7, 74.3, 65.8, 57.1]),
}

# ── 2. Visual design — NOSR green matches fig_quality_time_tradeoff ───────────
COLORS = {
    "Global-MIP":      "#d62728",   # red
    "Global-GA":       "#ff7f0e",   # orange
    "Rolling-Horizon": "#9467bd",   # purple
    "NOSR":            "#2ca02c",   # green  ← consistent with §5.2 figure
}
MARKERS = {
    "Global-MIP":      "X",
    "Global-GA":       "s",
    "Rolling-Horizon": "^",
    "NOSR":            "o",
}
LINESTYLES = {
    "Global-MIP":      (0, (4, 2)),
    "Global-GA":       (0, (3, 1, 1, 1)),
    "Rolling-Horizon": "--",
    "NOSR":            "-",
}
LW = {
    "Global-MIP":      1.6,
    "Global-GA":       1.6,
    "Rolling-Horizon": 1.6,
    "NOSR":            2.4,
}
MS       = 8
TAU_MAX  = 10.0
METHODS  = ["Global-MIP", "Global-GA", "Rolling-Horizon", "NOSR"]

# ── 3. Figure layout: 1 row × 3 panels ───────────────────────────────────────
fig, axes = plt.subplots(
    1, 3,
    figsize=(14.5, 4.4),
    gridspec_kw={"wspace": 0.38},
)
ax_gap, ax_time, ax_phi = axes

# ═════════════════════════════════════════════════════════════════════════════
#  PANEL (a): Optimality Gap vs. k
# ═════════════════════════════════════════════════════════════════════════════
for method in METHODS:
    y = gap[method]
    is_mip = (method == "Global-MIP")

    # Draw line up to k=3 for MIP (k=4 point is a timeout marker)
    k_plot = k_vals[:3] if is_mip else k_vals
    y_plot = y[:3]      if is_mip else y

    ax_gap.plot(
        k_plot, y_plot,
        color=COLORS[method], marker=MARKERS[method],
        linestyle=LINESTYLES[method], linewidth=LW[method],
        markersize=MS, label=method, zorder=3,
    )

    if is_mip:
        # k=4: red ✕ at gap=0 with SR annotation above
        ax_gap.plot(4, 0.0, color=COLORS[method],
                    marker="x", markersize=MS + 3,
                    markeredgewidth=2.5, linestyle="none", zorder=4)
        ax_gap.annotate(
            "SR=4%\n(96% TO)",
            xy=(4, 0.0),
            xytext=(3.55, 2.8),
            fontsize=8.5, color=COLORS[method],
            arrowprops=dict(arrowstyle="-", color=COLORS[method], lw=0.8),
        )

# Annotate NOSR gap values
for i, (kv, gv) in enumerate(zip(k_vals, gap["NOSR"])):
    offset_y = 0.5 if i < 3 else -1.2
    ax_gap.text(kv + 0.06, gv + offset_y, f"{gv:.1f}%",
                fontsize=8.5, color=COLORS["NOSR"], fontweight="bold")

ax_gap.set_xlabel("Number of Concurrent Disturbances $k$")
ax_gap.set_ylabel("Optimality Gap (%)")
ax_gap.set_title("(a)  Optimality Gap vs. $k$")
ax_gap.set_xticks(k_vals)
ax_gap.set_xlim(0.7, 4.5)
ax_gap.set_ylim(-0.5, 25)
ax_gap.yaxis.set_minor_locator(ticker.MultipleLocator(1))
ax_gap.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.7)
ax_gap.grid(axis="x", linestyle=":", linewidth=0.4, alpha=0.4)
ax_gap.legend(loc="upper left", framealpha=0.92, edgecolor="#cccccc")

# ═════════════════════════════════════════════════════════════════════════════
#  PANEL (b): Computation Time vs. k  — LOG-SCALE y-axis  (FIXED)
# ═════════════════════════════════════════════════════════════════════════════
ax_time.set_yscale("log")   # ← KEY FIX: caption says "log scale"

for method in METHODS:
    y = time[method]
    is_mip = (method == "Global-MIP")

    # MIP: solid line k=1..3, dashed upward arrow at k=4
    if is_mip:
        ax_time.plot(
            k_vals[:3], y[:3],
            color=COLORS[method], marker=MARKERS[method],
            linestyle=LINESTYLES[method], linewidth=LW[method],
            markersize=MS, label=method, zorder=3,
        )
        # Dashed arrow from k=3 point upward to indicate >120 s
        ax_time.annotate(
            "",
            xy=(4, 130), xytext=(4, y[2]),
            arrowprops=dict(
                arrowstyle="-|>", color=COLORS[method],
                lw=1.4, linestyle="dashed",
            ),
        )
        ax_time.text(
            4.08, 115, ">120 s\n(SR=4%)",
            fontsize=8, color=COLORS[method], va="center",
        )
    else:
        ax_time.plot(
            k_vals, y,
            color=COLORS[method], marker=MARKERS[method],
            linestyle=LINESTYLES[method], linewidth=LW[method],
            markersize=MS, label=method, zorder=3,
        )

# τ_max reference line
ax_time.axhline(TAU_MAX, color="#2ca02c", linestyle="-.",
                linewidth=1.8, label=r"$\tau_{\max}=10\,$s", zorder=2)

# Shade infeasible zone (above τ_max)
ax_time.axhspan(TAU_MAX, 200, color="#2ca02c", alpha=0.06, zorder=1)
ax_time.text(0.78, 12.5, "Budget exceeded",
             fontsize=8, color="#2ca02c", alpha=0.85)

# Annotate NOSR time values
for i, (kv, tv) in enumerate(zip(k_vals, time["NOSR"])):
    # On log axis: offset multiplicatively
    offset_factor = 0.78 if i < 3 else 1.18
    ax_time.text(kv + 0.06, tv * offset_factor, f"{tv:.1f} s",
                 fontsize=8.5, color=COLORS["NOSR"], fontweight="bold")

# Mark k=4 NOSR with SR=92% annotation
ax_time.annotate(
    "SR=92%",
    xy=(4, time["NOSR"][3]),
    xytext=(3.3, time["NOSR"][3] * 1.6),
    fontsize=8.5, color=COLORS["NOSR"],
    arrowprops=dict(arrowstyle="->", color=COLORS["NOSR"], lw=0.9),
)

ax_time.set_xlabel("Number of Concurrent Disturbances $k$")
ax_time.set_ylabel("Computation Time (s)  [log scale]")
ax_time.set_title("(b)  Computation Time vs. $k$")
ax_time.set_xticks(k_vals)
ax_time.set_xlim(0.7, 4.5)
ax_time.set_ylim(3, 200)
ax_time.yaxis.set_major_formatter(
    ticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
ax_time.yaxis.set_minor_locator(ticker.LogLocator(subs="all", numticks=10))
ax_time.grid(axis="y", which="both", linestyle=":", linewidth=0.5, alpha=0.6)
ax_time.grid(axis="x", linestyle=":", linewidth=0.4, alpha=0.4)
ax_time.legend(loc="upper left", framealpha=0.92, edgecolor="#cccccc")

# ═════════════════════════════════════════════════════════════════════════════
#  PANEL (c): Schedule Stability Φ vs. k  (NEW — covers Key Finding 3)
# ═════════════════════════════════════════════════════════════════════════════
for method in METHODS:
    y = phi[method]
    ax_phi.plot(
        k_vals, y,
        color=COLORS[method], marker=MARKERS[method],
        linestyle=LINESTYLES[method], linewidth=LW[method],
        markersize=MS, label=method, zorder=3,
    )

# Annotate NOSR Φ values
for i, (kv, pv) in enumerate(zip(k_vals, phi["NOSR"])):
    offset_y = 2.5 if i < 3 else -4.5
    ax_phi.text(kv + 0.06, pv + offset_y, f"{pv:.1f}%",
                fontsize=8.5, color=COLORS["NOSR"], fontweight="bold")

# Shade "NOSR advantage" region between NOSR and Rolling-Horizon
ax_phi.fill_between(
    k_vals,
    phi["Rolling-Horizon"],
    phi["NOSR"],
    alpha=0.10, color=COLORS["NOSR"],
    label="NOSR advantage",
)

ax_phi.set_xlabel("Number of Concurrent Disturbances $k$")
ax_phi.set_ylabel("Schedule Stability $\\Phi$ (% tasks unchanged)")
ax_phi.set_title("(c)  Schedule Stability vs. $k$")
ax_phi.set_xticks(k_vals)
ax_phi.set_xlim(0.7, 4.5)
ax_phi.set_ylim(0, 95)
ax_phi.yaxis.set_minor_locator(ticker.MultipleLocator(5))
ax_phi.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.7)
ax_phi.grid(axis="x", linestyle=":", linewidth=0.4, alpha=0.4)
ax_phi.legend(loc="upper right", framealpha=0.92, edgecolor="#cccccc")

# ── 4. Shared legend note ─────────────────────────────────────────────────────
fig.suptitle(
    "Figure: Concurrent Disturbance Robustness  "
    "(Smart Manufacturing, $n=300$, 50 instances per $k$)",
    fontsize=11, y=1.02, fontstyle="italic",
)

# ── 5. Save ───────────────────────────────────────────────────────────────────
os.makedirs("figures", exist_ok=True)
plt.tight_layout()
fig.savefig("figures/fig_concurrent_disturbance_new.pdf",
            bbox_inches="tight", dpi=300)
print("✅  Saved: figures/fig_concurrent_disturbance.pdf / .png")
plt.show()