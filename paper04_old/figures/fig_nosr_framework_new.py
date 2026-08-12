import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
import numpy as np

# ── 全局样式 ──────────────────────────────────────────────
plt.rcParams.update({
    'font.family':        'DejaVu Sans',
    'font.size':          9,
    'mathtext.fontset':   'stix',
})

# ── 画布 ──────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 17))
ax.set_xlim(0, 13)
ax.set_ylim(0, 17)
ax.axis('off')

# ── 颜色方案 ──────────────────────────────────────────────
C_INPUT    = '#D6EAF8'   # 蓝  – 输入 / 输出
C_DECISION = '#FDEBD0'   # 橙  – 决策
C_PROCESS  = '#D5F5E3'   # 绿  – 处理
C_THEORY   = '#E8DAEF'   # 紫  – 理论保证
C_SOLVER   = {
    'mip':    '#FADBD8',   # 红
    'ga':     '#FEF9E7',   # 黄
    'greedy': '#D5F5E3',   # 绿
}
C_PASSIVE  = '#EBF5FB'   # 浅蓝 – 被动分支

EDGE_MAIN   = '#2C3E50'
EDGE_THEORY = '#6C3483'
EDGE_PASS   = '#1A5276'

# ── 辅助：圆角矩形 ────────────────────────────────────────
def box(ax, cx, cy, w, h, text, fc, ec=EDGE_MAIN,
        fs=9, fw='normal', lw=1.5, pad=0.12, zorder=2):
    rect = FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle=f'round,pad={pad}',
        facecolor=fc, edgecolor=ec, linewidth=lw, zorder=zorder)
    ax.add_patch(rect)
    ax.text(cx, cy, text, ha='center', va='center',
            fontsize=fs, fontweight=fw, zorder=zorder+1,
            multialignment='center', linespacing=1.4)

# ── 辅助：菱形 ────────────────────────────────────────────
def diamond(ax, cx, cy, w, h, text, fc, ec=EDGE_MAIN, fs=8.5, zorder=2):
    verts = np.array([
        [cx,       cy + h/2],
        [cx + w/2, cy      ],
        [cx,       cy - h/2],
        [cx - w/2, cy      ],
    ])
    poly = mpatches.Polygon(verts, closed=True,
                            facecolor=fc, edgecolor=ec,
                            linewidth=1.5, zorder=zorder)
    ax.add_patch(poly)
    ax.text(cx, cy, text, ha='center', va='center',
            fontsize=fs, fontweight='bold', zorder=zorder+1,
            multialignment='center', linespacing=1.4)

# ── 辅助：直线箭头 ────────────────────────────────────────
def arrow(ax, x1, y1, x2, y2, ec=EDGE_MAIN, lw=1.8, ms=18, zorder=1):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=ec,
                                lw=lw, mutation_scale=ms),
                zorder=zorder)

# ── 辅助：折线箭头（水平→垂直 或 垂直→水平）────────────────
def elbow_arrow(ax, x1, y1, x2, y2, via='h', ec=EDGE_MAIN, lw=1.6, ms=16):
    """via='h': 先水平后垂直; via='v': 先垂直后水平"""
    if via == 'h':
        mid = [(x1, y1), (x2, y1), (x2, y2)]
    else:
        mid = [(x1, y1), (x1, y2), (x2, y2)]
    xs = [p[0] for p in mid]
    ys = [p[1] for p in mid]
    ax.plot(xs[:-1], ys[:-1], color=ec, lw=lw, zorder=1)
    ax.annotate('', xy=(xs[-1], ys[-1]),
                xytext=(xs[-2], ys[-2]),
                arrowprops=dict(arrowstyle='->', color=ec,
                                lw=lw, mutation_scale=ms),
                zorder=1)

# ── 辅助：步骤编号圆圈 ────────────────────────────────────
def step_circle(ax, cx, cy, num, r=0.28):
    circ = mpatches.Circle((cx, cy), r,
                            facecolor='#2471A3', edgecolor='#1A5276',
                            linewidth=2, zorder=6)
    ax.add_patch(circ)
    ax.text(cx, cy, str(num), ha='center', va='center',
            fontsize=10, fontweight='bold', color='white', zorder=7)

# ── 辅助：侧边注释气泡 ────────────────────────────────────
def side_note(ax, cx, cy, text, fc='#FDFEFE', ec='#AAB7B8', fs=7.2):
    ax.text(cx, cy, text, ha='center', va='center',
            fontsize=fs, zorder=5, multialignment='center',
            linespacing=1.35,
            bbox=dict(boxstyle='round,pad=0.35',
                      facecolor=fc, edgecolor=ec,
                      linewidth=1.0, alpha=0.95))

