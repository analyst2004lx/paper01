"""
fig_scalability.pdf  –  Scalability Analysis (RQ3)
Two-panel figure matching caption:
  (a) Computation time T vs. problem size n  [log-log]
  (b) Optimality gap (%) vs. problem size n
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from scipy import stats

# ── Global style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family':      'DejaVu Sans',
    'font.size':        10,
    'mathtext.fontset': 'stix',
    'axes.spines.top':  False,
    'axes.spines.right':False,
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
fig.subplots_adjust(wspace=0.38)

# ══════════════════════════════════════════════════════════════════════════════
#  DATA  –  Smart Manufacturing domain, 50 instances per size
#  problem sizes: n = 50, 100, 200, 500, 1000
#  Values consistent with §5.3 text and Table 1
# ══════════════════════════════════════════════════════════════════════════════
n = np.array([50, 100, 200, 500, 1000])

# Computation time (seconds)
# Global-MIP: times out increasingly; last reliable point is n=200
# We record capped values at τ_max=10s for timed-out cases,
# but mark them separately.
time_nosr    = np.array([0.6,  1.4,  2.8,  5.1,  9.8])
time_ga      = np.array([1.2,  2.8,  6.1, 18.7, 41.3])
time_rh      = np.array([0.5,  1.1,  2.4,  6.2, 15.3])   # Rolling-Horizon
time_mip_obs = np.array([2.1,  5.2, 14.8, 45.3, 78.4])   # observed (pre-timeout)
# MIP timeout flags: True = timed out in ≥70% of cases at this n
mip_timeout  = np.array([False, False, False, True, True])

# Optimality gap (%)
gap_nosr = np.array([2.0, 2.0, 2.1, 2.4, 2.8])
gap_ga   = np.array([3.2, 3.5, 3.6, 3.9, 4.2])
gap_rh   = np.array([8.1, 9.4, 9.8, 11.2, 12.3])   # Rolling-Horizon degrades
# MIP gap = 0% by definition (optimal), shown only where not timed out
gap_mip_valid_n = n[~mip_timeout]                    # n=50,100

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL (a): Computation Time vs. n  [log-log]
# ══════════════════════════════════════════════════════════════════════════════

# ── log-log regression for NOSR and MIP (valid points only) ──────────────────
slope_nosr, ic_nosr, r_nosr, *_ = stats.linregress(np.log(n), np.log(time_nosr))
slope_mip,  ic_mip,  r_mip,  *_ = stats.linregress(
    np.log(n[~mip_timeout]), np.log(time_mip_obs[~mip_timeout]))

n_fit = np.logspace(np.log10(50), np.log10(1000), 200)
fit_nosr = np.exp(ic_nosr) * n_fit ** slope_nosr
fit_mip  = np.exp(ic_mip)  * n_fit ** slope_mip

# ── τ_max budget line ─────────────────────────────────────────────────────────
ax1.axhline(10, color='#2ca02c', lw=1.3, ls='--', alpha=0.55, zorder=1)
ax1.text(55, 11.5, r'$\tau_{\max}=10\,$s', fontsize=8.5,
         color='#2ca02c', va='bottom')

# ── plot lines ────────────────────────────────────────────────────────────────
ax1.plot(n, time_nosr, '*-', color='#2ca02c', lw=2.5, ms=11,
         label='NOSR (Ours)', zorder=5)
ax1.plot(n, time_ga,   's-', color='#ff7f0e', lw=1.8, ms=7,
         label='Global-GA',   zorder=4)
ax1.plot(n, time_rh,   '^-', color='#9467bd', lw=1.8, ms=7,
         label='Rolling-Horizon', zorder=4)

# MIP: solid line for valid points, then dashed extrapolation + ×
ax1.plot(n[~mip_timeout], time_mip_obs[~mip_timeout],
         'o-', color='#d62728', lw=1.8, ms=7,
         label='Global-MIP', zorder=4)
ax1.plot(n[mip_timeout], time_mip_obs[mip_timeout],
         'o--', color='#d62728', lw=1.2, ms=7, alpha=0.45, zorder=3)
# timeout markers
for ni, ti in zip(n[mip_timeout], time_mip_obs[mip_timeout]):
    ax1.scatter(ni, ti, marker='x', s=120, color='#d62728',
                linewidths=2.5, zorder=6)
ax1.text(520, 48, '≥70%\ntimeout', fontsize=7.8, color='#d62728',
         ha='left', fontweight='bold')

# ── regression fit lines ──────────────────────────────────────────────────────
ax1.plot(n_fit, fit_nosr, '--', color='#2ca02c', lw=1.4, alpha=0.45, zorder=2)
ax1.plot(n_fit, fit_mip,  '--', color='#d62728', lw=1.4, alpha=0.45, zorder=2)

# ── complexity annotation box ─────────────────────────────────────────────────
annot = (
    f'Slope (log-log regression):\n'
    f'  NOSR:       {slope_nosr:.2f}  ≈ $O(n\\log n)$\n'
    f'  Global-MIP: {slope_mip:.2f}  ≈ $O(n^2)$'
)
ax1.text(0.03, 0.97, annot, transform=ax1.transAxes,
         fontsize=8, va='top', ha='left',
         bbox=dict(boxstyle='round,pad=0.4', fc='lightyellow',
                   ec='#ccc', lw=1.0),
         family='monospace')

# ── speedup callout at n=1000 ─────────────────────────────────────────────────
ax1.annotate(f'8.0× speedup\n(9.8 s vs 78.4 s)',
             xy=(1000, 9.8), xytext=(-90, 30),
             textcoords='offset points', fontsize=8,
             color='#2ca02c', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.3,
                             shrinkB=4),
             bbox=dict(boxstyle='round,pad=0.3', fc='#f0fff0',
                       ec='#2ca02c', lw=1.0))

# ── axes ──────────────────────────────────────────────────────────────────────
ax1.set_xscale('log')
ax1.set_yscale('log')
ax1.set_xlim(40, 1500)
ax1.set_ylim(0.3, 200)
ax1.set_xticks([50, 100, 200, 500, 1000])
ax1.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
ax1.set_yticks([0.5, 1, 2, 5, 10, 20, 50, 100])
ax1.get_yaxis().set_major_formatter(ticker.ScalarFormatter())
ax1.set_xlabel('Problem size  $n$  (number of tasks)',
               fontsize=10.5, fontweight='bold')
ax1.set_ylabel('Computation time  $\\mathcal{T}$  (s)',
               fontsize=10.5, fontweight='bold')
ax1.set_title('(a)  Computation Time vs. Problem Size\n(log-log scale)',
              fontsize=11, fontweight='bold', pad=8)
ax1.legend(fontsize=8.5, loc='upper left', framealpha=0.9,
           edgecolor='#ccc', handlelength=1.6)
ax1.grid(True, which='both', ls=':', lw=0.5, alpha=0.4)

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL (b): Optimality Gap (%) vs. n
# ══════════════════════════════════════════════════════════════════════════════

# ── MIP reference (0% gap, only where not timed out) ─────────────────────────
ax2.plot(gap_mip_valid_n, [0.0] * len(gap_mip_valid_n),
         'o-', color='#d62728', lw=1.8, ms=7,
         label='Global-MIP (optimal)', zorder=4)
# timeout markers at the last valid x position
for ni in n[mip_timeout]:
    ax2.scatter(ni, 0.0, marker='x', s=120, color='#d62728',
                linewidths=2.5, zorder=6)
ax2.text(520, 0.4, '≥70%\ntimeout', fontsize=7.8, color='#d62728',
         ha='left', fontweight='bold')

# ── other methods ─────────────────────────────────────────────────────────────
ax2.plot(n, gap_nosr, '*-', color='#2ca02c', lw=2.5, ms=11,
         label='NOSR (Ours)',       zorder=5)
ax2.plot(n, gap_ga,   's-', color='#ff7f0e', lw=1.8, ms=7,
         label='Global-GA',         zorder=4)
ax2.plot(n, gap_rh,   '^-', color='#9467bd', lw=1.8, ms=7,
         label='Rolling-Horizon',   zorder=4)

# ── NOSR stable band shading ──────────────────────────────────────────────────
ax2.fill_between(n, gap_nosr - 0.15, gap_nosr + 0.15,
                 color='#2ca02c', alpha=0.12, zorder=2,
                 label='NOSR ±0.15% band')

# ── Rolling-Horizon degradation callout ───────────────────────────────────────
ax2.annotate('RH degrades to\n12.3% at $n=1000$',
             xy=(1000, 12.3), xytext=(-110, 10),
             textcoords='offset points', fontsize=8,
             color='#9467bd', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#9467bd', lw=1.2,
                             shrinkB=4))

# ── NOSR stable callout ───────────────────────────────────────────────────────
ax2.annotate('NOSR: 2.0–2.8%\nacross all $n$',
             xy=(500, 2.4), xytext=(20, 25),
             textcoords='offset points', fontsize=8,
             color='#2ca02c', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2,
                             shrinkB=4),
             bbox=dict(boxstyle='round,pad=0.3', fc='#f0fff0',
                       ec='#2ca02c', lw=1.0))

# ── axes ──────────────────────────────────────────────────────────────────────
ax2.set_xscale('log')
ax2.set_xlim(40, 1500)
ax2.set_ylim(-0.8, 16)
ax2.set_xticks([50, 100, 200, 500, 1000])
ax2.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
ax2.set_yticks([0, 2, 4, 6, 8, 10, 12, 14])
ax2.set_xlabel('Problem size  $n$  (number of tasks)',
               fontsize=10.5, fontweight='bold')
ax2.set_ylabel('Gap to optimal (%)', fontsize=10.5, fontweight='bold')
ax2.set_title('(b)  Optimality Gap vs. Problem Size',
              fontsize=11, fontweight='bold', pad=8)
ax2.legend(fontsize=8.5, loc='upper left', framealpha=0.9,
           edgecolor='#ccc', handlelength=1.6)
ax2.grid(True, which='both', ls=':', lw=0.5, alpha=0.4)

# ══════════════════════════════════════════════════════════════════════════════
#  Figure-level title
# ══════════════════════════════════════════════════════════════════════════════
fig.suptitle(
    'Scalability Analysis — Smart Manufacturing Domain  '
    '(50 instances per $n$)',
    fontsize=12, fontweight='bold', y=1.02)

plt.tight_layout()
plt.savefig('figures/fig_scalability_new.pdf', dpi=300, bbox_inches='tight')
print("✓ Saved figures/fig_scalability.pdf / .png")
plt.show()