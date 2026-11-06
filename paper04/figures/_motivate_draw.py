# -*- coding: utf-8 -*-
"""Shared layout for fig_strc_motivate(_CN): same schedule, two scoping views.

Scenario (time units):
  Notation follows the paper: vehicle k, machine M, operation O_{ji}, blocked corridor e^star.
  t_now = 5, blockage on corridor e^star during [7, 9).
  Machine layer: M1 runs O11 [0,4), O21 [4,7); M2 runs O12 [12,16), O22 [16,19).
  Corridor layer: k1 (job 1) e^star [6,9) -> e2 [9,12) -> delivers O12;
                  k2 (job 2) e^star [9,12) -> e2 [13,16) -> delivers O22;
                  k3 (other job) e3 [2,4) finished, e3 [13,16) outside the closure.
  k1@e^star overlaps the blockage (seed). k2@e^star abuts k1@e^star (yield edge) but not
  the blockage, so it enters the closure only through propagation.
"""
from __future__ import annotations

from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Rectangle

T_NOW = 5.0
BLOCK = (7.0, 9.0)
XMIN, XMAX = -0.2, 20.0
YMIN_STRC = -1.9
HEIGHT_RATIOS = [9.6 + 0.9, 9.6 - YMIN_STRC]

Y = {"M1": 8.3, "M2": 7.3, "e*": 4.9, "e2": 3.9, "e3": 2.9}
H = 0.62

OPS = [("M1", 0, 4, r"$O_{11}$"), ("M1", 4, 7, r"$O_{21}$"),
       ("M2", 12, 16, r"$O_{12}$"), ("M2", 16, 19, r"$O_{22}$")]

# key, row, start, end, vehicle, role
OCC = [
    ("v1e", "e*", 6, 9, r"$k_1$", "seed"),
    ("v1f", "e2", 9, 12, r"$k_1$", "in"),
    ("v2e", "e*", 9, 12, r"$k_2$", "in"),
    ("v2f", "e2", 13, 16, r"$k_2$", "in"),
    ("v3a", "e3", 2, 4, r"$k_3$", "done"),
    ("v3b", "e3", 13, 16, r"$k_3$", "out"),
]
DELIVERS = {"v1f": "O12", "v2f": "O22"}

C_OP = "#e8eef5"
C_SEED = "#c45c26"
C_IN = "#1f4e79"
C_OUT = "#9e9e9e"
C_DONE = "#d9d9d9"
C_BLOCK = "#e8a0a0"
C_RED = "#b22222"
C_GREEN = "#2e7d32"


def _bar(ax, x0, x1, y, fc, ec="#222222", alpha=1.0, hatch=None, text="",
         tc="white", fs=7.0):
    ax.add_patch(FancyBboxPatch(
        (x0 + 0.05, y - H / 2), x1 - x0 - 0.1, H,
        boxstyle="round,pad=0.0,rounding_size=0.12",
        facecolor=fc, edgecolor=ec, linewidth=0.9, alpha=alpha, hatch=hatch))
    if text:
        ax.text((x0 + x1) / 2, y, text, ha="center", va="center", fontsize=fs,
                color=tc, alpha=max(alpha, 0.35), fontweight="bold")


def _center(key):
    for k, row, s, e, _, _ in OCC:
        if k == key:
            return (s + e) / 2, Y[row]
    raise KeyError(key)