# ════════════════════════════════════════════════════════════
#  布局常量
# ════════════════════════════════════════════════════════════
CX   = 6.5          # 主流程中心 x
LX   = 2.2          # 左侧被动分支 x
RX   = 10.8         # 右侧注释 x
W_MAIN  = 5.2       # 主流程框宽
W_SIDE  = 2.6       # 侧边注释宽
H_BOX   = 0.72      # 标准框高
H_DIA   = 0.80      # 菱形高
GAP     = 0.38      # 框间箭头间距

# y 坐标（从上到下）
Y = {
    'title':   16.4,
    'input':   15.5,
    'step1':   14.2,   # 菱形 – Classify
    'pass_box':13.1,   # 被动分支框
    'pass_out':12.2,   # 被动分支输出
    'step2':   13.1,   # Compute Impact Boundary（主流程，与被动分支同高）
    'step3':   11.8,
    'step4':   10.5,
    'solver':   9.2,   # Multi-Scale Solver 主框
    'mip':      8.2,   # 三个 solver 子框
    'step6':    7.0,
    'consist':  5.9,   # 菱形 – Consistent?
    'fallback': 5.9,   # Fallback 框（同高，左侧）
    'output':   4.7,
    'theory':   3.4,
    'guarantee':2.2,
}

# ════════════════════════════════════════════════════════════
#  (0) 标题
# ════════════════════════════════════════════════════════════
ax.text(CX, Y['title'],
        'NOSR Framework: Near-Optimal Segmented Rescheduling',
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=EDGE_MAIN)

# ════════════════════════════════════════════════════════════
#  (1) 输入框
# ════════════════════════════════════════════════════════════
box(ax, CX, Y['input'], W_MAIN, H_BOX,
    r'Input: Disturbance $d$ detected at $t_{\mathrm{now}}$',
    C_INPUT, fs=10, fw='bold')
arrow(ax, CX, Y['input'] - H_BOX/2,
          CX, Y['step1'] + H_DIA/2)

# ════════════════════════════════════════════════════════════
#  Step 1 – Classify Disturbance
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['step1'], 1)
diamond(ax, CX, Y['step1'], 4.4, H_DIA,
        'Step 1: Classify Disturbance\n(Temporary  vs.  Permanent)',
        C_DECISION, fs=8.5)

# ── 左分支：Temporary → Passive Rescheduling ──────────────
# 水平箭头出菱形左侧 → 折向下
elbow_arrow(ax, CX - 2.2, Y['step1'],
                LX, Y['pass_box'] + H_BOX/2,
                via='h', ec=EDGE_PASS)
ax.text((CX - 2.2 + LX)/2, Y['step1'] + 0.18,
        'Temporary', ha='center', fontsize=7.8,
        color=EDGE_PASS, fontstyle='italic')

box(ax, LX, Y['pass_box'], 2.8, H_BOX,
    'Passive Rescheduling\n(Wait-if-Possible / Reassign)',
    C_PASSIVE, ec=EDGE_PASS, fs=8)

arrow(ax, LX, Y['pass_box'] - H_BOX/2,
          LX, Y['pass_out'] + H_BOX/2,
          ec=EDGE_PASS)

box(ax, LX, Y['pass_out'], 2.8, 0.60,
    r'Delay tasks by $\Delta t$  →  Output $S^{\prime}$',
    C_INPUT, ec=EDGE_PASS, fs=7.8)

# 被动分支注释
side_note(ax, LX, Y['pass_out'] - 0.80,
          'Deadline check:\nif $s_i + \Delta t \leq d_i$  →  wait\nelse  →  reassign',
          fc='#EBF5FB', ec=EDGE_PASS)

# ── 右分支：Permanent → 主流程继续 ───────────────────────
ax.text(CX + 2.5, Y['step1'] + 0.20,
        'Permanent', ha='center', fontsize=7.8,
        color='#922B21', fontstyle='italic')
arrow(ax, CX, Y['step1'] - H_DIA/2,
          CX, Y['step2'] + H_BOX/2)

# ════════════════════════════════════════════════════════════
#  Step 2 – Compute Impact Boundary
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['step2'], 2)
box(ax, CX, Y['step2'], W_MAIN, H_BOX,
    r'Step 2: Compute Impact Boundary $T_{\mathrm{affected}}$'
    '\n'
    r'BFS propagation with depth $\theta$',
    C_PROCESS, fs=9)

