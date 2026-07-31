"""
生成HDP方法示意图
展示CSS子问题、DES子问题及迭代协调流程
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import numpy as np

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['font.size'] = 10

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# ========== 标题 ==========
ax.text(5, 9.5, 'Hybrid Dynamic Programming (HDP) Framework', 
        ha='center', va='top', fontsize=16, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', 
                 edgecolor='black', linewidth=2))

# ========== 初始化阶段 ==========
init_box = FancyBboxPatch((0.5, 7.5), 2, 1, 
                          boxstyle="round,pad=0.1", 
                          facecolor='#FFE5CC', edgecolor='black', linewidth=2)
ax.add_patch(init_box)
ax.text(1.5, 8.3, 'Initialization', ha='center', va='center', 
        fontsize=11, fontweight='bold')
ax.text(1.5, 7.9, 'Greedy Schedule', ha='center', va='center', 
        fontsize=9, style='italic')

# ========== 迭代循环框 ==========
iteration_box = FancyBboxPatch((3, 2), 6.5, 5, 
                               boxstyle="round,pad=0.15", 
                               facecolor='#E8F8F5', edgecolor='#27AE60', 
                               linewidth=3, linestyle='--', alpha=0.3)
ax.add_patch(iteration_box)
ax.text(6.25, 6.8, 'Iterative Coordination Loop', 
        ha='center', va='center', fontsize=12, fontweight='bold', 
        color='#27AE60')

# ========== CSS子问题 ==========
css_box = FancyBboxPatch((3.5, 4.5), 2.5, 1.8, 
                         boxstyle="round,pad=0.1", 
                         facecolor='#D6EAF8', edgecolor='#2874A6', linewidth=2.5)
ax.add_patch(css_box)
ax.text(4.75, 6, 'CSS Subproblem', ha='center', va='center', 
        fontsize=11, fontweight='bold', color='#1A5490')
ax.text(4.75, 5.6, 'AGV Trajectory', ha='center', va='center', 
        fontsize=9)
ax.text(4.75, 5.3, 'Planning (DP)', ha='center', va='center', 
        fontsize=9)
ax.text(4.75, 4.9, r'$\min \sum_{i} T_i^{travel}$', ha='center', va='center', 
        fontsize=9, style='italic', color='#1A5490')

# ========== DES子问题 ==========
des_box = FancyBboxPatch((3.5, 2.3), 2.5, 1.8, 
                         boxstyle="round,pad=0.1", 
                         facecolor='#FADBD8', edgecolor='#943126', linewidth=2.5)
ax.add_patch(des_box)
ax.text(4.75, 3.8, 'DES Subproblem', ha='center', va='center', 
        fontsize=11, fontweight='bold', color='#7B241C')
ax.text(4.75, 3.4, 'Task Scheduling', ha='center', va='center', 
        fontsize=9)
ax.text(4.75, 3.1, '(Priority-based DP)', ha='center', va='center', 
        fontsize=9)
ax.text(4.75, 2.7, r'$\min C_{max}$', ha='center', va='center', 
        fontsize=9, style='italic', color='#7B241C')

# ========== 信息传递：到达时间 ==========
info_box = FancyBboxPatch((6.5, 4), 2.5, 1.2, 
                          boxstyle="round,pad=0.1", 
                          facecolor='#FEF9E7', edgecolor='#D68910', linewidth=2)
ax.add_patch(info_box)
ax.text(7.75, 4.9, 'Information', ha='center', va='center', 
        fontsize=10, fontweight='bold', color='#9C640C')
ax.text(7.75, 4.6, 'Passing', ha='center', va='center', 
        fontsize=10, fontweight='bold', color='#9C640C')
ax.text(7.75, 4.25, r'Arrival Times $\{t_j^{arr}\}$', ha='center', va='center', 
        fontsize=9, style='italic', color='#9C640C')

# ========== 收敛判断 ==========
conv_box = FancyBboxPatch((3.5, 0.5), 2.5, 1.2, 
                          boxstyle="round,pad=0.1", 
                          facecolor='#E8DAEF', edgecolor='#6C3483', linewidth=2)
ax.add_patch(conv_box)
ax.text(4.75, 1.4, 'Convergence Check', ha='center', va='center', 
        fontsize=10, fontweight='bold', color='#4A235A')
ax.text(4.75, 0.95, r'$|C_{max}^{k} - C_{max}^{k-1}| < \epsilon$', 
        ha='center', va='center', fontsize=9, style='italic', color='#4A235A')

# ========== 最终输出 ==========
output_box = FancyBboxPatch((7.5, 7.5), 2, 1, 
                            boxstyle="round,pad=0.1", 
                            facecolor='#D5F4E6', edgecolor='#0E6655', linewidth=2.5)
ax.add_patch(output_box)
ax.text(8.5, 8.3, 'Optimal Schedule', ha='center', va='center', 
        fontsize=11, fontweight='bold', color='#0B5345')
ax.text(8.5, 7.9, r'$\mathcal{S}^* = \{\pi, \tau\}$', ha='center', va='center', 
        fontsize=9, style='italic', color='#0B5345')

# ========== 箭头：流程控制 ==========
# 初始化 → CSS
arrow1 = FancyArrowPatch((2.5, 8), (3.5, 5.4), 
                        arrowstyle='->', mutation_scale=25, 
                        linewidth=2.5, color='black')
ax.add_patch(arrow1)

# CSS → 信息传递
arrow2 = FancyArrowPatch((6, 5.4), (6.5, 4.6), 
                        arrowstyle='->', mutation_scale=25, 
                        linewidth=2.5, color='#D68910')
ax.add_patch(arrow2)

# 信息传递 → DES
arrow3 = FancyArrowPatch((6.5, 4.6), (6, 3.2), 
                        arrowstyle='->', mutation_scale=25, 
                        linewidth=2.5, color='#D68910')
ax.add_patch(arrow3)

# DES → 收敛判断
arrow4 = FancyArrowPatch((4.75, 2.3), (4.75, 1.7), 
                        arrowstyle='->', mutation_scale=25, 
                        linewidth=2.5, color='black')
ax.add_patch(arrow4)

# 收敛判断 → CSS（循环）
arrow5 = FancyArrowPatch((3.5, 1.1), (3, 5.4), 
                        arrowstyle='->', mutation_scale=25, 
                        linewidth=2.5, color='#27AE60', linestyle='--')
ax.add_patch(arrow5)
ax.text(2.5, 3.5, 'No', ha='center', va='center', 
        fontsize=10, fontweight='bold', color='#27AE60',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                 edgecolor='#27AE60', linewidth=1.5))

# 收敛判断 → 输出
arrow6 = FancyArrowPatch((6.25, 1.1), (8.5, 7.5), 
                        arrowstyle='->', mutation_scale=30, 
                        linewidth=3, color='#0E6655')
ax.add_patch(arrow6)
ax.text(7.5, 4.5, 'Yes', ha='center', va='center', 
        fontsize=10, fontweight='bold', color='#0E6655',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                 edgecolor='#0E6655', linewidth=1.5))

# ========== 图例：关键特性 ==========
legend_y = 0.8
ax.text(0.3, legend_y, 'Key Features:', fontsize=10, fontweight='bold')

features = [
    ('✓ Decoupling: CSS ⊥ DES', '#2874A6'),
    ('✓ Iterative Coordination', '#27AE60'),
    ('✓ Near-Optimal Solution', '#0E6655'),
    ('✓ Polynomial Complexity', '#9C640C')
]

for i, (text, color) in enumerate(features):
    ax.text(0.3, legend_y - 0.3 * (i + 1), text, 
           fontsize=9, color=color, fontweight='bold')

# ========== 添加迭代次数标注 ==========
ax.text(9.3, 5, r'Iteration $k$', ha='center', va='center', 
        fontsize=10, style='italic', color='#27AE60',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#E8F8F5', 
                 edgecolor='#27AE60', linewidth=2))

plt.tight_layout()
plt.savefig('figures/fig_hdp_methodology.pdf', dpi=300, bbox_inches='tight')
plt.savefig('figures/fig_hdp_methodology.png', dpi=300, bbox_inches='tight')

print("✅ Methodology diagram saved:")
print("   - figures/fig_hdp_methodology.pdf")
print("   - figures/fig_hdp_methodology.png")

plt.show()