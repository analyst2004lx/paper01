import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.gridspec as gridspec
import numpy as np

# ── 全局设置 ──────────────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 11))
gs = gridspec.GridSpec(2, 2, figure=fig,
                       hspace=0.38, wspace=0.32)

ax_a = fig.add_subplot(gs[0, 0])   # 物理场景
ax_b = fig.add_subplot(gs[0, 1])   # HDP 分解框架
ax_c = fig.add_subplot(gs[1, 0])   # 迭代协调过程
ax_d = fig.add_subplot(gs[1, 1])   # 收敛曲线 + Gantt

# ── 颜色方案 ──────────────────────────────────────────────────────────
C_CSS    = '#1565C0'    # 深蓝：CSS/AGV
C_DES    = '#E65100'    # 深橙：DES/RA
C_COORD  = '#6A1B9A'    # 紫色：Coordinator
C_OK     = '#2E7D32'    # 绿色：收敛/成功
C_LB     = '#E3F2FD'    # 浅蓝背景
C_LO     = '#FFF3E0'    # 浅橙背景
C_LP     = '#F3E5F5'    # 浅紫背景
C_LG     = '#E8F5E9'    # 浅绿背景

AGV_COLORS = ['#1565C0', '#0288D1', '#0097A7']  # AGV1/2/3
RA_COLORS  = ['#EF5350', '#66BB6A', '#FFA726']  # RA1/2/3

# ════════════════════════════════════════════════════════════════════
# (A) 物理场景：3 AGV + 3 RA，无障碍物
# ════════════════════════════════════════════════════════════════════
ax_a.set_xlim(0, 10)
ax_a.set_ylim(0, 10)
ax_a.axis('off')
ax_a.set_title('(A) Physical Scenario: 3 AGVs + 3 Robotic Arms',
               fontsize=13, fontweight='bold', pad=12)

# 工厂边界
factory = FancyBboxPatch((0.3, 0.3), 9.4, 9.4,
                          boxstyle="square,pad=0",
                          facecolor='#FAFAFA', edgecolor='#90A4AE',
                          linewidth=2, zorder=1)
ax_a.add_patch(factory)

# AGV（左侧，圆形）
agv_pos  = [(1.8, 2.0), (1.8, 5.5), (1.8, 8.5)]
agv_name = ['AGV1', 'AGV2', 'AGV3']
for i, ((x, y), col, name) in enumerate(zip(agv_pos, AGV_COLORS, agv_name)):
    c = plt.Circle((x, y), 0.55, color=col, zorder=5, ec='white', lw=2)
    ax_a.add_patch(c)
    ax_a.text(x, y + 0.02, name, ha='center', va='center',
              color='white', fontweight='bold', fontsize=9, zorder=6)
    # 运动方向箭头
    ax_a.annotate('', xy=(x + 0.9, y), xytext=(x + 0.55, y),
                  arrowprops=dict(arrowstyle='->', color=col,
                                  lw=2.0), zorder=6)

# RA（右侧，矩形）
ra_pos   = [(8.2, 2.0), (8.2, 5.5), (8.2, 8.5)]
ra_name  = ['RA1\n(busy 12s)', 'RA2\n(idle)', 'RA3\n(busy 5s)']
ra_state_col = ['#EF5350', '#66BB6A', '#FFA726']
for i, ((x, y), col, name) in enumerate(zip(ra_pos, ra_state_col, ra_name)):
    rect = FancyBboxPatch((x - 0.75, y - 0.75), 1.5, 1.5,
                           boxstyle="round,pad=0.1",
                           facecolor=col, edgecolor='black',
                           linewidth=2, zorder=5, alpha=0.88)
    ax_a.add_patch(rect)
    ax_a.text(x, y, name, ha='center', va='center',
              fontsize=8, fontweight='bold', color='white', zorder=6)

# 连接线（AGV → RA 的任务分配示意）
assign_pairs = [(0, 1), (1, 2), (2, 0)]   # AGV1→RA2, AGV2→RA3, AGV3→RA1
for (ai, ri) in assign_pairs:
    ax_a.annotate('',
                  xy=(ra_pos[ri][0] - 0.75, ra_pos[ri][1]),
                  xytext=(agv_pos[ai][0] + 0.55, agv_pos[ai][1]),
                  arrowprops=dict(arrowstyle='->', color=AGV_COLORS[ai],
                                  lw=1.8, linestyle='dashed',
                                  connectionstyle='arc3,rad=0.15'),
                  zorder=4)

