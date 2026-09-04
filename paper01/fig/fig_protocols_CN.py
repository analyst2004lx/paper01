# -*- coding: utf-8 -*-
"""两种预算口径对照中文版。数据与 fig_protocols.py 相同，输出 fig_protocols_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _style as S  # noqa: E402

S.use_cjk()

df = S.load("protocols.csv")
m = S.meta_protocols()

order = ["twostage", "nofeedback", "opendispatch", "nostagger"]
order = [b for b in order if b in set(df["baseline"])]

ROW_LABEL = {
    "twostage": "闭环整体",
    "nofeedback": "两条决策层机制",
    "opendispatch": "预约表感知派遣",
    "nostagger": "错峰算子",
}

PROTO = [
    ("wallclock", "同挂钟时间", "#08519c", "o"),
    ("generations", "同代数", "#d95f02", "s"),
]

fig, ax = S.plt.subplots(figsize=(S.COL * 1.55, 1.05 + 0.44 * len(order)))

for row, base in enumerate(order):
    y = len(order) - 1 - row
    ax.axhspan(y - 0.5, y + 0.5, color="#f2f2f2" if row % 2 else "none", lw=0)
    for k, (proto, label, color, marker) in enumerate(PROTO):
        sub = df[(df["baseline"] == base) & (df["protocol"] == proto)]
        if sub.empty:
            continue
        r = sub.iloc[0]
        off = 0.17 * (1 if k == 0 else -1)
        gain = float(r["rel_gain"])
        ax.plot([gain], [y + off], marker=marker, color=color, ms=5.2,
                ls="none", label=label if row == 0 else None, zorder=3)
        ax.plot([0, gain], [y + off, y + off], color=color, lw=1.1,
                alpha=0.55, zorder=2)
        txt = "%+.1f%%%s" % (100 * gain, S.stars(r["p_value"]))
        ax.annotate(txt, (gain, y + off), textcoords="offset points",
                    xytext=(7 if gain >= 0 else -7, 0), fontsize=7,
                    ha="left" if gain >= 0 else "right", va="center",
                    color=color)

ax.axvline(0.0, color="0.25", lw=0.9, zorder=1)
ax.set_yticks(range(len(order)))
ax.set_yticklabels([ROW_LABEL.get(b, S.BASELINE_LABEL.get(b, b))
                    for b in reversed(order)], fontsize=7)
ax.set_ylim(-0.6, len(order) - 0.4)
ax.set_xlabel(r"$C_{\max}$ 相对变化（正值 $=$ 完整闭环更好）")
ax.xaxis.set_major_locator(S.mticker.MultipleLocator(0.05))
ax.xaxis.set_minor_locator(S.mticker.MultipleLocator(0.025))
ax.xaxis.set_major_formatter(
    S.mticker.FuncFormatter(lambda v, _p: "%+.0f%%" % (100 * v)))
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right", ncol=1)

lo, hi = ax.get_xlim()
ax.set_xlim(lo - 0.02, hi + 0.03)

fig.text(0.0, -0.02,
         "%d 个算例，%d 个种子，配对 Wilcoxon；* $p<0.05$，** $p<0.01$，"
         "*** $p<0.001$。该批次测于第 4.5 节降本之前。"
         % (len(m.get("instances", [])), m.get("num_seeds", 0)),
         fontsize=S.FS_FOOT, color="0.35")
fig.subplots_adjust(bottom=0.26)
S.save(fig, "fig_protocols_CN")
