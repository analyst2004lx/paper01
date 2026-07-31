import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
ax_scene, ax_abstract, ax_gantt = axes

# ── (a) 物理场景 ──────────────────────────────────────
ax_scene.set_xlim(0, 10)
ax_scene.set_ylim(0, 10)
ax_scene.set_title('(a) Physical Scenario', fontsize=13, fontweight='bold')
ax_scene.set_aspect('equal')
ax_scene.axis('off')

# 画3个AGV（圆形）
agv_positions = [(2, 2), (2, 5), (2, 8)]
agv_colors = ['#1976D2', '#388E3C', '#7B1FA2']
for i, (x, y) in enumerate(agv_positions):
    circle = plt.Circle((x, y), 0.4, color=agv_colors[i], zorder=5)
    ax_scene.add_patch(circle)
    ax_scene.text(x, y, f'A{i+1}', ha='center', va='center',
                  color='white', fontweight='bold', fontsize=10, zorder=6)

# 画3个Robotic Arm（矩形）
ra_positions = [(7, 2), (7, 5), (7, 8)]
ra_labels = ['RA1\n(busy 12s)', 'RA2\n(idle)', 'RA3\n(busy 5s)']
ra_colors = ['#EF5350', '#66BB6A', '#FFA726']
for i, (x, y) in enumerate(ra_positions):
    rect = FancyBboxPatch((x-0.6, y-0.5), 1.2, 1.0,
                          boxstyle="round,pad=0.1",
                          facecolor=ra_colors[i], edgecolor='black',
                          linewidth=2, zorder=5)
    ax_scene.add_patch(rect)
    ax_scene.text(x, y, ra_labels[i], ha='center', va='center',
                  fontsize=8, fontweight='bold', zorder=6)

# 画关键路径：AGV1 → RA1（近但忙）vs AGV1 → RA2（远但空闲）
ax_scene.annotate('', xy=(6.4, 5), xytext=(2.4, 2),
                  arrowprops=dict(arrowstyle='->', color='green',
                                  lw=2.5, linestyle='dashed'))
ax_scene.text(4, 3.8, 'HDP: 5m\n(RA2 idle!)', fontsize=8,
              color='green', ha='center', style='italic')
ax_scene.annotate('', xy=(6.4, 2), xytext=(2.4, 2),
                  arrowprops=dict(arrowstyle='->', color='red', lw=2.5))
ax_scene.text(4.5, 1.5, 'Greedy: 2m\n(RA1 busy!)', fontsize=8,
              color='red', ha='center', style='italic')

# ── (b) 循环依赖抽象（原左图核心内容）────────────────────
ax_abstract.set_xlim(0, 10)
ax_abstract.set_ylim(0, 10)
ax_abstract.set_title('(b) The Challenge: Circular Dependency',
                       fontsize=13, fontweight='bold')
ax_abstract.axis('off')

# CSS box
css_box = FancyBboxPatch((0.8, 5.5), 3.4, 2.0,
                          boxstyle="round,pad=0.3",
                          facecolor='#E3F2FD', edgecolor='#1565C0',
                          linewidth=3, zorder=5)
ax_abstract.add_patch(css_box)
ax_abstract.text(2.5, 6.8, 'CSS Agent', fontsize=12,
                 ha='center', fontweight='bold', color='#0D47A1', zorder=6)
ax_abstract.text(2.5, 6.2, '(AGV Trajectory)', fontsize=9,
                 ha='center', color='#1565C0', style='italic', zorder=6)
ax_abstract.text(2.5, 5.7, 'Needs: task schedule', fontsize=8,
                 ha='center', color='#1976D2', zorder=6)

# DES box
des_box = FancyBboxPatch((5.8, 5.5), 3.4, 2.0,
                          boxstyle="round,pad=0.3",
                          facecolor='#FFF3E0', edgecolor='#E65100',
                          linewidth=3, zorder=5)
ax_abstract.add_patch(des_box)
ax_abstract.text(7.5, 6.8, 'DES Agent', fontsize=12,
                 ha='center', fontweight='bold', color='#BF360C', zorder=6)
ax_abstract.text(7.5, 6.2, '(Robotic Arm)', fontsize=9,
                 ha='center', color='#E65100', style='italic', zorder=6)