# 图例
ax_a.text(5.0, 0.65, 'Dashed arrows: HDP-optimized assignments',
          ha='center', fontsize=8, color='#555', style='italic')

# 标签
ax_a.text(1.8, 9.55, 'CSS Agents (AGVs)', ha='center',
          fontsize=9, color=C_CSS, fontweight='bold')
ax_a.text(8.2, 9.55, 'DES Agents (RAs)', ha='center',
          fontsize=9, color=C_DES, fontweight='bold')

# ════════════════════════════════════════════════════════════════════
# (B) HDP 分解框架
# ════════════════════════════════════════════════════════════════════
ax_b.set_xlim(0, 10)
ax_b.set_ylim(0, 10)
ax_b.axis('off')
ax_b.set_title('(B) HDP Framework: Decompose–Coordinate–Converge',
               fontsize=13, fontweight='bold', pad=12)

# CDHAS 问题框
cdhas = FancyBboxPatch((2.5, 8.0), 5.0, 1.6,
                        boxstyle="round,pad=0.2",
                        facecolor='#FFF9E6', edgecolor='#F57C00',
                        linewidth=2.5, linestyle='--', zorder=5)
ax_b.add_patch(cdhas)
ax_b.text(5.0, 9.0, 'CDHAS Problem',
          ha='center', fontsize=11, fontweight='bold', color='#E65100', zorder=6)
ax_b.text(5.0, 8.35, r'$\min$ makespan  s.t. CSS $\otimes$ DES constraints',
          ha='center', fontsize=9, color='#EF6C00', style='italic', zorder=6)

# 分解箭头
ax_b.annotate('', xy=(2.5, 6.5), xytext=(3.8, 7.9),
              arrowprops=dict(arrowstyle='->', color='#555', lw=2.0))
ax_b.annotate('', xy=(7.5, 6.5), xytext=(6.2, 7.9),
              arrowprops=dict(arrowstyle='->', color='#555', lw=2.0))
ax_b.text(5.0, 7.4, 'Decompose', ha='center',
          fontsize=9.5, color='#555', style='italic', fontweight='bold')

# CSS-DP 框
css = FancyBboxPatch((0.3, 4.5), 4.0, 2.0,
                      boxstyle="round,pad=0.25",
                      facecolor=C_LB, edgecolor=C_CSS,
                      linewidth=3, zorder=5)
ax_b.add_patch(css)
ax_b.text(2.3, 6.1, 'CSS-DP', ha='center',
          fontsize=12, fontweight='bold', color=C_CSS, zorder=6)
ax_b.text(2.3, 5.6, 'Trajectory Optimization', ha='center',
          fontsize=9, color=C_CSS, zorder=6)
ax_b.text(2.3, 5.15, r'Input: schedule $\boldsymbol{\tau}^{(\ell)}$', ha='center',
          fontsize=8.5, color='#1976D2', zorder=6)
ax_b.text(2.3, 4.72, r'Output: arrival times $\mathbf{t}^{(\ell)}$', ha='center',
          fontsize=8.5, color=C_CSS, fontweight='bold', zorder=6)

# DES-DP 框
des = FancyBboxPatch((5.7, 4.5), 4.0, 2.0,
                      boxstyle="round,pad=0.25",
                      facecolor=C_LO, edgecolor=C_DES,
                      linewidth=3, zorder=5)
ax_b.add_patch(des)
ax_b.text(7.7, 6.1, 'DES-DP', ha='center',
          fontsize=12, fontweight='bold', color=C_DES, zorder=6)
ax_b.text(7.7, 5.6, 'Task Scheduling', ha='center',
          fontsize=9, color=C_DES, zorder=6)
ax_b.text(7.7, 5.15, r'Input: arrival times $\mathbf{t}^{(\ell)}$', ha='center',
          fontsize=8.5, color='#EF6C00', zorder=6)
ax_b.text(7.7, 4.72, r'Output: schedule $\boldsymbol{\tau}^{(\ell+1)}$', ha='center',
          fontsize=8.5, color=C_DES, fontweight='bold', zorder=6)

# Coordinator 框
coord = FancyBboxPatch((2.8, 2.3), 4.4, 1.7,
                        boxstyle="round,pad=0.2",
                        facecolor=C_LP, edgecolor=C_COORD,
                        linewidth=2.5, zorder=5)
ax_b.add_patch(coord)
ax_b.text(5.0, 3.65, 'Coordinator', ha='center',
          fontsize=11, fontweight='bold', color=C_COORD, zorder=6)