side_note(ax, RX, Y['step2'],
          r'Theorem 1:' '\n'
          r'$|T_{\mathrm{aff}}| \leq |T_{\mathrm{dir}}|'
          r'\cdot(1+\rho\,\bar{d})^{\theta}$',
          fc=C_THEORY, ec=EDGE_THEORY)
# 虚线连接注释
ax.annotate('', xy=(RX - W_SIDE/2 - 0.05, Y['step2']),
            xytext=(CX + W_MAIN/2, Y['step2']),
            arrowprops=dict(arrowstyle='-', color=EDGE_THEORY,
                            lw=1.0, linestyle='dashed'))

arrow(ax, CX, Y['step2'] - H_BOX/2,
          CX, Y['step3'] + H_BOX/2)

# ════════════════════════════════════════════════════════════
#  Step 3 – Filter by Task State
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['step3'], 3)
box(ax, CX, Y['step3'], W_MAIN, H_BOX,
    r'Step 3: Filter by Task State  →  $T_{\mathrm{reschedulable}}$'
    '\n'
    'Classify: Completed | Ongoing | Pending',
    C_PROCESS, fs=9)

side_note(ax, RX, Y['step3'],
          'State filter\nreduces problem\nsize by 30–50%',
          fc='#FDFEFE', ec='#AAB7B8')
ax.annotate('', xy=(RX - W_SIDE/2 - 0.05, Y['step3']),
            xytext=(CX + W_MAIN/2, Y['step3']),
            arrowprops=dict(arrowstyle='-', color='#AAB7B8',
                            lw=1.0, linestyle='dashed'))

arrow(ax, CX, Y['step3'] - H_BOX/2,
          CX, Y['step4'] + H_BOX/2)

# ════════════════════════════════════════════════════════════
#  Step 4 – Adaptive Decomposition
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['step4'], 4)
box(ax, CX, Y['step4'], W_MAIN, H_BOX,
    r'Step 4: Adaptive Decomposition into $k$ Segments'
    '\n'
    r'Strategy selected by dependency density $\rho$',
    C_PROCESS, fs=9, fw='bold')

# 两种策略子标签
for dx, label in [(-1.55, r'$\rho < 0.4$:' '\nConnected\nComponents'),
                  ( 1.55, r'$\rho \geq 0.4$:' '\nTime-Window\nPartitioning')]:
    fc = '#D6EAF8' if dx < 0 else '#D5F5E3'
    side_note(ax, CX + dx, Y['step4'] - 1.05, label, fc=fc, ec='#7FB3D3')

arrow(ax, CX, Y['step4'] - H_BOX/2,
          CX, Y['solver'] + H_BOX/2)

# ════════════════════════════════════════════════════════════
#  Step 5 – Multi-Scale Solver (主框 + 三子框)
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['solver'], 5)
box(ax, CX, Y['solver'], W_MAIN, H_BOX,
    'Step 5: Solve Each Segment  —  Multi-Scale Solver Hierarchy',
    C_PROCESS, fs=9, fw='bold')

# 三个 solver 子框
solver_specs = [
    (CX - 2.0, C_SOLVER['mip'],    r'$m \leq 20$' '\nMIP\n' r'$\varepsilon = 0$'),
    (CX,       C_SOLVER['ga'],     r'$20 < m \leq 100$' '\nGA\n' r'$\varepsilon \leq 5\%$'),
    (CX + 2.0, C_SOLVER['greedy'],r'$m > 100$' '\nGreedy+LS\n' r'$\varepsilon \leq 10\%$'),
]
for sx, fc, txt in solver_specs:
    # 从主框底部连线到子框
    arrow(ax, sx, Y['solver'] - H_BOX/2,
              sx, Y['mip'] + 0.38, ms=14)
    box(ax, sx, Y['mip'], 1.75, 0.75, txt, fc, fs=7.8)

arrow(ax, CX, Y['mip'] - 0.38,
          CX, Y['step6'] + H_BOX/2)

# ════════════════════════════════════════════════════════════
#  Step 6 – Merge & Validate
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['step6'], 6)
box(ax, CX, Y['step6'], W_MAIN, H_BOX,
    'Step 6: Merge Local Solutions\n& Validate Global Consistency',
    C_PROCESS, fs=9)

arrow(ax, CX, Y['step6'] - H_BOX/2,
          CX, Y['consist'] + H_DIA/2)

