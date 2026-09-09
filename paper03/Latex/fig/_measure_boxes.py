# Temporary overflow check; delete after use.
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def measure_attack_tree() -> None:
    fig, ax = plt.subplots(figsize=(9.6, 7.6), dpi=200)
    ax.set_xlim(-0.15, 14.7)
    ax.set_ylim(-0.45, 11.0)
    ax.axis("off")
    items = []

    def rbox(cx, cy, w, h, text, fs=7.6):
        t = ax.text(cx, cy, text, ha="center", va="center",
                    fontsize=fs, linespacing=1.2)
        items.append((cx - w / 2, cy - h / 2, w, h, text, t))

    def diamond(cx, cy, w, h, text, fs=7.2):
        t = ax.text(cx, cy, text, ha="center", va="center",
                    fontsize=fs, linespacing=1.15)
        items.append((cx - w / 2, cy - h / 2, w, h, text, t))

    rbox(7.2, 10.15, 4.3, 1.05,
         "Hijacked device\nwants false ``done / idle''", 8.0)
    diamond(7.2, 8.35, 2.7, 1.35, "Send\ncompletion?")
    rbox(1.15, 6.35, 2.15, 1.15,
         r"Silence:" + "\n" + r"missing $h_k$" + "\n" + r"($\sim$1.8 s)", 6.8)
    rbox(3.65, 6.35, 2.15, 0.85, r"$\mathbf{P2}$ silence")
    diamond(9.55, 6.45, 2.6, 1.3, "Keep\nheartbeat?")
    rbox(3.45, 4.25, 2.2, 0.95, "Both:\nsilence faster", 7.2)
    rbox(6.05, 4.25, 2.25, 0.95, r"$\mathbf{P1}$ lie," + "\nno heartbeat")
    rbox(10.75, 4.25, 2.25, 0.95, r"$\mathbf{P3}$ lie +" + "\n" + r"reveal $h_k$")
    rbox(13.35, 4.25, 2.15, 0.95, "Corr. only\n(silence DR${=}0$)", 6.6)
    diamond(9.55, 2.15, 2.75, 1.3, "Collude with\ncounterpart?")
    rbox(9.35, 0.45, 2.7, 0.8, r"$\mathbf{P4}$ one-hop collusion")
    rbox(12.45, 0.45, 2.25, 0.95, "Next-hop\nhonest refute", 7.2)

    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    print("=== attack_tree ===")
    for x, y, w, h, text, t in items:
        bb = t.get_window_extent(rend)
        x0, y0 = inv.transform((bb.x0, bb.y0))
        x1, y1 = inv.transform((bb.x1, bb.y1))
        pl, pr = x0 - x, (x + w) - x1
        pb, pt = y0 - y, (y + h) - y1
        flag = "ok"
        if min(pl, pr) < 0.08 or min(pb, pt) < 0.06:
            flag = "TIGHT"
        if min(pl, pr, pb, pt) < 0:
            flag = "OVERFLOW"
        one = text.replace("\n", " | ")
        print("%-9s L=%+.3f R=%+.3f B=%+.3f T=%+.3f  %s" % (
            flag, pl, pr, pb, pt, one))
    plt.close(fig)


def measure_arch() -> None:
    fig, ax = plt.subplots(figsize=(8.6, 3.55), dpi=200)
    ax.set_xlim(-0.25, 13.3)
    ax.set_ylim(-0.85, 4.15)
    ax.axis("off")
    items = []
    w, h = 2.15, 0.95
    xs = [0.35 + i * (w + 0.28) for i in range(5)]
    labs = [
        "M1 ingest",
        r"M2 taskgraph" + "\n" + r"$G\!\to\!H$",
        "M5 coverage",
        "M6 collusion",
        r"M7 budget" + "\n" + r"$(r,T_{hb})$",
    ]
    for x, lab in zip(xs, labs):
        t = ax.text(x + w / 2, 2.35 + h / 2, lab, ha="center", va="center",
                    fontsize=7.8, linespacing=1.2)
        items.append((x, 2.35, w, h, lab, t))
    w2 = 2.35
    xs2 = [0.35, 3.55, 6.75, 9.95]
    labs2 = [
        r"cmd $u$" + "\nopens pending",
        r"M3 corroborate" + "\n" + r"$W(a)$",
        r"M4 silence" + "\n" + r"preimage $h_k$",
        "freeze\ndispatch",
    ]
    for x, lab in zip(xs2, labs2):
        t = ax.text(x + w2 / 2, 0.15 + 0.525, lab, ha="center", va="center",
                    fontsize=7.8, linespacing=1.2)
        items.append((x, 0.15, w2, 1.05, lab, t))
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    print("=== architecture ===")
    for x, y, ww, hh, text, t in items:
        bb = t.get_window_extent(rend)
        x0, y0 = inv.transform((bb.x0, bb.y0))
        x1, y1 = inv.transform((bb.x1, bb.y1))
        pl, pr = x0 - x, (x + ww) - x1
        pb, pt = y0 - y, (y + hh) - y1
        flag = "ok"
        if min(pl, pr) < 0.10 or min(pb, pt) < 0.08:
            flag = "TIGHT"
        if min(pl, pr, pb, pt) < 0:
            flag = "OVERFLOW"
        one = text.replace("\n", " | ")
        print("%-9s L=%+.3f R=%+.3f B=%+.3f T=%+.3f  %s" % (
            flag, pl, pr, pb, pt, one))
    plt.close(fig)


if __name__ == "__main__":
    measure_attack_tree()
    measure_arch()