ax_b.text(5.0, 3.1, r'Check: $|\text{makespan}^{(\ell+1)} - \text{makespan}^{(\ell)}| < \delta$',
          ha='center', fontsize=8.5, color=C_COORD, zorder=6)
ax_b.text(5.0, 2.55, 'Converged? → Output  |  Else → Next iteration',
          ha='center', fontsize=8, color=C_COORD, style='italic', zorder=6)

# CSS-DP ↔ DES-DP 双向箭头
arr1 = FancyArrowPatch((4.3, 5.7), (5.7, 5.7),
                        arrowstyle='->', mutation_scale=22,
                        linewidth=2.5, color=C_CSS,
                        connectionstyle='arc3,rad=-0.3', zorder=7)
ax_b.add_patch(arr1)
ax_b.text(5.0, 6.35, r'$\mathbf{t}^{(\ell)}$ (arrival times)',
          ha='center', fontsize=8.5, color=C_CSS, fontweight='bold')

arr2 = FancyArrowPatch((5.7, 5.0), (4.3, 5.0),
                        arrowstyle='->', mutation_scale=22,
                        linewidth=2.5, color=C_DES,
                        connectionstyle='arc3,rad=-0.3', zorder=7)
ax_b.add_patch(arr2)
ax_b.text(5.0, 4.25, r'$\boldsymbol{\tau}^{(\ell+1)}$ (schedule)',
          ha='center', fontsize=8.5, color=C_DES, fontweight='bold')

# 向下到 Coordinator 的箭头
ax_b.annotate('', xy=(5.0, 4.0), xytext=(5.0, 4.5),
              arrowprops=dict(arrowstyle='->', color=C_COORD, lw=2.0))

# 收敛输出
conv = FancyBboxPatch((2.8, 0.3), 4.4, 1.5,
                       boxstyle="round,pad=0.2",
                       facecolor=C_LG, edgecolor=C_OK,
                       linewidth=2.5, zorder=5)
ax_b.add_patch(conv)
ax_b.text(5.0, 1.35, '✅ Near-Optimal Solution', ha='center',
          fontsize=10, fontweight='bold', color=C_OK, zorder=6)
ax_b.text(5.0, 0.75, r'$\mathbf{u}^{c,*}$, $\mathbf{t}^{*}$, $\boldsymbol{\tau}^{*}$, $\mathbf{z}^{*}$',
          ha='center', fontsize=9, color=C_OK, zorder=6)
ax_b.annotate('', xy=(5.0, 1.8), xytext=(5.0, 2.3),
              arrowprops=dict(arrowstyle='->', color=C_OK, lw=2.0))

# ════════════════════════════════════════════════════════════════════
# (C) 迭代协调过程：3 AGV 的 τ↔S 变量交换示意
# ════════════════════════════════════════════════════════════════════
ax_c.set_xlim(0, 10)
ax_c.set_ylim(0, 10)
ax_c.axis('off')
ax_c.set_title('(C) Iterative Coordination: Variable Exchange',
               fontsize=13, fontweight='bold', pad=12)

# 迭代轮次标签（纵向排列）
iter_labels = ['Init\n(ℓ=0)', 'Iter 1\n(ℓ=1)', 'Iter 2\n(ℓ=2)',
               'Iter 3\n(ℓ=3)', 'Converge\n(ℓ=4)']
iter_y = [8.8, 7.0, 5.2, 3.4, 1.6]
iter_makespan = [None, 18.0, 15.5, 14.3, 14.0]

