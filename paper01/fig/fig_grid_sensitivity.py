"""
生成 Figure: Grid Resolution Sensitivity
【已修正逻辑错误】
"""

import matplotlib.pyplot as plt
import numpy as np

# 设置全局字体和样式
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 10,
    'lines.linewidth': 2,
    'figure.dpi': 300
})

# ✅ 修正: 添加缺失的数据点 (0.25m 和 0.1m)
delta_x = np.array([1.0, 0.75, 0.5, 0.4, 0.3, 0.25, 0.2, 0.1])
comp_time_hdp = np.array([2.4, 4.1, 9.8, 15.3, 27.2, 39.0, 61.5, 245.0])
comp_time_milp = np.full_like(delta_x, 45.0)
makespan_hdp = np.array([89.7, 88.5, 87.2, 86.8, 86.3, 86.1, 86.0, 85.8])

# 创建双子图
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

# ============================================================
# 左图: Computation Time
# ============================================================

ax1.plot(delta_x, comp_time_hdp, 'o-', color='#1f77b4', linewidth=2.5, 
         markersize=8, label='HDP', zorder=3)
ax1.plot(delta_x, comp_time_milp, 's--', color='#d62728', linewidth=2, 
         markersize=7, label='MILP (timeout)', alpha=0.7, zorder=2)

# Sweet spot 标注
ax1.plot(0.5, 9.8, '*', color='red', markersize=18, label='Sweet spot ($\Delta x = 0.5$ m)', 
         zorder=4, markeredgecolor='darkred', markeredgewidth=1.5)
ax1.axvline(x=0.5, color='red', linestyle='--', alpha=0.4, linewidth=1.5)

# ✅ 修正: 拟合指数标注 (包含置信区间)
ax1.text(0.65, 180, r'$O\left(\left(\frac{1}{\Delta x}\right)^{1.97 \pm 0.08}\right)$', 
         fontsize=12, fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', edgecolor='black', 
                  alpha=0.8, linewidth=1.5))

# 标注关键数据点
ax1.annotate('9.8s', xy=(0.5, 9.8), xytext=(0.55, 20),
            arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
            fontsize=10, color='red', fontweight='bold')

ax1.annotate('39s (4× slower)', xy=(0.25, 39), xytext=(0.3, 80),
            arrowprops=dict(arrowstyle='->', color='blue', lw=1.5),
            fontsize=10, color='blue', fontweight='bold')

ax1.annotate('245s (25× slower)', xy=(0.1, 245), xytext=(0.15, 200),
            arrowprops=dict(arrowstyle='->', color='purple', lw=1.5),
            fontsize=10, color='purple', fontweight='bold')

# 坐标轴设置
ax1.set_xlabel('Grid Resolution $\Delta x$ (m)', fontsize=13, fontweight='bold')
ax1.set_ylabel('Computation Time (s)', fontsize=13, fontweight='bold')
ax1.set_title('(a) Computation Time vs. $\Delta x$', fontsize=14, fontweight='bold', pad=12)
ax1.set_xlim(0.05, 1.05)
ax1.set_ylim(0, 260)
ax1.legend(loc='upper right', fontsize=10, framealpha=0.95)
ax1.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)

# 添加边框
for spine in ax1.spines.values():
    spine.set_linewidth(1.5)

# ============================================================
# 右图: Makespan
# ============================================================

ax2.plot(delta_x, makespan_hdp, 'o-', color='#1f77b4', linewidth=2.5, 
         markersize=8, label='HDP makespan', zorder=3)

# Sweet spot 标注
ax2.plot(0.5, 87.2, '*', color='red', markersize=18, label='Sweet spot ($\Delta x = 0.5$ m)', 
         zorder=4, markeredgecolor='darkred', markeredgewidth=1.5)
ax2.axhline(y=87.2, color='red', linestyle='--', alpha=0.4, linewidth=1.5)
ax2.axvline(x=0.5, color='red', linestyle='--', alpha=0.4, linewidth=1.5)

# ✅ 修正: Diminishing returns 区域 (Δx ≤ 0.3 m)
ax2.axvspan(0.05, 0.3, alpha=0.15, color='gray', label='Diminishing returns ($\Delta x \leq 0.3$ m)')

# ✅ 修正: Recommended range (0.25-0.5 m)
ax2.axvspan(0.25, 0.5, alpha=0.15, color='green', label='Recommended range (0.25-0.5 m)')

# ✅ 添加: Discretization error 标注
ax2.text(0.5, 88.5, '3.2% error\n9.8s comp.', ha='center', va='bottom',
         fontsize=10, fontweight='bold', color='red',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='white', 
                  edgecolor='red', linewidth=1.5, alpha=0.9))

# 标注关键改进
ax2.annotate('1.3% gain', xy=(0.2, 86.1), xytext=(0.15, 87.5),
            arrowprops=dict(arrowstyle='->', color='blue', lw=1.5),
            fontsize=10, color='blue', fontweight='bold')

ax2.annotate('0.3% gain\n(25× cost)', xy=(0.1, 85.8), xytext=(0.12, 84.5),
            arrowprops=dict(arrowstyle='->', color='purple', lw=1.5),
            fontsize=9, color='purple', fontweight='bold')

# 标注 plateau 点
ax2.plot(0.3, 86.3, 'D', color='orange', markersize=10, 
         label=r'Plateau point ($\Delta x \approx 0.3$ m)', zorder=4)

# 坐标轴设置
ax2.set_xlabel('Grid Resolution $\Delta x$ (m)', fontsize=13, fontweight='bold')
ax2.set_ylabel('Makespan (s)', fontsize=13, fontweight='bold')
ax2.set_title('(b) Makespan vs. $\Delta x$', fontsize=14, fontweight='bold', pad=12)
ax2.set_xlim(0.05, 1.05)
ax2.set_ylim(85.5, 90.0)
ax2.legend(loc='upper right', fontsize=9, framealpha=0.95)
ax2.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)

# 添加边框
for spine in ax2.spines.values():
    spine.set_linewidth(1.5)

# ============================================================
# 整体布局调整
# ============================================================

plt.tight_layout(pad=2.0, w_pad=3.0)

# 保存图片
plt.savefig('fig/fig_grid_sensitivity.pdf', dpi=300, bbox_inches='tight')
plt.savefig('fig/fig_grid_sensitivity.png', dpi=300, bbox_inches='tight')

print("✓ Figure saved as fig_grid_sensitivity.pdf and .png")
print("✓ Resolution: 300 DPI")
print("✓ Size: 14×5.5 inches (suitable for two-column layout)")
print("\n✅ 已修正以下逻辑错误:")
print("  1. 添加缺失数据点: Δx = 0.25m (39s) 和 0.1m (245s)")
print("  2. 添加缺失 makespan: Δx = 0.1m (85.8s)")
print("  3. 修正拟合指数标注: 添加置信区间 ± 0.08")
print("  4. 修正 Diminishing returns 区域: 0.2-0.3m → 0.05-0.3m")
print("  5. 修正 Recommended range: 0.4-0.6m → 0.25-0.5m")
print("  6. 添加 discretization error 标注: 3.2% error")

plt.show()