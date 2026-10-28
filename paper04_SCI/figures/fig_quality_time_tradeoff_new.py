import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

# ── Global style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family':        'DejaVu Sans',
    'font.size':          10,
    'mathtext.fontset':   'stix',
    'axes.spines.top':    False,
    'axes.spines.right':  False,
})

fig = plt.figure(figsize=(13, 5.5))
gs  = gridspec.GridSpec(1, 2, width_ratios=[1.15, 0.85], wspace=0.38)
ax1 = fig.add_subplot(gs[0])   # (a) quality–time scatter
ax2 = fig.add_subplot(gs[1])   # (b) stability bar chart

# ══════════════════════════════════════════════════════════════════════════════
#  DATA  –  SM domain only, directly from Table 1
# ══════════════════════════════════════════════════════════════════════════════
methods_ordered = [
    # name,              gap,   time,  phi,   color,       marker, ms,  group
    ('Global-MIP',       0.0,   45.3,  12.4,  '#d62728',   'X',   180, 'global'),
    ('Global-GA',        3.5,   18.7,  15.6,  '#ff7f0e',   'D',   100, 'global'),
    ('Rolling-Horizon',  9.4,   12.3,  58.3,  '#9467bd',   's',   100, 'window'),
    ('DRL-PPO',          6.2,    0.3,  71.4,  '#17becf',   '^',   110, 'learned'),
    ('Reactive-EDF',    20.5,    0.8,  76.2,  '#8c564b',   '^',   100, 'reactive'),
    ('Reactive-SPT',    23.1,    0.6,  78.5,  '#7f7f7f',   'v',   100, 'reactive'),
    ('Right-Shift',     29.9,    0.1,  94.3,  '#bcbd22',   'P',   100, 'reactive'),
    ('NOSR (Ours)',       2.0,    5.1,  82.7,  '#2ca02c',   '*',   320, 'nosr'),
]

names  = [m[0] for m in methods_ordered]
gaps   = [m[1] for m in methods_ordered]
times  = [m[2] for m in methods_ordered]
phis   = [m[3] for m in methods_ordered]
colors = [m[4] for m in methods_ordered]
marks  = [m[5] for m in methods_ordered]
sizes  = [m[6] for m in methods_ordered]

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL (a): Quality–Time scatter
# ══════════════════════════════════════════════════════════════════════════════

# ── real-time budget shading ──────────────────────────────────────────────────
ax1.axvspan(0.05, 10, alpha=0.07, color='#2ca02c', zorder=0)
ax1.axvline(10, color='#2ca02c', lw=1.2, ls='--', alpha=0.55, zorder=1)
ax1.text(10.4, 31.5, r'$\tau_{\max}=10\,$s', fontsize=8.5,
         color='#2ca02c', va='top')

# ── Pareto frontier: Right-Shift → NOSR → Global-MIP ─────────────────────────
pareto = [(0.1, 29.9), (5.1, 2.0), (45.3, 0.0)]
px, py = zip(*pareto)
ax1.plot(px, py, ls='--', lw=1.8, color='#1f77b4', alpha=0.45,
         label='Pareto frontier', zorder=2)

# ── scatter points ────────────────────────────────────────────────────────────
for i, (name, gap, time, phi, color, marker, ms, grp) in enumerate(methods_ordered):
    timeout = (name == 'Global-MIP')
    zord = 6 if grp == 'nosr' else 5
    unfilled_markers = {'x', '+', '|', '_', '1', '2', '3', '4'}

    # avoid passing edgecolors for markers that are rendered as unfilled
    # (Matplotlib warns when edgecolors is set for unfilled markers)
    ec = 'black' if marker not in unfilled_markers else None
    lw = 2.0 if grp == 'nosr' else 1.2

    ax1.scatter(time, gap, c=color, marker=marker, s=ms,
                edgecolors=ec,
                linewidths=lw,
                alpha=1.0, zorder=zord, label=name)
    if timeout:
        ax1.annotate('32.8%\ntimeout', xy=(time, gap),
                     xytext=(6, 8), textcoords='offset points',
                     fontsize=7.5, color='#d62728', fontweight='bold',
                     arrowprops=dict(arrowstyle='->', color='#d62728',
                                     lw=1.2, shrinkB=4))

# ── NOSR label (only NOSR gets an explicit callout) ───────────────────────────
ax1.annotate('NOSR\n2.0%, 5.1 s',
             xy=(5.1, 2.0), xytext=(18, 22),
             textcoords='offset points', fontsize=9,
             color='#2ca02c', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#2ca02c',
                             lw=1.5, shrinkB=5),
             bbox=dict(boxstyle='round,pad=0.3', fc='#f0fff0',
                       ec='#2ca02c', lw=1.2))

# ── method-group annotations (compact, no clutter) ───────────────────────────
# Just label cluster regions, not every point
ax1.text(0.22, 26.5, 'Reactive\nheuristics', fontsize=8, color='#555',
         ha='center', style='italic')
ax1.text(13,   9.4,  'Rolling-\nHorizon',    fontsize=8, color='#9467bd',
         ha='center', style='italic')
ax1.text(30,   3.5,  'Global-GA',            fontsize=8, color='#ff7f0e',
         ha='left',   style='italic')