def _frame(ax, L, faded_layer, ymin=-0.9, block_label=True):
    ax.set_xlim(-3.8, XMAX + 3.2)
    ax.set_ylim(ymin, 9.6)
    ax.axis("off")

    a_m = 0.28 if faded_layer == "machine" else 1.0
    a_c = 0.28 if faded_layer == "corridor" else 1.0

    # layer captions and row labels
    ax.text(-3.5, (Y["M1"] + Y["M2"]) / 2, L["machine_layer"], fontsize=7.5,
            rotation=90, va="center", ha="center", color="#333333", alpha=max(a_m, 0.5))
    ax.text(-3.5, Y["e2"], L["corridor_layer"], fontsize=7.5,
            rotation=90, va="center", ha="center", color="#333333", alpha=max(a_c, 0.5))
    for r in ("M1", "M2"):
        ax.text(-0.4, Y[r], L["machine"] + " " + r, fontsize=7, ha="right",
                va="center", alpha=max(a_m, 0.5))
    for r, sym in (("e*", r"$e^\star$"), ("e2", r"$e_2$"), ("e3", r"$e_3$")):
        ax.text(-0.4, Y[r], L["corridor"] + " " + sym, fontsize=7, ha="right",
                va="center", alpha=max(a_c, 0.5))

    # layer separator and time axis
    ax.plot([XMIN, XMAX], [6.1, 6.1], color="#bbbbbb", lw=0.6, ls="-")
    ax.annotate("", xy=(XMAX, 2.15), xytext=(XMIN, 2.15),
                arrowprops=dict(arrowstyle="->", color="#444444", lw=0.8))
    ax.text(XMAX + 0.1, 2.15, "t", fontsize=7.5, va="center")

    # t_now across both layers
    ax.plot([T_NOW, T_NOW], [2.15, 9.0], color="#555555", lw=0.9, ls=(0, (4, 2)))
    ax.text(T_NOW, 9.15, r"$t_{\mathrm{now}}$", fontsize=7.5, ha="center", va="bottom")

    # blockage band only on corridor e*
    ax.add_patch(Rectangle((BLOCK[0], Y["e*"] - 0.42), BLOCK[1] - BLOCK[0], 0.84,
                           facecolor="none", edgecolor="#8b1e1e", hatch="////",
                           linewidth=1.0, zorder=3))
    if block_label:
        ax.text((BLOCK[0] + BLOCK[1]) / 2, Y["e*"] - 0.5, L["block"], fontsize=6.8,
                ha="center", va="top", color="#8b1e1e", fontweight="bold")

    # machine layer
    for row, s, e, lab in OPS:
        _bar(ax, s, e, Y[row], C_OP, ec="#555555", alpha=a_m, text=lab,
             tc="#1a1a1a", fs=6.8)

    # transport -> operation links
    for k, op in DELIVERS.items():
        _, row, s, e, _, _ = next(o for o in OCC if o[0] == k)
        ax.plot([e, e], [Y[row] + H / 2, Y["M2"] - H / 2], color="#777777",
                lw=0.6, ls=":", alpha=0.8)
    return a_m, a_c


def draw_aor(ax, L):
    a_m, a_c = _frame(ax, L, faded_layer="corridor")
    ax.set_title(L["title_aor"], fontsize=9.5, pad=6)

    for k, row, s, e, v, role in OCC:
        if role == "done":
            _bar(ax, s, e, Y[row], C_DONE, alpha=a_c, hatch="////", text=v, tc="#444444")
        else:
            _bar(ax, s, e, Y[row], "#5a7a9a", alpha=a_c, text=v)

    for row, s, e, _ in OPS:
        ax.text(e - 0.05, Y[row] + H / 2 + 0.05, L["check"], fontsize=8.5,
                color=C_GREEN, ha="right", va="bottom", fontweight="bold")

    x, y = _center("v1e")
    ax.text(x + 0.5, y, "×", fontsize=17, color=C_RED, ha="center", va="center",
            fontweight="bold")
    ax.annotate(L["conflict"], xy=(x + 0.9, y - 0.3), xytext=(11.2, 5.5),
                fontsize=6.8, color=C_RED, ha="left", va="center",
                arrowprops=dict(arrowstyle="->", color=C_RED, lw=0.8))

    ax.text(10, 1.05, L["aor_seed"], ha="center", fontsize=8, color="#8b1e1e",
            fontweight="bold")
    ax.text(10, 0.1, L["aor_verdict"], ha="center", fontsize=7.6, color="#8b1e1e")