for k, (label, y) in enumerate(zip(iter_labels, iter_y)):
    # 迭代标签
    ax_c.text(0.5, y, label, ha='center', va='center',
              fontsize=8.5, color='#555', fontweight='bold')

    if k == 0:
        # 初始化：DES-DP 给出初始调度
        box = FancyBboxPatch((1.2, y - 0.55), 7.6, 1.1,
                              boxstyle="round,pad=0.15",
                              facecolor='#F5F5F5', edgecolor='#BDBDBD',
                              linewidth=1.5, zorder=4)
        ax_c.add_patch(box)
        ax_c.text(5.0, y,
                  r'DES-DP initializes: $\boldsymbol{\tau}^{(0)}$ = [RA1→AGV1, RA2→AGV2, RA3→AGV3]',
                  ha='center', va='center', fontsize=8.5, color='#555', zorder=5)
    elif k < 4:
        # CSS-DP 框
        css_b = FancyBboxPatch((1.2, y - 0.5), 2.8, 1.0,
                                boxstyle="round,pad=0.1",
                                facecolor=C_LB, edgecolor=C_CSS,
                                linewidth=2, zorder=4)
        ax_c.add_patch(css_b)
        # 3 AGV 的到达时间
        t_vals = {1: [2.0, 3.0, 4.0],
                  2: [5.0, 3.0, 4.0],
                  3: [5.0, 3.0, 4.0]}[k]
        ax_c.text(2.6, y + 0.18, 'CSS-DP', ha='center',
              fontsize=8.5, fontweight='bold', color=C_CSS, zorder=5)
        ax_c.text(2.6, y - 0.2,
              r'$\mathbf{{t}}$=[{:.0f}s,{:.0f}s,{:.0f}s]'.format(*t_vals),
              ha='center', fontsize=8, color=C_CSS, zorder=5)

        # 双向箭头
        arr_r = FancyArrowPatch((4.0, y + 0.15), (5.2, y + 0.15),
                                 arrowstyle='->', mutation_scale=18,
                                 linewidth=2, color=C_CSS, zorder=6)
        ax_c.add_patch(arr_r)
        ax_c.text(4.6, y + 0.45, r'$\mathbf{t}^{(\ell)}$',
                  ha='center', fontsize=8, color=C_CSS, fontweight='bold')

        arr_l = FancyArrowPatch((5.2, y - 0.15), (4.0, y - 0.15),
                                 arrowstyle='->', mutation_scale=18,
                                 linewidth=2, color=C_DES, zorder=6)
        ax_c.add_patch(arr_l)
        ax_c.text(4.6, y - 0.48, r'$\boldsymbol{\tau}^{(\ell+1)}$',
                  ha='center', fontsize=8, color=C_DES, fontweight='bold')

        # DES-DP 框
        des_b = FancyBboxPatch((5.2, y - 0.5), 2.8, 1.0,
                                boxstyle="round,pad=0.1",
                                facecolor=C_LO, edgecolor=C_DES,
                                linewidth=2, zorder=4)
        ax_c.add_patch(des_b)
        schedules = {1: 'AGV1→RA1', 2: 'AGV1→RA2', 3: 'AGV1→RA2'}
        ax_c.text(6.6, y + 0.18, 'DES-DP', ha='center',
                  fontsize=8.5, fontweight='bold', color=C_DES, zorder=5)
        ax_c.text(6.6, y - 0.2, schedules[k],
                  ha='center', fontsize=8, color=C_DES, zorder=5)

        # Makespan 标注
        ms_col = '#EF5350' if iter_makespan[k] > 14.5 else C_OK
        ax_c.text(9.3, y,
                  f'{iter_makespan[k]}s',
                  ha='center', va='center', fontsize=9,
                  color=ms_col, fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.25',
                            facecolor='white', edgecolor=ms_col, lw=1.5))
    else:
        # 收敛
        conv_b = FancyBboxPatch((1.2, y - 0.55), 7.6, 1.1,
                                 boxstyle="round,pad=0.15",
                                 facecolor=C_LG, edgecolor=C_OK,
                                 linewidth=2.5, zorder=4)
        ax_c.add_patch(conv_b)
        ax_c.text(5.0, y,
                  r'✅ Converged: makespan = 14s  |  AGV1→RA2, AGV2→RA3, AGV3→RA1',
                  ha='center', va='center', fontsize=8.5,
                  color=C_OK, fontweight='bold', zorder=5)

    # 向下箭头（非最后一行）
    if k < len(iter_labels) - 1:
        ax_c.annotate('', xy=(5.0, iter_y[k + 1] + 0.6),
                      xytext=(5.0, y - 0.6),
                      arrowprops=dict(arrowstyle='->', color='#BDBDBD',
                                      lw=1.5, linestyle='dotted'))

# 列标题
ax_c.text(2.6, 9.65, 'CSS-DP Output', ha='center',
          fontsize=9, color=C_CSS, fontweight='bold')
ax_c.text(6.6, 9.65, 'DES-DP Output', ha='center',
          fontsize=9, color=C_DES, fontweight='bold')
ax_c.text(9.3, 9.65, 'Makespan', ha='center',
          fontsize=9, color='#555', fontweight='bold')

# ════════════════════════════════════════════════════════════════════
# (D) 收敛曲线 + Gantt 结果
# ════════════════════════════════════════════════════════════════════
ax_d.axis('off')
ax_d.set_title('(D) Convergence & Final Schedule (3 AGVs)',
               fontsize=13, fontweight='bold', pad=12)