# ── 菱形：Consistent? ─────────────────────────────────────
diamond(ax, CX, Y['consist'], 3.2, H_DIA,
        'Globally\nConsistent?', C_DECISION, fs=8.5)

# No 分支 → Fallback
elbow_arrow(ax, CX - 1.6, Y['consist'],
                LX, Y['fallback'] + H_BOX/2,
                via='h', ec='#922B21')
ax.text((CX - 1.6 + LX)/2 - 0.1, Y['consist'] + 0.20,
        'No  (<2%)', ha='center', fontsize=7.5,
        color='#922B21', fontstyle='italic')
box(ax, LX, Y['fallback'], 2.6, H_BOX,
    'Fallback:\nGlobal MIP Solver',
    '#FADBD8', ec='#922B21', fs=8)

# Fallback → Output（折线）
elbow_arrow(ax, LX, Y['fallback'] - H_BOX/2,
                CX - W_MAIN/2, Y['output'],
                via='v', ec='#922B21')

# Yes 分支
ax.text(CX + 1.85, Y['consist'] + 0.20,
        'Yes', ha='center', fontsize=7.5,
        color='#1D8348', fontstyle='italic')
arrow(ax, CX, Y['consist'] - H_DIA/2,
          CX, Y['output'] + H_BOX/2)

# ════════════════════════════════════════════════════════════
#  Step 7 – Output
# ════════════════════════════════════════════════════════════
step_circle(ax, CX - W_MAIN/2 - 0.55, Y['output'], 7)
box(ax, CX, Y['output'], W_MAIN, H_BOX,
    r"Output: Updated Schedule $S'$",
    C_INPUT, fs=10, fw='bold')

arrow(ax, CX, Y['output'] - H_BOX/2,
          CX, Y['theory'] + 0.55)

# ════════════════════════════════════════════════════════════
#  理论保证框（双层）
# ════════════════════════════════════════════════════════════
# 外框
outer = FancyBboxPatch(
    (CX - 4.2, Y['guarantee'] - 0.55), 8.4, 2.2,
    boxstyle='round,pad=0.15',
    facecolor=C_THEORY, edgecolor=EDGE_THEORY,
    linewidth=2.2, zorder=2)
ax.add_patch(outer)

ax.text(CX, Y['theory'] + 0.48,
        'Theoretical Guarantees',
        ha='center', va='center',
        fontsize=10, fontweight='bold', color=EDGE_THEORY, zorder=3)

# 三列保证
guarantees = [
    (CX - 2.6, r'$(1+\varepsilon)$-Approx.' '\n'
               r'$\varepsilon = O(\rho\delta\theta)$' '\n'
               '(Theorem 3)'),
    (CX,       r'Time Complexity' '\n'
               r'$O(n \log n)$' '\n'
               '(Theorem 4)'),
    (CX + 2.6, r'Stability' '\n'
               r'$\geq (1-\delta(1+\rho\bar{d})^\theta)$' '\n'
               '(Theorem 5)'),
]
for gx, gtxt in guarantees:
    box(ax, gx, Y['guarantee'], 2.3, 0.95,
        gtxt, fc='white', ec=EDGE_THEORY,
        fs=7.8, lw=1.2, pad=0.10, zorder=3)

# ════════════════════════════════════════════════════════════
#  图例
# ════════════════════════════════════════════════════════════
legend_items = [
    mpatches.Patch(facecolor=C_INPUT,    edgecolor=EDGE_MAIN,   label='Input / Output'),
    mpatches.Patch(facecolor=C_DECISION, edgecolor=EDGE_MAIN,   label='Decision'),
    mpatches.Patch(facecolor=C_PROCESS,  edgecolor=EDGE_MAIN,   label='Process Step'),
    mpatches.Patch(facecolor=C_PASSIVE,  edgecolor=EDGE_PASS,   label='Passive Branch'),
    mpatches.Patch(facecolor=C_THEORY,   edgecolor=EDGE_THEORY, label='Theory Guarantee'),
]
ax.legend(handles=legend_items,
          loc='upper right',
          bbox_to_anchor=(0.995, 0.995),
          fontsize=8, framealpha=0.95,
          edgecolor='#BDC3C7', title='Legend',
          title_fontsize=8.5)

# ════════════════════════════════════════════════════════════
#  保存
# ════════════════════════════════════════════════════════════
plt.tight_layout(pad=0.5)
plt.savefig('fig_nosr_framework_new.pdf', dpi=300, bbox_inches='tight')
print("✓ Saved: fig_nosr_framework_new.pdf")
plt.show()