import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.gridspec as gridspec
import numpy as np

fig = plt.figure(figsize=(22, 7))
gs = gridspec.GridSpec(1, 4, figure=fig, wspace=0.35)

ax_a = fig.add_subplot(gs[0])   # 物理场景
ax_b = fig.add_subplot(gs[1])   # Decompose
ax_c = fig.add_subplot(gs[2])   # Coordinate
ax_d = fig.add_subplot(gs[3])   # Converge → 结果

for ax in [ax_a, ax_b, ax_c, ax_d]:
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

# ── 颜色方案 ──────────────────────────────────────────
C_CSS   = '#1565C0'   # 深蓝：CSS/AGV
C_DES   = '#E65100'   # 深橙：DES/RA
C_COORD = '#6A1B9A'   # 紫色：Coordinator
C_OK    = '#2E7D32'   # 绿色：成功/收敛
C_LIGHT_BLUE  = '#E3F2FD'
C_LIGHT_ORANGE = '#FFF3E0'
C_LIGHT_GREEN  = '#E8F5E9'
C_LIGHT_PURPLE = '#F3E5F5'

# ════════════════════════════════════════════════════
# (a) 物理场景
# ════════════════════════════════════════════════════
ax_a.set_title('(a) Physical Scenario\n(Initial State)', 
               fontsize=12, fontweight='bold', pad=8)

# 画障碍物
for (ox, oy) in [(4.5, 4.5), (4.5, 6.5)]:
    obs = FancyBboxPatch((ox-0.4, oy-0.4), 0.8, 0.8,
                          boxstyle="square,pad=0",
                          facecolor='#B0BEC5', edgecolor='#546E7A',
                          linewidth=1.5, zorder=3)
    ax_a.add_patch(obs)
    ax_a.text(ox, oy, '■', ha='center', va='center',
              fontsize=8, color='#546E7A', zorder=4)

# AGV（圆形）
agv_pos  = [(1.5, 2.0), (1.5, 5.5), (1.5, 8.5)]
agv_col  = [C_CSS, '#0288D1', '#0097A7']
agv_name = ['AGV1', 'AGV2', 'AGV3']
for i, ((x, y), col, name) in enumerate(zip(agv_pos, agv_col, agv_name)):
    c = plt.Circle((x, y), 0.5, color=col, zorder=5)
    ax_a.add_patch(c)
    ax_a.text(x, y, name, ha='center', va='center',
              color='white', fontweight='bold', fontsize=8, zorder=6)

# RA（矩形）
ra_pos   = [(8.0, 2.0), (8.0, 5.5), (8.0, 8.5)]
ra_col   = ['#EF5350', '#66BB6A', '#FFA726']
ra_name  = ['RA1\n(busy\n12s)', 'RA2\n(idle)', 'RA3\n(busy\n5s)']
for i, ((x, y), col, name) in enumerate(zip(ra_pos, ra_col, ra_name)):
    rect = FancyBboxPatch((x-0.7, y-0.7), 1.4, 1.4,
                           boxstyle="round,pad=0.1",
                           facecolor=col, edgecolor='black',
                           linewidth=2, zorder=5, alpha=0.85)
    ax_a.add_patch(rect)
    ax_a.text(x, y, name, ha='center', va='center',
              fontsize=7, fontweight='bold', zorder=6)

# 关键路径标注
ax_a.annotate('', xy=(7.3, 5.5), xytext=(2.0, 2.0),
              arrowprops=dict(arrowstyle='->', color=C_OK,
                              lw=2.0, linestyle='dashed'))
ax_a.text(4.2, 4.2, 'HDP: →RA2\n(5m, idle!)',
          fontsize=7.5, color=C_OK, ha='center',
          bbox=dict(boxstyle='round,pad=0.2', facecolor='#E8F5E9',
                    edgecolor=C_OK, linewidth=1))

ax_a.annotate('', xy=(7.3, 2.0), xytext=(2.0, 2.0),
              arrowprops=dict(arrowstyle='->', color='#C62828', lw=2.0))
ax_a.text(4.8, 1.3, 'Greedy: →RA1\n(2m, busy!)',
          fontsize=7.5, color='#C62828', ha='center',
          bbox=dict(boxstyle='round,pad=0.2', facecolor='#FFEBEE',
                    edgecolor='#C62828', linewidth=1))

# ════════════════════════════════════════════════════
# (b) Decompose：CSS-DP 与 DES-DP 分别求解
# ════════════════════════════════════════════════════
ax_b.set_title('(b) Step 1: Decompose\n(Decouple Subproblems)',
               fontsize=12, fontweight='bold', pad=8)