# ── 收敛曲线（上半部分）────────────────────────────────────────────
ax_conv = fig.add_axes([0.545, 0.555, 0.195, 0.18])
iters = [0, 1, 2, 3, 4]
makespans = [20.0, 18.0, 15.5, 14.3, 14.0]
ax_conv.plot(iters, makespans, 'o-', color=C_CSS,
             linewidth=2.5, markersize=7, markerfacecolor='white',
             markeredgewidth=2.5, zorder=5)
ax_conv.axhline(y=14.0, color=C_OK, linestyle='--',
                linewidth=2, label='Converged: 14s')
ax_conv.fill_between(iters, makespans, 14.0,
                     alpha=0.12, color=C_CSS)
ax_conv.set_xlabel('Iteration $\ell$', fontsize=9)
ax_conv.set_ylabel('Makespan (s)', fontsize=9)
ax_conv.set_title('Convergence Curve', fontsize=9, fontweight='bold')
ax_conv.set_xticks(iters)
ax_conv.set_ylim(12, 22)
ax_conv.legend(fontsize=8, loc='upper right')
ax_conv.grid(True, alpha=0.3)
for i, (x, y) in enumerate(zip(iters, makespans)):
    ax_conv.text(x, y + 0.5, f'{y}s', ha='center',
                 fontsize=7.5, color=C_CSS, fontweight='bold')

# ── Gantt 图（下半部分）──────────────────────────────────────────────
ax_gantt = fig.add_axes([0.545, 0.08, 0.42, 0.40])
ax_gantt.set_xlim(0, 17)
ax_gantt.set_ylim(-0.5, 2.8)
ax_gantt.set_xlabel('Time (s)', fontsize=10)
ax_gantt.set_yticks([0, 1, 2])
ax_gantt.set_yticklabels(['AGV3', 'AGV2', 'AGV1'], fontsize=10)
ax_gantt.set_title('Final HDP Schedule: Makespan = 14s (vs. Greedy 18s)',
                   fontsize=10, fontweight='bold', color=C_OK)
ax_gantt.axvline(x=14, color=C_OK, linestyle='--',
                 linewidth=2.5, label='HDP Makespan=14s', zorder=5)
ax_gantt.axvline(x=18, color='#C62828', linestyle=':',
                 linewidth=2, label='Greedy Makespan=18s', zorder=5)
ax_gantt.grid(axis='x', alpha=0.3)

# AGV1: 行驶5s → 任务4s（→RA2，无等待）
ax_gantt.barh(2, 5, left=0, color=AGV_COLORS[0], height=0.55,
              edgecolor='white', linewidth=1.5, alpha=0.85, label='Travel')
ax_gantt.barh(2, 4, left=5, color='#42A5F5', height=0.55,
              edgecolor='white', linewidth=1.5, alpha=0.85, label='Task')
ax_gantt.text(2.5, 2, 'Travel\n5s→RA2', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(7.0, 2, 'Task\n4s', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(9.2, 2.35, '✓ No idle!', fontsize=8,
              color=C_OK, fontweight='bold')

# AGV2: 行驶3s → 任务6s（→RA3）
ax_gantt.barh(1, 3, left=0, color=AGV_COLORS[1], height=0.55,
              edgecolor='white', linewidth=1.5, alpha=0.85)
ax_gantt.barh(1, 6, left=3, color='#4FC3F7', height=0.55,
              edgecolor='white', linewidth=1.5, alpha=0.85)
ax_gantt.text(1.5, 1, 'Travel\n3s→RA3', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(6.0, 1, 'Task\n6s', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')

# AGV3: 行驶4s → 任务5s（→RA1）
ax_gantt.barh(0, 4, left=0, color=AGV_COLORS[2], height=0.55,
              edgecolor='white', linewidth=1.5, alpha=0.85)
ax_gantt.barh(0, 5, left=4, color='#4DD0E1', height=0.55,
              edgecolor='white', linewidth=1.5, alpha=0.85)
ax_gantt.text(2.0, 0, 'Travel\n4s→RA1', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')
ax_gantt.text(6.5, 0, 'Task\n5s', ha='center', va='center',
              fontsize=7.5, color='white', fontweight='bold')

ax_gantt.legend(loc='lower right', fontsize=8.5, framealpha=0.9,
                ncol=2)

# ── 全局标题 ──────────────────────────────────────────────────────
fig.suptitle(
    'HDP Framework Architecture: Decompose–Coordinate–Converge',
    fontsize=15, fontweight='bold', y=1.01
)

plt.savefig('fig_hdp_architecture_new.pdf', dpi=300, bbox_inches='tight')
print("✅ Figure saved successfully!")
plt.show()