import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.ticker import FixedLocator

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['mathtext.fontset'] = 'stix'

fig, axes = plt.subplots(1, 3, figsize=(13, 5))
fig.subplots_adjust(wspace=0.42)

C_BASELINE = '#D9534F'
C_NOSR     = '#5B9BD5'
C_UNCHANGED= '#70AD47'
C_CHANGED  = '#5B9BD5'

# ══════════════════════════════════════════════════════════
# 子图 (a)：双 Y 轴 — Makespan（左）& On-Time Rate（右）
# ══════════════════════════════════════════════════════════
ax1 = axes[0]
ax1_r = ax1.twinx()   # 右轴：On-Time Rate

labels   = ['Baseline', 'NOSR']
makespan = [508.3, 485.9]
ontime   = [78.6,  87.4]
x        = np.arange(len(labels))
width    = 0.32

# 左轴：Makespan
bars_m = ax1.bar(x - width/2, makespan, width,
                 color=[C_BASELINE, C_NOSR],
                 edgecolor='white', linewidth=1.2, zorder=3,
                 label='Makespan (min)')
for bar, val in zip(bars_m, makespan):
    ax1.text(bar.get_x() + bar.get_width()/2, val + 2,
             f'{val}', ha='center', va='bottom',
             fontsize=9, fontweight='bold',
             color=bar.get_facecolor())

# 右轴：On-Time Rate
bars_o = ax1_r.bar(x + width/2, ontime, width,
                   color=[C_BASELINE, C_NOSR],
                   edgecolor='white', linewidth=1.2,
                   alpha=0.55, zorder=3,
                   label='On-Time Rate (%)')
for bar, val, base in zip(bars_o, ontime, [78.6, 87.4]):
    delta = val - 78.6 if val != 78.6 else 0
    label = f'{val}%' if delta == 0 else f'{val}%\n(+{delta:.1f} pp)'
    ax1_r.text(bar.get_x() + bar.get_width()/2, val + 0.5,
               label, ha='center', va='bottom',
               fontsize=8.5, fontweight='bold',
               color=bar.get_facecolor())

ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=10.5)
ax1.set_ylim(450, 540)
ax1.set_ylabel('Makespan (min)', fontsize=10, color='black')
ax1_r.set_ylim(60, 100)
ax1_r.set_ylabel('On-Time Rate (%)', fontsize=10, color='black')
ax1.set_title('(a) Makespan & On-Time Rate', fontsize=10.5,
              fontweight='bold', pad=8)
ax1.yaxis.grid(True, linestyle='--', alpha=0.4, zorder=0)
ax1.set_axisbelow(True)
ax1.spines[['top']].set_visible(False)
ax1_r.spines[['top']].set_visible(False)

# 手动图例
patch_m = mpatches.Patch(color='gray',       label='Makespan (left axis)')
patch_o = mpatches.Patch(color='gray', alpha=0.5, label='On-Time Rate (right axis)')
ax1.legend(handles=[patch_m, patch_o], fontsize=8, framealpha=0.9,
           loc='lower right')

# ══════════════════════════════════════════════════════════
# 子图 (b)：任务状态堆叠条形图（两段：Unchanged / Rescheduled）
# ══════════════════════════════════════════════════════════
ax2 = axes[1]

total = 320
data = {
    'Baseline': {'Unchanged':  48, 'Rescheduled': 272},   # 合并 Late 入 Rescheduled
    'NOSR':     {'Unchanged': 231, 'Rescheduled':  89},
}
categories  = ['Baseline', 'NOSR']
unchanged   = [data[c]['Unchanged']   for c in categories]
rescheduled = [data[c]['Rescheduled'] for c in categories]

x2 = np.arange(len(categories))
w2 = 0.45

b1 = ax2.bar(x2, unchanged,   w2, label='Unchanged',
             color=C_UNCHANGED, zorder=3)
b2 = ax2.bar(x2, rescheduled, w2, bottom=unchanged,
             label='Rescheduled', color=C_CHANGED, zorder=3)

for i, cat in enumerate(categories):
    u = data[cat]['Unchanged']
    r = data[cat]['Rescheduled']
    ax2.text(i, u/2, f"{u/total*100:.0f}%",
             ha='center', va='center',
             fontsize=9, fontweight='bold', color='white')
    ax2.text(i, u + r/2, f"{r/total*100:.0f}%",
             ha='center', va='center',
             fontsize=9, fontweight='bold', color='white')

