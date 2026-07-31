"""Figure: the reproducible negative result on pricing the interface.

All points share one wall-clock budget per instance, calibrated from the
theta=0 configuration, so the degradation cannot be explained by the priced
variant simply performing less search -- although it does, and the second axis
records by how much.
"""
from __future__ import annotations

import numpy as np

import _style as S


def main():
    df = S.load("theta_sweep.csv")
    insts = list(dict.fromkeys(df["instance"]))
    tag_of = {i: df[df["instance"] == i]["tag"].iloc[0] for i in insts}

    fig, ax = S.plt.subplots(figsize=(S.COL * 1.45, 2.2))
    ax2 = ax.twinx()
    ax2.grid(False)

    for inst in insts:
        sub = df[df["instance"] == inst]
        thetas = sorted(sub["theta"].unique())
        ref = sub[sub["theta"] == 0.0]["makespan"].mean()
        mus, errs = [], []
        for t in thetas:
            v = sub[sub["theta"] == t]["makespan"]
            # expressed relative to theta=0 so the two instances share an axis
            mus.append(100.0 * (v.mean() - ref) / ref)
            errs.append(100.0 * v.std(ddof=1) / np.sqrt(len(v)) / ref
                        if len(v) > 1 else 0.0)
        tag = tag_of[inst]
        ax.errorbar(thetas, mus, yerr=errs, marker="o" if tag == "high" else "s",
                    ms=4, elinewidth=0.8, capsize=2,
                    color=S.TAG_COLOR.get(tag, "0.3"),
                    label="%s congestion" % tag)

        cost = [sub[sub["theta"] == t]["ms_per_eval"].mean() for t in thetas]
        ax2.plot(thetas, cost, ls=":", lw=0.9, color=S.TAG_COLOR.get(tag, "0.3"),
                 alpha=0.55)

    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_xlabel(r"pricing strength $\theta$")
    ax.set_ylabel(r"$C_{\max}$ change vs $\theta=0$ (%)")
    ax2.set_ylabel("ms per evaluation (dotted)", fontsize=7.5, color="0.45")
    ax2.tick_params(axis="y", colors="0.45", labelsize=7)
    ax.legend(loc="upper left", handletextpad=0.5)
    ax.set_title("positive is worse; equal wall-clock budget throughout",
                 fontsize=6.8, color="0.3", pad=4)
    S.save(fig, "fig_theta")


if __name__ == "__main__":
    main()