def draw_strc(ax, L):
    a_m, a_c = _frame(ax, L, faded_layer="machine", ymin=YMIN_STRC, block_label=False)
    ax.set_title(L["title_strc"], fontsize=9.5, pad=6)

    for k, row, s, e, v, role in OCC:
        if role == "seed":
            _bar(ax, s, e, Y[row], C_SEED, text=v + " " + L["seed"])
        elif role == "in":
            _bar(ax, s, e, Y[row], C_IN, text=v)
        elif role == "out":
            _bar(ax, s, e, Y[row], C_OUT, text=v)
        else:
            _bar(ax, s, e, Y[row], C_DONE, hatch="////", text=v, tc="#444444")

    def arrow(a, b, ls, rad, color="#c45c26"):
        (x1, y1), (x2, y2) = _center(a), _center(b)
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2), connectionstyle="arc3,rad=%s" % rad,
            arrowstyle="-|>", mutation_scale=8, color=color, lw=1.2,
            linestyle=ls, shrinkA=7, shrinkB=7, zorder=5))

    arrow("v1e", "v2e", "-", -0.55)          # yield on e*
    arrow("v1e", "v1f", "--", 0.0)           # same vehicle V1
    arrow("v2e", "v2f", "--", 0.0)           # same vehicle V2
    arrow("v1f", "v2f", ":", 0.3)            # same machine M2: O12 -> O22

    def tag(x, y, s, ha="center"):
        ax.text(x, y, s, fontsize=6.4, color=C_SEED, ha=ha, va="center",
                fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))

    tag(10.25, Y["e*"] + 0.62, L["tag_yield"], ha="left")
    tag(8.5, Y["e2"] + 0.38, L["tag_vehicle"], ha="right")
    tag(12.8, Y["e*"] - 0.38, L["tag_vehicle"], ha="left")
    tag(11.0, Y["e2"] - 0.62, L["tag_machine"], ha="right")

    ax.add_patch(FancyBboxPatch(
        (5.75, Y["e2"] - 0.6), 10.6, Y["e*"] - Y["e2"] + 1.53,
        boxstyle="round,pad=0.0,rounding_size=0.3", facecolor="none",
        edgecolor=C_IN, linewidth=1.1, linestyle=(0, (5, 2.5)), zorder=4))
    ax.text(16.5, Y["e*"] + 0.55, L["impact_set"], fontsize=7.2, color=C_IN,
            ha="left", va="center", fontweight="bold")
    ax.text(16.15, Y["e3"], L["keep"], fontsize=6.6, color="#555555",
            ha="left", va="center")
    ax.text(2.3, Y["e3"] + 0.4, L["done"], fontsize=6.4, color="#555555",
            ha="center", va="bottom")

    handles = [
        Line2D([0], [0], color=C_SEED, lw=1.2, ls="-"),
        Line2D([0], [0], color=C_SEED, lw=1.2, ls="--"),
        Line2D([0], [0], color=C_SEED, lw=1.2, ls=":"),
        Patch(facecolor="none", edgecolor="#8b1e1e", hatch="////"),
        Patch(facecolor=C_SEED, edgecolor="#222222"),
        Patch(facecolor=C_IN, edgecolor="#222222"),
        Patch(facecolor=C_OUT, edgecolor="#222222"),
        Patch(facecolor=C_DONE, edgecolor="#222222", hatch="////"),
    ]
    labels = [L["lg_yield"], L["lg_vehicle"], L["lg_job_machine"], L["lg_block"],
              L["lg_seed"], L["lg_in"], L["lg_out"], L["lg_done"]]
    ax.legend(handles, labels, loc="upper center",
              bbox_to_anchor=(0.5, (1.75 - YMIN_STRC) / (9.6 - YMIN_STRC)), ncol=2,
              fontsize=6.4, frameon=False, handlelength=2.4, columnspacing=1.6,
              labelspacing=0.55)


def draw_notes(fig, L):
    fig.text(0.5, 0.005, L["notes"], ha="center", va="bottom", fontsize=6.6,
             color="#333333", linespacing=1.5)