ax1.text(0.22,  6.2, 'DRL-PPO',              fontsize=8, color='#17becf',
         ha='center', style='italic')

# ── axes ─────────────────────────────────────────────────────────────────────
ax1.set_xscale('log')
ax1.set_xlim(0.07, 120)
ax1.set_ylim(-1.5, 35)
ax1.set_xticks([0.1, 1, 10, 100])
ax1.set_xticklabels(['0.1', '1', '10', '100'])
ax1.set_yticks([0, 5, 10, 15, 20, 25, 30])
ax1.set_xlabel('Computation time  $\\mathcal{C}$ (s, log scale)',
               fontsize=10.5, fontweight='bold')
ax1.set_ylabel('Gap to optimal (%)', fontsize=10.5, fontweight='bold')
ax1.set_title('(a)  Quality–Time Trade-off', fontsize=11, fontweight='bold',
              pad=8)
ax1.grid(True, which='both', ls=':', lw=0.5, alpha=0.4)

# ── compact legend (symbols only) ────────────────────────────────────────────
handles = []
for name, gap, time, phi, color, marker, ms, grp in methods_ordered:
    h = plt.Line2D([0], [0], marker=marker, color='w',
                   markerfacecolor=color, markersize=8 if grp != 'nosr' else 11,
                   markeredgecolor='black', markeredgewidth=0.8,
                   label=name)
    handles.append(h)
handles.append(
    plt.Line2D([0], [0], ls='--', lw=1.8, color='#1f77b4',
               alpha=0.6, label='Pareto frontier'))
ax1.legend(handles=handles, fontsize=7.8, loc='upper left',
           framealpha=0.92, edgecolor='#ccc',
           title='Method', title_fontsize=8.5,
           ncol=1, handlelength=1.4)

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL (b): Schedule Stability Φ  (horizontal bar chart)
# ══════════════════════════════════════════════════════════════════════════════

# Sort by Φ ascending for readability
order = sorted(range(len(names)), key=lambda i: phis[i])
names_s  = [names[i]  for i in order]
phis_s   = [phis[i]   for i in order]
gaps_s   = [gaps[i]   for i in order]
colors_s = [colors[i] for i in order]

y_pos = np.arange(len(names_s))
bars  = ax2.barh(y_pos, phis_s, height=0.62,
                 color=colors_s, edgecolor='white', linewidth=0.8,
                 alpha=0.88)

# ── gap annotation on each bar ────────────────────────────────────────────────
for i, (bar, phi, gap) in enumerate(zip(bars, phis_s, gaps_s)):
    # stability value at bar end
    ax2.text(phi + 0.8, i, f'{phi:.1f}%',
             va='center', ha='left', fontsize=8.2,
             color=colors_s[i], fontweight='bold')
    # gap value inside bar (right-aligned)
    label = f'gap {gap:.1f}%'
    ax2.text(max(phi - 1, 2), i, label,
             va='center', ha='right', fontsize=7.5, color='white',
             fontweight='bold')

# ── highlight NOSR bar ────────────────────────────────────────────────────────
nosr_idx = names_s.index('NOSR (Ours)')
bars[nosr_idx].set_edgecolor('#1a6e1a')
bars[nosr_idx].set_linewidth(2.2)

# ── real-time budget line (τ_max shading doesn't apply here;
#    instead mark the "stability–quality sweet spot") ─────────────────────────
ax2.axvline(82.7, color='#2ca02c', lw=1.4, ls='--', alpha=0.6)
ax2.text(83.5, -0.7, 'NOSR\n82.7%', fontsize=7.8, color='#2ca02c',
         va='top', fontweight='bold')

# ── axes ─────────────────────────────────────────────────────────────────────
ax2.set_yticks(y_pos)
ax2.set_yticklabels(names_s, fontsize=9)
ax2.set_xlim(0, 105)
ax2.set_xticks([0, 20, 40, 60, 80, 100])
ax2.set_xticklabels(['0%', '20%', '40%', '60%', '80%', '100%'])
ax2.set_xlabel('Schedule stability  $\\Phi$ (% tasks unchanged)',
               fontsize=10.5, fontweight='bold')
ax2.set_title('(b)  Schedule Stability', fontsize=11, fontweight='bold', pad=8)
ax2.grid(True, axis='x', ls=':', lw=0.5, alpha=0.4)

# ── annotation: Right-Shift high Φ but poor quality ──────────────────────────
rs_idx = names_s.index('Right-Shift')
ax2.annotate('High stability,\nbut 29.9% gap',
             xy=(phis_s[rs_idx], rs_idx),
             xytext=(-30, -18), textcoords='offset points',
             fontsize=7.5, color='#888',
             arrowprops=dict(arrowstyle='->', color='#aaa', lw=1.0))

# ══════════════════════════════════════════════════════════════════════════════
#  Figure-level title
# ══════════════════════════════════════════════════════════════════════════════
fig.suptitle(
    'NOSR vs. Baselines — Smart Manufacturing Domain  '
    '(50 instances, $n=150$–$300$ tasks)',
    fontsize=12, fontweight='bold', y=1.01)

plt.tight_layout()
plt.savefig('fig_quality_time_tradeoff_new.pdf', dpi=300, bbox_inches='tight')
print("✓ Saved fig_quality_time_tradeoff.pdf / .png")
plt.show()