# CDHAS 问题框（顶部）
cdhas = FancyBboxPatch((2.5, 8.0), 5.0, 1.5,
                        boxstyle="round,pad=0.2",
                        facecolor='#FFF9E6', edgecolor='#F57C00',
                        linewidth=2.5, linestyle='--', zorder=5)
ax_b.add_patch(cdhas)
ax_b.text(5.0, 8.85, 'CDHAS Problem',
          ha='center', fontsize=10, fontweight='bold',
          color='#E65100', zorder=6)
ax_b.text(5.0, 8.25, '(CSS ⊗ DES)',
          ha='center', fontsize=8.5, color='#EF6C00',
          style='italic', zorder=6)

# 分解箭头
ax_b.annotate('', xy=(2.8, 6.3), xytext=(4.0, 7.9),
              arrowprops=dict(arrowstyle='->', color='#555',
                              lw=2.0))
ax_b.annotate('', xy=(7.2, 6.3), xytext=(6.0, 7.9),
              arrowprops=dict(arrowstyle='->', color='#555',
                              lw=2.0))
ax_b.text(5.0, 7.3, 'Decompose', ha='center',
          fontsize=9, color='#555', style='italic')

# CSS-DP 框
css_box = FancyBboxPatch((0.5, 4.2), 4.0, 2.0,
                          boxstyle="round,pad=0.25",
                          facecolor=C_LIGHT_BLUE,
                          edgecolor=C_CSS, linewidth=3, zorder=5)
ax_b.add_patch(css_box)
ax_b.text(2.5, 5.85, 'CSS-DP', ha='center',
          fontsize=11, fontweight='bold', color=C_CSS, zorder=6)
ax_b.text(2.5, 5.3, 'Trajectory Optimization', ha='center',
          fontsize=8, color=C_CSS, zorder=6)
ax_b.text(2.5, 4.75, 'AGV1: start→RA2 (5s)', ha='center',
          fontsize=7.5, color='#1976D2', style='italic', zorder=6)
ax_b.text(2.5, 4.35, 'Output: arrival times τ', ha='center',
          fontsize=7.5, color=C_CSS, fontweight='bold', zorder=6)

# DES-DP 框
des_box = FancyBboxPatch((5.5, 4.2), 4.0, 2.0,
                          boxstyle="round,pad=0.25",
                          facecolor=C_LIGHT_ORANGE,
                          edgecolor=C_DES, linewidth=3, zorder=5)
ax_b.add_patch(des_box)
ax_b.text(7.5, 5.85, 'DES-DP', ha='center',
          fontsize=11, fontweight='bold', color=C_DES, zorder=6)
ax_b.text(7.5, 5.3, 'Task Scheduling', ha='center',
          fontsize=8, color=C_DES, zorder=6)
ax_b.text(7.5, 4.75, 'RA2: available at t=0', ha='center',
          fontsize=7.5, color='#EF6C00', style='italic', zorder=6)
ax_b.text(7.5, 4.35, 'Output: schedule S', ha='center',
          fontsize=7.5, color=C_DES, fontweight='bold', zorder=6)

# 关键洞察框
insight = FancyBboxPatch((0.5, 0.8), 9.0, 2.8,
                          boxstyle="round,pad=0.3",
                          facecolor=C_LIGHT_GREEN,
                          edgecolor=C_OK, linewidth=2, zorder=5)
ax_b.add_patch(insight)
ax_b.text(5.0, 3.2, '💡 Key Insight',
          ha='center', fontsize=10, fontweight='bold',
          color=C_OK, zorder=6)
ax_b.text(5.0, 2.6,
          'CSS-DP: "AGV1 can reach RA2 in 5s"',
          ha='center', fontsize=8, color='#1565C0', zorder=6)
ax_b.text(5.0, 2.05,
          'DES-DP: "RA2 is available immediately"',
          ha='center', fontsize=8, color='#E65100', zorder=6)
ax_b.text(5.0, 1.4,
          '→ Solve independently, then coordinate',
          ha='center', fontsize=8.5, fontweight='bold',
          color=C_OK, zorder=6)

# ════════════════════════════════════════════════════
# (c) Coordinate：迭代交换耦合变量
# ════════════════════════════════════════════════════
ax_c.set_title('(c) Step 2: Coordinate\n(Iterative Variable Exchange)',
               fontsize=12, fontweight='bold', pad=8)

# CSS-DP 框
css2 = FancyBboxPatch((0.3, 6.5), 3.8, 2.5,
                       boxstyle="round,pad=0.25",
                       facecolor=C_LIGHT_BLUE,
                       edgecolor=C_CSS, linewidth=3, zorder=5)