ax_abstract.text(7.5, 5.7, 'Needs: arrival times', fontsize=8,
                 ha='center', color='#EF6C00', zorder=6)

# 双向箭头
arrow_up = FancyArrowPatch((4.2, 7.0), (5.8, 7.0),
                            arrowstyle='->', mutation_scale=25,
                            linewidth=3, color='#FF6F00',
                            connectionstyle='arc3,rad=-0.3', zorder=4)
ax_abstract.add_patch(arrow_up)
ax_abstract.text(5.0, 7.8, 'Constrains\n(trajectory→schedule)',
                 fontsize=8, ha='center', color='#FF6F00', zorder=6)

arrow_down = FancyArrowPatch((5.8, 6.0), (4.2, 6.0),
                              arrowstyle='->', mutation_scale=25,
                              linewidth=3, color='#1976D2',
                              connectionstyle='arc3,rad=-0.3', zorder=4)
ax_abstract.add_patch(arrow_down)
ax_abstract.text(5.0, 4.8, 'Constrains\n(schedule→trajectory)',
                 fontsize=8, ha='center', color='#1976D2', zorder=6)

# 问题框
prob_box = FancyBboxPatch((1.0, 1.0), 8.0, 2.5,
                           boxstyle="round,pad=0.3",
                           facecolor='#FFEBEE', edgecolor='#C62828',
                           linewidth=3, zorder=5)
ax_abstract.add_patch(prob_box)
ax_abstract.text(5.0, 3.0, '⚠ Circular Dependency',
                 fontsize=12, ha='center', fontweight='bold',
                 color='#B71C1C', zorder=6)
ax_abstract.text(5.0, 2.3, 'Cannot solve CSS without knowing DES',
                 fontsize=9, ha='center', color='#C62828', zorder=6)
ax_abstract.text(5.0, 1.7, 'Cannot solve DES without knowing CSS',
                 fontsize=9, ha='center', color='#C62828', zorder=6)
ax_abstract.text(5.0, 1.15, '→ Traditional sequential methods fail',
                 fontsize=9, ha='center', color='#B71C1C',
                 style='italic', fontweight='bold', zorder=6)

# ── (c) Gantt图：传统方法失败后果 ─────────────────────
ax_gantt.set_xlim(0, 20)
ax_gantt.set_ylim(-0.5, 3.5)
ax_gantt.set_title('(c) Consequence: Greedy-Single Failure\n(Makespan = 18s)',
                    fontsize=13, fontweight='bold', color='#C62828')
ax_gantt.set_xlabel('Time (s)', fontsize=11)
ax_gantt.set_yticks([0, 1, 2])
ax_gantt.set_yticklabels(['AGV3', 'AGV2', 'AGV1'], fontsize=11)
ax_gantt.axvline(x=18, color='red', linestyle='--', linewidth=2, label='Makespan=18s')
ax_gantt.grid(axis='x', alpha=0.4)

# AGV1: 行驶2s → 等待10s（idle）→ 任务4s
ax_gantt.barh(2, 2, left=0, color='#1976D2', edgecolor='black',
              height=0.6, label='Travel')
ax_gantt.barh(2, 10, left=2, color='#FFCDD2', edgecolor='#C62828',
              height=0.6, linewidth=2, linestyle='--', label='Idle wait')
ax_gantt.barh(2, 4, left=12, color='#42A5F5', edgecolor='black', height=0.6)
ax_gantt.text(7, 2, 'IDLE\n10s', ha='center', va='center',
              fontsize=10, color='#C62828', fontweight='bold')

# AGV2 & AGV3: 正常任务
ax_gantt.barh(1, 3, left=0, color='#388E3C', edgecolor='black', height=0.6)
ax_gantt.barh(1, 5, left=5, color='#66BB6A', edgecolor='black', height=0.6)
ax_gantt.barh(0, 4, left=0, color='#7B1FA2', edgecolor='black', height=0.6)
ax_gantt.barh(0, 6, left=6, color='#AB47BC', edgecolor='black', height=0.6)

ax_gantt.legend(loc='lower right', fontsize=9)

plt.suptitle('The Challenge: Why Coupling-Aware Optimization Matters',
             fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('fig_intro_problem_new2.pdf', bbox_inches='tight', dpi=300)
plt.show()