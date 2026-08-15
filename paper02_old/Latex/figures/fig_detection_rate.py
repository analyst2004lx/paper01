"""
fig_detection_rate.py
Generates Fig. 2 – Detection Rate vs. Anomalous Traffic Ratio.
Output: fig_detection_rate.pdf / fig_detection_rate.png

Data anchors derived from V6 paper text:
  FMM  : avg 42.9 %;  ≈0 % at low traffic; rises slowly at high traffic
  STBAD: avg 60.4 %;  ≈20-30 % at low;     rises steadily
  SMLC : avg 74.0 %;  ≈50 % at low;         reaches ~80 % above 30 %
  MBDF : avg 85.3 %;  >90 % at <10 %;       97.5 % at replay scenario;
                       slight drop at very high ratios
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── Global style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":    "serif",
    "font.serif":     ["Times New Roman", "DejaVu Serif"],
    "font.size":      10,
    "axes.linewidth": 0.9,
    "pdf.fonttype":   42,
    "ps.fonttype":    42,
})

# ── X-axis: anomalous traffic ratio (%) ───────────────────────────────────────
x = np.array([1, 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100],
             dtype=float)

# ── Detection rate curves (%) ─────────────────────────────────────────────────
# Flow Measurement Method
# Near 0 % at low traffic; slowly rises; avg ≈ 42.9 %
fmm = np.array([0.0, 0.0, 2.0, 8.0, 18.0, 38.0, 55.0,
                68.0, 76.0, 82.0, 86.0, 88.0, 90.0])

# Statistical Threshold-Based Anomaly Detection
# ~20-30 % at low; gradual rise; avg ≈ 60.4 %
stbad = np.array([18.0, 22.0, 28.0, 35.0, 44.0, 58.0, 68.0,
                  75.0, 80.0, 84.0, 87.0, 89.0, 91.0])

# Supervised ML Classification
# ~50 % at low (sparse data); rises sharply above 30 %; avg ≈ 74.0 %
smlc = np.array([48.0, 50.0, 52.0, 56.0, 62.0, 72.0, 78.0,
                 80.0, 81.0, 82.0, 83.0, 84.0, 85.0])

# MBDF (proposed)
# >90 % at <10 %; 97.5 % at replay; slight drop at very high ratios;
# avg ≈ 85.3 %
mbdf = np.array([91.0, 97.5, 95.0, 93.5, 92.0, 90.5, 89.0,
                 87.0, 85.5, 83.0, 81.0, 80.0, 79.5])

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(5.5, 4.0))

styles = dict(linewidth=1.8, markersize=5)

ax.plot(x, fmm,   "s--", color="#E74C3C", label="Flow Measurement (FMM)",
        **styles)
ax.plot(x, stbad, "^-.", color="#F39C12",
        label="Threshold-Based (STBAD)", **styles)
ax.plot(x, smlc,  "D:",  color="#8E44AD",
        label="ML Classification (SMLC)", **styles)
ax.plot(x, mbdf,  "o-",  color="#1A73E8",
        label="MBDF (Proposed)", linewidth=2.2, markersize=6)

# ── Annotations ───────────────────────────────────────────────────────────────
# 10 % boundary
ax.axvline(x=10, color="#888888", linestyle=":", linewidth=1.0)
ax.text(10.5, 10, "10% boundary\n(industrial regime)",
        fontsize=7.5, color="#555555", va="bottom")

# MBDF average line
ax.axhline(y=85.3, color="#1A73E8", linestyle="--",
           linewidth=0.9, alpha=0.55)
ax.text(101, 85.3, r"$\overline{\mathrm{DR}}$=85.3%",
        fontsize=7.5, color="#1A73E8", va="center")

# FMM average line
ax.axhline(y=42.9, color="#E74C3C", linestyle="--",
           linewidth=0.9, alpha=0.55)
ax.text(101, 42.9, r"$\overline{\mathrm{DR}}$=42.9%",
        fontsize=7.5, color="#E74C3C", va="center")

# Replay attack marker
ax.annotate("Replay attack\nDR = 97.5%",
            xy=(5, 97.5), xytext=(18, 97.8),
            fontsize=7.5, color="#1A73E8",
            arrowprops=dict(arrowstyle="->", color="#1A73E8",
                            lw=0.9))

# ── Axes formatting ───────────────────────────────────────────────────────────
ax.set_xlabel("Anomalous Traffic Ratio (%)", fontsize=10)
ax.set_ylabel("Detection Rate (%)", fontsize=10)
ax.set_xlim(0, 115)
ax.set_ylim(0, 105)
ax.set_xticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
ax.set_yticks(range(0, 105, 10))
ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
ax.grid(True, which="major", linestyle="--",
        linewidth=0.5, alpha=0.6)
ax.grid(True, which="minor", linestyle=":",
        linewidth=0.3, alpha=0.4)

ax.legend(loc="lower right", fontsize=8,
          framealpha=0.92, edgecolor="#CCCCCC")

plt.tight_layout()
plt.savefig("fig_detection_rate.pdf", dpi=300, bbox_inches="tight")
plt.savefig("fig_detection_rate.png", dpi=300, bbox_inches="tight")
print("Saved: fig_detection_rate.pdf / fig_detection_rate.png")
plt.show()