ax_c.add_patch(css2)
ax_c.text(2.2, 8.6, 'CSS-DP', ha='center',
          fontsize=11, fontweight='bold', color=C_CSS, zorder=6)
ax_c.text(2.2, 8.05, 'Given: schedule S', ha='center',
          fontsize=8, color='#1976D2', zorder=6)
ax_c.text(2.2, 7.5, 'Compute: trajectory', ha='center',
          fontsize=8, color='#1976D2', zorder=6)
ax_c.text(2.2, 6.95, 'Output: τ(AGV1→RA2)=5s', ha='center',
          fontsize=7.5, color=C_CSS, fontweight='bold',
          style='italic', zorder=6)

# DES-DP 框
des2 = FancyBboxPatch((5.9, 6.5), 3.8, 2.5,
                       boxstyle="round,pad=0.25",
                       facecolor=C_LIGHT_ORANGE,
                       edgecolor=C_DES, linewidth=3, zorder=5)
ax_c.add_patch(des2)
ax_c.text(7.8, 8.6, 'DES-DP', ha='center',
          fontsize=11, fontweight='bold', color=C_DES, zorder=6)
ax_c.text(7.8, 8.05, 'Given: arrival times τ', ha='center',
          fontsize=8, color='#EF6C00', zorder=6)
ax_c.text(7.8, 7.5, 'Reschedule tasks', ha='center',
          fontsize=8, color='#EF6C00', zorder=6)
ax_c.text(7.8, 6.95, 'Output: S(RA2 start=5s)', ha='center',
          fontsize=7.5, color=C_DES, fontweight='bold',
          style='italic', zorder=6)

# 双向箭头（τ 和 S 的交换）
arr_tau = FancyArrowPatch((4.1, 8.0), (5.9, 8.0),
                           arrowstyle='->', mutation_scale=22,
                           linewidth=2.5, color=C_CSS,
                           connectionstyle='arc3,rad=-0.25', zorder=7)
ax_c.add_patch(arr_tau)
ax_c.text(5.0, 8.85, 'τ (arrival times)',
          ha='center', fontsize=8, color=C_CSS, fontweight='bold')

arr_s = FancyArrowPatch((5.9, 7.2), (4.1, 7.2),
                          arrowstyle='->', mutation_scale=22,
                          linewidth=2.5, color=C_DES,
                          connectionstyle='arc3,rad=-0.25', zorder=7)
ax_c.add_patch(arr_s)
ax_c.text(5.0, 6.35, 'S (task schedule)',
          ha='center', fontsize=8, color=C_DES, fontweight='bold')

# Coordinator 框
coord = FancyBboxPatch((2.8, 4.3), 4.4, 1.7,
                        boxstyle="round,pad=0.2",
                        facecolor=C_LIGHT_PURPLE,
                        edgecolor=C_COORD, linewidth=2.5, zorder=5)
ax_c.add_patch(coord)
ax_c.text(5.0, 5.65, 'Coordinator',
          ha='center', fontsize=10, fontweight='bold',
          color=C_COORD, zorder=6)
ax_c.text(5.0, 5.1, 'Check: |makespan_new − makespan_old| < ε',
          ha='center', fontsize=7.5, color=C_COORD, zorder=6)
ax_c.text(5.0, 4.6, 'If not converged → next iteration',
          ha='center', fontsize=7.5, color=C_COORD,
          style='italic', zorder=6)

# 迭代过程数字示意
iter_data = [
    ('Iter 1', 18.0, '#EF5350'),
    ('Iter 2', 15.5, '#FF7043'),
    ('Iter 3', 14.8, '#FFA726'),
    ('Iter 4', 14.2, '#66BB6A'),
    ('Iter 5', 14.0, C_OK),
]
ax_c.text(5.0, 3.7, 'Makespan Convergence:',
          ha='center', fontsize=8.5, fontweight='bold', color='#333')
for k, (label, val, col) in enumerate(iter_data):
    x = 0.8 + k * 1.7
    bar_h = (val - 13.5) / 5.0 * 2.2
    bar = FancyBboxPatch((x, 0.5), 1.2, bar_h,
                          boxstyle="square,pad=0",
                          facecolor=col, edgecolor='white',
                          linewidth=1, zorder=5, alpha=0.85)
    ax_c.add_patch(bar)
    ax_c.text(x + 0.6, 0.5 + bar_h + 0.15, f'{val}s',
              ha='center', fontsize=7, color=col, fontweight='bold')
    ax_c.text(x + 0.6, 0.2, label,
              ha='center', fontsize=7, color='#555')

