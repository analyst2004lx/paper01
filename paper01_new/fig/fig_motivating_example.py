"""
生成 Figure 2: Motivating Example
包含4个子图：(a) Physical Scenario, (b) Greedy-Single, (c) HDP, (d) Gantt Chart
【已修正逻辑错误】
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle, Polygon
import numpy as np

# 设置全局字体和样式
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'lines.linewidth': 2.5,
    'patch.linewidth': 1.5,
    'figure.dpi': 300
})

# 创建图形
fig = plt.figure(figsize=(16, 10))

# ============================================================
# 辅助函数
# ============================================================

def draw_agv(ax, x, y, color, label, angle=0):
    """绘制AGV（圆形+方向箭头）"""
    # 圆形底座
    circle = Circle((x, y), 0.25, color=color, alpha=0.7, zorder=3)
    ax.add_patch(circle)
    
    # 方向箭头
    dx = 0.35 * np.cos(np.radians(angle))
    dy = 0.35 * np.sin(np.radians(angle))
    arrow = FancyArrowPatch((x, y), (x + dx, y + dy),
                           arrowstyle='->', mutation_scale=20,
                           color='black', linewidth=2, zorder=4)
    ax.add_patch(arrow)
    
    # 标签
    ax.text(x, y - 0.5, label, ha='center', va='top', 
            fontsize=10, fontweight='bold', color=color)

def draw_robotic_arm(ax, x, y, width, height, color, label, status=''):
    """绘制Robotic Arm（矩形）"""
    rect = FancyBboxPatch((x - width/2, y - height/2), width, height,
                          boxstyle="round,pad=0.05", 
                          facecolor=color, edgecolor='black',
                          linewidth=2, alpha=0.8, zorder=2)
    ax.add_patch(rect)
    
    # 标签
    ax.text(x, y, label, ha='center', va='center',
            fontsize=11, fontweight='bold', color='black')
    
    # 状态标签
    if status:
        ax.text(x, y + height/2 + 0.3, status, ha='center', va='bottom',
                fontsize=9, style='italic', 
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                         edgecolor='gray', alpha=0.9))

def draw_trajectory(ax, x1, y1, x2, y2, color, label, style='-', linewidth=2.5):
    """绘制轨迹"""
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                           arrowstyle='->', mutation_scale=25,
                           color=color, linewidth=linewidth, 
                           linestyle=style, zorder=1)
    ax.add_patch(arrow)
    
    # 标签（放在轨迹中点）
    mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
    ax.text(mid_x, mid_y + 0.3, label, ha='center', va='bottom',
            fontsize=9, color=color, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                     edgecolor=color, alpha=0.9))

def setup_workspace(ax, title):
    """设置工作空间背景"""
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 6)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_xlabel('X Position (m)', fontsize=11)
    ax.set_ylabel('Y Position (m)', fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    
    # 添加边框
    for spine in ax.spines.values():
        spine.set_linewidth(1.5)

# ============================================================
# (a) Physical Scenario
# ============================================================

ax1 = plt.subplot(2, 2, 1)
setup_workspace(ax1, '(a) Physical Scenario')

# AGVs
draw_agv(ax1, 1, 3, '#1f77b4', 'AGV1', angle=0)
draw_agv(ax1, 1, 1, '#2ca02c', 'AGV2', angle=90)
draw_agv(ax1, 6, 1, '#ff7f0e', 'AGV3', angle=180)

# Robotic Arms
draw_robotic_arm(ax1, 3, 3, 0.8, 0.6, '#d3d3d3', 'RA1', 'Busy (12s)')
draw_robotic_arm(ax1, 6, 3, 0.8, 0.6, '#90EE90', 'RA2', 'Idle')
draw_robotic_arm(ax1, 3, 1, 0.8, 0.6, '#d3d3d3', 'RA3', 'Busy (8s)')

# 距离标注（虚线）
ax1.plot([1, 3], [3, 3], 'k--', alpha=0.5, linewidth=1, zorder=0)
ax1.text(2, 3.2, '2m', ha='center', fontsize=9, color='gray')

ax1.plot([1, 6], [3, 3], 'k--', alpha=0.5, linewidth=1, zorder=0)
ax1.text(3.5, 3.2, '5m', ha='center', fontsize=9, color='gray')

# 添加图例
legend_elements = [
    mpatches.Patch(facecolor='#1f77b4', edgecolor='black', label='AGV (mobile)'),
    mpatches.Patch(facecolor='#d3d3d3', edgecolor='black', label='RA (busy)'),
    mpatches.Patch(facecolor='#90EE90', edgecolor='black', label='RA (idle)')
]
ax1.legend(handles=legend_elements, loc='upper right', fontsize=9)

# ============================================================
# (b) Greedy-Single Solution
# ============================================================

ax2 = plt.subplot(2, 2, 2)
setup_workspace(ax2, '(b) Greedy-Single Solution')

# AGVs (起始位置)
draw_agv(ax2, 1, 3, '#1f77b4', 'AGV1', angle=0)
draw_agv(ax2, 1, 1, '#2ca02c', 'AGV2', angle=90)
draw_agv(ax2, 6, 1, '#ff7f0e', 'AGV3', angle=180)

# Robotic Arms
draw_robotic_arm(ax2, 3, 3, 0.8, 0.6, '#d3d3d3', 'RA1', '')
draw_robotic_arm(ax2, 6, 3, 0.8, 0.6, '#90EE90', 'RA2', 'Idle')  # ✅ 保持 Idle
draw_robotic_arm(ax2, 3, 1, 0.8, 0.6, '#d3d3d3', 'RA3', '')

# AGV1 轨迹到 RA1
draw_trajectory(ax2, 1.25, 3, 2.6, 3, '#1f77b4', 'Travel: 2s', style='-')

# 等待时间标注（红色虚线框）
wait_box = FancyBboxPatch((2.3, 2.5), 1.4, 1.0,
                          boxstyle="round,pad=0.1",
                          facecolor='none', edgecolor='red',
                          linewidth=2.5, linestyle='--', zorder=5)
ax2.add_patch(wait_box)
ax2.text(3, 2.3, 'Wait: 8s', ha='center', va='top',
         fontsize=10, fontweight='bold', color='red')

# RA2 idle 标注
ax2.text(6, 2.3, 'Remains Idle', ha='center', va='top',
         fontsize=9, style='italic', color='gray')

# 时间轴
ax2.text(0.5, 5.5, 'Timeline: 0s → 2s (arrive) → 10s (wait) → 18s (finish)',
         fontsize=9, style='italic',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffe6e6', alpha=0.8))

# Makespan 标注
ax2.text(6.5, 0.3, 'Makespan:\n18s', ha='right', va='bottom',
         fontsize=11, fontweight='bold', color='red',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='white', 
                  edgecolor='red', linewidth=2))

# ============================================================
# (c) HDP Solution
# ============================================================

ax3 = plt.subplot(2, 2, 3)
setup_workspace(ax3, '(c) HDP Solution')

# AGVs (起始位置)
draw_agv(ax3, 1, 3, '#1f77b4', 'AGV1', angle=0)
draw_agv(ax3, 1, 1, '#2ca02c', 'AGV2', angle=90)
draw_agv(ax3, 6, 1, '#ff7f0e', 'AGV3', angle=180)

# Robotic Arms
draw_robotic_arm(ax3, 3, 3, 0.8, 0.6, '#d3d3d3', 'RA1', '')
# ✅ 修正: RA2 应该显示为 "Processing" (灰色)
draw_robotic_arm(ax3, 6, 3, 0.8, 0.6, '#d3d3d3', 'RA2', 'Processing')
draw_robotic_arm(ax3, 3, 1, 0.8, 0.6, '#d3d3d3', 'RA3', '')

# AGV1 轨迹到 RA2（曲线）
from matplotlib.patches import FancyBboxPatch, PathPatch
from matplotlib.path import Path

# 使用贝塞尔曲线绘制轨迹
verts = [
    (1.25, 3),      # 起点
    (3, 4),         # 控制点1
    (5, 3.5),       # 控制点2
    (5.6, 3)        # 终点
]
codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]
path = Path(verts, codes)
patch = PathPatch(path, facecolor='none', edgecolor='#1f77b4', 
                 linewidth=2.5, zorder=1)
ax3.add_patch(patch)

# 箭头头部
arrow_head = FancyArrowPatch((5.4, 3), (5.6, 3),
                            arrowstyle='->', mutation_scale=25,
                            color='#1f77b4', linewidth=2.5, zorder=1)
ax3.add_patch(arrow_head)

# 轨迹标签
ax3.text(3.5, 4.2, 'Travel: 3s', ha='center', va='bottom',
         fontsize=9, color='#1f77b4', fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                  edgecolor='#1f77b4', alpha=0.9))

# No wait 标注（绿色对勾）
ax3.text(6, 2.3, '✓ No Wait', ha='center', va='top',
         fontsize=11, fontweight='bold', color='green')

# 时间轴
ax3.text(0.5, 5.5, 'Timeline: 0s → 3s (arrive) → 14s (finish)',
         fontsize=9, style='italic',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#e6ffe6', alpha=0.8))

# Makespan 标注
ax3.text(6.5, 0.3, 'Makespan:\n14s', ha='right', va='bottom',
         fontsize=11, fontweight='bold', color='green',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='white', 
                  edgecolor='green', linewidth=2))

# 改进百分比
ax3.annotate('', xy=(6.5, 0.9), xytext=(6.5, 1.5),
            arrowprops=dict(arrowstyle='->', lw=2, color='green'))
ax3.text(6.5, 1.7, '22% faster', ha='center', va='bottom',
         fontsize=10, fontweight='bold', color='green')

# ============================================================
# (d) Gantt Chart Comparison
# ============================================================

ax4 = plt.subplot(2, 2, 4)
ax4.set_xlim(0, 20)
ax4.set_ylim(0, 7)
ax4.set_xlabel('Time (seconds)', fontsize=12)
ax4.set_title('(d) Gantt Chart Comparison', fontsize=13, fontweight='bold', pad=10)
ax4.grid(True, axis='x', alpha=0.3, linestyle='--', linewidth=0.5)

# 颜色方案
task_colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd']
idle_color = 'white'

# ========== Greedy-Single (上半部分) ==========
ax4.text(-1.5, 5, 'Greedy-Single:', ha='right', va='center', 
         fontsize=11, fontweight='bold')

# ✅ 修正: 简化为 3 个任务
# RA1: 原有任务 (0-12s) + AGV1 等待到达 (12-14s) + AGV1 任务 (14-18s)
ax4.add_patch(Rectangle((0, 5), 12, 0.6, facecolor=task_colors[0], 
                        edgecolor='black', linewidth=1))
ax4.text(6, 5.3, 'Existing Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

ax4.add_patch(Rectangle((12, 5), 2, 0.6, facecolor=idle_color, 
                        edgecolor='red', linewidth=2, linestyle='--'))
ax4.text(13, 5.3, 'WAIT', ha='center', va='center', fontsize=8, color='red', fontweight='bold')

ax4.add_patch(Rectangle((14, 5), 4, 0.6, facecolor=task_colors[1], 
                        edgecolor='black', linewidth=1))
ax4.text(16, 5.3, 'AGV1 Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

# RA2: 一直 idle
ax4.add_patch(Rectangle((0, 4), 18, 0.6, facecolor=idle_color, 
                        edgecolor='gray', linewidth=1, linestyle='--'))
ax4.text(9, 4.3, 'IDLE (No Assignment)', ha='center', va='center', fontsize=9, color='gray', style='italic')

# RA3: AGV2 任务 (0-8s) + AGV3 任务 (8-14s)
ax4.add_patch(Rectangle((0, 3), 8, 0.6, facecolor=task_colors[2], 
                        edgecolor='black', linewidth=1))
ax4.text(4, 3.3, 'AGV2 Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

ax4.add_patch(Rectangle((8, 3), 6, 0.6, facecolor=task_colors[3], 
                        edgecolor='black', linewidth=1))
ax4.text(11, 3.3, 'AGV3 Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

# Makespan 标注
ax4.plot([18, 18], [3, 5.6], 'r--', linewidth=2)
ax4.text(18.5, 4.3, 'Makespan\n18s', ha='left', va='center',
         fontsize=10, fontweight='bold', color='red')

# ========== HDP (下半部分) ==========
ax4.text(-1.5, 1.3, 'HDP:', ha='right', va='center', 
         fontsize=11, fontweight='bold')

# ✅ 修正: 简化为 3 个任务
# RA1: 原有任务 (0-12s) + AGV2 任务 (12-16s)
ax4.add_patch(Rectangle((0, 1.6), 12, 0.6, facecolor=task_colors[0], 
                        edgecolor='black', linewidth=1))
ax4.text(6, 1.9, 'Existing Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

ax4.add_patch(Rectangle((12, 1.6), 4, 0.6, facecolor=task_colors[2], 
                        edgecolor='black', linewidth=1))
ax4.text(14, 1.9, 'AGV2 Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

# RA2: AGV1 任务 (3-14s)
ax4.add_patch(Rectangle((3, 1), 11, 0.6, facecolor=task_colors[1], 
                        edgecolor='black', linewidth=1))
ax4.text(8.5, 1.3, 'AGV1 Task (No Wait)', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

# RA3: AGV3 任务 (0-8s)
ax4.add_patch(Rectangle((0, 0.4), 8, 0.6, facecolor=task_colors[3], 
                        edgecolor='black', linewidth=1))
ax4.text(4, 0.7, 'AGV3 Task', ha='center', va='center', fontsize=9, color='white', fontweight='bold')

# Makespan 标注
ax4.plot([14, 14], [0.4, 2.2], 'g--', linewidth=2)
ax4.text(14.5, 1.3, 'Makespan\n14s', ha='left', va='center',
         fontsize=10, fontweight='bold', color='green')

# ✅ 修正: Y轴刻度（从上到下）
ax4.set_yticks([0.7, 1.3, 1.9, 3.3, 4.3, 5.3])
ax4.set_yticklabels(['RA3', 'RA2', 'RA1', 'RA3', 'RA2', 'RA1'], fontsize=10)

# 分隔线
ax4.axhline(y=2.5, color='black', linewidth=2, linestyle='-')

# 图例
legend_elements = [
    mpatches.Patch(facecolor=task_colors[0], edgecolor='black', label='Task (processing)'),
    mpatches.Patch(facecolor=idle_color, edgecolor='gray', label='Idle/Wait time')
]
ax4.legend(handles=legend_elements, loc='upper right', fontsize=9)

# ============================================================
# 整体布局调整
# ============================================================

plt.tight_layout(pad=2.0, h_pad=2.5, w_pad=2.5)

# 保存图片
plt.savefig('fig_motivating_example.pdf', dpi=300, bbox_inches='tight')
plt.savefig('fig_motivating_example.png', dpi=300, bbox_inches='tight')

print("✓ Figure saved as fig_motivating_example.pdf and .png")
print("✓ Resolution: 300 DPI")
print("✓ Size: 16×10 inches (suitable for two-column layout)")
print("\n✅ 已修正以下逻辑错误:")
print("  1. Gantt Chart 任务数量: 5-6个 → 3个 (匹配 3 AGVs)")
print("  2. 子图(c) RA2 状态: Idle → Processing")
print("  3. Gantt Chart 时间轴: 简化为核心场景")
print("  4. Y轴标签顺序: 修正为 RA1-RA2-RA3")

plt.show()