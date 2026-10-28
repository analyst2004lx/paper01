"""
fig_segmentation_strategies.pdf / .png
对应论文 4.4 节 Figure (fig:segmentation)：
  (a) Connected Components — sparse graph (ρ_sub < 0.3)  → 3 segments
  (b) Time-Window Partitioning — dense graph (ρ_sub ≥ 0.3) → 4 segments
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
import networkx as nx
import numpy as np

# ── 全局样式 ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size':   9,
})

fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))
fig.patch.set_facecolor('white')

# ── 颜色：caption 明确写 blue / green / orange；子图(b)增加第4色 red ──────
SEG_COLORS = ['#2980B9', '#27AE60', '#E67E22', '#C0392B']
SEG_FACE   = ['#D6EAF8', '#D5F5E3', '#FDEBD0', '#FADBD8']   # 浅色背景框

# ══════════════════════════════════════════════════════════════════════════
#  子图 (a)：Connected Components — sparse graph
# ══════════════════════════════════════════════════════════════════════════
ax = axes[0]

# 构造稀疏图：3 个完全独立的连通分量，共 12 个节点
# 边数 = 9，节点对数 = 12*11/2 = 66  →  ρ ≈ 0.136（< 0.3 ✓）
G_sp = nx.DiGraph()
nodes_sp = [f'$T_{{{i}}}$' for i in range(1, 13)]
G_sp.add_nodes_from(nodes_sp)

edges_sp = [
    # Segment 1 (blue)  — 4 nodes, chain
    ('$T_{1}$', '$T_{2}$'), ('$T_{2}$', '$T_{3}$'), ('$T_{3}$', '$T_{4}$'),
    # Segment 2 (green) — 4 nodes, chain + branch
    ('$T_{5}$', '$T_{6}$'), ('$T_{5}$', '$T_{7}$'), ('$T_{6}$', '$T_{8}$'),
    # Segment 3 (orange)— 4 nodes, chain
    ('$T_{9}$', '$T_{10}$'), ('$T_{10}$', '$T_{11}$'), ('$T_{11}$', '$T_{12}$'),
]
G_sp.add_edges_from(edges_sp)

n_sp   = G_sp.number_of_nodes()
e_sp   = G_sp.number_of_edges()
rho_sp = e_sp / (n_sp * (n_sp - 1) / 2)

# 手动布局：三行，每行一个分量，水平展开
pos_sp = {
    '$T_{1}$':  (0.5, 2.8), '$T_{2}$':  (1.5, 2.8),
    '$T_{3}$':  (2.5, 2.8), '$T_{4}$':  (3.5, 2.8),

    '$T_{5}$':  (0.5, 1.5), '$T_{6}$':  (1.5, 1.9),
    '$T_{7}$':  (1.5, 1.1), '$T_{8}$':  (2.5, 1.5),

    '$T_{9}$':  (0.5, 0.2), '$T_{10}$': (1.5, 0.2),
    '$T_{11}$': (2.5, 0.2), '$T_{12}$': (3.5, 0.2),
}

segments_sp = [
    ['$T_{1}$', '$T_{2}$', '$T_{3}$', '$T_{4}$'],
    ['$T_{5}$', '$T_{6}$', '$T_{7}$', '$T_{8}$'],
    ['$T_{9}$', '$T_{10}$', '$T_{11}$', '$T_{12}$'],
]
seg_labels_sp = ['Segment 1', 'Segment 2', 'Segment 3']

# 绘制边
nx.draw_networkx_edges(
    G_sp, pos_sp, ax=ax,
    edge_color='#555555', arrows=True,
    arrowsize=18, width=2.0, alpha=0.75,
    connectionstyle='arc3,rad=0.05',
    min_source_margin=14, min_target_margin=14,
)

# 绘制节点（按分量着色）
for i, seg in enumerate(segments_sp):
    nx.draw_networkx_nodes(
        G_sp, pos_sp, nodelist=seg, ax=ax,
        node_color=SEG_COLORS[i], node_size=620,
        edgecolors='white', linewidths=2.0,
    )

# 节点标签
nx.draw_networkx_labels(
    G_sp, pos_sp, ax=ax,
    font_size=7.5, font_weight='bold', font_color='white',
)

# 分量包围框 + 标签
for i, seg in enumerate(segments_sp):
    xs = [pos_sp[n][0] for n in seg]
    ys = [pos_sp[n][1] for n in seg]
    pad = 0.32
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    rect = FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle='round,pad=0.05',
        linewidth=2.2, linestyle='--',
        edgecolor=SEG_COLORS[i], facecolor=SEG_FACE[i], alpha=0.35,
        zorder=0,
    )
    ax.add_patch(rect)
    ax.text(
        (x0 + x1) / 2, y1 + 0.18,
        seg_labels_sp[i],
        ha='center', fontsize=8.5, fontweight='bold',
        color=SEG_COLORS[i],
        bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                  edgecolor=SEG_COLORS[i], linewidth=1.2, alpha=0.9),
    )

# 统计信息框
cross_sp = 0   # 三个分量完全独立，跨段边 = 0
info_sp = (
    f'Strategy: Connected Components\n'
    f'Algorithm: Tarjan\'s SCC\n'
    f'Density  $\\rho_{{\\mathrm{{sub}}}} = {rho_sp:.3f} < 0.3$\n'
    f'Segments: 3  |  Sizes: [4, 4, 4]\n'
    f'Cross-segment edges: {cross_sp}  (independent)'
)
ax.text(
    0.02, 0.02, info_sp,
    transform=ax.transAxes, fontsize=7.8, va='bottom',
    bbox=dict(boxstyle='round,pad=0.4', facecolor='#FDFEFE',
              edgecolor='#AAB7B8', linewidth=1.0, alpha=0.95),
)

ax.set_xlim(-0.2, 4.8)
ax.set_ylim(-0.3, 3.8)
ax.set_title(
    r'(a) Connected Components  ($\rho_{\mathrm{sub}} < \rho_0 = 0.3$)',
    fontsize=11, fontweight='bold', pad=10,
)
ax.axis('off')

# ══════════════════════════════════════════════════════════════════════════
#  子图 (b)：Time-Window Partitioning — dense graph
# ══════════════════════════════════════════════════════════════════════════
ax = axes[1]

# 构造密集图：12 个节点，按 earliest-start-time 分 4 个时间窗口（每窗 3 个节点）
# 边数 = 20，节点对数 = 66  →  ρ ≈ 0.303（≥ 0.3 ✓）
G_dn = nx.DiGraph()
nodes_dn = [f'$T_{{{i}}}$' for i in range(1, 13)]
G_dn.add_nodes_from(nodes_dn)

# 窗口分配（按 s_i_est 排序）
time_windows = [
    ['$T_{1}$', '$T_{2}$', '$T_{3}$'],    # Window 1  (earliest)
    ['$T_{4}$', '$T_{5}$', '$T_{6}$'],    # Window 2
    ['$T_{7}$', '$T_{8}$', '$T_{9}$'],    # Window 3
    ['$T_{10}$', '$T_{11}$', '$T_{12}$'], # Window 4  (latest)
]

# 模拟 s_i_est（用于标注）
s_est = {
    '$T_{1}$': 0,  '$T_{2}$': 2,  '$T_{3}$': 4,
    '$T_{4}$': 8,  '$T_{5}$': 10, '$T_{6}$': 12,
    '$T_{7}$': 16, '$T_{8}$': 18, '$T_{9}$': 20,
    '$T_{10}$': 24,'$T_{11}$': 26,'$T_{12}$': 28,
}

# 边：大量窗口内部边 + 少量跨窗口边（体现 dense 特性）
edges_dn = [
    # 窗口内部（intra-window）
    ('$T_{1}$', '$T_{2}$'), ('$T_{2}$', '$T_{3}$'), ('$T_{1}$', '$T_{3}$'),
    ('$T_{4}$', '$T_{5}$'), ('$T_{5}$', '$T_{6}$'), ('$T_{4}$', '$T_{6}$'),
    ('$T_{7}$', '$T_{8}$'), ('$T_{8}$', '$T_{9}$'), ('$T_{7}$', '$T_{9}$'),
    ('$T_{10}$', '$T_{11}$'), ('$T_{11}$', '$T_{12}$'), ('$T_{10}$', '$T_{12}$'),
    # 跨窗口（cross-window）— 体现 dense 图的必要跨段依赖
    ('$T_{2}$', '$T_{4}$'), ('$T_{3}$', '$T_{5}$'),
    ('$T_{5}$', '$T_{7}$'), ('$T_{6}$', '$T_{8}$'),
    ('$T_{8}$', '$T_{10}$'), ('$T_{9}$', '$T_{11}$'),
    ('$T_{3}$', '$T_{6}$'), ('$T_{6}$', '$T_{9}$'),
]
G_dn.add_edges_from(edges_dn)

n_dn   = G_dn.number_of_nodes()
e_dn   = G_dn.number_of_edges()
rho_dn = e_dn / (n_dn * (n_dn - 1) / 2)

# 布局：4 列（时间窗口），每列 3 个节点垂直排列
col_x = [0.8, 2.4, 4.0, 5.6]
row_y = [2.2, 1.1, 0.0]
pos_dn = {}
for wi, win in enumerate(time_windows):
    for ni, node in enumerate(win):
        pos_dn[node] = (col_x[wi], row_y[ni])

# 区分跨段边和窗口内边
node_to_win = {}
for wi, win in enumerate(time_windows):
    for nd in win:
        node_to_win[nd] = wi

intra_edges = [(u, v) for u, v in edges_dn if node_to_win[u] == node_to_win[v]]
cross_edges = [(u, v) for u, v in edges_dn if node_to_win[u] != node_to_win[v]]

# 绘制窗口内部边（实线，深色）
nx.draw_networkx_edges(
    G_dn, pos_dn, edgelist=intra_edges, ax=ax,
    edge_color='#2C3E50', arrows=True,
    arrowsize=16, width=1.8, alpha=0.80,
    min_source_margin=14, min_target_margin=14,
)
# 绘制跨段边（虚线，红色，突出显示）
nx.draw_networkx_edges(
    G_dn, pos_dn, edgelist=cross_edges, ax=ax,
    edge_color='#E74C3C', arrows=True,
    arrowsize=14, width=1.4, alpha=0.70,
    style='dashed',
    min_source_margin=14, min_target_margin=14,
)

# 绘制节点
for wi, win in enumerate(time_windows):
    nx.draw_networkx_nodes(
        G_dn, pos_dn, nodelist=win, ax=ax,
        node_color=SEG_COLORS[wi], node_size=620,
        edgecolors='white', linewidths=2.0,
    )

nx.draw_networkx_labels(
    G_dn, pos_dn, ax=ax,
    font_size=7.5, font_weight='bold', font_color='white',
)

# 时间窗口背景色块 + 标签
win_labels = ['Window 1', 'Window 2', 'Window 3', 'Window 4']
for wi, win in enumerate(time_windows):
    xs = [pos_dn[n][0] for n in win]
    ys = [pos_dn[n][1] for n in win]
    pad = 0.32
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    rect = FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle='round,pad=0.05',
        linewidth=2.0, linestyle='-',
        edgecolor=SEG_COLORS[wi], facecolor=SEG_FACE[wi], alpha=0.30,
        zorder=0,
    )
    ax.add_patch(rect)
    # 窗口标签（顶部）
    t_min = s_est[win[0]]
    t_max = s_est[win[-1]]
    ax.text(
        (x0 + x1) / 2, y1 + 0.20,
        f'{win_labels[wi]}\n$s^{{\\mathrm{{est}}}} \\in [{t_min},{t_max}]$',
        ha='center', fontsize=7.8, fontweight='bold',
        color=SEG_COLORS[wi],
        bbox=dict(boxstyle='round,pad=0.22', facecolor='white',
                  edgecolor=SEG_COLORS[wi], linewidth=1.2, alpha=0.9),
    )

# 图例：实线 = intra，虚线红 = cross-segment
legend_handles = [
    mpatches.Patch(facecolor='#2C3E50', label='Intra-window edge'),
    mpatches.Patch(facecolor='#E74C3C', label='Cross-window edge (coupling)',
                   linestyle='--'),
]
ax.legend(handles=legend_handles, loc='lower right', fontsize=7.5,
          framealpha=0.92, edgecolor='#BDC3C7')

# 统计信息框
info_dn = (
    f'Strategy: Time-Window Partitioning\n'
    f'Sort by $s_i^{{\\mathrm{{est}}}} = \\max(r_i,\\, \\max_{{t_j \\in \\mathrm{{Pred}}_i}} C_j^0)$\n'
    f'Density  $\\rho_{{\\mathrm{{sub}}}} = {rho_dn:.3f} \\geq 0.3$\n'
    f'Segments: 4  |  Size per window: 3\n'
    f'Cross-segment edges: {len(cross_edges)}'
)
ax.text(
    0.02, 0.02, info_dn,
    transform=ax.transAxes, fontsize=7.8, va='bottom',
    bbox=dict(boxstyle='round,pad=0.4', facecolor='#FDFEFE',
              edgecolor='#AAB7B8', linewidth=1.0, alpha=0.95),
)

ax.set_xlim(-0.1, 7.0)
ax.set_ylim(-0.6, 3.8)
ax.set_title(
    r'(b) Time-Window Partitioning  ($\rho_{\mathrm{sub}} \geq \rho_0 = 0.3$)',
    fontsize=11, fontweight='bold', pad=10,
)
ax.axis('off')

# ── 全图标题 ──────────────────────────────────────────────────────────────
fig.suptitle(
    'Adaptive Segmentation Strategies for $T_{\\mathrm{resch}}$',
    fontsize=13, fontweight='bold', y=1.01,
)

plt.tight_layout(pad=1.2)
plt.savefig('figures/fig_segmentation_strategies.pdf',
            dpi=300, bbox_inches='tight')
plt.savefig('figures/fig_segmentation_strategies.png',
            dpi=300, bbox_inches='tight')
print("✓ Saved: figures/fig_segmentation_strategies.pdf / .png")
plt.show()