# ════════════════════════════════════════════════════
# (d) Converge → 最终结果 Gantt 图
# ════════════════════════════════════════════════════
ax_d.set_title('(d) Step 3: Converge\n(Near-Optimal Solution)',
               fontsize=12, fontweight='bold', pad=8)

# 用内嵌子图画 Gantt
ax_d.axis('off')
ax_gantt = fig.add_axes([0.77, 0.18, 0.20, 0.55])
ax_gantt.set_xlim(0, 16)
ax_gantt.set_ylim(-0.5, 3.5)
ax_gantt.set_xlabel('Time (s)', fontsize=9)
ax_gantt.set_yticks([0, 1, 2])
ax_gantt.set_yticklabels(['AGV3', 'AGV2', 'AGV1'], fontsize=9)
ax_gantt.set_title('HDP Result\nMakespan = 14s ✓',
                   fontsize=9, fontweight='bold', color=C_OK)
ax_gantt.axvline(x=14, color=C_OK, linestyle='--',
                 linewidth=2, label='Makespan=14s')
ax_gantt.grid(axis='x', alpha=0.3)

# AGV1: 行驶5s → 任务4s（无等待！）
ax_gantt.barh(2, 5, left=0, color=C_CSS, edgecolor='white',
              height=0.55, label='Travel', alpha=0.85)
ax_gantt.barh(2, 4, left=5, color='#42A5F5', edgecolor='white',
              height=0.55, label='Task', alpha=0.85)
ax_gantt.text(2.5, 2, '5s', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(7.0, 2, 'Task\n4s', ha='center', va='center',
              fontsize=7, color='white', fontweight='bold')

# AGV2
ax_gantt.barh(1, 3, left=0, color='#0288D1', edgecolor='white',
              height=0.55, alpha=0.85)
ax_gantt.barh(1, 5, left=3, color='#4FC3F7', edgecolor='white',
              height=0.55, alpha=0.85)
ax_gantt.text(1.5, 1, '3s', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(5.5, 1, 'Task\n5s', ha='center', va='center',
              fontsize=7, color='white', fontweight='bold')

# AGV3
ax_gantt.barh(0, 4, left=0, color='#0097A7', edgecolor='white',
              height=0.55, alpha=0.85)
ax_gantt.barh(0, 6, left=4, color='#4DD0E1', edgecolor='white',
              height=0.55, alpha=0.85)
ax_gantt.text(2.0, 0, '4s', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(7.0, 0, 'Task\n6s', ha='center', va='center',
              fontsize=7, color='white', fontweight='bold')

# 无 idle gap 标注
ax_gantt.text(14.5, 2, '✓ No\nidle!', ha='left', va='center',
              fontsize=7.5, color=C_OK, fontweight='bold')

ax_gantt.legend(loc='lower right', fontsize=7, framealpha=0.8)

# 在 ax_d 上补充文字说明
ax_d.text(5.0, 9.3, '✅ Convergence Achieved',
          ha='center', fontsize=11, fontweight='bold',
          color=C_OK,
          bbox=dict(boxstyle='round,pad=0.4', facecolor=C_LIGHT_GREEN,
                    edgecolor=C_OK, linewidth=2))

results = [
    ('Makespan',    '14s',   '18s (Greedy)', C_OK),
    ('Improvement', '22%↓',  '—',            C_OK),
    ('AGV1 idle',   '0s ✓',  '10s ✗',        C_OK),
    ('Utilization', '76%',   '61%',          C_OK),
]
for k, (metric, hdp_val, greedy_val, col) in enumerate(results):
    y = 7.8 - k * 1.1
    ax_d.text(0.5, y, f'{metric}:', fontsize=9,
              color='#333', fontweight='bold')
    ax_d.text(3.8, y, hdp_val, fontsize=9,
              color=col, fontweight='bold')
    ax_d.text(5.8, y, f'(vs {greedy_val})',
              fontsize=8, color='#999')

ax_d.text(5.0, 3.2,
          '"Trade 3s extra travel\nfor eliminating 10s wait"',
          ha='center', fontsize=9, style='italic',
          color='#555',
          bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFFDE7',
                    edgecolor='#F9A825', linewidth=1.5))

# ── 全局标题 ──────────────────────────────────────────
fig.suptitle(
    'Our Solution: Hybrid Dynamic Programming (HDP) — Decompose → Coordinate → Converge',
    fontsize=14, fontweight='bold', y=1.01
)

plt.savefig('fig_intro_solution.pdf', bbox_inches='tight', dpi=300)
plt.show()