ax2.set_xticks(x2)
ax2.set_xticklabels(categories, fontsize=10.5)
ax2.set_ylabel('Number of Tasks (per day)', fontsize=10)
ax2.set_ylim(0, 360)
ax2.set_title('(b) Task Status Distribution', fontsize=10.5,
              fontweight='bold', pad=8)
ax2.legend(fontsize=9, framealpha=0.9, loc='upper right')
ax2.yaxis.grid(True, linestyle='--', alpha=0.5, zorder=0)
ax2.set_axisbelow(True)
ax2.spines[['top', 'right']].set_visible(False)

# ══════════════════════════════════════════════════════════
# 子图 (c)：响应时间对比（对数轴）— 只标数值，不标单事件 speedup
# ══════════════════════════════════════════════════════════
ax3 = axes[2]

disturbances = [
    {'label': 'D1: AGV Battery\nDepletion (t=120)',  'base': 18.1, 'nosr': 0.11},
    {'label': 'D2: Robot Arm\nFailure (t=280)',      'base': 16.8, 'nosr': 0.13},
    {'label': 'D3: Urgent Order\nInsertion (t=410)', 'base': 17.0, 'nosr': 0.12},
]

x3    = np.arange(len(disturbances))
width = 0.32

base_vals = [d['base'] for d in disturbances]
nosr_vals = [d['nosr'] for d in disturbances]

bars_b = ax3.bar(x3 - width/2, base_vals, width,
                 label='Baseline (Manual)', color=C_BASELINE,
                 edgecolor='white', linewidth=1.2, zorder=3)
bars_n = ax3.bar(x3 + width/2, nosr_vals, width,
                 label='NOSR (Automated)', color=C_NOSR,
                 edgecolor='white', linewidth=1.2, zorder=3)

ax3.set_yscale('log')
ax3.set_ylim(0.05, 60)

# 只标响应时间数值，不标各事件 speedup（避免与表格 144× 不一致）
for bar, val in zip(bars_b, base_vals):
    ax3.text(bar.get_x() + bar.get_width()/2, val * 1.15,
             f'{val:.1f}', ha='center', va='bottom',
             fontsize=8.5, fontweight='bold', color=C_BASELINE)

for bar, val in zip(bars_n, nosr_vals):
    ax3.text(bar.get_x() + bar.get_width()/2, val * 1.15,
             f'{val:.2f}', ha='center', va='bottom',
             fontsize=8.5, fontweight='bold', color=C_NOSR)

# 平均 speedup 标注在图内右上角
ax3.text(0.97, 0.97, 'Avg. speedup: 144×',
         transform=ax3.transAxes, ha='right', va='top',
         fontsize=9, color=C_NOSR, fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                   edgecolor=C_NOSR, alpha=0.8))

# 实时阈值参考线（1 min）
ax3.axhline(y=1.0, color='gray', linestyle='--',
            linewidth=1.2, alpha=0.7, zorder=2)
ax3.text(2.55, 1.0 * 1.1, 'Real-time\nthreshold (1 min)',
         ha='right', va='bottom', fontsize=7.5,
         color='gray', style='italic')

ax3.set_xticks(x3)
ax3.set_xticklabels([d['label'] for d in disturbances],
                    fontsize=8.2, linespacing=1.3)
ax3.set_ylabel('Response Time (min, log scale)', fontsize=10)
ax3.set_title('(c) Response Time per Disturbance Event',
              fontsize=10.5, fontweight='bold', pad=8)
ax3.legend(fontsize=9, framealpha=0.9, loc='upper right')
ax3.yaxis.grid(True, linestyle='--', alpha=0.4, zorder=0)
ax3.set_axisbelow(True)
ax3.spines[['top', 'right']].set_visible(False)

ax3.yaxis.set_major_locator(FixedLocator([0.1, 0.5, 1, 5, 10, 20]))
ax3.yaxis.set_major_formatter(
    plt.FuncFormatter(lambda val, _: f'{val:g}'))

# ══════════════════════════════════════════════════════════
fig.suptitle(
    'Real-World Case Study: Automotive Assembly Line (4-Week Deployment)',
    fontsize=12, fontweight='bold', y=1.01
)

plt.savefig('fig_case_study_new.pdf', dpi=300, bbox_inches='tight')
print("✓ Saved fig_case_study.pdf / .png")
plt.show()