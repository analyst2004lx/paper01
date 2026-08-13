"""
fig_framework.py
Generates the MBDF architecture diagram (framework figure).
Output: framework.pdf / framework.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# ── Global style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":      "serif",
    "font.serif":       ["Times New Roman", "DejaVu Serif"],
    "font.size":        10,
    "axes.linewidth":   0.8,
    "pdf.fonttype":     42,   # editable text in PDF
    "ps.fonttype":      42,
})

# ── Colour palette ────────────────────────────────────────────────────────────
C_OFFLINE  = "#D6EAF8"   # light blue  – offline training boxes
C_ONLINE   = "#D5F5E3"   # light green – online inference boxes
C_DECISION = "#FDEBD0"   # light orange – decision box
C_BORDER   = "#2C3E50"   # dark border
C_ARROW    = "#2C3E50"
C_PHASE    = "#7F8C8D"   # phase label colour

fig, ax = plt.subplots(figsize=(7.0, 5.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 8)
ax.axis("off")

# ── Helper: rounded rectangle ─────────────────────────────────────────────────
def draw_box(ax, x, y, w, h, label, sublabel=None,
             fc=C_OFFLINE, ec=C_BORDER, lw=1.2, fontsize=9):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.12",
                         facecolor=fc, edgecolor=ec, linewidth=lw)
    ax.add_patch(box)
    cy = y + h / 2 + (0.18 if sublabel else 0)
    ax.text(x + w / 2, cy, label,
            ha="center", va="center", fontsize=fontsize,
            fontweight="bold", color=C_BORDER)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.28, sublabel,
                ha="center", va="center", fontsize=7.5,
                color="#555555", style="italic")

# ── Helper: solid arrow ───────────────────────────────────────────────────────
def arrow(ax, x1, y1, x2, y2, label=None, color=C_ARROW, lw=1.5):
    ax.annotate("",
                xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>",
                                color=color, lw=lw,
                                mutation_scale=14))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.12, my, label,
                fontsize=7.5, color=color, va="center")

# ── Helper: dashed arrow ──────────────────────────────────────────────────────
def dashed_arrow(ax, x1, y1, x2, y2, label=None, color="#999999"):
    ax.annotate("",
                xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=1.2, linestyle="dashed",
                                mutation_scale=12))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.12, my, label,
                fontsize=7.5, color=color, va="center", style="italic")

# ══════════════════════════════════════════════════════════════════════════════
# OFFLINE TRAINING PHASE  (left column, dashed border region)
# ══════════════════════════════════════════════════════════════════════════════
offline_rect = FancyBboxPatch((0.3, 3.9), 3.8, 3.7,
                               boxstyle="round,pad=0.1",
                               facecolor="#EBF5FB", edgecolor="#AED6F1",
                               linewidth=1.0, linestyle="dashed")
ax.add_patch(offline_rect)
ax.text(0.72, 7.42, "Offline Training Phase",
        fontsize=8, color=C_PHASE, fontstyle="italic")

# Box 1 – Historical log
draw_box(ax, 0.55, 6.35, 3.3, 0.95,
         "Historical State Log  $\\mathcal{D}$",
         sublabel="188 transitions (normal operation)",
         fc=C_OFFLINE)

# Box 2 – Transition matrix estimation
draw_box(ax, 0.55, 5.05, 3.3, 0.95,
         "Transition Matrix Estimation",
         sublabel=r"$\hat{P}_{ij}=c_{ij}/\sum_{j'}c_{ij'}$",
         fc=C_OFFLINE)

# Box 3 – Bayesian network inference
draw_box(ax, 0.55, 3.75, 3.3, 0.95,
         "Bayesian Network Inference",
         sublabel=r"$\mathcal{P}_{BN}(s_i)=P(S=s_i\mid\mathcal{D})$",
         fc=C_OFFLINE)

# Arrows inside offline region
arrow(ax, 2.20, 6.35, 2.20, 6.00)   # log → matrix
arrow(ax, 2.20, 5.05, 2.20, 4.70)   # log → Bayesian

# ══════════════════════════════════════════════════════════════════════════════
# ONLINE INFERENCE PHASE  (right column)
# ══════════════════════════════════════════════════════════════════════════════
online_rect = FancyBboxPatch((5.9, 1.0), 3.8, 6.6,
                              boxstyle="round,pad=0.1",
                              facecolor="#EAFAF1", edgecolor="#A9DFBF",
                              linewidth=1.0, linestyle="dashed")
ax.add_patch(online_rect)
ax.text(6.28, 7.42, "Online Inference Phase",
        fontsize=8, color=C_PHASE, fontstyle="italic")

# Input box
draw_box(ax, 6.15, 6.35, 3.3, 0.95,
         "Observed State  $\\mathbf{s}_t$",
         sublabel="One-hot encoded agent state",
         fc="#FDFEFE", ec="#AED6F1")

# Layer 1 box
draw_box(ax, 6.15, 4.75, 3.3, 1.15,
         "Layer 1 — Markov Prediction",
         sublabel=r"$\hat{\mathbf{s}}_{t+1}=\hat{\mathbf{P}}^{\top}\mathbf{s}_t$",
         fc=C_ONLINE)

# Layer 2 box
draw_box(ax, 6.15, 3.15, 3.3, 1.15,
         "Layer 2 — Bayesian Thresholding",
         sublabel=r"$\varepsilon_i = \mathcal{P}_{BN}(s_i)\cdot k$",
         fc=C_ONLINE)

# Decision box
draw_box(ax, 6.15, 1.55, 3.3, 1.15,
         "Anomaly Decision",
         sublabel=r"$\|\mathbf{s}_{t+1}-\hat{\mathbf{s}}_{t+1}\|_2 \geq \varepsilon_i$?",
         fc=C_DECISION)

# Arrows inside online region
arrow(ax, 7.80, 6.35, 7.80, 5.90)   # input → L1
arrow(ax, 7.80, 4.75, 7.80, 4.30)   # L1 → L2
arrow(ax, 7.80, 3.15, 7.80, 2.70)   # L2 → decision

# Output labels
ax.text(9.72, 2.12, "Anomaly (1)", fontsize=8,
        color="#C0392B", fontweight="bold", va="center")
ax.text(9.72, 1.72, "Normal  (0)", fontsize=8,
        color="#1A5276", fontweight="bold", va="center")
arrow(ax, 9.45, 2.12, 9.68, 2.12, color="#C0392B", lw=1.2)
arrow(ax, 9.45, 1.72, 9.68, 1.72, color="#1A5276", lw=1.2)

# ══════════════════════════════════════════════════════════════════════════════
# CROSS-PHASE DASHED ARROWS  (trained parameters feed into online)
# ══════════════════════════════════════════════════════════════════════════════
# P_hat: matrix estimation → Layer 1
dashed_arrow(ax, 3.85, 5.52, 6.15, 5.32,
             label=r"$\hat{\mathbf{P}}$")

# P_BN: Bayesian → Layer 2
dashed_arrow(ax, 3.85, 4.22, 6.15, 3.72,
             label=r"$\mathcal{P}_{BN}$")

# ══════════════════════════════════════════════════════════════════════════════
# TITLE
# ══════════════════════════════════════════════════════════════════════════════
ax.text(5.0, 7.75,
        "MBDF: Markov-Bayesian Dual-Layer Detection Framework",
        ha="center", va="center", fontsize=11,
        fontweight="bold", color=C_BORDER)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(facecolor=C_OFFLINE,  edgecolor=C_BORDER,
                   label="Offline training component"),
    mpatches.Patch(facecolor=C_ONLINE,   edgecolor=C_BORDER,
                   label="Online inference component"),
    mpatches.Patch(facecolor=C_DECISION, edgecolor=C_BORDER,
                   label="Decision component"),
]
ax.legend(handles=legend_items, loc="lower center",
          bbox_to_anchor=(0.5, -0.01),
          ncol=3, fontsize=8, framealpha=0.9,
          edgecolor="#CCCCCC")

plt.tight_layout()
plt.savefig("framework.pdf", dpi=300, bbox_inches="tight")
plt.savefig("framework.png", dpi=300, bbox_inches="tight")
print("Saved: framework.pdf / framework.png")
plt.show()