# -*- coding: utf-8 -*-
"""Ablation / coverage matrix (paper03 fig:ablation)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import apply_style_cn, load, save  # noqa: E402


def main():
    apply_style_cn()
    a = load()["ablation"]
    mat = np.array(a["dr"], dtype=float)
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    im = ax.imshow(mat, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4))
    ax.set_xticklabels(["S1 看门狗", "仅互证", "仅沉默", "合用"], rotation=18, ha="right")
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
    ax.set_title("消融 / 覆盖矩阵（DR / 中位时延）")
    save(fig, "fig_ablation_CN.pdf")


if __name__ == "__main__":
    main()
